"""
The product service layer.
"""

import datetime
import re
from typing import Any, Literal

from beanie import Link, PydanticObjectId, WriteRules
from beanie.operators import Text
from bson.errors import InvalidId
from loguru import logger
from pydantic import BaseModel
from pydantic_core import ValidationError

from hippometa import ALL_METADATA_TYPE, SimpleMetadata
from hipposerve.database import (
    Collection,
    CollectionPolicy,
    File,
    Product,
    ProductMetadata,
)
from hipposerve.service import storage as storage_service
from hipposerve.service import utils, versioning
from hipposerve.service.acl import check_user_access
from hipposerve.storage import Storage

INITIAL_VERSION = "1.0.0"
LINK_POLICY = {
    "fetch_links": True,
    "nesting_depth": 2,
}


class ProductExists(Exception):
    pass


class ProductNotFound(Exception):
    pass


class PreUploadFile(BaseModel):
    name: str
    size: int
    checksum: str
    description: str | None = None


class PostUploadFile(BaseModel):
    uuid: str
    name: str
    size: int
    slug: str
    checksum: str
    url: str | None
    description: str | None
    object_name: str | None
    available: bool


async def presign_uploads(
    sources: dict[str, PreUploadFile],
    storage: Storage,
    user_name: str,
    mutlipart_size: int = 50 * 1024 * 1024,
) -> tuple[dict[str, list[str]], dict[str, File]]:
    """
    Note that upload pre-signing does _not_ validate sources' slugs as it does not
    know about the metadata type.
    """
    presigned = {}
    pre_upload_sources = {}

    for slug, source in sources.items():
        pre_upload_source, presigned_urls = await storage_service.create(
            name=source.name,
            description=source.description,
            slug=slug,
            uploader=user_name,
            size=source.size,
            checksum=source.checksum,
            storage=storage,
        )

        presigned[source.name] = presigned_urls
        pre_upload_sources[slug] = pre_upload_source

    return presigned, pre_upload_sources


async def exists(name: str) -> bool:
    """
    Check whether a product exists with this name.
    Product names are unique but this cannot be enforced at the
    database level due to versioning.
    """
    return (await Product.find(Product.name == name).count()) > 0


def validate_slugs(sources: dict[str, PreUploadFile], metadata: ALL_METADATA_TYPE):
    """
    Ensures that the slugs available in sources are valid according
    to the metadata type. If they are not, raises a pydantic ValidationError.
    """

    errors = []

    for k in sources.keys():
        if k not in metadata.valid_slugs:
            errors.append(
                ValueError(
                    f"Slug '{k}' not part of acceptable slugs: {metadata.valid_slugs} for this metadata type"
                )
            )

    if errors:
        raise ExceptionGroup("Invalid slugs", errors)


async def create(
    name: str,
    description: str,
    metadata: ALL_METADATA_TYPE,
    sources: dict[str, PreUploadFile],
    user_name: str,
    storage: Storage,
    product_readers: list[str] | None = None,
    product_writers: list[str] | None = None,
    mutlipart_size: int = 50 * 1024 * 1024,
) -> tuple[Product, dict[str, list[str]]]:
    if metadata is None:
        metadata = SimpleMetadata()

    validate_slugs(sources=sources, metadata=metadata)

    presigned, pre_upload_sources = await presign_uploads(
        sources=sources,
        storage=storage,
        user_name=user_name,
        mutlipart_size=mutlipart_size,
    )

    current_utc_time = datetime.datetime.now(datetime.timezone.utc)

    product = Product(
        name=name,
        description=description,
        metadata=metadata,
        uploaded=current_utc_time,
        updated=current_utc_time,
        current=True,
        version=INITIAL_VERSION,
        sources=pre_upload_sources,
        owner=user_name,
        replaces=None,
        child_of=[],
        parent_of=[],
        collections=[],
        readers=set(product_readers or []) | {user_name},
        writers=set(product_writers or []) | {user_name},
    )

    await product.create()

    return product, presigned


async def read_by_name(
    name: str, version: str | None, groups: list[str], scopes: set[str]
) -> Product:
    """
    If version is None, we grab the latest version of a product.
    """

    if version is None:
        potential = await Product.find_one(
            Product.name == name,
            Product.current == True,  # noqa: E712
            **LINK_POLICY,
        )
    else:
        potential = await Product.find_one(
            Product.name == name,
            Product.version == version,
            **LINK_POLICY,
        )

    if potential is None:
        raise ProductNotFound

    assert check_user_access(
        user_groups=groups,
        document_groups=potential.readers + potential.writers,
        scopes=scopes,
    )

    return potential


async def read_by_id(
    id: PydanticObjectId, groups: list[str], scopes: set[str]
) -> Product:
    try:
        potential = await Product.get(document_id=id, **LINK_POLICY)
    except (InvalidId, ValidationError, ValueError):
        raise ProductNotFound

    if potential is None:
        raise ProductNotFound

    assert check_user_access(
        user_groups=groups,
        document_groups=potential.readers + potential.writers,
        scopes=scopes,
    )

    return potential


async def search_by_name(
    name: str, groups: list[str], scopes: set[str], fetch_links: bool = True
) -> list[Product]:
    """
    Search for products by name using the text index.
    """

    if "hippo:admin" in scopes:
        access_query = {}
    else:
        access_query = {
            "$or": [{"readers": {"$in": groups}}, {"writers": {"$in": groups}}]
        }

    results = (
        await Product.find(
            access_query,
            Text(name),
            Product.current == True,  # noqa: E712
            fetch_links=fetch_links,
        )
        .sort([("score", {"$meta": "textScore"})])
        .to_list()
    )

    return results


async def search_by_metadata(
    metadata_filters: dict[str, Any],
    groups: list[str],
    scopes: set[str],
    fetch_links: bool = True,
) -> list[Product]:
    """
    Search for products by metadata.
    """

    if "hippo:admin" in scopes:
        access_query = {}
    else:
        access_query = {
            "$or": [{"readers": {"$in": groups}}, {"writers": {"$in": groups}}]
        }

    # Construct the query by embedding metadata field names and values
    query = {f"metadata.{key}": value for key, value in metadata_filters.items()}

    # Execute the query
    results = await Product.find(access_query, query, fetch_links=fetch_links).to_list()

    return results


async def search_by_owner(
    owner: str,
    groups: list[str],
    scopes: set[str],
    fetch_links: bool = True,
) -> list[Collection]:
    """
    Search for products by owner; owner search is case insensitive
    but must otherwise be an exact match
    """

    owner_regex = {"$regex": f"^{re.escape(owner)}$", "$options": "i"}

    if "hippo:admin" in scopes:
        access_query = {}
    else:
        access_query = {
            "$or": [{"readers": {"$in": groups}}, {"writers": {"$in": groups}}]
        }

    results = await Product.find(
        {**access_query, "owner": owner_regex},
        Product.current == True,  # noqa: E712
        fetch_links=fetch_links,
    ).to_list()

    return results


async def walk_history(product: Product) -> dict[str, ProductMetadata]:
    """
    Walk the history of the product from this point backwards.
    It is recommended that you walk to the current version first,
    to get the whole history.
    """
    versions = {}

    while product.replaces is not None:
        versions[product.version] = await product.to_metadata()
        product = product.replaces

        if isinstance(product, Link):
            product = await product.fetch(fetch_links=True)

    versions[product.version] = await product.to_metadata()

    return versions


async def walk_to_current(
    product: Product, groups: list[str], scopes: set[str]
) -> Product:
    """
    Walk the list of products until you get to the one
    marked 'current'.
    """

    # Re-read the product from the database, in case it
    # is stale!
    product = await read_by_id(id=product.id, groups=groups, scopes=scopes)

    while not product.current:
        product = await Product.find_one(
            Product.replaces.id == product.id, **LINK_POLICY
        )

        if product is None:  # pragma: no cover
            raise RuntimeError

    return product


async def complete(
    product: Product,
    storage: Storage,
    headers: dict[str, list[dict[str, str]]],
    sizes: dict[str, list[int]],
) -> bool:
    for file in product.sources.values():
        if file.multipart_closed:
            continue

        await storage_service.complete(
            file=file,
            storage=storage,
            response_headers=headers[file.name],
            sizes=sizes[file.name],
        )

        file.multipart_closed = True
        await file.save()

    return True


async def confirm(product: Product, storage: Storage) -> bool:
    for slug, file in product.sources.items():
        if not await storage_service.confirm(file=file, storage=storage):
            logger.debug(f"File {file.name} ({slug}) not confirmed")
            return False

    return True


async def read_files(product: Product, storage: Storage) -> dict[str, PostUploadFile]:
    return {
        slug: PostUploadFile(
            uuid=x.uuid,
            name=x.name,
            size=x.size,
            slug=x.slug,
            checksum=x.checksum,
            description=x.description,
            url=storage.get(
                name=x.name, uploader=x.uploader, uuid=x.uuid, bucket=x.bucket
            )
            if x.available
            else None,
            object_name=storage.object_name(
                filename=x.name, uploader=x.uploader, uuid=x.uuid
            )
            if x.available
            else None,
            available=x.available,
        )
        for slug, x in product.sources.items()
    }


async def read_most_recent(
    groups: list[str],
    scopes: set[str],
    fetch_links: bool = False,
    maximum: int = 16,
    current_only: bool = False,
) -> list[Product]:
    if "hippo:admin" in scopes:
        access_query = {}
    else:
        access_query = {
            "$or": [{"readers": {"$in": groups}}, {"writers": {"$in": groups}}]
        }

    if current_only:
        query = {"$and": [{"current": True}, access_query]}
    else:
        query = access_query

    found = Product.find(
        query,
        fetch_links=fetch_links,
    )
    return await found.sort(-Product.updated).to_list(maximum)


async def metadata_diff(
    product: Product,
    name: str | None,
    description: str | None,
    metadata: ALL_METADATA_TYPE | None,
    level: versioning.VersionRevision,
):
    """
    Calculate the diff between the current product and the new metadata.
    This is used to determine what has changed and what needs to be updated.
    """

    if not product.current:
        raise versioning.VersioningError(
            "Attempting to update a non-current product. You must always "
            "make changes to the head of the list"
        )

    changes = {}

    if name is not None and name != product.name:
        changes["name"] = [product.name, name]

    if description is not None and description != product.description:
        changes["description"] = [product.description, description]

    if metadata is not None:
        metadata_diff = {}
        for key, value in metadata.model_dump().items():
            original_value = getattr(product.metadata, key, None)

            if value != original_value:
                metadata_diff[key] = [original_value, value]

        if metadata_diff:
            changes["metadata"] = metadata_diff

    changes["version"] = [
        product.version,
        versioning.revise_version(product.version, level=level),
    ]

    return changes


async def update_metadata(
    product: Product,
    name: str | None,
    description: str | None,
    metadata: ALL_METADATA_TYPE | None,
    level: versioning.VersionRevision,
) -> Product:
    """
    Update only the metadata of a product. Note that you can call this with all
    the variables as `None` and this will simply rev the version. That should
    be used when only updating sources.
    """

    if not product.current:
        raise versioning.VersioningError(
            "Attempting to update a non-current product. You must always "
            "make changes to the head of the list"
        )

    # We don't actually 'update' the database; we actually create a new
    # product and link it in.

    new = Product(
        name=product.name if name is None else name,
        description=product.description if description is None else description,
        metadata=product.metadata if metadata is None else metadata,
        uploaded=product.uploaded,
        owner=product.owner,
        updated=utils.current_utc_time(),
        current=True,
        version=versioning.revise_version(product.version, level=level),
        sources=product.sources,
        replaces=product,
        # This product is a child of nothing util it is told it is. Child
        # relationships only stick around for a single version.
        child_of=[],
        collections=[
            c
            for c, p in zip(product.collections, product.collection_policies)
            if p
            in [CollectionPolicy.ALL, CollectionPolicy.NEW, CollectionPolicy.CURRENT]
        ],
        collection_policies=[
            p
            for p in product.collection_policies
            if p
            in [CollectionPolicy.ALL, CollectionPolicy.NEW, CollectionPolicy.CURRENT]
        ],
        readers=product.readers,
        writers=product.writers,
    )

    # Need to perform a small number of modifications on the original
    # product.
    product.current = False
    product.collections = [
        c
        for c, p in zip(product.collections, product.collection_policies)
        if p in [CollectionPolicy.ALL, CollectionPolicy.NEW, CollectionPolicy.FIXED]
    ]
    product.collection_policies = [
        p
        for p in product.collection_policies
        if p in [CollectionPolicy.ALL, CollectionPolicy.NEW, CollectionPolicy.FIXED]
    ]

    await new.save(link_rule=WriteRules.WRITE)
    await product.save(link_rule=WriteRules.WRITE)

    return new


async def update_sources(
    product: Product,
    new: dict[str, PreUploadFile],
    replace: dict[str, PreUploadFile],
    drop: list[str],
    storage: Storage,
) -> tuple[Product, dict[str, str]]:
    """
    Change the sources associated with a product. New and replace provide
    pre-signed URLs for file uploads (and you should call confirm after),
    and drop is a list of names of files to remove.
    """

    existing_slugs = set(product.sources.keys())
    new_slugs = set(new.keys())
    replace_slugs = set(replace.keys())
    drop_slugs = set(drop)

    if len(existing_slugs & new_slugs) != 0:
        raise FileExistsError

    if len(existing_slugs & replace_slugs) != len(replace_slugs):
        raise FileNotFoundError

    if len(existing_slugs & drop_slugs) != len(drop_slugs):
        raise FileNotFoundError

    # Check our slugs are valid for this metadata type
    validate_slugs(sources={**new, **replace}, metadata=product.metadata)

    presigned_new, pre_upload_sources_new = await presign_uploads(
        sources=new,
        storage=storage,
        user_name=product.owner,
    )

    presigned_replace, pre_upload_sources_replace = await presign_uploads(
        sources=replace, storage=storage, user_name=product.owner
    )

    presigned = {**presigned_new, **presigned_replace}
    pre_upload_sources = {**pre_upload_sources_new, **pre_upload_sources_replace}

    # Filter out the sources we're keeping
    keep_slugs = existing_slugs ^ replace_slugs ^ drop_slugs
    keep_sources = {x: y for x, y in product.sources.items() if x in keep_slugs}

    # Final check -
    expected_number_of_sources = len(product.sources) - len(drop) + len(new)

    if (
        not (len(keep_sources) + len(pre_upload_sources)) == expected_number_of_sources
    ):  # pragma: no cover
        raise RuntimeError

    product.sources = {**pre_upload_sources, **keep_sources}

    await product.save(link_rule=WriteRules.WRITE)

    return product, presigned


async def update(
    product: Product,
    access_groups: list[str],
    scopes: set[str],
    storage: Storage,
    level: versioning.VersionRevision,
    name: str | None = None,
    description: str | None = None,
    metadata: ALL_METADATA_TYPE | None = None,
    new_sources: dict[str, PreUploadFile] | None = None,
    replace_sources: dict[str, PreUploadFile] | None = None,
    drop_sources: list[str] | None = None,
) -> tuple[Product, dict[str, str]]:
    """
    Rev the version of the product and update its contents.
    """
    assert check_user_access(
        user_groups=access_groups, document_groups=product.writers, scopes=scopes
    )

    new_product = await update_metadata(
        product=product,
        name=name,
        description=description,
        metadata=metadata,
        level=level,
    )

    new_sources = new_sources or {}
    replace_sources = replace_sources or {}
    drop_sources = drop_sources or []

    # For some reason:
    # a) Beanie won't allow fetch_all_links to be called on `new_product` because
    #    it has back-links, and it crashes.
    # b) Beanie won't allow fetching specific links on that object. fetch_link()
    #    or .fetch() fails silently.
    # So we just re-fetch our object from the database.

    new_product = await read_by_id(
        new_product.id, new_product.writers + new_product.readers, scopes=scopes
    )  # who should read this product?

    if any([len(new_sources) > 0, len(replace_sources) > 0, len(drop_sources) > 0]):
        try:
            new_product, presigned = await update_sources(
                product=new_product,
                new=new_sources,
                replace=replace_sources,
                drop=drop_sources,
                storage=storage,
            )
        except Exception as e:
            # Need to roll-back our new product. Full transactions when?
            await delete_one(
                new_product,
                [new_product.owner],
                storage=storage,
                data=False,
                scopes=scopes,
            )
            raise e
    else:
        presigned = {}

    return new_product, presigned


async def pin(
    product: Product,
    access_groups: list[str],
    scopes: set[str],
):
    """
    Pin a product in the database.
    """

    assert check_user_access(
        user_groups=access_groups, document_groups=product.writers, scopes=scopes
    )

    product.pinned = True
    await product.save()

    return


async def unpin(
    product: Product,
    access_groups: list[str],
    scopes: set[str],
):
    """
    Unpin a product in the database.
    """

    assert check_user_access(
        user_groups=access_groups, document_groups=product.writers, scopes=scopes
    )

    product.pinned = False
    await product.save()

    return


async def delete_one(
    product: Product,
    access_groups: list[str],
    scopes: set[str],
    storage: Storage,
    data: bool = False,
):
    """
    Delete a single product (i.e. leaving the history intact on either side.)
    """

    # Deal with parent/child replacement relationship
    assert check_user_access(
        user_groups=access_groups, document_groups=product.writers, scopes=scopes
    )
    if product.current:
        replaced_by = None
        replaces = product.replaces
        if replaces is not None:
            replaces.current = True
    else:
        replaced_by = await Product.find_one(Product.replaces.id == product.id)
        replaces = product.replaces
        replaced_by.replaces = replaces

    # Deal with potentially newly ingested files

    if replaces is None:
        past_source_uuids = set()
    else:
        past_source_uuids = {x.uuid for x in replaces.sources.values()}

    current_source_uuids = {x.uuid for x in product.sources.values()}

    if replaced_by is None:
        future_source_uuids = set()
    else:
        future_source_uuids = {x.uuid for x in replaced_by.sources.values()}

    net_source_uuids = current_source_uuids ^ past_source_uuids ^ future_source_uuids

    # Deletion of only uniquely created (in this specific version of the product)
    # data products.

    if data:
        for file in product.sources.values():
            if file.uuid in net_source_uuids:
                await storage_service.delete(file=file, storage=storage)

    if replaced_by is not None:
        await replaced_by.save()

    if replaces is not None:
        await replaces.save()

    await product.delete()

    return


async def delete_tree(
    product: Product,
    access_groups: list[str],
    scopes: set[str],
    storage: Storage,
    data: bool = False,
):
    """
    Delete an entire tree of products, from this one down. You must provide
    a current product.
    """
    assert check_user_access(
        user_groups=access_groups, document_groups=product.writers, scopes=scopes
    )
    if not product.current:
        raise versioning.VersioningError(
            "Attempting to delete the tree starting from a non-current product"
        )

    uuids_to_delete = set()
    files_to_delete = []
    products_to_delete = []

    while product is not None:
        products_to_delete.append(product)

        for source in product.sources.values():
            if source.uuid not in uuids_to_delete:
                uuids_to_delete.update(source.uuid)
                files_to_delete.append(source)

        if isinstance(product.replaces, Link):
            product = await product.replaces.fetch()
        else:
            product = product.replaces

    if data:
        for source in files_to_delete:
            await storage_service.delete(file=source, storage=storage)

    for product in products_to_delete:
        await product.delete()

    return


async def add_relationship(
    source: Product,
    destination: Product,
    access_groups: list[str],
    scopes: set[str],
    type: Literal["child"],
):
    if type == "child":
        source.child_of = source.child_of + [destination]
    assert check_user_access(
        user_groups=access_groups, document_groups=source.writers, scopes=scopes
    )
    await source.save()

    return


async def remove_relationship(
    source: Product,
    destination: Product,
    access_groups: list[str],
    scopes: set[str],
    type: Literal["child"],
):
    if type == "child":
        source.child_of = [c for c in source.child_of if c.id != destination.id]
    assert check_user_access(
        user_groups=access_groups, document_groups=source.writers, scopes=scopes
    )
    await source.save()

    return


async def add_collection(
    product: Product, access_groups: list[str], scopes: set[str], collection: Collection
):
    product.collections = product.collections + [collection]
    assert check_user_access(
        user_groups=access_groups, document_groups=product.writers, scopes=scopes
    )
    await product.save()

    return


async def remove_collection(
    product: Product, access_groups: list[str], scopes: set[str], collection: Collection
):
    product.collections = [c for c in product.collections if c.id != collection.id]
    assert check_user_access(
        user_groups=access_groups, document_groups=product.writers, scopes=scopes
    )
    await product.save()

    return product

"""
The product service layer.
"""

import datetime
from typing import Any, Literal

from beanie import Link, PydanticObjectId, WriteRules
from beanie.operators import Text
from bson.errors import InvalidId
from loguru import logger
from pydantic import BaseModel
from pydantic_core import ValidationError

from hippometa import ALL_METADATA_TYPE
from hipposerve.database import (
    Collection,
    CollectionPolicy,
    File,
    Product,
    ProductMetadata,
    User,
)
from hipposerve.service import storage as storage_service
from hipposerve.service import utils, versioning
from hipposerve.service.auth import (
    check_product_read_access,
    check_product_write_access,
)
from hipposerve.storage import Storage

INITIAL_VERSION = "1.0.0"
LINK_POLICY = {
    "fetch_links": True,
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
    checksum: str
    url: str | None
    description: str | None
    object_name: str | None
    available: bool


async def presign_uploads(
    sources: list[PreUploadFile],
    storage: Storage,
    user: User,
    mutlipart_size: int = 50 * 1024 * 1024,
) -> tuple[dict[str, list[str]], list[File]]:
    presigned = {}
    pre_upload_sources = []

    for source in sources:
        pre_upload_source, presigned_urls = await storage_service.create(
            name=source.name,
            description=source.description,
            uploader=user.name,
            size=source.size,
            checksum=source.checksum,
            storage=storage,
        )

        presigned[source.name] = presigned_urls
        pre_upload_sources.append(pre_upload_source)

    return presigned, pre_upload_sources


async def exists(name: str) -> bool:
    """
    Check whether a product exists with this name.
    Product names are unique but this cannot be enforced at the
    database level due to versioning.
    """
    return (await Product.find(Product.name == name).count()) > 0


async def create(
    name: str,
    description: str,
    metadata: ALL_METADATA_TYPE,
    sources: list[PreUploadFile],
    user: User,
    storage: Storage,
    product_readers: list[str] | None = None,
    product_writers: list[str] | None = None,
    mutlipart_size: int = 50 * 1024 * 1024,
) -> tuple[Product, dict[str, list[str]]]:
    presigned, pre_upload_sources = await presign_uploads(
        sources=sources, storage=storage, user=user, mutlipart_size=mutlipart_size
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
        owner=user,
        replaces=None,
        child_of=[],
        parent_of=[],
        collections=[],
        collection_policies=[],
    )
    product_readers = product_readers or []
    product_writers = product_writers or []

    if product_readers is not None:
        product.readers.extend(product_readers)
    if user.name not in product.writers:
        product_writers.append(user.name)
    product.writers.extend(product_writers)

    await product.create()

    return product, presigned


async def read_by_name(name: str, version: str | None, user: User) -> Product:
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

    await check_product_read_access(user=user, target_product=potential)

    return potential


async def read_by_id(id: PydanticObjectId, user: User) -> Product:
    try:
        potential = await Product.get(document_id=id, **LINK_POLICY)
    except (InvalidId, ValidationError):
        raise ProductNotFound

    if potential is None:
        raise ProductNotFound

    await check_product_read_access(user=user, target_product=potential)

    return potential


async def search_by_name(name: str, fetch_links: bool = True) -> list[Product]:
    """
    Search for products by name using the text index.
    """

    results = (
        await Product.find(Text(name), Product.current == True, fetch_links=fetch_links)  # noqa: E712
        .sort([("score", {"$meta": "textScore"})])
        .to_list()
    )

    return results


async def search_by_metadata(
    metadata_filters: dict[str, Any], fetch_links: bool = True
) -> list[Product]:
    """
    Search for products by metadata.
    """

    # Construct the query by embedding metadata field names and values
    query = {f"metadata.{key}": value for key, value in metadata_filters.items()}

    # Execute the query
    results = await Product.find(query, fetch_links=fetch_links).to_list()
    return results


async def walk_history(product: Product) -> dict[str, ProductMetadata]:
    """
    Walk the history of the product from this point backwards.
    It is recommended that you walk to the current version first,
    to get the whole history.
    """
    versions = {}

    while product.replaces is not None:
        versions[product.version] = product.to_metadata()
        product = product.replaces

    versions[product.version] = product.to_metadata()

    return versions


async def walk_to_current(product: Product, user: User) -> Product:
    """
    Walk the list of products until you get to the one
    marked 'current'.
    """

    # Re-read the product from the database, in case it
    # is stale!
    product = await read_by_id(id=product.id, user=user)

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
    for file in product.sources:
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
    for file in product.sources:
        if not await storage_service.confirm(file=file, storage=storage):
            logger.debug(f"File {file.name} not confirmed")
            return False

    return True


async def read_files(product: Product, storage: Storage) -> list[PostUploadFile]:
    return [
        PostUploadFile(
            uuid=x.uuid,
            name=x.name,
            size=x.size,
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
        for x in product.sources
    ]


async def read_most_recent(
    user: User, fetch_links: bool = False, maximum: int = 16, current_only: bool = False
) -> list[Product]:
    group_names = [group.name for group in user.groups]
    access_query = {
        "$or": [{"readers": {"$in": group_names}}, {"writers": {"$in": group_names}}]
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


async def update_metadata(
    product: Product,
    name: str | None,
    description: str | None,
    metadata: ALL_METADATA_TYPE | None,
    owner: User | None,
    level: versioning.VersionRevision,
    add_readers: list[str] | None = None,
    remove_readers: list[str] | None = None,
    add_writers: list[str] | None = None,
    remove_writers: list[str] | None = None,
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
    readers = product.readers.copy()
    writers = product.writers.copy()
    # We don't actually 'update' the database; we actually create a new
    # product and link it in.
    if owner is not None:
        writers.append(owner.name)
    if add_readers is not None:
        readers.extend(add_readers)
    if remove_readers is not None:
        readers = [x for x in readers if x not in remove_readers]
    if add_writers is not None:
        writers.extend(add_writers)
    if remove_writers is not None:
        writers = [x for x in writers if x not in remove_writers]

    new = Product(
        name=product.name if name is None else name,
        description=product.description if description is None else description,
        metadata=product.metadata if metadata is None else metadata,
        uploaded=product.uploaded,
        updated=utils.current_utc_time(),
        current=True,
        version=versioning.revise_version(product.version, level=level),
        sources=product.sources,
        owner=product.owner if owner is None else owner,
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
        readers=readers,
        writers=writers,
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

    return new


async def update_sources(
    product: Product,
    new: list[PreUploadFile],
    replace: list[PreUploadFile],
    drop: list[str],
    storage: Storage,
) -> tuple[Product, dict[str, str]]:
    """
    Change the sources associated with a product. New and replace provide
    pre-signed URLs for file uploads (and you should call confirm after),
    and drop is a list of names of files to remove.
    """

    existing_names = {x.name for x in product.sources}
    new_names = {x.name for x in new}
    replace_names = {x.name for x in replace}
    drop_names = set(drop)

    if len(existing_names & new_names) != 0:
        raise FileExistsError

    if len(existing_names & replace_names) != len(replace_names):
        raise FileNotFoundError

    if len(existing_names & drop_names) != len(drop_names):
        raise FileNotFoundError

    presigned_new, pre_upload_sources_new = await presign_uploads(
        sources=new,
        storage=storage,
        user=product.owner,
    )

    presigned_replace, pre_upload_sources_replace = await presign_uploads(
        sources=replace, storage=storage, user=product.owner
    )

    presigned = {**presigned_new, **presigned_replace}
    pre_upload_sources = pre_upload_sources_new + pre_upload_sources_replace

    # Filter out the sources we're keeping
    keep_names = existing_names ^ replace_names ^ drop_names
    keep_sources = [x for x in product.sources if x.name in keep_names]

    # Final check -
    expected_number_of_sources = len(product.sources) - len(drop) + len(new)

    if (
        not (len(keep_sources) + len(pre_upload_sources)) == expected_number_of_sources
    ):  # pragma: no cover
        raise RuntimeError

    product.sources = pre_upload_sources + keep_sources

    await product.save(link_rule=WriteRules.WRITE)

    return product, presigned


async def update(
    product: Product,
    access_user: User,
    name: str | None,
    description: str | None,
    metadata: ALL_METADATA_TYPE | None,
    owner: User | None,
    new_sources: list[PreUploadFile],
    replace_sources: list[PreUploadFile],
    drop_sources: list[str],
    storage: Storage,
    level: versioning.VersionRevision,
    add_readers: list[str] | None = None,
    remove_readers: list[str] | None = None,
    add_writers: list[str] | None = None,
    remove_writers: list[str] | None = None,
) -> tuple[Product, dict[str, str]]:
    await check_product_write_access(user=access_user, target_product=product)
    new_product = await update_metadata(
        product=product,
        name=name,
        description=description,
        metadata=metadata,
        owner=owner,
        level=level,
        add_readers=add_readers,
        remove_readers=remove_readers,
        add_writers=add_writers,
        remove_writers=remove_writers,
    )

    # For some reason:
    # a) Beanie won't allow fetch_all_links to be called on `new_product` because
    #    it has back-links, and it crashes.
    # b) Beanie won't allow fetching specific links on that object. fetch_link()
    #    or .fetch() fails silently.
    # So we just re-fetch our object from the database.

    new_product = await read_by_id(
        new_product.id, new_product.owner
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
                new_product, new_product.owner, storage=storage, data=False
            )
            raise e
    else:
        presigned = {}

    return new_product, presigned


async def delete_one(
    product: Product,
    access_user: User,
    storage: Storage,
    data: bool = False,
):
    """
    Delete a single product (i.e. leaving the history intact on either side.)
    """

    # Deal with parent/child replacement relationship
    await check_product_write_access(user=access_user, target_product=product)
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
        past_source_uuids = {x.uuid for x in replaces.sources}

    current_source_uuids = {x.uuid for x in product.sources}

    if replaced_by is None:
        future_source_uuids = set()
    else:
        future_source_uuids = {x.uuid for x in replaced_by.sources}

    net_source_uuids = current_source_uuids ^ past_source_uuids ^ future_source_uuids

    # Deletion of only uniquely created (in this specific version of the product)
    # data products.

    if data:
        for file in product.sources:
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
    access_user: User,
    storage: Storage,
    data: bool = False,
):
    """
    Delete an entire tree of products, from this one down. You must provide
    a current product.
    """
    await check_product_write_access(user=access_user, target_product=product)
    if not product.current:
        raise versioning.VersioningError(
            "Attempting to delete the tree starting from a non-current product"
        )

    uuids_to_delete = set()
    files_to_delete = []
    products_to_delete = []

    while product is not None:
        products_to_delete.append(product)

        for source in product.sources:
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
    access_user: User,
    type: Literal["child"],
):
    if type == "child":
        source.child_of = source.child_of + [destination]
    await check_product_write_access(user=access_user, target_product=source)
    await source.save()

    return


async def remove_relationship(
    source: Product,
    destination: Product,
    access_user: User,
    type: Literal["child"],
):
    if type == "child":
        source.child_of = [c for c in source.child_of if c.id != destination.id]
    await check_product_write_access(user=access_user, target_product=source)
    await source.save()

    return


async def add_collection(product: Product, access_user: User, collection: Collection):
    product.collections = product.collections + [collection]
    await check_product_write_access(user=access_user, target_product=product)
    await product.save()

    return


async def remove_collection(
    product: Product, access_user: User, collection: Collection
):
    product.collections = [c for c in product.collections if c.id != collection.id]
    await check_product_write_access(user=access_user, target_product=product)
    await product.save()

    return product

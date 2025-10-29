"""
Tests for just the product service.
"""

import datetime
import io

import pytest
import requests
from beanie import PydanticObjectId
from beanie.odm.fields import Link

import hippometa
from hipposerve.service import acl, product, versioning


@pytest.mark.asyncio(loop_scope="session")
async def test_created_product_groups(created_full_product, database):
    assert created_full_product.owner in created_full_product.writers
    assert created_full_product.owner in created_full_product.readers


@pytest.mark.asyncio(loop_scope="session")
async def test_get_existing_file(created_full_product, database, created_user):
    selected_product = await product.read_by_id(
        created_full_product.id, created_user.groups, scopes=set()
    )

    assert selected_product.name == created_full_product.name

    for key in created_full_product.model_fields_set:
        original = getattr(created_full_product, key)
        loaded = getattr(selected_product, key)
        # Mongo datetimes are lossy. Just make sure they were created at the same HH:MM:SS
        if isinstance(original, datetime.datetime):
            original_time = f"{original.hour}:{original.minute}:{original.second}"
            loaded_time = f"{loaded.hour}:{loaded.minute}:{loaded.second}"

            assert original_time == loaded_time
        else:
            if isinstance(original, Link):
                original = await original.fetch()
            if isinstance(loaded, Link):
                loaded = await loaded.fetch()

            assert original == loaded


@pytest.mark.asyncio(loop_scope="session")
async def test_create_file_with_multiple_sources(database, created_user, storage):
    sources = {
        "map": product.PreUploadFile(name="file1.txt", size=128, checksum="not_real"),
        "hits": product.PreUploadFile(name="file2.txt", size=128, checksum="not_real"),
    }

    created_product, uploads = await product.create(
        name="Multiple Source Product",
        description="A product with multiple sources",
        metadata=hippometa.MapSet(pixelisation="equirectangular"),
        sources=sources,
        user_name=created_user.display_name,
        storage=storage,
    )

    assert len(created_product.sources) == 2

    FILE_CONTENTS = b"0x0" * 128

    responses = {}
    sizes = {}

    with io.BytesIO(FILE_CONTENTS) as f:
        for file_name, put in uploads.items():
            # Must go back to the start or we write 0 bytes!
            f.seek(0)
            response = requests.put(put[0], f)

            responses[file_name] = [response.headers]
            sizes[file_name] = [len(FILE_CONTENTS)]

    # Not ready yet - must be completed!
    assert not await product.confirm(created_product, storage=storage)

    await product.complete(
        created_product, storage=storage, headers=responses, sizes=sizes
    )

    assert await product.confirm(created_product, storage=storage)

    await product.delete_one(
        created_product, created_user.groups, storage=storage, data=True, scopes=set()
    )


@pytest.mark.asyncio(loop_scope="session")
async def test_presign_read(created_full_product, storage):
    sources = await product.read_files(created_full_product, storage)

    for source in sources.values():
        assert source.url is not None


@pytest.mark.asyncio(loop_scope="session")
async def test_get_missing_file(database, created_user):
    with pytest.raises(product.ProductNotFound):
        await product.read_by_name(
            name="Missing Product",
            version=None,
            groups=created_user.groups,
            scopes=set(),
        )

    with pytest.raises(product.ProductNotFound):
        await product.read_by_id(
            id=PydanticObjectId("7" * 24), groups=created_user.groups, scopes=set()
        )

    with pytest.raises(product.ProductNotFound):
        await product.read_by_id(
            id="abcdefghijk", groups=created_user.groups, scopes=set()
        )


@pytest.mark.asyncio(loop_scope="session")
async def test_add_to_collection(
    created_collection, created_full_product, database, created_user
):
    await product.add_collection(
        product=created_full_product,
        access_groups=created_user.groups,
        collection=created_collection,
        scopes=set(),
    )

    selected_product = await product.read_by_id(
        created_full_product.id, created_user.groups, scopes=set()
    )

    assert created_collection.name in [c.name for c in selected_product.collections]

    await product.remove_collection(
        product=selected_product,
        access_groups=created_user.groups,
        collection=created_collection,
        scopes=set(),
    )

    selected_product = await product.read_by_id(
        created_full_product.id, created_user.groups, scopes=set()
    )

    assert created_collection.name not in [c.name for c in selected_product.collections]


@pytest.mark.asyncio(loop_scope="session")
async def test_update_access_control(created_full_product, created_user):
    existing_version = created_full_product.version
    existing_readers = set(created_full_product.readers)
    existing_writers = set(created_full_product.writers)

    updated_product = await acl.update_access_control(
        created_full_product, add_readers={"fake_reader"}, add_writers={"fake_writer"}
    )

    assert updated_product.version == existing_version
    assert set(updated_product.readers) == (existing_readers | {"fake_reader"})
    assert set(updated_product.writers) == (existing_writers | {"fake_writer"})

    updated_product = await acl.update_access_control(
        created_full_product,
        remove_readers={"fake_reader"},
        remove_writers={"fake_writer"},
    )

    assert updated_product.version == existing_version
    assert set(updated_product.readers) == existing_readers
    assert set(updated_product.writers) == existing_writers

    return


@pytest.mark.asyncio(loop_scope="session")
async def test_update_metadata(created_full_product, database, storage, created_user):
    existing_version = created_full_product.version

    await product.update(
        created_full_product,
        created_user.groups,
        scopes=set(),
        name=None,
        description="New description",
        metadata={"metadata_type": "simple"},
        level=versioning.VersionRevision.MAJOR,
        new_sources=[],
        replace_sources=[],
        drop_sources=[],
        storage=storage,
    )

    new_product = await product.read_by_name(
        name=created_full_product.name,
        version=None,
        groups=created_user.groups,
        scopes=set(),
    )

    assert new_product.name == created_full_product.name
    assert new_product.description == "New description"
    assert new_product.owner == created_user.display_name
    assert new_product.version != existing_version
    assert new_product.replaces.id == created_full_product.id
    assert new_product.current

    # try to read old version
    metadata = await product.read_by_name(
        name=created_full_product.name,
        version=existing_version,
        groups=created_user.groups,
        scopes=set(),
    )

    assert not metadata.current
    assert metadata.name == created_full_product.name
    assert metadata.description == created_full_product.description
    assert metadata.owner == created_full_product.owner
    assert metadata.version == existing_version

    with pytest.raises(versioning.VersioningError):
        await product.update_metadata(
            product=metadata,
            name=None,
            description=None,
            metadata=None,
            level=versioning.VersionRevision.MAJOR,
        )

    assert new_product.current
    await product.delete_one(
        new_product, created_user.groups, storage=storage, data=True, scopes=set()
    )


@pytest.mark.asyncio(loop_scope="session")
async def test_update_sources(created_full_product, database, storage, created_user):
    # Get the current version of the created_full_product in case it has been
    # mutated.
    created_full_product = await product.walk_to_current(
        product=created_full_product, groups=created_user.groups, scopes=set()
    )

    assert created_full_product.current

    FILE_CONTENTS = b"0x0" * 128

    new = {
        "map": product.PreUploadFile(
            name="additional_file.txt", size=128, checksum="not_real"
        )
    }
    replace = {
        "data": product.PreUploadFile(
            name="you_can_call_this_whatever_u_like.txt",
            checksum="replacement",
            size=128,
        )
    }

    _, uploads = await product.update(
        created_full_product,
        created_user.groups,
        scopes=set(),
        name=None,
        description="Updated version of the created_full_product",
        metadata=None,
        new_sources=new,
        replace_sources=replace,
        drop_sources=[],
        storage=storage,
        level=versioning.VersionRevision.MINOR,
    )

    headers = {}
    sizes = {}

    with io.BytesIO(FILE_CONTENTS) as f:
        for file_name, put in uploads.items():
            # Must go back to the start or we write 0 bytes!
            f.seek(0)
            headers[file_name] = [requests.put(put[0], f).headers]
            sizes[file_name] = [len(FILE_CONTENTS)]

    # Grab it back and check
    new_product = await product.read_by_name(
        created_full_product.name,
        version=None,
        groups=created_user.groups,
        scopes=set(),
    )

    assert "map" not in created_full_product.sources
    assert "map" in new_product.sources
    assert (
        created_full_product.sources["data"].name
        != "you_can_call_this_whatever_u_like.txt"
    )
    assert new_product.sources["data"].name == "you_can_call_this_whatever_u_like.txt"

    _, uploads = await product.update(
        new_product,
        created_user.groups,
        scopes=set(),
        drop_sources=["map"],
        storage=storage,
        level=versioning.VersionRevision.MINOR,
    )

    # Grab it back and check
    reverted_product = await product.read_by_name(
        created_full_product.name,
        version=None,
        groups=created_user.groups,
        scopes=set(),
    )

    assert "map" not in reverted_product.sources


@pytest.mark.asyncio(loop_scope="session")
async def test_update_sources_failure_modes(
    created_full_product, database, storage, created_user
):
    created_full_product = await product.walk_to_current(
        product=created_full_product, groups=created_user.groups, scopes=set()
    )

    # Check we do not rev the version when stuff fails!
    starting_version = created_full_product.version

    with pytest.raises(FileExistsError):
        await product.update(
            await product.walk_to_current(
                created_full_product, groups=created_user.groups, scopes=set()
            ),
            created_user.groups,
            scopes=set(),
            name=None,
            description=None,
            metadata=None,
            new_sources={
                "data": product.PreUploadFile(
                    name=created_full_product.sources["data"].name,
                    size=created_full_product.sources["data"].size,
                    checksum=created_full_product.sources["data"].checksum,
                )
            },
            replace_sources=[],
            drop_sources=[],
            storage=storage,
            level=versioning.VersionRevision.MINOR,
        )

    with pytest.raises(FileNotFoundError):
        await product.update(
            await product.walk_to_current(
                created_full_product, groups=created_user.groups, scopes=set()
            ),
            created_user.groups,
            scopes=set(),
            name=None,
            description=None,
            metadata=None,
            new_sources=[],
            replace_sources={
                "xlink_coadd": product.PreUploadFile(
                    name=created_full_product.sources["data"].name,
                    size=created_full_product.sources["data"].size,
                    checksum=created_full_product.sources["data"].checksum,
                )
            },
            drop_sources=[],
            storage=storage,
            level=versioning.VersionRevision.MINOR,
        )

    with pytest.raises(FileNotFoundError):
        await product.update(
            await product.walk_to_current(
                created_full_product, groups=created_user.groups, scopes=set()
            ),
            created_user.groups,
            scopes=set(),
            name=None,
            description=None,
            metadata=None,
            new_sources=[],
            replace_sources=[],
            drop_sources=["xlink_coadd"],
            storage=storage,
            level=versioning.VersionRevision.MINOR,
        )

    current = await product.walk_to_current(
        created_full_product, groups=created_user.groups, scopes=set()
    )
    assert current.version == starting_version


@pytest.mark.asyncio(loop_scope="session")
async def test_read_most_recent_products(database, created_user, storage):
    # Insert a bunch of products.
    for i in range(20):
        await product.create(
            name=f"product_{i}",
            description=f"description_{i}",
            metadata=None,
            sources={},
            user_name=created_user.display_name,
            storage=storage,
        )

    products = await product.read_most_recent(
        groups=created_user.groups,
        scopes=set(),
        fetch_links=False,
        maximum=8,
        current_only=False,
    )

    assert len(products) == 8

    # Now update all those products with a no-op update
    bad_ids = set()

    for x in products[:4]:
        await product.update_metadata(
            x,
            name=None,
            description=None,
            metadata=None,
            level=versioning.VersionRevision.MAJOR,
        )
        bad_ids.add(x.id)

    products = await product.read_most_recent(
        groups=created_user.groups, scopes=set(), fetch_links=False, current_only=True
    )

    for x in products:
        assert x.id not in bad_ids

    # Clean up.
    for i in range(20):
        await product.delete_tree(
            product=await product.read_by_name(
                name=f"product_{i}",
                version=None,
                groups=created_user.groups,
                scopes=set(),
            ),
            access_groups=created_user.groups,
            storage=storage,
            data=True,
        )

    products = await product.read_most_recent(
        groups=created_user.groups, scopes=set(), fetch_links=False, maximum=8
    )


@pytest.mark.asyncio(loop_scope="session")
async def test_walk_history(database, created_full_product, created_user):
    latest = await product.walk_to_current(
        created_full_product, created_user.groups, scopes=set()
    )

    versions = await product.walk_history(latest)

    assert created_full_product.version in versions.keys()
    assert latest.version in versions.keys()


@pytest.mark.asyncio(loop_scope="session")
async def test_add_relationships(database, created_user, created_full_product, storage):
    # First, make a secondary metadata-only product.
    secondary_product, _ = await product.create(
        name="secondary_product",
        description="A secondary product",
        metadata=None,
        sources={},
        user_name=created_user.display_name,
        storage=storage,
    )

    await product.add_relationship(
        source=secondary_product,
        destination=created_full_product,
        access_groups=created_user.groups,
        type="child",
        scopes=set(),
    )

    # Grab the original product and check that the created_full_product is a _parent_
    # of the child.
    secondary_product = await product.read_by_id(
        secondary_product.id, groups=created_user.groups, scopes=set()
    )
    original_product = await product.read_by_id(
        created_full_product.id, groups=created_user.groups, scopes=set()
    )

    assert original_product.name in [c.name for c in secondary_product.child_of]
    assert secondary_product.name in [c.name for c in original_product.parent_of]

    # Remove this relationship.
    await product.remove_relationship(
        source=secondary_product,
        destination=created_full_product,
        access_groups=created_user.groups,
        scopes=set(),
        type="child",
    )

    original_product = await product.read_by_id(
        created_full_product.id, groups=created_user.groups, scopes=set()
    )

    assert secondary_product.name not in [c.name for c in original_product.parent_of]

    await product.delete_tree(
        product=await product.read_by_name(
            name=secondary_product.name,
            version=None,
            groups=created_user.groups,
            scopes=set(),
        ),
        access_groups=created_user.groups,
        scopes=set(),
        storage=storage,
        data=True,
    )


@pytest.mark.asyncio(loop_scope="session")
async def test_product_middle_deletion(database, created_user, storage):
    initial, _ = await product.create(
        name="Middle-out Product",
        description="Trying to remove version 1.0.1",
        metadata={"metadata_type": "simple"},
        sources={},
        user_name=created_user.display_name,
        storage=storage,
    )

    middle, uploads = await product.update(
        initial,
        created_user.groups,
        scopes=set(),
        name=None,
        metadata=None,
        description=None,
        new_sources={
            "data": product.PreUploadFile(
                name="to_be_deleted.txt", size=128, checksum="not_important"
            )
        },
        drop_sources=[],
        replace_sources=[],
        storage=storage,
        level=versioning.VersionRevision.PATCH,
    )

    # Upload that file.

    FILE_CONTENTS = b"0x0" * 128

    headers = {}
    sizes = {}

    with io.BytesIO(FILE_CONTENTS) as f:
        for file_name, put in uploads.items():
            # Must go back to the start or we write 0 bytes!
            f.seek(0)
            headers[file_name] = [requests.put(put[0], f).headers]
            sizes[file_name] = [len(FILE_CONTENTS)]

    await product.complete(
        product=middle,
        storage=storage,
        headers=headers,
        sizes=sizes,
    )
    assert await product.confirm(middle, storage)

    final, _ = await product.update(
        middle,
        created_user.groups,
        scopes=set(),
        name=None,
        metadata=None,
        description=None,
        new_sources=[],
        replace_sources=[],
        drop_sources=["data"],
        storage=storage,
        level=versioning.VersionRevision.PATCH,
    )

    with pytest.raises(versioning.VersioningError):
        await product.delete_tree(
            product=middle,
            access_groups=created_user.groups,
            storage=storage,
            data=False,
            scopes=set(),
        )

    await product.delete_one(
        middle, created_user.groups, storage, data=True, scopes=set()
    )

    # Refresh them from the database to give this the best chance
    initial = await product.read_by_id(initial.id, created_user.groups, scopes=set())
    final = await product.read_by_id(final.id, created_user.groups, scopes=set())

    assert final.current
    assert final.replaces == initial

    # Make sure we deleted the object.
    with pytest.raises(product.ProductNotFound):
        await product.read_by_name(
            initial.name, version="1.0.1", groups=created_user.groups, scopes=set()
        )

    # See if we deleted that file we uploaded. As it was not part of v1.0.2 and
    # not part of v1.0.0, it should be gone.
    from hipposerve.service import storage as storage_service

    assert not await storage_service.confirm(
        file=middle.sources["data"], storage=storage
    )


@pytest.mark.asyncio(loop_scope="session")
async def test_text_name_search(database, created_user, storage):
    # Insert two products with similar names.
    product_A, _ = await product.create(
        name="My Favorite Product A",
        description="A product",
        metadata=None,
        sources={},
        user_name=created_user.display_name,
        storage=storage,
    )

    product_B, _ = await product.create(
        name="my favorite product b",
        description="A product",
        metadata=None,
        sources={},
        user_name=created_user.display_name,
        storage=storage,
    )

    # Search for them

    results = await product.search_by_name(
        "my favorite", created_user.groups, scopes=set()
    )

    assert len(results) == 2

    assert {x.id for x in results} == {product_A.id, product_B.id}

    # Clean up.

    await product.delete_one(
        product_A, created_user.groups, storage=storage, data=True, scopes=set()
    )
    await product.delete_one(
        product_B, created_user.groups, storage=storage, data=True, scopes=set()
    )


@pytest.mark.asyncio(loop_scope="session")
async def test_product_with_five_versions(database, created_user, storage):
    # Create a new product
    new_product, _ = await product.create(
        name="Five Version Product",
        description="A product with five versions",
        metadata=None,
        sources={},
        user_name=created_user.display_name,
        storage=storage,
    )

    for i in range(5):
        new_product, _ = await product.update(
            product=new_product,
            access_groups=created_user.groups,
            scopes=set(),
            description=f"Version {i + 1} of the product",
            storage=storage,
            level=versioning.VersionRevision.MINOR,
        )

    # Now try to get the fifth version by name.
    final_product = await product.read_by_name(
        name=new_product.name, version=None, groups=created_user.groups, scopes=set()
    )

    history = await product.walk_history(final_product)

    assert len(history) == 6

    # Delete the tree.
    await product.delete_tree(
        product=final_product,
        access_groups=created_user.groups,
        scopes=set(),
        storage=storage,
        data=True,
    )

"""
Tests for just the product service.
"""

import datetime
import io

import pytest
import requests
from beanie import PydanticObjectId
from beanie.odm.fields import Link

from hipposerve.service import product, versioning


@pytest.mark.asyncio(loop_scope="session")
async def test_created_product_groups(created_full_product, database):
    assert created_full_product.owner in created_full_product.writers
    assert "admin" in created_full_product.writers
    assert created_full_product.readers == []


@pytest.mark.asyncio(loop_scope="session")
async def test_get_existing_file(created_full_product, database, created_user):
    selected_product = await product.read_by_id(
        created_full_product.id, created_user.groups
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
    sources = [
        product.PreUploadFile(name="file1.txt", size=128, checksum="not_real"),
        product.PreUploadFile(name="file2.txt", size=128, checksum="not_real"),
    ]

    created_product, uploads = await product.create(
        name="Multiple Source Product",
        description="A product with multiple sources",
        metadata={"metadata_type": "simple"},
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
        created_product, created_user.groups, storage=storage, data=True
    )


@pytest.mark.asyncio(loop_scope="session")
async def test_presign_read(created_full_product, storage):
    sources = await product.read_files(created_full_product, storage)

    for source in sources:
        assert source.url is not None


@pytest.mark.asyncio(loop_scope="session")
async def test_get_missing_file(database, created_user):
    with pytest.raises(product.ProductNotFound):
        await product.read_by_name(
            name="Missing Product", version=None, groups=created_user.groups
        )

    with pytest.raises(product.ProductNotFound):
        await product.read_by_id(
            id=PydanticObjectId("7" * 24), groups=created_user.groups
        )

    with pytest.raises(product.ProductNotFound):
        await product.read_by_id(id="abcdefghijk", groups=created_user.groups)


@pytest.mark.asyncio(loop_scope="session")
async def test_add_to_collection(
    created_collection, created_full_product, database, created_user
):
    await product.add_collection(
        product=created_full_product,
        access_groups=created_user.groups,
        collection=created_collection,
    )

    selected_product = await product.read_by_id(
        created_full_product.id, created_user.groups
    )

    assert created_collection.name in [c.name for c in selected_product.collections]
    print("access_groups", created_user.groups)
    await product.remove_collection(
        product=selected_product,
        access_groups=created_user.groups,
        collection=created_collection,
    )

    selected_product = await product.read_by_id(
        created_full_product.id, created_user.groups
    )

    assert created_collection.name not in [c.name for c in selected_product.collections]


@pytest.mark.asyncio(loop_scope="session")
async def test_update_metadata(created_full_product, database, storage, created_user):
    existing_version = created_full_product.version

    await product.update(
        created_full_product,
        created_user.groups,
        name=None,
        description="New description",
        owner=created_user.display_name,
        metadata={"metadata_type": "simple"},
        level=versioning.VersionRevision.MAJOR,
        new_sources=[],
        replace_sources=[],
        drop_sources=[],
        storage=storage,
    )

    new_product = await product.read_by_name(
        name=created_full_product.name, version=None, groups=created_user.groups
    )

    assert new_product.name == created_full_product.name
    assert new_product.description == "New description"
    assert new_product.owner == created_user.display_name
    assert new_product.version != existing_version
    assert new_product.replaces.id == created_full_product.id
    # try to read old version
    metadata = await product.read_by_name(
        name=created_full_product.name,
        version=existing_version,
        groups=created_user.groups,
    )

    assert not metadata.current
    assert metadata.name == created_full_product.name
    assert metadata.description == created_full_product.description
    assert metadata.owner == created_full_product.owner
    assert metadata.version == existing_version

    with pytest.raises(versioning.VersioningError):
        await product.update_metadata(
            metadata, None, None, None, None, level=versioning.VersionRevision.MAJOR
        )

    assert new_product.current
    await product.delete_one(
        new_product, created_user.groups, storage=storage, data=True
    )


@pytest.mark.asyncio(loop_scope="session")
async def test_update_product_groups(
    created_full_product, database, storage, created_user
):
    created_full_product = await product.walk_to_current(
        product=created_full_product, groups=created_user.groups
    )
    assert created_full_product.current
    created_group = "New Reader"
    await product.update(
        created_full_product,
        created_user.groups,
        name=None,
        description=None,
        owner=None,
        metadata={"metadata_type": "simple"},
        level=versioning.VersionRevision.MAJOR,
        new_sources=[],
        replace_sources=[],
        drop_sources=[],
        storage=storage,
        add_readers=[created_group],
    )
    updated_product = await product.read_by_name(
        name=created_full_product.name, version=None, groups=created_user.groups
    )
    assert created_group in updated_product.readers

    created_full_product = await product.walk_to_current(
        product=created_full_product, groups=created_user.groups
    )
    assert created_full_product.current
    await product.update(
        created_full_product,
        created_user.groups,
        name=None,
        description=None,
        owner=None,
        metadata={"metadata_type": "simple"},
        level=versioning.VersionRevision.MAJOR,
        new_sources=[],
        replace_sources=[],
        drop_sources=[],
        storage=storage,
        remove_readers=[created_group],
    )
    updated_product = await product.read_by_name(
        name=created_full_product.name, version=None, groups=created_user.groups
    )
    assert created_group not in updated_product.readers

    await product.delete_one(
        updated_product, updated_product.writers, storage=storage, data=True
    )


@pytest.mark.asyncio(loop_scope="session")
async def test_update_sources(created_full_product, database, storage, created_user):
    # Get the current version of the created_full_product in case it has been
    # mutated.
    created_full_product = await product.walk_to_current(
        product=created_full_product, groups=created_user.groups
    )

    assert created_full_product.current

    FILE_CONTENTS = b"0x0" * 128

    new = [
        product.PreUploadFile(name="additional_file.txt", size=128, checksum="not_real")
    ]
    replace = [
        product.PreUploadFile(
            name=created_full_product.sources[0].name, size=128, checksum="replacement"
        )
    ]
    drop = [created_full_product.sources[1].name]

    new_product_created, uploads = await product.update(
        created_full_product,
        created_user.groups,
        None,
        "Updated version of the created_full_product",
        None,
        None,
        new_sources=new,
        replace_sources=replace,
        drop_sources=drop,
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
        created_full_product.name, version=None, groups=created_user.groups
    )

    for source in created_full_product.sources[:2]:
        assert source not in new_product.sources

    for source in created_full_product.sources[2:]:
        assert source in new_product.sources

    for source in replace:
        assert source.name in [x.name for x in new_product.sources]

    for source in new:
        assert source.name in [x.name for x in new_product.sources]


@pytest.mark.asyncio(loop_scope="session")
async def test_update_sources_failure_modes(
    created_full_product, database, storage, created_user
):
    created_full_product = await product.walk_to_current(
        product=created_full_product, groups=created_user.groups
    )

    # Check we do not rev the version when stuff fails!
    starting_version = created_full_product.version

    with pytest.raises(FileExistsError):
        await product.update(
            await product.walk_to_current(
                created_full_product, groups=created_user.groups
            ),
            created_user.groups,
            None,
            None,
            None,
            None,
            new_sources=[
                product.PreUploadFile(
                    name=created_full_product.sources[0].name,
                    size=created_full_product.sources[0].size,
                    checksum=created_full_product.sources[0].checksum,
                )
            ],
            replace_sources=[],
            drop_sources=[],
            storage=storage,
            level=versioning.VersionRevision.MINOR,
        )

    with pytest.raises(FileNotFoundError):
        await product.update(
            await product.walk_to_current(
                created_full_product, groups=created_user.groups
            ),
            created_user.groups,
            None,
            None,
            None,
            None,
            new_sources=[],
            replace_sources=[
                product.PreUploadFile(
                    name=created_full_product.sources[0].name + "ABCD",
                    size=created_full_product.sources[0].size,
                    checksum=created_full_product.sources[0].checksum,
                )
            ],
            drop_sources=[],
            storage=storage,
            level=versioning.VersionRevision.MINOR,
        )

    with pytest.raises(FileNotFoundError):
        await product.update(
            await product.walk_to_current(
                created_full_product, groups=created_user.groups
            ),
            created_user.groups,
            None,
            None,
            None,
            None,
            new_sources=[],
            replace_sources=[],
            drop_sources=["non_existent_file.fake"],
            storage=storage,
            level=versioning.VersionRevision.MINOR,
        )

    current = await product.walk_to_current(
        created_full_product, groups=created_user.groups
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
            sources=[],
            user_name=created_user.display_name,
            storage=storage,
        )

    products = await product.read_most_recent(
        groups=created_user.groups, fetch_links=False, maximum=8, current_only=False
    )

    assert len(products) == 8

    # Now update all those products with a no-op update
    bad_ids = set()

    for x in products[:4]:
        await product.update_metadata(
            x,
            None,
            None,
            None,
            None,
            level=versioning.VersionRevision.MAJOR,
        )
        bad_ids.add(x.id)

    products = await product.read_most_recent(
        groups=created_user.groups, fetch_links=False, current_only=True
    )

    for x in products:
        assert x.id not in bad_ids

    # Clean up.
    for i in range(20):
        await product.delete_tree(
            product=await product.read_by_name(
                name=f"product_{i}", version=None, groups=created_user.groups
            ),
            access_groups=created_user.groups,
            storage=storage,
            data=True,
        )

    products = await product.read_most_recent(
        groups=created_user.groups, fetch_links=False, maximum=8
    )


@pytest.mark.asyncio(loop_scope="session")
async def test_walk_history(database, created_full_product, created_user):
    latest = await product.walk_to_current(created_full_product, created_user.groups)

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
        sources=[],
        user_name=created_user.display_name,
        storage=storage,
    )

    await product.add_relationship(
        source=secondary_product,
        destination=created_full_product,
        access_groups=created_user.groups,
        type="child",
    )

    # Grab the original product and check that the created_full_product is a _parent_
    # of the child.
    secondary_product = await product.read_by_id(
        secondary_product.id, groups=created_user.groups
    )
    original_product = await product.read_by_id(
        created_full_product.id, groups=created_user.groups
    )

    assert original_product.name in [c.name for c in secondary_product.child_of]
    assert secondary_product.name in [c.name for c in original_product.parent_of]

    # Remove this relationship.
    await product.remove_relationship(
        source=secondary_product,
        destination=created_full_product,
        access_groups=created_user.groups,
        type="child",
    )

    original_product = await product.read_by_id(
        created_full_product.id, groups=created_user.groups
    )

    assert secondary_product.name not in [c.name for c in original_product.parent_of]

    await product.delete_tree(
        product=await product.read_by_name(
            name=secondary_product.name, version=None, groups=created_user.groups
        ),
        access_groups=created_user.groups,
        storage=storage,
        data=True,
    )


@pytest.mark.asyncio(loop_scope="session")
async def test_product_middle_deletion(database, created_user, storage):
    initial, _ = await product.create(
        name="Middle-out Product",
        description="Trying to remove version 1.0.1",
        metadata={"metadata_type": "simple"},
        sources=[],
        user_name=created_user.display_name,
        storage=storage,
    )

    middle, uploads = await product.update(
        initial,
        created_user.groups,
        None,
        None,
        None,
        None,
        [
            product.PreUploadFile(
                name="to_be_deleted.txt", size=128, checksum="not_important"
            )
        ],
        [],
        [],
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
        None,
        None,
        None,
        None,
        new_sources=[],
        replace_sources=[],
        drop_sources=["to_be_deleted.txt"],
        storage=storage,
        level=versioning.VersionRevision.PATCH,
    )

    with pytest.raises(versioning.VersioningError):
        await product.delete_tree(
            product=middle,
            access_groups=created_user.groups,
            storage=storage,
            data=False,
        )

    await product.delete_one(middle, created_user.groups, storage, data=True)

    # Refresh them from the database to give this the best chance
    initial = await product.read_by_id(initial.id, created_user.groups)
    final = await product.read_by_id(final.id, created_user.groups)

    assert final.current
    assert final.replaces == initial

    # Make sure we deleted the object.
    with pytest.raises(product.ProductNotFound):
        await product.read_by_name(
            initial.name, version="1.0.1", groups=created_user.groups
        )

    # See if we deleted that file we uploaded. As it was not part of v1.0.2 and
    # not part of v1.0.0, it should be gone.
    from hipposerve.service import storage as storage_service

    assert not await storage_service.confirm(file=middle.sources[0], storage=storage)


@pytest.mark.asyncio(loop_scope="session")
async def test_text_name_search(database, created_user, storage):
    # Insert two products with similar names.
    product_A, _ = await product.create(
        name="My Favorite Product A",
        description="A product",
        metadata=None,
        sources=[],
        user_name=created_user.display_name,
        storage=storage,
    )

    product_B, _ = await product.create(
        name="my favorite product b",
        description="A product",
        metadata=None,
        sources=[],
        user_name=created_user.display_name,
        storage=storage,
    )

    # Search for them

    results = await product.search_by_name("my favorite", created_user.groups)

    assert len(results) == 2

    assert {x.id for x in results} == {product_A.id, product_B.id}

    # Clean up.

    await product.delete_one(product_A, created_user.groups, storage=storage, data=True)
    await product.delete_one(product_B, created_user.groups, storage=storage, data=True)

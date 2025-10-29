"""
Tests for the collection service.
"""

import pytest
from beanie import PydanticObjectId

from hipposerve.service import acl, collection


@pytest.mark.asyncio(loop_scope="session")
async def test_create(created_user):
    new_collection = await collection.create(
        name="Test Collection x",
        user=created_user.display_name,
        description="Test description x",
    )
    assert new_collection.name == "Test Collection x"
    assert created_user.display_name in new_collection.writers
    await collection.delete(new_collection.id, created_user.groups)


@pytest.mark.asyncio(loop_scope="session")
async def test_update_access_control(created_collection, created_user):
    existing_readers = set(created_collection.readers)
    existing_writers = set(created_collection.writers)

    updated_collection = await acl.update_access_control(
        created_collection, add_readers={"fake_reader"}, add_writers={"fake_writer"}
    )

    assert set(updated_collection.readers) == (existing_readers | {"fake_reader"})
    assert set(updated_collection.writers) == (existing_writers | {"fake_writer"})

    updated_collection = await acl.update_access_control(
        created_collection,
        remove_readers={"fake_reader"},
        remove_writers={"fake_writer"},
    )

    assert set(updated_collection.readers) == existing_readers
    assert set(updated_collection.writers) == existing_writers

    return


@pytest.mark.asyncio(loop_scope="session")
async def test_update(created_collection, created_user):
    ORIGINAL_NAME = created_collection.name
    ORIGINAL_DESCRIPTION = created_collection.description

    updated = await collection.update(
        id=created_collection.id,
        access_groups=created_user.groups,
        scopes=set(),
        name="New Name",
        description="New description",
    )

    assert updated.name == "New Name"
    assert updated.description == "New description"

    updated = await collection.update(
        id=created_collection.id,
        access_groups=created_user.groups,
        scopes=set(),
        name=ORIGINAL_NAME,
        description=ORIGINAL_DESCRIPTION,
    )


@pytest.mark.asyncio(loop_scope="session")
async def test_search(created_collection, created_user):
    read = (
        await collection.search_by_name(
            name=created_collection.name, groups=created_user.groups, scopes=()
        )
    )[0]

    assert read.name == created_collection.name


@pytest.mark.asyncio(loop_scope="session")
async def test_update_missing(created_user):
    with pytest.raises(collection.CollectionNotFound):
        await collection.update(
            id=PydanticObjectId("7" * 24),
            access_groups=created_user.groups,
            scopes=set(),
            name=None,
            description="New description",
        )


@pytest.mark.asyncio(loop_scope="session")
async def test_child_relationship(created_user):
    # Add then remove a child relationship.
    parent = await collection.create(
        name="Parent", user=created_user.display_name, description="Parent"
    )
    child = await collection.create(
        name="Child", user=created_user.display_name, description="Child"
    )

    await collection.add_child(
        parent_id=parent.id, child_id=child.id, groups=created_user.groups, scopes=set()
    )

    # Grab both from the database.
    parent = await collection.read(
        id=parent.id, groups=created_user.groups, scopes=set()
    )
    child = await collection.read(id=child.id, groups=created_user.groups, scopes=set())

    assert child.id in (x.id for x in parent.child_collections)
    assert parent.id in (x.id for x in child.parent_collections)

    await collection.remove_child(
        parent_id=parent.id,
        child_id=child.id,
        groups=created_user.groups,
        scopes=set(),
    )

    # Grab both from the database.
    parent = await collection.read(
        id=parent.id, groups=created_user.groups, scopes=set()
    )
    child = await collection.read(id=child.id, groups=created_user.groups, scopes=set())

    assert child.id not in (x.id for x in parent.child_collections)
    assert parent.id not in (x.id for x in child.parent_collections)

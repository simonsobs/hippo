"""
Tests for the collection service.
"""

import pytest
from beanie import PydanticObjectId

from hipposerve.service import collection


@pytest.mark.asyncio(loop_scope="session")
async def test_create(created_user):
    new_collection = await collection.create(
        name="Test Collection x",
        user=created_user,
        description="Test description x",
    )
    assert new_collection.name == "Test Collection x"
    assert created_user.name in new_collection.writers
    await collection.delete(new_collection.id, created_user)


@pytest.mark.asyncio(loop_scope="session")
async def test_update(created_collection, created_user):
    updated = await collection.update(
        id=created_collection.id,
        access_user=created_user,
        owner=None,
        description="New description",
    )

    assert updated.name == created_collection.name
    assert updated.description == "New description"


@pytest.mark.asyncio(loop_scope="session")
async def test_search(created_collection, created_user):
    read = (
        await collection.search_by_name(name=created_collection.name, user=created_user)
    )[0]

    assert read.name == created_collection.name


@pytest.mark.asyncio(loop_scope="session")
async def test_update_missing(created_user):
    with pytest.raises(collection.CollectionNotFound):
        await collection.update(
            id=PydanticObjectId("7" * 24),
            access_user=created_user,
            owner=None,
            description="New description",
        )


@pytest.mark.asyncio(loop_scope="session")
async def test_child_relationship(created_user):
    # Add then remove a child relationship.
    parent = await collection.create(
        name="Parent", user=created_user, description="Parent"
    )
    child = await collection.create(
        name="Child", user=created_user, description="Child"
    )

    await collection.add_child(
        parent_id=parent.id, child_id=child.id, user=created_user
    )

    # Grab both from the database.
    parent = await collection.read(id=parent.id, user=created_user)
    child = await collection.read(id=child.id, user=created_user)

    assert child.id in (x.id for x in parent.child_collections)
    assert parent.id in (x.id for x in child.parent_collections)

    await collection.remove_child(
        parent_id=parent.id, child_id=child.id, user=created_user
    )

    # Grab both from the database.
    parent = await collection.read(id=parent.id, user=created_user)
    child = await collection.read(id=child.id, user=created_user)

    assert child.id not in (x.id for x in parent.child_collections)
    assert parent.id not in (x.id for x in child.parent_collections)

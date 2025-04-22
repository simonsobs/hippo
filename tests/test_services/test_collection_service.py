"""
Tests for the collection service.
"""

import pytest
from beanie import PydanticObjectId

from hipposerve.service import collection


@pytest.mark.asyncio(loop_scope="session")
async def test_update(created_collection):
    updated = await collection.update(
        id=created_collection.id,
        description="New description",
    )

    assert updated.name == created_collection.name
    assert updated.description == "New description"


@pytest.mark.asyncio(loop_scope="session")
async def test_search(created_collection):
    read = (await collection.search_by_name(name=created_collection.name))[0]

    assert read.name == created_collection.name


@pytest.mark.asyncio(loop_scope="session")
async def test_update_missing():
    with pytest.raises(collection.CollectionNotFound):
        await collection.update(
            id=PydanticObjectId("7" * 24),
            description="New description",
        )


@pytest.mark.asyncio(loop_scope="session")
async def test_child_relationship():
    # Add then remove a child relationship.
    parent = await collection.create(name="Parent", description="Parent")
    child = await collection.create(name="Child", description="Child")

    await collection.add_child(parent_id=parent.id, child_id=child.id)

    # Grab both from the database.
    parent = await collection.read(id=parent.id)
    child = await collection.read(id=child.id)

    assert child.id in (x.id for x in parent.child_collections)
    assert parent.id in (x.id for x in child.parent_collections)

    await collection.remove_child(parent_id=parent.id, child_id=child.id)

    # Grab both from the database.
    parent = await collection.read(id=parent.id)
    child = await collection.read(id=child.id)

    assert child.id not in (x.id for x in parent.child_collections)
    assert parent.id not in (x.id for x in child.parent_collections)

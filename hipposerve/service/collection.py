"""
Service layer for collections.

Note that adding to and removing from collections is provided as part of
the product service.
"""

from beanie import PydanticObjectId
from beanie.operators import Text

from hipposerve.database import Collection


class CollectionNotFound(Exception):
    pass


async def create(
    name: str,
    description: str,
):
    collection = Collection(
        name=name,
        description=description,
    )

    await collection.insert()

    return collection


async def read(
    id: PydanticObjectId,
):
    collection = await Collection.find_one(Collection.id == id, fetch_links=True)

    if collection is None:
        raise CollectionNotFound

    return collection


async def read_most_recent(
    fetch_links: bool = False, maximum: int = 16
) -> list[Collection]:
    # TODO: Implement updated time for collections.
    return await Collection.find(fetch_links=fetch_links).to_list(maximum)


async def search_by_name(name: str, fetch_links: bool = True) -> list[Collection]:
    """
    Search for Collections by name using the text index.
    """

    results = (
        await Collection.find(Text(name), fetch_links=fetch_links)  # noqa: E712
        .sort([("score", {"$meta": "textScore"})])
        .to_list()
    )

    return results


async def update(
    id: PydanticObjectId,
    description: str | None,
):
    collection = await read(id=id)

    if description is not None:
        await collection.set({Collection.description: description})

    return collection


async def add_child(
    parent_id: PydanticObjectId,
    child_id: PydanticObjectId,
) -> Collection:
    parent = await read(id=parent_id)
    child = await read(id=child_id)

    parent.child_collections.append(child)
    await parent.save()

    return parent


async def remove_child(
    parent_id: PydanticObjectId,
    child_id: PydanticObjectId,
) -> Collection:
    parent = await read(id=parent_id)

    await parent.set(
        {
            Collection.child_collections: [
                x for x in parent.child_collections if x.id != child_id
            ]
        }
    )

    return parent


async def delete(
    id: PydanticObjectId,
):
    collection = await read(id=id)

    await collection.delete()

    return

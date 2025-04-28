"""
Service layer for collections.

Note that adding to and removing from collections is provided as part of
the product service.
"""

from beanie import PydanticObjectId
from beanie.operators import Text

from hipposerve.database import Collection, User


class CollectionNotFound(Exception):
    pass


async def create(
    name: str,
    user: User,
    description: str,
    collection_readers: list[str] | None = None,
    collection_writers: list[str] | None = None,
):
    collection = Collection(
        name=name,
        owner=user,
        description=description,
    )
    collection_readers = collection_readers or []
    collection_writers = collection_writers or []

    if collection_readers is not None:
        collection.readers.extend(collection_readers)
    if user.name not in collection.writers:
        collection_writers.append(user.name)
    collection.writers.extend(collection_writers)
    await collection.insert()

    return collection


async def read(
    id: PydanticObjectId,
    user: User,
):
    collection = await Collection.find_one(Collection.id == id, fetch_links=True)

    if collection is None:
        raise CollectionNotFound

    return collection


async def read_most_recent(
    user: User,
    fetch_links: bool = False,
    maximum: int = 16,
) -> list[Collection]:
    # TODO: Implement updated time for collections.
    return await Collection.find(fetch_links=fetch_links).to_list(maximum)


async def search_by_name(
    name: str, user: User, fetch_links: bool = True
) -> list[Collection]:
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
    access_user: User,
    owner: User | None,
    description: str | None,
    add_readers: list[str] | None = None,
    remove_readers: list[str] | None = None,
    add_writers: list[str] | None = None,
    remove_writers: list[str] | None = None,
):
    collection = await read(id=id, user=access_user)

    readers = collection.readers.copy()
    writers = collection.writers.copy()
    # We don't actually 'update' the database; we actually create a new
    # product and link it in.
    if owner is not None:
        await collection.set({Collection.owner: owner})
        writers.append(owner.name)
    if add_readers is not None:
        readers.extend(add_readers)
        await collection.set({Collection.readers: readers})
    if remove_readers is not None:
        readers = [x for x in readers if x not in remove_readers]
        await collection.set({Collection.readers: readers})
    if add_writers is not None:
        writers.extend(add_writers)
        await collection.set({Collection.writers: writers})
    if remove_writers is not None:
        writers = [x for x in writers if x not in remove_writers]
        await collection.set({Collection.writers: writers})
    if description is not None:
        await collection.set({Collection.description: description})

    return collection


async def add_child(
    parent_id: PydanticObjectId,
    child_id: PydanticObjectId,
    user: User,
) -> Collection:
    parent = await read(id=parent_id, user=user)
    child = await read(id=child_id, user=user)

    parent.child_collections.append(child)
    await parent.save()

    return parent


async def remove_child(
    parent_id: PydanticObjectId,
    child_id: PydanticObjectId,
    user: User,
) -> Collection:
    parent = await read(id=parent_id, user=user)

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
    user: User,
):
    collection = await read(id=id, user=user)

    await collection.delete()

    return

"""
Service layer for collections.

Note that adding to and removing from collections is provided as part of
the product service.
"""

from beanie import PydanticObjectId
from beanie.operators import Text
from fastapi import HTTPException

from hipposerve.database import Collection, User
from hipposerve.service.auth import (
    check_collection_read_access,
    check_collection_write_access,
    check_product_read_access,
)


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
    await check_collection_read_access(user, collection)
    if collection.products:
        collection_list = await collection_product_filter(user, [collection])
        collection = collection_list[0]
    return collection


async def read_most_recent(
    user: User,
    fetch_links: bool = False,
    maximum: int = 16,
) -> list[Collection]:
    # TODO: Implement updated time for collections.
    group_names = [group.name for group in user.groups]
    access_query = {
        "$or": [{"readers": {"$in": group_names}}, {"writers": {"$in": group_names}}]
    }
    collection_list = await Collection.find(
        access_query, fetch_links=fetch_links
    ).to_list(maximum)
    filtered_collection_list = await collection_product_filter(user, collection_list)
    return filtered_collection_list


async def search_by_name(
    name: str, user: User, fetch_links: bool = True
) -> list[Collection]:
    """
    Search for Collections by name using the text index.
    """
    group_names = [group.name for group in user.groups]
    access_query = {
        "$or": [{"readers": {"$in": group_names}}, {"writers": {"$in": group_names}}]
    }
    results = (
        await Collection.find(access_query, Text(name), fetch_links=fetch_links)  # noqa: E712
        .sort([("score", {"$meta": "textScore"})])
        .to_list()
    )

    filtered_collection_list = await collection_product_filter(user, results)
    return filtered_collection_list


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
    await check_collection_write_access(access_user, collection)
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
    await check_collection_write_access(user, parent)
    parent.child_collections.append(child)
    await parent.save()

    return parent


async def remove_child(
    parent_id: PydanticObjectId,
    child_id: PydanticObjectId,
    user: User,
) -> Collection:
    parent = await read(id=parent_id, user=user)
    await check_collection_write_access(user, parent)
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
    await check_collection_write_access(user, collection)
    await collection.delete()

    return


async def collection_product_filter(
    user: User,
    collection_list: list[Collection],
) -> list[Collection]:
    filtered_collection_list = []
    for collection in collection_list:
        if collection.products:
            product_list = []
            for product in collection.products:
                try:
                    await check_product_read_access(user, product)
                    product_list.append(product)
                except HTTPException:
                    continue
            collection.products = product_list
        filtered_collection_list.append(collection)
    return filtered_collection_list

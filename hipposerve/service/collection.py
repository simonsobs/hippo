"""
Service layer for collections.

Note that adding to and removing from collections is provided as part of
the product service.
"""

from beanie import PydanticObjectId
from beanie.operators import Text
from fastapi import HTTPException

from hipposerve.database import Collection
from hipposerve.service.auth import (
    check_collection_access,
    check_product_access,
)


class CollectionNotFound(Exception):
    pass


async def create(
    name: str,
    user: str,
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
    if user not in collection.writers:
        collection_writers.append(user)
    collection.writers.extend(collection_writers)
    await collection.insert()

    return collection


async def read(
    id: PydanticObjectId,
    groups: list[str],
):
    collection = await Collection.find_one(Collection.id == id, fetch_links=True)

    if collection is None:
        raise CollectionNotFound
    await check_collection_access(groups, collection.readers + collection.writers)
    if collection.products:
        collection_list = await collection_product_filter(groups, [collection])
        collection = collection_list[0]
    return collection


async def read_most_recent(
    groups: list[str],
    fetch_links: bool = False,
    maximum: int = 16,
) -> list[Collection]:
    # TODO: Implement updated time for collections.
    access_query = {"$or": [{"readers": {"$in": groups}}, {"writers": {"$in": groups}}]}
    collection_list = await Collection.find(
        access_query, fetch_links=fetch_links
    ).to_list(maximum)
    filtered_collection_list = await collection_product_filter(groups, collection_list)
    return filtered_collection_list


async def search_by_name(
    name: str, groups: list[str], fetch_links: bool = True
) -> list[Collection]:
    """
    Search for Collections by name using the text index.
    """

    access_query = {"$or": [{"readers": {"$in": groups}}, {"writers": {"$in": groups}}]}
    results = (
        await Collection.find(access_query, Text(name), fetch_links=fetch_links)  # noqa: E712
        .sort([("score", {"$meta": "textScore"})])
        .to_list()
    )

    filtered_collection_list = await collection_product_filter(groups, results)
    return filtered_collection_list


async def update(
    id: PydanticObjectId,
    access_groups: list[str],
    owner: str | None,
    description: str | None,
    add_readers: list[str] | None = None,
    remove_readers: list[str] | None = None,
    add_writers: list[str] | None = None,
    remove_writers: list[str] | None = None,
):
    collection = await read(id=id, groups=access_groups)
    await check_collection_access(access_groups, collection.writers)
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
    groups: list[str],
) -> Collection:
    parent = await read(id=parent_id, groups=groups)
    child = await read(id=child_id, groups=groups)
    await check_collection_access(groups, parent.writers)
    parent.child_collections.append(child)
    await parent.save()

    return parent


async def remove_child(
    parent_id: PydanticObjectId,
    child_id: PydanticObjectId,
    groups: list[str],
) -> Collection:
    parent = await read(id=parent_id, groups=groups)
    await check_collection_access(groups, parent.writers)
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
    groups: list[str],
):
    collection = await read(id=id, groups=groups)
    await check_collection_access(groups, collection.readers + collection.writers)
    await collection.delete()

    return


async def collection_product_filter(
    groups: list[str],
    collection_list: list[Collection],
) -> list[Collection]:
    filtered_collection_list = []
    for collection in collection_list:
        if collection.products:
            product_list = []
            for product in collection.products:
                try:
                    await check_product_access(
                        groups, product.readers + product.writers
                    )
                    product_list.append(product)
                except HTTPException:
                    continue
            collection.products = product_list
        filtered_collection_list.append(collection)
    return filtered_collection_list

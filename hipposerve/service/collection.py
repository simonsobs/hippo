"""
Service layer for collections.

Note that adding to and removing from collections is provided as part of
the product service.
"""

import re

from beanie import PydanticObjectId
from beanie.operators import Text
from fastapi import HTTPException

from hipposerve.database import Collection
from hipposerve.service.acl import check_user_access


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
        readers=set(collection_readers or []) | {user},
        writers=set(collection_writers or []) | {user},
    )

    await collection.insert()

    return collection


async def read(
    id: PydanticObjectId,
    groups: list[str],
):
    collection = await Collection.find_one(Collection.id == id, fetch_links=True)

    if collection is None:
        raise CollectionNotFound
    assert check_user_access(groups, collection.readers + collection.writers)
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


async def search_by_owner(
    owner: str,
    groups: list[str],
    fetch_links: bool = True,
) -> list[Collection]:
    """
    Search for Collections by owner; owner search is case insensitive
    but must otherwise be an exact match
    """

    owner_regex = {"$regex": f"^{re.escape(owner)}$", "$options": "i"}

    access_query = {"$or": [{"readers": {"$in": groups}}, {"writers": {"$in": groups}}]}
    results = await Collection.find(
        {**access_query, "owner": owner_regex}, fetch_links=fetch_links
    ).to_list()

    filtered_collection_list = await collection_product_filter(groups, results)
    return filtered_collection_list


async def update(
    id: PydanticObjectId,
    access_groups: list[str],
    name: str | None,
    description: str | None,
):
    collection = await read(id=id, groups=access_groups)
    assert check_user_access(access_groups, collection.writers)

    if name:
        collection.name = name

    if description:
        collection.description = description

    await collection.save()

    return collection


async def add_child(
    parent_id: PydanticObjectId,
    child_id: PydanticObjectId,
    groups: list[str],
) -> Collection:
    parent = await read(id=parent_id, groups=groups)
    child = await read(id=child_id, groups=groups)
    assert check_user_access(groups, parent.writers)
    parent.child_collections.append(child)
    await parent.save()

    return parent


async def remove_child(
    parent_id: PydanticObjectId,
    child_id: PydanticObjectId,
    groups: list[str],
) -> Collection:
    parent = await read(id=parent_id, groups=groups)
    assert check_user_access(groups, parent.writers)
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
    assert check_user_access(groups, collection.readers + collection.writers)
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
                    assert check_user_access(groups, product.readers + product.writers)
                    product_list.append(product)
                except HTTPException:
                    continue
            collection.products = product_list
        filtered_collection_list.append(collection)
    return filtered_collection_list

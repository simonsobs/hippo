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

LINK_POLICY = {
    "fetch_links": True,
    "nesting_depth": 1,
}


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


async def read(id: PydanticObjectId, groups: list[str], scopes: set[str]):
    collection = await Collection.find_one(Collection.id == id, **LINK_POLICY)

    if collection is None:
        raise CollectionNotFound
    assert check_user_access(
        groups, collection.readers + collection.writers, scopes=scopes
    )
    if collection.products:
        collection_list = await collection_product_filter(groups, scopes, [collection])
        collection = collection_list[0]
    return collection


async def read_most_recent(
    groups: list[str],
    scopes: set[str],
    maximum: int = 16,
) -> list[Collection]:
    # TODO: Implement updated time for collections.
    if "hippo:admin" in scopes:
        access_query = {}
    else:
        access_query = {
            "$or": [{"readers": {"$in": groups}}, {"writers": {"$in": groups}}]
        }

    collection_list = await Collection.find(access_query, **LINK_POLICY).to_list(
        maximum
    )

    filtered_collection_list = await collection_product_filter(
        groups, scopes, collection_list
    )

    return filtered_collection_list


async def search_by_name(
    name: str, groups: list[str], scopes: set[str]
) -> list[Collection]:
    """
    Search for Collections by name using the text index.
    """

    if "hippo:admin" in scopes:
        access_query = {}
    else:
        access_query = {
            "$or": [{"readers": {"$in": groups}}, {"writers": {"$in": groups}}]
        }

    results = (
        await Collection.find(access_query, Text(name), **LINK_POLICY)  # noqa: E712
        .sort([("score", {"$meta": "textScore"})])
        .to_list()
    )

    filtered_collection_list = await collection_product_filter(groups, scopes, results)

    return filtered_collection_list


async def search_by_owner(
    owner: str, groups: list[str], scopes: set[str]
) -> list[Collection]:
    """
    Search for Collections by owner; owner search is case insensitive
    but must otherwise be an exact match
    """

    owner_regex = {"$regex": f"^{re.escape(owner)}$", "$options": "i"}

    if "hippo:admin" in scopes:
        access_query = {}
    else:
        access_query = {
            "$or": [{"readers": {"$in": groups}}, {"writers": {"$in": groups}}]
        }

    results = await Collection.find(
        {**access_query, "owner": owner_regex}, **LINK_POLICY
    ).to_list()

    filtered_collection_list = await collection_product_filter(groups, scopes, results)

    return filtered_collection_list


async def diff(
    id: PydanticObjectId,
    access_groups: list[str],
    scopes: set[str],
    name: str | None = None,
    description: str | None = None,
):
    """
    Diff a collection against the current version.
    """
    collection = await read(id=id, groups=access_groups, scopes=scopes)

    diff_dict = {}

    if name and name != collection.name:
        diff_dict["name"] = [collection.name, name]

    if description and description != collection.description:
        diff_dict["description"] = [collection.description, description]

    return diff_dict


async def update(
    id: PydanticObjectId,
    access_groups: list[str],
    scopes: set[str],
    name: str | None,
    description: str | None,
):
    collection = await read(id=id, groups=access_groups, scopes=scopes)

    assert check_user_access(access_groups, collection.writers, scopes=scopes)

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
    scopes: set[str],
) -> Collection:
    parent = await read(id=parent_id, groups=groups, scopes=scopes)
    child = await read(id=child_id, groups=groups, scopes=scopes)
    assert check_user_access(groups, parent.writers, scopes=scopes)
    parent.child_collections.append(child)
    await parent.save()

    return parent


async def remove_child(
    parent_id: PydanticObjectId,
    child_id: PydanticObjectId,
    groups: list[str],
    scopes: set[str],
) -> Collection:
    parent = await read(id=parent_id, groups=groups, scopes=scopes)
    assert check_user_access(groups, parent.writers, scopes=scopes)
    await parent.set(
        {
            Collection.child_collections: [
                x for x in parent.child_collections if x.id != child_id
            ]
        }
    )

    return parent


async def delete(id: PydanticObjectId, groups: list[str], scopes: set[str]):
    collection = await read(id=id, groups=groups, scopes=scopes)
    assert check_user_access(
        groups, collection.readers + collection.writers, scopes=scopes
    )
    await collection.delete()

    return


async def collection_product_filter(
    groups: list[str],
    scopes: set[str],
    collection_list: list[Collection],
) -> list[Collection]:
    filtered_collection_list = []
    for collection in collection_list:
        if collection.products:
            product_list = []
            for product in collection.products:
                try:
                    assert check_user_access(
                        groups, product.readers + product.writers, scopes=scopes
                    )
                    product_list.append(product)
                except HTTPException:
                    continue
            collection.products = product_list
        filtered_collection_list.append(collection)
    return filtered_collection_list

"""
API endpoints for relationships between products and collections.
"""

from beanie import PydanticObjectId
from fastapi import APIRouter, HTTPException, Request, status
from loguru import logger

from hipposerve.api.models.relationships import (
    CreateCollectionRequest,
    ReadCollectionCollectionResponse,
    ReadCollectionProductResponse,
    ReadCollectionResponse,
)
from hipposerve.database import Privilege
from hipposerve.service import collection, product
from hipposerve.service.auth import UserDependency, check_group_for_privilege

relationship_router = APIRouter(prefix="/relationships")


@relationship_router.put("/collection/{name}")
async def create_collection(
    name: str,
    model: CreateCollectionRequest,
    calling_user: UserDependency,
) -> PydanticObjectId:
    """
    Create a new collection with {name}.
    """

    logger.info("Request to create collection: {} from {}", name, calling_user.name)

    await check_group_for_privilege(calling_user, Privilege.CREATE_COLLECTION)

    # TODO: What to do if collection exists?
    # TODO: Collections should have a 'manager' who can change their properties.
    coll = await collection.create(name=name, description=model.description)

    logger.info("Collection {} ({}) created for {}", coll.id, name, calling_user.name)

    return coll.id


@relationship_router.get("/collection/{id}")
async def read_collection(
    id: PydanticObjectId,
    request: Request,
    calling_user: UserDependency,
) -> ReadCollectionResponse:
    """
    Read a collection's details.
    """

    logger.info("Request to read collection: {} from {}", id, calling_user.name)

    await check_group_for_privilege(calling_user, Privilege.READ_COLLECTION)

    try:
        item = await collection.read(id=id)
    except collection.CollectionNotFound:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Collection not found."
        )

    return ReadCollectionResponse(
        id=item.id,
        name=item.name,
        description=item.description,
        products=[
            ReadCollectionProductResponse(
                id=x.id,
                name=x.name,
                version=x.version,
                description=x.description,
                owner=x.owner.name,
                uploaded=x.uploaded,
                metadata=x.metadata,
            )
            for x in item.products
        ],
        child_collections=[
            ReadCollectionCollectionResponse(
                id=x.id,
                name=x.name,
                description=x.description,
            )
            for x in item.child_collections
        ],
        parent_collections=[
            ReadCollectionCollectionResponse(
                id=x.id,
                name=x.name,
                description=x.description,
            )
            for x in item.parent_collections
        ],
    )


@relationship_router.get("/collection/search/{name}")
async def search_collection(
    name: str,
    request: Request,
    calling_user: UserDependency,
) -> list[ReadCollectionResponse]:
    """
    Search for collections by name. Products and sub-collections are not
    returned; these should be fetched separately through the read_collection
    endpoint.
    """

    logger.info("Request to search for collection: {} from {}", name, calling_user.name)

    await check_group_for_privilege(calling_user, Privilege.READ_COLLECTION)

    results = await collection.search_by_name(name=name)

    logger.info(
        "Found {} collections for {} from {}", len(results), name, calling_user.name
    )

    return [
        ReadCollectionResponse(
            id=item.id,
            name=item.name,
            description=item.description,
            products=None,
        )
        for item in results
    ]


@relationship_router.put("/collection/{collection_id}/{product_id}")
async def add_product_to_collection(
    collection_id: PydanticObjectId,
    product_id: PydanticObjectId,
    calling_user: UserDependency,
) -> None:
    """
    Add a product to a collection.
    """

    logger.info(
        "Request to add product {} to collection {} from {}",
        product_id,
        collection_id,
        calling_user.name,
    )

    await check_group_for_privilege(calling_user, Privilege.UPDATE_COLLECTION)

    try:
        coll = await collection.read(id=collection_id)
    except collection.CollectionNotFound:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Collection not found."
        )

    try:
        item = await product.read_by_id(id=product_id, user=calling_user)
        await product.add_collection(
            product=item, access_user=calling_user, collection=coll
        )
        logger.info("Successfully added {} to collection {}", item.name, coll.name)
    except product.ProductNotFound:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Product not found."
        )


@relationship_router.delete("/collection/{collection_id}/{product_id}")
async def remove_product_from_collection(
    collection_id: PydanticObjectId,
    product_id: PydanticObjectId,
    calling_user: UserDependency,
) -> None:
    """
    Remove a product from a collection.
    """

    logger.info(
        "Request to remove product {} from collection {} from {}",
        product_id,
        collection_id,
        calling_user.name,
    )

    await check_group_for_privilege(calling_user, Privilege.UPDATE_COLLECTION)

    try:
        coll = await collection.read(id=collection_id)
    except collection.CollectionNotFound:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Collection not found."
        )

    try:
        item = await product.read_by_id(id=product_id, user=calling_user)
        await product.remove_collection(
            product=item, access_user=calling_user, collection=coll
        )
        logger.info("Successfully removed {} from collection {}", item.name, coll.name)
    except product.ProductNotFound:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Product not found."
        )


@relationship_router.delete("/collection/{id}")
async def delete_collection(
    id: PydanticObjectId,
    calling_user: UserDependency,
) -> None:
    """
    Delete a collection.
    """

    logger.info("Request to delete collection: {} from {}", id, calling_user.name)

    await check_group_for_privilege(calling_user, Privilege.DELETE_COLLECTION)

    try:
        # Check if we have a parent; if we do, we need to remove its link to us.
        coll = await collection.read(id=id)

        if coll.parent_collections:
            for parent in coll.parent_collections:
                await collection.remove_child(parent_id=parent.id, child_id=id)

        await collection.delete(id=id)
        logger.info("Successfully deleted collection {} from {}", id, calling_user.name)
    except collection.CollectionNotFound:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Collection not found."
        )


@relationship_router.put("/product/{parent_id}/child_of/{child_id}")
async def add_child_product(
    parent_id: PydanticObjectId,
    child_id: PydanticObjectId,
    calling_user: UserDependency,
) -> None:
    """
    Add a child product to a parent product.
    """

    logger.info(
        "Request to add product {} as child of {} from {}",
        child_id,
        parent_id,
        calling_user.name,
    )

    await check_group_for_privilege(calling_user, Privilege.CREATE_RELATIONSHIP)

    try:
        source = await product.read_by_id(id=parent_id, user=calling_user)
        destination = await product.read_by_id(id=child_id, user=calling_user)
        await product.add_relationship(
            source=source,
            destination=destination,
            access_user=calling_user,
            type="child",
        )
        logger.info(
            "Successfully added {} as child of {}", destination.name, source.name
        )
    except product.ProductNotFound:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Product not found."
        )


@relationship_router.delete("/product/{parent_id}/child_of/{child_id}")
async def remove_child_product(
    parent_id: PydanticObjectId,
    child_id: PydanticObjectId,
    calling_user: UserDependency,
) -> None:
    """
    Remove a parent-child relationship between two products.
    """

    logger.info(
        "Request to remove product {} as child of {} from {}",
        child_id,
        parent_id,
        calling_user.name,
    )

    await check_group_for_privilege(calling_user, Privilege.DELETE_RELATIONSHIP)

    try:
        source = await product.read_by_id(id=parent_id, user=calling_user)
        destination = await product.read_by_id(id=child_id, user=calling_user)
        await product.remove_relationship(
            source=source,
            destination=destination,
            access_user=calling_user,
            type="child",
        )
        logger.info(
            "Successfully removed {} as child of {}", destination.name, source.name
        )
    except product.ProductNotFound:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Product not found."
        )


@relationship_router.put("/collection/{parent_id}/child_of/{child_id}")
async def add_child_collection(
    parent_id: PydanticObjectId,
    child_id: PydanticObjectId,
    calling_user: UserDependency,
) -> None:
    """
    Add a child collection to a parent collection.
    """

    logger.info(
        "Request to add collection {} as child of {} from {}",
        child_id,
        parent_id,
        calling_user.name,
    )

    await check_group_for_privilege(calling_user, Privilege.CREATE_RELATIONSHIP)

    try:
        await collection.add_child(parent_id=parent_id, child_id=child_id)
        logger.info("Successfully added {} as child of {}", child_id, parent_id)
    except collection.CollectionNotFound:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Collection not found."
        )


@relationship_router.delete("/collection/{parent_id}/child_of/{child_id}")
async def remove_child_collection(
    parent_id: PydanticObjectId,
    child_id: PydanticObjectId,
    calling_user: UserDependency,
) -> None:
    """
    Remove a parent-child relationship between two collections.
    """

    logger.info(
        "Request to remove collection {} as child of {} from {}",
        child_id,
        parent_id,
        calling_user.name,
    )

    await check_group_for_privilege(calling_user, Privilege.DELETE_RELATIONSHIP)

    try:
        await collection.remove_child(parent_id=parent_id, child_id=child_id)
        logger.info("Successfully removed {} as child of {}", child_id, parent_id)
    except collection.CollectionNotFound:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Collection not found."
        )

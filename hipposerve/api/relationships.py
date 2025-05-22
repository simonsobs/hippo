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
    UpdateCollectionRequest,
)
from hipposerve.service import collection, product
from hipposerve.service.auth import requires

relationship_router = APIRouter(prefix="/relationships")


@relationship_router.put("/collection/{name}")
@requires(["hippo:admin", "hippo:write"])
async def create_collection(
    name: str,
    model: CreateCollectionRequest,
    request: Request,
) -> PydanticObjectId:
    """
    Create a new collection with {name}.
    """

    logger.info(
        "Request to create collection: {} from {}", name, request.user.display_name
    )

    # TODO: What to do if collection exists?
    # TODO: Collections should have a 'manager' who can change their properties.
    coll = await collection.create(
        name=name,
        user=request.user.display_name,
        description=model.description,
        collection_readers=model.readers,
        collection_writers=model.writers,
    )

    logger.info(
        "Collection {} ({}) created for {}", coll.id, name, request.user.display_name
    )

    return coll.id


@relationship_router.get("/collection/{id}")
@requires(["hippo:admin", "hippo:write", "hippo:read"])
async def read_collection(
    id: PydanticObjectId,
    request: Request,
) -> ReadCollectionResponse:
    """
    Read a collection's details.
    """

    logger.info("Request to read collection: {} from {}", id, request.user.display_name)

    try:
        item = await collection.read(id=id, groups=request.user.groups)
    except collection.CollectionNotFound:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Collection not found."
        )

    return ReadCollectionResponse(
        id=item.id,
        name=item.name,
        description=item.description,
        owner=item.owner,
        readers=item.readers,
        writers=item.writers,
        products=[
            ReadCollectionProductResponse(
                id=x.id,
                name=x.name,
                version=x.version,
                description=x.description,
                owner=x.owner,
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
                owner=x.owner,
                readers=x.readers,
                writers=x.writers,
            )
            for x in item.child_collections
        ],
        parent_collections=[
            ReadCollectionCollectionResponse(
                id=x.id,
                name=x.name,
                description=x.description,
                owner=x.owner,
                readers=x.readers,
                writers=x.writers,
            )
            for x in item.parent_collections
        ],
    )


@relationship_router.get("/collection/search/{name}")
@requires(["hippo:admin", "hippo:write", "hippo:read"])
async def search_collection(
    name: str,
    request: Request,
) -> list[ReadCollectionResponse]:
    """
    Search for collections by name. Products and sub-collections are not
    returned; these should be fetched separately through the read_collection
    endpoint.
    """

    logger.info(
        "Request to search for collection: {} from {}", name, request.user.display_name
    )

    results = await collection.search_by_name(name=name, groups=request.user.groups)

    logger.info(
        "Found {} collections for {} from {}",
        len(results),
        name,
        request.user.display_name,
    )

    return [
        ReadCollectionResponse(
            id=item.id,
            name=item.name,
            description=item.description,
            owner=item.owner,
            readers=item.readers,
            writers=item.writers,
            products=None,
        )
        for item in results
    ]


@relationship_router.put("/collection/{collection_id}/{product_id}")
@requires(["hippo:admin", "hippo:write"])
async def add_product_to_collection(
    collection_id: PydanticObjectId,
    product_id: PydanticObjectId,
    request: Request,
) -> None:
    """
    Add a product to a collection.
    """

    logger.info(
        "Request to add product {} to collection {} from {}",
        product_id,
        collection_id,
        request.user.display_name,
    )

    try:
        coll = await collection.read(id=collection_id, groups=request.user.groups)
    except collection.CollectionNotFound:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Collection not found."
        )

    try:
        item = await product.read_by_id(id=product_id, groups=request.user.groups)
        await product.add_collection(
            product=item, access_groups=request.user.groups, collection=coll
        )
        logger.info("Successfully added {} to collection {}", item.name, coll.name)
    except product.ProductNotFound:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Product not found."
        )


@relationship_router.delete("/collection/{collection_id}/{product_id}")
@requires(["hippo:admin", "hippo:write"])
async def remove_product_from_collection(
    collection_id: PydanticObjectId,
    product_id: PydanticObjectId,
    request: Request,
) -> None:
    """
    Remove a product from a collection.
    """

    logger.info(
        "Request to remove product {} from collection {} from {}",
        product_id,
        collection_id,
        request.user.display_name,
    )

    try:
        coll = await collection.read(id=collection_id, groups=request.user.groups)
    except collection.CollectionNotFound:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Collection not found."
        )

    try:
        item = await product.read_by_id(id=product_id, groups=request.user.groups)
        await product.remove_collection(
            product=item, access_groups=request.user.groups, collection=coll
        )
        logger.info("Successfully removed {} from collection {}", item.name, coll.name)
    except product.ProductNotFound:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Product not found."
        )


@relationship_router.post("/collection/{id}")
@requires(["hippo:admin", "hippo:write"])
async def update_collection(
    id: PydanticObjectId,
    model: UpdateCollectionRequest,
    request: Request,
) -> PydanticObjectId:
    logger.info(
        "Request to update collection: {} from {}", id, request.user.display_name
    )
    coll = await collection.update(
        id=id,
        access_groups=request.user.groups,
        owner=model.owner,
        description=model.description,
        add_readers=model.add_readers,
        remove_readers=model.remove_readers,
        add_writers=model.add_writers,
        remove_writers=model.remove_writers,
    )
    logger.info(
        "Successfully updated collection {} from {}", id, request.user.display_name
    )
    return coll.id


@relationship_router.delete("/collection/{id}")
@requires(["hippo:admin", "hippo:write"])
async def delete_collection(
    id: PydanticObjectId,
    request: Request,
) -> None:
    """
    Delete a collection.
    """

    logger.info(
        "Request to delete collection: {} from {}", id, request.user.display_name
    )

    try:
        # Check if we have a parent; if we do, we need to remove its link to us.
        coll = await collection.read(id=id, groups=request.user.groups)

        if coll.parent_collections:
            for parent in coll.parent_collections:
                await collection.remove_child(
                    parent_id=parent.id, child_id=id, groups=request.user.groups
                )

        await collection.delete(id=id, groups=request.user.groups)
        logger.info(
            "Successfully deleted collection {} from {}", id, request.user.display_name
        )
    except collection.CollectionNotFound:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Collection not found."
        )


@relationship_router.put("/product/{parent_id}/child_of/{child_id}")
@requires(["hippo:admin", "hippo:write"])
async def add_child_product(
    parent_id: PydanticObjectId,
    child_id: PydanticObjectId,
    request: Request,
) -> None:
    """
    Add a child product to a parent product.
    """

    logger.info(
        "Request to add product {} as child of {} from {}",
        child_id,
        parent_id,
        request.user.display_name,
    )

    try:
        source = await product.read_by_id(id=parent_id, groups=request.user.groups)
        destination = await product.read_by_id(id=child_id, groups=request.user.groups)
        await product.add_relationship(
            source=source,
            destination=destination,
            access_groups=request.user.groups,
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
@requires(["hippo:admin", "hippo:write"])
async def remove_child_product(
    parent_id: PydanticObjectId,
    child_id: PydanticObjectId,
    request: Request,
) -> None:
    """
    Remove a parent-child relationship between two products.
    """

    logger.info(
        "Request to remove product {} as child of {} from {}",
        child_id,
        parent_id,
        request.user.display_name,
    )

    try:
        source = await product.read_by_id(id=parent_id, groups=request.user.groups)
        destination = await product.read_by_id(id=child_id, groups=request.user.groups)
        await product.remove_relationship(
            source=source,
            destination=destination,
            access_groups=request.user.groups,
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
@requires(["hippo:admin", "hippo:write"])
async def add_child_collection(
    parent_id: PydanticObjectId,
    child_id: PydanticObjectId,
    request: Request,
) -> None:
    """
    Add a child collection to a parent collection.
    """

    logger.info(
        "Request to add collection {} as child of {} from {}",
        child_id,
        parent_id,
        request.user.display_name,
    )

    try:
        await collection.add_child(
            parent_id=parent_id, child_id=child_id, groups=request.user.groups
        )
        logger.info("Successfully added {} as child of {}", child_id, parent_id)
    except collection.CollectionNotFound:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Collection not found."
        )


@relationship_router.delete("/collection/{parent_id}/child_of/{child_id}")
@requires(["hippo:admin", "hippo:write"])
async def remove_child_collection(
    parent_id: PydanticObjectId,
    child_id: PydanticObjectId,
    request: Request,
) -> None:
    """
    Remove a parent-child relationship between two collections.
    """

    logger.info(
        "Request to remove collection {} as child of {} from {}",
        child_id,
        parent_id,
        request.user.display_name,
    )

    try:
        await collection.remove_child(
            parent_id=parent_id, child_id=child_id, groups=request.user.groups
        )
        logger.info("Successfully removed {} as child of {}", child_id, parent_id)
    except collection.CollectionNotFound:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Collection not found."
        )

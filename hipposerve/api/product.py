"""
Routes for the product service.
"""

from beanie import PydanticObjectId
from fastapi import APIRouter, HTTPException, Request, status
from loguru import logger

from hipposerve.api.models.product import (
    CompleteProductRequest,
    CreateProductRequest,
    CreateProductResponse,
    ReadFilesResponse,
    ReadProductResponse,
    UpdateProductRequest,
    UpdateProductResponse,
)
from hipposerve.database import ProductMetadata
from hipposerve.service import product, users
from hipposerve.service.auth import requires

product_router = APIRouter(prefix="/product")

DEFAULT_USER_USER_NAME = "default_user"


@product_router.put("/new")
@requires(["hippo:admin", "hippo:write"])
async def create_product(
    request: Request,
    model: CreateProductRequest,
) -> CreateProductResponse:
    """
    Create a new product, returning the pre-signed URLs for the sources.
    """

    logger.info(
        "Create product request: {} from {}", model.name, request.user.display_name
    )

    if await product.exists(name=model.name):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="Product already exists"
        )

    item, presigned = await product.create(
        name=model.name,
        description=model.description,
        metadata=model.metadata,
        sources=model.sources,
        user_name=request.user.display_name,
        storage=request.app.storage,
        product_readers=model.product_readers,
        product_writers=model.product_writers,
        mutlipart_size=model.multipart_batch_size,
    )

    logger.info(
        "Successfully created {} pre-signed URL(s) for product upload {} (id: {}) from {}",
        sum(len(x) for x in presigned.values()),
        model.name,
        item.id,
        request.user.display_name,
    )

    return CreateProductResponse(id=item.id, upload_urls=presigned)


@product_router.post("/{id}/complete")
@requires(["hippo:admin", "hippo:write"])
async def complete_product(
    id: PydanticObjectId,
    request: Request,
    model: CompleteProductRequest,
) -> None:
    """
    Complete a product's upload. Must be called before the sources are available.
    """
    logger.info(
        "Complete product request for {} from {}", id, request.user.display_name
    )

    try:
        item = await product.read_by_id(id=id, groups=request.user.groups)
    except product.ProductNotFound:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Product not found"
        )

    success = await product.complete(
        product=item,
        storage=request.app.storage,
        headers=model.headers,
        sizes=model.sizes,
    )

    if not success:
        raise HTTPException(
            status_code=status.HTTP_424_FAILED_DEPENDENCY,
            detail="Not all sources were present.",
        )

    logger.info("Successfully completed product {} (id: {})", item.name, item.id)


@product_router.get("/{id}")
@requires(["hippo:admin", "hippo:read"])
async def read_product(
    id: PydanticObjectId,
    request: Request,
) -> ReadProductResponse:
    """
    Read a single product's metadata.
    """

    logger.info("Read product request for {} from {}", id, request.user.display_name)

    try:
        item = (await product.read_by_id(id, request.user.groups)).to_metadata()

        response = ReadProductResponse(
            current_present=item.current,
            current=item.version if item.current else None,
            requested=item.version,
            versions={item.version: item},
        )

        logger.info(
            "Successfully read product {} (id: {}) requested by {}",
            item.name,
            item.id,
            request.user.display_name,
        )

        return response
    except product.ProductNotFound:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Product not found"
        )


@product_router.get("/{id}/tree")
@requires(["hippo:admin", "hippo:read"])
async def read_tree(
    id: PydanticObjectId,
    request: Request,
) -> ReadProductResponse:
    """
    Read a single product's entire history.
    """

    logger.info(
        "Read product tree request for {} from {}", id, request.user.display_name
    )

    try:
        requested_item = await product.read_by_id(id=id, groups=request.user.groups)
        current_item = await product.walk_to_current(
            product=requested_item, groups=request.user.groups
        )
        history = await product.walk_history(product=current_item)

        if not current_item.current:
            raise HTTPException(
                status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Unable to find the current version of the requested item",
            )

        response = ReadProductResponse(
            current_present=True,
            current=current_item.version,
            requested=requested_item.version,
            versions=history,
        )

        logger.info(
            "Successfully read product tree for {} (id: {}) requested by {}",
            requested_item.name,
            requested_item.id,
            request.user.display_name,
        )

        return response
    except product.ProductNotFound:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Product not found"
        )


@product_router.get("/{id}/files")
@requires(["hippo:admin", "hippo:read"])
async def read_files(id: PydanticObjectId, request: Request) -> ReadFilesResponse:
    """
    Read a single product's including pre-signed URLs for downloads.
    """

    logger.info("Read files request for {} from {}", id, request.user.display_name)

    try:
        item = await product.read_by_id(id=id, groups=request.user.groups)
    except product.ProductNotFound:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Product not found"
        )

    files = await product.read_files(product=item, storage=request.app.storage)

    logger.info(
        "Read {} pre-signed URLs for product {} (id: {}) requested by {}",
        len(files),
        item.name,
        item.id,
        request.user.display_name,
    )

    return ReadFilesResponse(
        product=item.to_metadata(),
        files=files,
    )


@product_router.post("/{id}/update")
@requires(["hippo:admin", "hippo:write"])
async def update_product(
    id: PydanticObjectId,
    model: UpdateProductRequest,
    request: Request,
) -> UpdateProductResponse:
    """
    Update a product's details.
    """

    logger.info("Update product request for {} from {}", id, request.user.display_name)

    try:
        item = await product.read_by_id(id=id, groups=request.user.groups)
    except product.ProductNotFound:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Product not found"
        )

    if model.owner is not None:
        try:
            await users.confirm_user(name=model.owner)
            user = model.owner
        except users.UserNotFound:
            raise HTTPException(
                status_code=status.HTTP_406_NOT_ACCEPTABLE, detail="User not found."
            )
    else:
        user = None

    new_product, upload_urls = await product.update(
        product=item,
        access_groups=request.user.groups,
        name=model.name,
        description=model.description,
        metadata=model.metadata,
        owner=user,
        new_sources=model.new_sources,
        replace_sources=model.replace_sources,
        drop_sources=model.drop_sources,
        storage=request.app.storage,
        level=model.level,
        add_readers=model.add_readers,
        remove_readers=model.remove_readers,
        add_writers=model.add_writers,
        remove_writers=model.remove_writers,
    )

    logger.info(
        "Successfully updated product {} (new id: {}; {}; old id: {}; {}) from {}",
        new_product.name,
        new_product.id,
        new_product.version,
        item.id,
        item.version,
        request.user.display_name,
    )

    return UpdateProductResponse(
        version=new_product.version,
        id=new_product.id,
        upload_urls=upload_urls,
    )


@product_router.post("/{id}/confirm")
@requires(["hippo:admin", "hippo:read"])
async def confirm_product(id: PydanticObjectId, request: Request) -> None:
    """
    Confirm a product's sources.
    """

    logger.info("Confirm product request for {} from {}", id, request.user.display_name)

    try:
        item = await product.read_by_id(id=id, groups=request.user.groups)
        success = await product.confirm(
            product=item,
            storage=request.app.storage,
        )
    except product.ProductNotFound:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Product not found."
        )

    if not success:
        raise HTTPException(
            status_code=status.HTTP_424_FAILED_DEPENDENCY,
            detail="Not all sources were present.",
        )

    logger.info("Successfully confirmed product {} (id: {})", item.name, item.id)


@product_router.delete("/{id}")
@requires(["hippo:admin", "hippo:write"])
async def delete_product(
    id: PydanticObjectId,
    request: Request,
    data: bool = False,
) -> None:
    """
    Delete a product.
    """

    logger.info(
        "Delete (single) product request for {} from {}", id, request.user.display_name
    )

    try:
        item = await product.read_by_id(id=id, groups=request.user.groups)
    except product.ProductNotFound:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Product not found."
        )

    await product.delete_one(
        product=item,
        access_groups=request.user.groups,
        storage=request.app.storage,
        data=data,
    )

    logger.info(
        "Successfully deleted product {} (id: {}) including data"
        if data
        else "Successfully deleted product {} (id: {}) excluding data",
        item.name,
        item.id,
    )


@product_router.delete("/{id}/tree")
@requires(["hippo:admin", "hippo:write"])
async def delete_tree(
    id: PydanticObjectId,
    request: Request,
    data: bool = False,
) -> None:
    """
    Delete a product.
    """

    logger.info(
        "Delete (tree) product request for {} from {}", id, request.user.display_name
    )

    try:
        item = await product.read_by_id(id=id, groups=request.user.groups)
    except product.ProductNotFound:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Product not found."
        )

    await product.delete_tree(
        product=item,
        access_groups=request.user.groups,
        storage=request.app.storage,
        data=data,
    )

    logger.info(
        "Successfully deleted product tree for {} (id: {}) including data"
        if data
        else "Successfully deleted product tree for {} (id: {}) excluding data",
        item.name,
        item.id,
    )


@product_router.get("/search/{text}")
@requires(["hippo:admin", "hippo:read"])
async def search(
    text: str,
    request: Request,
) -> list[ProductMetadata]:
    """
    Search for a product by name.
    """

    logger.info(
        "Search for product {} request from {}", text, request.user.display_name
    )

    items = await product.search_by_name(name=text, groups=request.user.groups)

    logger.info(
        "Successfully found {} product(s) matching {} requested by {}",
        len(items),
        text,
        request.user.display_name,
    )

    return [item.to_metadata() for item in items]

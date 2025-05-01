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
from hipposerve.database import Privilege, ProductMetadata
from hipposerve.service import product, users
from hipposerve.service.auth import UserDependency, check_group_for_privilege

product_router = APIRouter(prefix="/product")

DEFAULT_USER_USER_NAME = "default_user"


@product_router.put("/new")
async def create_product(
    request: Request,
    model: CreateProductRequest,
    calling_user: UserDependency,
) -> CreateProductResponse:
    """
    Create a new product, returning the pre-signed URLs for the sources.
    """

    logger.info("Create product request: {} from {}", model.name, calling_user.name)

    await check_group_for_privilege(calling_user, Privilege.CREATE_PRODUCT)

    if await product.exists(name=model.name):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="Product already exists"
        )

    item, presigned = await product.create(
        name=model.name,
        description=model.description,
        metadata=model.metadata,
        sources=model.sources,
        user=calling_user,
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
        calling_user.name,
    )

    return CreateProductResponse(id=item.id, upload_urls=presigned)


@product_router.post("/{id}/complete")
async def complete_product(
    id: PydanticObjectId,
    request: Request,
    model: CompleteProductRequest,
    calling_user: UserDependency,
) -> None:
    """
    Complete a product's upload. Must be called before the sources are available.
    """

    logger.info("Complete product request for {} from {}", id, calling_user.name)

    await check_group_for_privilege(calling_user, Privilege.CREATE_PRODUCT)

    try:
        item = await product.read_by_id(id=id, user=calling_user)
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
async def read_product(
    id: PydanticObjectId,
    request: Request,
    calling_user: UserDependency,
) -> ReadProductResponse:
    """
    Read a single product's metadata.
    """

    logger.info("Read product request for {} from {}", id, calling_user.name)

    await check_group_for_privilege(calling_user, Privilege.READ_PRODUCT)

    try:
        item = (await product.read_by_id(id, calling_user)).to_metadata()

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
            calling_user.name,
        )

        return response
    except product.ProductNotFound:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Product not found"
        )


@product_router.get("/{id}/tree")
async def read_tree(
    id: PydanticObjectId, request: Request, calling_user: UserDependency
) -> ReadProductResponse:
    """
    Read a single product's entire history.
    """

    logger.info("Read product tree request for {} from {}", id, calling_user.name)

    await check_group_for_privilege(calling_user, Privilege.READ_PRODUCT)

    try:
        requested_item = await product.read_by_id(id, calling_user)
        current_item = await product.walk_to_current(requested_item, calling_user)
        history = await product.walk_history(current_item)

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
            calling_user.name,
        )

        return response
    except product.ProductNotFound:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Product not found"
        )


@product_router.get("/{id}/files")
async def read_files(
    id: PydanticObjectId, request: Request, calling_user: UserDependency
) -> ReadFilesResponse:
    """
    Read a single product's including pre-signed URLs for downloads.
    """

    logger.info("Read files request for {} from {}", id, calling_user.name)

    await check_group_for_privilege(calling_user, Privilege.READ_PRODUCT)

    try:
        item = await product.read_by_id(id=id, user=calling_user)
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
        calling_user.name,
    )

    return ReadFilesResponse(
        product=item.to_metadata(),
        files=files,
    )


@product_router.post("/{id}/update")
async def update_product(
    id: PydanticObjectId,
    model: UpdateProductRequest,
    request: Request,
    calling_user: UserDependency,
) -> UpdateProductResponse:
    """
    Update a product's details.
    """

    logger.info("Update product request for {} from {}", id, calling_user.name)

    # For now only privileged users can update products, and they can update everyone's.
    await check_group_for_privilege(calling_user, Privilege.UPDATE_PRODUCT)

    try:
        item = await product.read_by_id(id=id, user=calling_user)
    except product.ProductNotFound:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Product not found"
        )

    if model.owner is not None:
        try:
            user = await users.read(name=model.owner)
        except users.UserNotFound:
            raise HTTPException(
                status_code=status.HTTP_406_NOT_ACCEPTABLE, detail="User not found."
            )
    else:
        user = None

    new_product, upload_urls = await product.update(
        item,
        calling_user,
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
        calling_user.name,
    )

    return UpdateProductResponse(
        version=new_product.version,
        id=new_product.id,
        upload_urls=upload_urls,
    )


@product_router.post("/{id}/confirm")
async def confirm_product(
    id: PydanticObjectId, request: Request, calling_user: UserDependency
) -> None:
    """
    Confirm a product's sources.
    """

    logger.info("Confirm product request for {} from {}", id, calling_user.name)

    await check_group_for_privilege(calling_user, Privilege.CONFIRM_PRODUCT)

    try:
        item = await product.read_by_id(id=id, user=calling_user)
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
async def delete_product(
    id: PydanticObjectId,
    request: Request,
    calling_user: UserDependency,
    data: bool = False,
) -> None:
    """
    Delete a product.
    """

    logger.info("Delete (single) product request for {} from {}", id, calling_user.name)

    await check_group_for_privilege(calling_user, Privilege.DELETE_PRODUCT)

    try:
        item = await product.read_by_id(id=id, user=calling_user)
    except product.ProductNotFound:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Product not found."
        )

    await product.delete_one(
        item,
        access_user=calling_user,
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
async def delete_tree(
    id: PydanticObjectId,
    request: Request,
    calling_user: UserDependency,
    data: bool = False,
) -> None:
    """
    Delete a product.
    """

    logger.info("Delete (tree) product request for {} from {}", id, calling_user.name)

    await check_group_for_privilege(calling_user, Privilege.DELETE_PRODUCT)

    try:
        item = await product.read_by_id(id=id, user=calling_user)
    except product.ProductNotFound:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Product not found."
        )

    await product.delete_tree(
        item,
        access_user=calling_user,
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
async def search(
    text: str,
    request: Request,
    calling_user: UserDependency,
) -> list[ProductMetadata]:
    """
    Search for a product by name.
    """

    logger.info("Search for product {} request from {}", text, calling_user.name)

    await check_group_for_privilege(calling_user, Privilege.READ_PRODUCT)

    items = await product.search_by_name(name=text, user=calling_user)

    logger.info(
        "Successfully found {} product(s) matching {} requested by {}",
        len(items),
        text,
        calling_user.name,
    )

    return [item.to_metadata() for item in items]

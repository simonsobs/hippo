"""
Authentication code for the API, which uses api key based
authentication.
"""

from typing import Annotated

from fastapi import Depends, HTTPException, Security, status
from fastapi.security import APIKeyHeader
from loguru import logger

from hipposerve.database import Collection, Product
from hipposerve.service import groups, users

api_key_header = APIKeyHeader(name="X-API-Key")


async def get_user(api_key_header: str = Security(api_key_header)) -> users.User:
    try:
        user = await users.user_from_api_key(api_key_header)
        logger.info(f"Authenticated user using API key: {user.name}")
        return user
    except users.UserNotFound:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API Key",
        )


UserDependency = Annotated[users.User, Depends(get_user)]


async def check_group_for_privilege(
    user: users.User, privilege: groups.Privilege
) -> None:
    for group in user.groups:
        if privilege in group.access_controls:
            return

    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="Insufficient privileges",
    )


async def check_product_read_access(user: users.User, target_product: Product) -> None:
    product_groups = target_product.readers + target_product.writers
    for group in user.groups:
        if (
            group.name in product_groups
            and groups.Privilege.READ_PRODUCT in group.access_controls
        ):
            return

    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="Insufficient privileges for product access",
    )


async def check_product_write_access(user: users.User, target_product: Product) -> None:
    product_groups = target_product.writers
    for group in user.groups:
        if (
            group.name in product_groups
            and groups.Privilege.UPDATE_PRODUCT in group.access_controls
        ):
            return

    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="Insufficient privileges for product access",
    )


async def check_collection_read_access(
    user: users.User, target_collection: Collection
) -> None:
    collection_groups = target_collection.readers + target_collection.writers
    for group in user.groups:
        if (
            group.name in collection_groups
            and groups.Privilege.READ_COLLECTION in group.access_controls
        ):
            return

    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="Insufficient privileges for collection access",
    )


async def check_collection_write_access(
    user: users.User, target_collection: Collection
) -> None:
    collection_groups = target_collection.writers
    for group in user.groups:
        if (
            group.name in collection_groups
            and groups.Privilege.UPDATE_COLLECTION in group.access_controls
        ):
            return

    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="Insufficient privileges for collection access",
    )

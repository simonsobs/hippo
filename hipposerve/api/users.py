"""
Routes for user management.

TODO: Authentication.
"""

from fastapi import APIRouter, HTTPException, status
from loguru import logger

from hipposerve.api.models.users import (
    CreateUserRequest,
    CreateUserResponse,
    ReadUserResponse,
    UpdateUserRequest,
    UpdateUserResponse,
)
from hipposerve.service import users
from hipposerve.service.auth import UserDependency, check_group_for_privilege
from hipposerve.settings import SETTINGS

users_router = APIRouter(prefix="/users")


@users_router.put("/{name}")
async def create_user(
    name: str,
    request: CreateUserRequest,
    calling_user: UserDependency,
) -> CreateUserResponse:
    """
    Create a new user.
    """

    logger.info("Request to create user: {} from {}", name, calling_user.name)

    await check_group_for_privilege(calling_user, users.Privilege.CREATE_USER)

    try:
        user = await users.read(name=name)

        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="User already exists."
        )
    except users.UserNotFound:
        user = await users.create(
            name=name,
            password=request.password,
            email=request.email,
            avatar_url=request.avatar_url,
            gh_profile_url=request.gh_profile_url,
            privileges=request.privileges,
            hasher=SETTINGS.hasher,
            compliance=request.compliance,
        )

    logger.info("User {} created for {}", user.name, calling_user.name)

    return CreateUserResponse(api_key=user.api_key)


@users_router.get("/{name}")
async def read_user(name: str, calling_user: UserDependency) -> ReadUserResponse:
    """
    Read a user's details, but not their API key.
    """

    logger.info("Request to read user: {} from {}", name, calling_user.name)

    if name != calling_user.name:
        await check_group_for_privilege(calling_user, users.Privilege.READ_USER)

    user = await users.read(name=name)

    logger.info("User {} read by {}", name, calling_user.name)

    return ReadUserResponse(
        name=user.name,
        privileges=user.privileges,
        compliance=user.compliance,
    )


@users_router.post("/{name}/update")
async def update_user(
    name: str, request: UpdateUserRequest, calling_user: UserDependency
) -> UpdateUserResponse:
    """
    Update a user's details. At present, only admins can update users.
    """

    logger.info("Request to update user: {} from {}", name, calling_user.name)

    await check_group_for_privilege(calling_user, users.Privilege.UPDATE_USER)

    user = await users.update(
        name=name,
        privileges=request.privileges,
        refresh_key=request.refresh_key,
        password=request.password,
        hasher=SETTINGS.hasher,
        compliance=request.compliance,
    )

    logger.info(
        "User {} updated by {} with new API key"
        if request.refresh_key
        else "User {} updated by {}",
        name,
        calling_user.name,
    )

    return UpdateUserResponse(
        api_key=user.api_key if request.refresh_key else None,
        compliance=user.compliance,
    )


@users_router.post("/{name}/updategroups")
async def update_user_groups(
    name: str,
    request: UpdateUserRequest,
    calling_user: UserDependency,
) -> UpdateUserResponse:
    """
    Update a user's groups.
    """

    logger.info("Request to update user groups: {} from {}", name, calling_user.name)

    await check_group_for_privilege(calling_user, users.Privilege.UPDATE_USER_GROUP)

    user = await users.update_groups(
        name=name,
        add_group=request.add_group,
        remove_group=request.remove_group,
    )

    logger.info("User {} updated by {}", name, calling_user.name)

    return UpdateUserResponse(
        api_key=None,
        compliance=user.compliance,
    )


@users_router.delete("/{name}")
async def delete_user(name: str, calling_user: UserDependency) -> None:
    """
    Delete a user.
    """

    logger.info("Request to delete user: {} from {}", name, calling_user.name)

    await check_group_for_privilege(calling_user, users.Privilege.DELETE_USER)

    await users.delete(name=name)

    logger.info("User {} deleted by {}", name, calling_user.name)

    return

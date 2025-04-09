from fastapi import APIRouter, HTTPException, status
from loguru import logger

from hipposerve.api.auth import UserDependency, check_group_for_privilege
from hipposerve.api.models.groups import (
    CreateGroupRequest,
    CreateGroupResponse,
    ReadGroupResponse,
    UpdateGroupAccessRequest,
    UpdateGroupAccessResponse,
    UpdateGroupDescriptionRequest,
    UpdateGroupDescriptionResponse,
)
from hipposerve.service import groups

groups_router = APIRouter(prefix="/groups")


@groups_router.put("/{name}")
async def create_group(
    name: str,
    request: CreateGroupRequest,
    calling_user: UserDependency,
) -> CreateGroupResponse:
    """
    Create a new group.
    """
    logger.info("Request to create group: {} from {}", name, calling_user.name)

    await check_group_for_privilege(calling_user, groups.Privilege.CREATE_GROUP)

    try:
        group = await groups.read_by_name(name=name)

        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="Group already exists."
        )
    except groups.GroupNotFound:
        group = await groups.create(
            name=name,
            description=request.description,
            access_control=request.privileges,
        )

    logger.info("Group {} created for {}", group.name, calling_user.name)
    return CreateGroupResponse(group_name=group.name)


@groups_router.get("/{name}")
async def read_group(name: str, calling_user: UserDependency) -> ReadGroupResponse:
    """
    Read a group.
    """

    logger.info("Request to read group: {} from {}", name, calling_user.name)

    await check_group_for_privilege(calling_user, groups.Privilege.READ_GROUP)

    try:
        group = await groups.read_by_name(name=name)

    except groups.GroupNotFound:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Group not found."
        )

    return ReadGroupResponse(
        name=group.name,
        privileges=group.access_controls,
        description=group.description,
    )


@groups_router.post("/{name}/updateaccess")
async def update_group_access(
    name: str,
    request: UpdateGroupAccessRequest,
    calling_user: UserDependency,
) -> UpdateGroupAccessResponse:
    """
    Update a group's access.
    """
    logger.info("Request to update group access: {} from {}", name, calling_user.name)

    await check_group_for_privilege(calling_user, groups.Privilege.UPDATE_PRIVILEGES)

    try:
        group = await groups.update_access_control(
            name=name,
            add_access_control=request.add_access_control,
            remove_access_control=request.remove_access_control,
        )
    except groups.GroupNotFound:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Group not found."
        )
    return UpdateGroupAccessResponse(access_controls=group.access_controls)


@groups_router.post("/{name}/updatedescription")
async def update_group_description(
    name: str,
    request: UpdateGroupDescriptionRequest,
    calling_user: UserDependency,
) -> UpdateGroupDescriptionResponse:
    """
    Update a group's access.
    """
    logger.info("Request to update group access: {} from {}", name, calling_user.name)

    await check_group_for_privilege(calling_user, groups.Privilege.UPDATE_GROUP)

    try:
        group = await groups.update_desciption(
            name=name,
            description=request.description,
        )
    except groups.GroupNotFound:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Group not found."
        )
    return UpdateGroupDescriptionResponse(description=group.description)


@groups_router.delete("/{name}")
async def delete_group(
    name: str,
    calling_user: UserDependency,
) -> None:
    """
    Delete a group.
    """
    logger.info("Request to delete group: {} from {}", name, calling_user.name)

    await check_group_for_privilege(calling_user, groups.Privilege.DELETE_GROUP)

    try:
        await groups.delete(name=name)
    except groups.GroupNotFound:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Group not found."
        )
    logger.info("Group {} deleted by {}", name, calling_user.name)
    return

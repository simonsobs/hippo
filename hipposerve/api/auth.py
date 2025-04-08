"""
Authentication code for the API, which uses api key based
authentication.
"""

from typing import Annotated

from fastapi import Depends, HTTPException, Security, status
from fastapi.security import APIKeyHeader
from loguru import logger

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


async def check_user_for_privilege(
    user: users.User, privilege: users.Privilege
) -> None:
    if privilege not in user.privileges:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient privileges",
        )


async def check_group_for_privilege(
    user: users.User, privilege: groups.Privilege
) -> None:
    from hipposerve.database import Group

    group_ids = [group.id for group in user.groups]

    group_matches = await Group.find(
        {"_id": {"$in": group_ids}, "access_controls": privilege}
    ).count()

    if group_matches == 0:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient privileges",
        )

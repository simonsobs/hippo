"""
Authentication code for the API, which uses api key based
authentication.
"""

import functools
import inspect
from typing import Annotated

from fastapi import Depends, HTTPException, Request, Security, status
from fastapi.security import APIKeyHeader
from loguru import logger
from starlette._utils import is_async_callable

from hipposerve.service import users

AVAILABLE_GRANTS = {
    "hippo:admin",
    "hippo:read",
    "hippo:write",
}


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


def has_required_scope(request: Request, scopes: list[str]) -> bool:
    for scope in scopes:
        if scope not in request.auth.scopes:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN)

    return True


def requires(scopes: str | list[str]):
    """
    Check whether your user has the required scope.
    """

    def decorator(func):
        scopes_list = [scopes] if isinstance(scopes, str) else list(scopes)

        for scope in scopes_list:
            if scope not in AVAILABLE_GRANTS:
                raise HTTPException(501, "Invalid scope, server error")

        sig = inspect.signature(func)
        for idx, parameter in enumerate(sig.parameters.values()):
            if parameter.name == "request":
                break
        else:
            raise Exception(f'No "request" argument on function "{func}"')

        if is_async_callable(func):

            @functools.wraps(func)
            async def async_wrapper(*args, **kwargs):
                request = kwargs.get("request", args[idx] if idx < len(args) else None)
                assert isinstance(request, Request)

                if has_required_scope(request, scopes_list):
                    return await func(*args, **kwargs)

            return async_wrapper
        else:

            @functools.wraps(func)
            def sync_wrapper(*args, **kwargs):
                request = kwargs.get("request", args[idx] if idx < len(args) else None)
                assert isinstance(request, Request)

                if has_required_scope(request, scopes_list):
                    return func(*args, **kwargs)

            return sync_wrapper

    return decorator


async def check_product_access(groups: list[str], product_groups: list[str]) -> None:
    allowed = set(product_groups)
    if any(group in allowed for group in groups):
        return

    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="Insufficient privileges for product access",
    )


async def check_collection_access(
    groups: list[str], collection_groups: list[str]
) -> None:
    allowed = set(collection_groups)
    if any(group in allowed for group in groups):
        return

    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="Insufficient privileges for collection access",
    )

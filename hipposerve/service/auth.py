"""
Authentication code for the API, which uses api key based
authentication.
"""

import functools
import inspect

from fastapi import HTTPException, Request, status
from starlette._utils import is_async_callable

AVAILABLE_GRANTS = {
    "hippo:admin",
    "hippo:read",
    "hippo:write",
}


def has_required_scope(request: Request, scopes: list[str]) -> bool:
    allowed = set(scopes)
    if any(scope in allowed for scope in request.auth.scopes):
        return True

    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN)


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

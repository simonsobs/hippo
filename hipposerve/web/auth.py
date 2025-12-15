"""
Authentication layer for the Web UI. Provides two core dependencies:

- `LoggedInUser` - a dependency that requires a user to be logged in. If the user is not logged in, a 401 Unauthorized response is returned.
- `PotentialLoggedInUser` - a dependency that returns a user if they are logged in, or `None` if they are not.
"""

from typing import Annotated
from urllib.parse import urlparse, urlunparse

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import RedirectResponse
from loguru import logger

from hipposerve.service import collection, product
from hipposerve.service import users as users_service
from hipposerve.settings import SETTINGS

from .router import templates


def replace_path_component(url: str, old: str, new: str) -> str:
    """
    Replace a path component in a URL.

    Parameters
    ----------
    url : str
        The URL to modify.
    old : str
        The old path component.
    new : str
        The new path component.

    Returns
    -------
    str
        The modified URL.
    """

    parsed = urlparse(url)
    fixed = parsed._replace(path=parsed.path.replace(old, new))
    return urlunparse(fixed)


def generate_redirect_response(
    request: Request, old: str, new: str
) -> RedirectResponse:
    """
    Generate a redirect response with a path component replaced.

    Parameters
    ----------
    request : Request
        The request object.
    old : str
        The old path component.
    new : str
        The new path component.

    Returns
    -------
    RedirectResponse
        The redirection response (code 302)
    """
    url = str(request.url)
    new_url = replace_path_component(url, old, new)

    return RedirectResponse(url=new_url, status_code=302)


router = APIRouter()


class UnauthorizedException(HTTPException):
    def __init__(
        self, detail: str | None = "Authentication required to access this page."
    ):
        super().__init__(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=detail,
        )


async def get_current_user(request: Request):
    """
    Returns the authenticated HIPPO user or raises UnauthorizedException.
    """
    user = request.user
    if not request.user.is_authenticated:
        raise UnauthorizedException()
    return user


async def get_potential_current_user(request: Request):
    try:
        return await get_current_user(request)
    except HTTPException:
        return None
    return None


LoggedInUser = Annotated[users_service.User, Depends(get_current_user)]
PotentialLoggedInUser = Annotated[
    users_service.User | None, Depends(get_potential_current_user)
]


@router.get("/user")
async def read_user(request: Request):
    username = request.user.display_name
    collections = (
        await collection.search_by_owner(
            username, request.user.groups, scopes=request.auth.scopes
        )
        or []
    )
    products = (
        await product.search_by_owner(
            username, request.user.groups, scopes=request.auth.scopes
        )
        or []
    )

    logger.info(
        "User page for {} has {} products and {} collections",
        username,
        len(products),
        len(collections),
    )

    return templates.TemplateResponse(
        "user.html",
        {
            "request": request,
            "products": products,
            "collections": collections,
            "web_root": SETTINGS.web_root,
        },
    )


@router.get("/login", name="login")
async def login(request: Request):
    return RedirectResponse(url=request.app.login_url, status_code=302)

"""
Authentication layer for the Web UI. Provides two core dependencies:

- `LoggedInUser` - a dependency that requires a user to be logged in. If the user is not logged in, a 401 Unauthorized response is returned.
- `PotentialLoggedInUser` - a dependency that returns a user if they are logged in, or `None` if they are not.
"""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import HTMLResponse, RedirectResponse

from hipposerve.service import users as users_service
from hipposerve.settings import SETTINGS

from .router import templates

router = APIRouter()


class UnauthorizedException(HTTPException):
    def __init__(self, detail: str | None = "Could not validate credentials"):
        super().__init__(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=detail,
            headers={"WWW-Authenticate": "Bearer"},
        )


async def get_hippo_user_from_soauth_request(request: Request):
    if SETTINGS.auth_system is None:
        try:
            user = await users_service.read("admin")
        except users_service.UserNotFound:
            raise UnauthorizedException()

    if not request.user.is_authenticated:
        raise UnauthorizedException()

    soauth_username = request.user.display_name
    soauth_useremail = request.user.email
    soauth_grants = (
        request.auth.scopes if hasattr(request, "auth") and request.auth else []
    )

    try:
        user = await users_service.read(name=soauth_username)
        # Sync user privileges with latest SOAuth grants
        return await sync_privileges_from_soauth_grants(user, soauth_grants)
    except users_service.UserNotFound:
        # Create a new user
        return await users_service.create(
            name=soauth_username,
            password=None,
            email=soauth_useremail,
            avatar_url=None,
            gh_profile_url=f"https://github.com/{soauth_username}",
            privileges=soauth_grants,
            hasher=SETTINGS.hasher,
            compliance=None,
        )


async def sync_privileges_from_soauth_grants(user, grants):
    """
    Updates a user's personal group privileges using direct MongoDB query.
    """
    from hipposerve.service.groups import Group

    # Find the user's personal group
    user_group = await Group.find_one(Group.name == user.name)
    await user_group.update({"$set": {"access_controls": grants}})

    return user


async def get_current_user(request: Request):
    """
    Returns the authenticated HIPPO user or raises UnauthorizedException.
    """
    user = await get_hippo_user_from_soauth_request(request)
    if user is None:
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


@router.get("/logout")
async def logout(request: Request) -> RedirectResponse:
    """Redirect to SOAuth logout."""
    try:
        logout_url = request.app.logout_url
    except AttributeError:
        logout_url = "/"

    return RedirectResponse(logout_url, status_code=302)


@router.post("/user/update")
async def update_compliance(request: Request, user: LoggedInUser):
    """Update user compliance information."""
    form_data = await request.form()
    compliance_info = form_data.get("nersc_user_name")
    await users_service.update(
        name=user.name,
        hasher=SETTINGS.hasher,
        password=None,
        privileges=user.privileges,
        compliance={"nersc_username": compliance_info},
        refresh_key=False,
    )
    return RedirectResponse("/web/user", status_code=302)


@router.get("/user")
async def read_user(request: Request, user: LoggedInUser):
    return templates.TemplateResponse(
        "user.html", {"request": request, "user": user, "web_root": SETTINGS.web_root}
    )


@router.get("/login", name="login")
async def login(request: Request):
    if SETTINGS.auth_system is None:
        return RedirectResponse(url="/web/user", status_code=302)

    login_url = request.app.login_url
    print(f"Redirecting to login URL: {login_url}")
    return HTMLResponse(
        f"<a href='{login_url}' referrerpolicy='no-referrer-when-downgrade'>Login</a>"
    )

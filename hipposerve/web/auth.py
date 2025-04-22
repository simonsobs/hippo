"""
Authentication layer for the Web UI. Provides two core dependencies:

- `LoggedInUser` - a dependency that requires a user to be logged in. If the user is not logged in, a 401 Unauthorized response is returned.
- `PotentialLoggedInUser` - a dependency that returns a user if they are logged in, or `None` if they are not.
"""

from datetime import datetime, timedelta, timezone
from typing import Annotated
from urllib.parse import urlparse, urlunparse

import httpx
import jwt
from beanie import PydanticObjectId
from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.openapi.models import OAuthFlows
from fastapi.responses import RedirectResponse
from fastapi.security import OAuth2, OAuth2PasswordRequestForm
from fastapi.security.utils import get_authorization_scheme_param
from pydantic import BaseModel

from hipposerve.service import users as user_service
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


class OAuth2PasswordBearerWithCookie(OAuth2):
    """
    A custom OAuth2 scheme (extremely similar to the built-in FastAPI
    ``OAuth2PasswordBearer`` scheme) that reads the token from a cookie
    instead of the `Authorization` header. The key method here is ``__call__``,
    which reads the token from the cookie, given a request object, and returns
    the token as a string.

    For more complete documentation see the FastAPI documentation on OAuth2
    authentication schemes: ``https://fastapi.tiangolo.com/reference/security/``.

    Parameters
    ----------
    tokenUrl : str
        The URL to obtain the OAuth2 token. This would be the path operation that has
        ``OAuth2PasswordRequestForm`` as a dependency.
    scheme_name : str, optional
        The name of the scheme for OpenAPI docs. Defaults to `None`.
    scopes : dict, optional
        The OAuth2 scopes that would be required by the path operations
        that use this dependency.
    auto_error : bool, optional
        By default, if no HTTP Authorization header is provided, required for
        OAuth2 authentication, it will automatically cancel the request and
        send the client an error.

        If auto_error is set to False, when the HTTP Authorization cookie
        is not available, instead of erroring out, the dependency result
        will be None.

        This is provided for compatibility with other OAuth2 schemes, however
        in hippo we use two separate dependencies for this purpose.

    Notes
    -----
    This should, in theory, enable the 'docs' Web UI to store the token in a cookie
    and work as expected. However, the current implementation does not fully satisfy
    this as I believe the password form is expecting to use a header. A potential
    way around this would be to set both, but that could lead to inconsistencies.

    """

    def __init__(
        self,
        tokenUrl: str,
        scheme_name: str = None,
        scopes: dict = None,
        auto_error: bool = True,
    ):
        if not scopes:
            scopes = {}
        flows = OAuthFlows(password={"tokenUrl": tokenUrl, "scopes": scopes})
        super().__init__(flows=flows, scheme_name=scheme_name, auto_error=auto_error)

    async def __call__(self, request: Request) -> str | None:
        authorization: str = request.cookies.get("access_token")

        scheme, param = get_authorization_scheme_param(authorization)
        if not authorization or scheme.lower() != "bearer":
            if self.auto_error:
                raise UnauthorizedException(
                    detail="Not authenticated",
                )
            else:
                return None

        return param


oauth2_scheme = OAuth2PasswordBearerWithCookie(tokenUrl="/web/token")


class WebTokenData(BaseModel):
    username: str | None = None
    user_id: PydanticObjectId | None = None
    origin: str | None = None

    def encode(self):
        return f"{self.username}:::{self.user_id}:::{self.origin}"

    @classmethod
    def decode(cls, token: str):
        username, user_id, origin = token.split(":::")
        return cls(username=username, user_id=PydanticObjectId(user_id), origin=origin)


class UnauthorizedException(HTTPException):
    def __init__(self, detail: str | None = "Could not validate credentials"):
        super().__init__(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=detail,
            headers={"WWW-Authenticate": "Bearer"},
        )


async def get_current_user(
    token: Annotated[str, Depends(oauth2_scheme)], request: Request
):
    try:
        payload = jwt.decode(
            token, SETTINGS.web_jwt_secret, algorithms=[SETTINGS.web_jwt_algorithm]
        )
        sub = payload.get("sub")
        if sub is None:
            raise UnauthorizedException()
        token_data = WebTokenData.decode(sub)
    except jwt.PyJWTError:
        raise UnauthorizedException()
    except ValueError:
        # Unable to split
        raise UnauthorizedException()

    if SETTINGS.web_jwt_check_origin:
        # Don't use the Origin header as it's often not set (e.g. it is never set
        # on GET requests as the browser already checked that). Let's just use the
        # Sec-Fetch-Site header instead.
        potential_origin = request.headers.get("Sec-Fetch-Site")
        if potential_origin == "cross-origin":
            raise UnauthorizedException()

    if SETTINGS.web_jwt_check_origin:
        # Don't use the Origin header as it's often not set (e.g. it is never set
        # on GET requests as the browser already checked that). Let's just use the
        # Sec-Fetch-Site header instead.
        potential_origin = request.headers.get("Sec-Fetch-Site")
        if potential_origin == "cross-origin":
            raise UnauthorizedException()

    try:
        user = await users_service.read_by_id(id=token_data.user_id)
    except users_service.UserNotFound:
        raise UnauthorizedException()

    return user


async def get_potential_current_user(request: Request):
    try:
        token = await oauth2_scheme(request=request)
        if token:
            return await get_current_user(token, request)
    except HTTPException:
        return None

    return None


def create_access_token(
    user: users_service.User, expires_delta: timedelta, origin: str
):
    to_encode = {
        "exp": datetime.now(timezone.utc) + expires_delta,
        "sub": WebTokenData(
            username=user.name, user_id=user.id, origin=origin
        ).encode(),
    }
    encoded_jwt = jwt.encode(
        to_encode, SETTINGS.web_jwt_secret, algorithm=SETTINGS.web_jwt_algorithm
    )
    return f"Bearer {encoded_jwt}"


LoggedInUser = Annotated[users_service.User, Depends(get_current_user)]
PotentialLoggedInUser = Annotated[
    users_service.User | None, Depends(get_potential_current_user)
]


@router.get("/github")
async def login_with_github_for_access_token(
    request: Request,
    code: str,
) -> RedirectResponse:
    if not SETTINGS.web_allow_github_login:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="GitHub login is not enabled.",
        )

    # See if we can exchange the code for a token.

    unauthorized = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not authenticate with GitHub.",
    )

    async with httpx.AsyncClient() as client:
        response = await client.post(
            "https://github.com/login/oauth/access_token",
            data={
                "client_id": SETTINGS.web_github_client_id,
                "client_secret": SETTINGS.web_github_client_secret,
                "code": code,
            },
            headers={"Accept": "application/json"},
        )

    if response.status_code != 200:
        raise unauthorized

    access_token = response.json().get("access_token")

    if access_token is None:
        raise unauthorized

    async with httpx.AsyncClient() as client:
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Accept": "application/json",
        }
        response = await client.get("https://api.github.com/user", headers=headers)

        if response.status_code != 200:
            raise unauthorized

        user_info = response.json()

        if SETTINGS.web_github_required_organisation_membership is not None:
            response = await client.get(user_info["organizations_url"], headers=headers)

            if response.status_code != 200:
                raise unauthorized

            orgs = response.json()

            if not any(
                org["login"] == SETTINGS.web_github_required_organisation_membership
                for org in orgs
            ):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="You are not a member of the required organisation.",
                )

    # At this point we are authenticated and have the user information.
    # Try to match this against a user in the database.
    try:
        user = await user_service.read(name=user_info["login"])
    except user_service.UserNotFound:
        # Need to create one!
        user = await user_service.create(
            name=user_info["login"],
            # TODO: MAKE PASSWORDS OPTIONAL
            password="GitHub",
            email=user_info["email"],
            avatar_url=user_info["avatar_url"],
            gh_profile_url=user_info["html_url"],
            privileges=list(user_service.Privilege),
            hasher=SETTINGS.hasher,
            compliance=None,
        )

    access_token = create_access_token(
        user=user,
        expires_delta=SETTINGS.web_jwt_expires,
        origin=request.headers.get("Origin"),
    )

    new_response = generate_redirect_response(request, "/github", "/user")
    new_response.set_cookie(key="access_token", value=access_token, httponly=True)
    return new_response


@router.post("/token")
async def login_for_access_token(
    request: Request,
    form_data: Annotated[OAuth2PasswordRequestForm, Depends()],
) -> RedirectResponse:
    if SETTINGS.web_only_allow_github_login:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="GitHub login is the only login method enabled",
        )

    try:
        user = await user_service.read_with_password_verification(
            name=form_data.username,
            password=form_data.password,
            hasher=SETTINGS.hasher,
        )
    except user_service.UserNotFound:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    access_token = create_access_token(
        user=user,
        expires_delta=SETTINGS.web_jwt_expires,
        origin=request.headers.get("Origin"),
    )

    new_response = generate_redirect_response(request, "/token", "/user")
    new_response.set_cookie(key="access_token", value=access_token, httponly=True)
    return new_response


@router.get("/logout")
async def logout(request: Request) -> RedirectResponse:
    new_response = generate_redirect_response(request, "/logout", "")
    new_response.delete_cookie(key="access_token")
    return new_response


@router.get("/user/apikey")
async def read_apikey(request: Request, user: LoggedInUser):
    updated_user = await user_service.update(
        name=user.name,
        hasher=SETTINGS.hasher,
        password=None,
        privileges=user.privileges,
        compliance=None,
        refresh_key=True,
    )
    return templates.TemplateResponse(
        "apikey.html",
        {
            "request": request,
            "user": updated_user,
            "web_root": SETTINGS.web_root,
        },
    )


@router.post("/user/update")
async def update_compliance(request: Request, user: LoggedInUser):
    form_data = await request.form()
    compliance_info = form_data.get("nersc_user_name")
    await user_service.update(
        name=user.name,
        hasher=SETTINGS.hasher,
        password=None,
        privileges=user.privileges,
        compliance={"nersc_username": compliance_info},
        refresh_key=False,
    )
    new_response = generate_redirect_response(request, "/user/update", "/user")
    return new_response


@router.get("/user")
async def read_user(request: Request, user: LoggedInUser):
    return templates.TemplateResponse(
        "user.html", {"request": request, "user": user, "web_root": SETTINGS.web_root}
    )


@router.get("/login", name="login")
async def login(request: Request):
    query_params = dict(request.query_params)
    unauthorized_details = query_params.get("detail", None)
    if SETTINGS.web_only_allow_github_login:
        return RedirectResponse(
            url=f"https://github.com/login/oauth/authorize?client_id={SETTINGS.web_github_client_id}",
            status_code=302,
        )
    return templates.TemplateResponse(
        "login.html",
        {
            "request": request,
            "github_client_id": SETTINGS.web_github_client_id,
            "only_allow_github_login": SETTINGS.web_only_allow_github_login,
            "allow_github_login": SETTINGS.web_allow_github_login,
            "unauthorized_details": unauthorized_details,
            "web_root": SETTINGS.web_root,
        },
    )

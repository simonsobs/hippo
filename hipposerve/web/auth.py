"""
Authentication layer for the Web UI. Provides two core dependencies:

- `LoggedInUser` - a dependency that requires a user to be logged in. If the user is not logged in, a 401 Unauthorized response is returned.
- `PotentialLoggedInUser` - a dependency that returns a user if they are logged in, or `None` if they are not.
"""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import RedirectResponse

from hipposerve.service import users as users_service
from hipposerve.settings import SETTINGS

from .router import templates

'''
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
'''

router = APIRouter()

'''
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
'''


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

    if not request.auth.user.is_authenticated:
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


"""
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
"""


@router.get("/login", name="login")
async def login(request: Request):
    """Redirect to SOAuth login page."""
    if SETTINGS.auth_system is None:
        # For development/testing without SOAuth
        return RedirectResponse(url="/web/user", status_code=302)

    try:
        login_url = request.app.login_url
    except AttributeError:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Authentication system not properly configured",
        )

    return RedirectResponse(login_url, status_code=302)

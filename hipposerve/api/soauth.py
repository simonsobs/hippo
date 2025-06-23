from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from loguru import logger
from starlette.middleware.base import BaseHTTPMiddleware

from hipposerve.service import users as user_service
from hipposerve.settings import SETTINGS


class UserMiddleware(BaseHTTPMiddleware):
    """
    Middleware to handle user authentication and updates. Responsible for keeping
    the in-database user record up to date with the one provided by SOAuth.

    This middleware checks if the user is authenticated and updates their last
    access time. If the user does not exist, it creates a new user record.
    """

    async def dispatch(self, request: Request, call_next):
        user_obj = request.scope.get("user")
        if user_obj and user_obj.is_authenticated:
            try:
                # Do not need to check if the user exists as touching
                # does that for us.
                await user_service.touch_last_access_time(
                    name=request.user.display_name
                )
            except user_service.UserNotFound:
                await user_service.create(
                    name=user_obj.display_name, email=user_obj.email
                )

        return await call_next(request)


def setup_auth(app: FastAPI) -> FastAPI:
    """
    Full authentication setup including all required middleware. Sets
    the authentication system based upon the `SETTINGS.auth_system`
    variable; if it's not "soauth" we default to the mock setup.
    """

    # Main authentication middleware. Note that this must come first
    # in the middleware stack so that it can set the user object
    # in the request scope.

    if SETTINGS.auth_system == "soauth":
        from soauth.toolkit.fastapi import global_setup
        from starlette.authentication import AuthenticationError

        app = global_setup(
            app=app,
            app_base_url=SETTINGS.soauth_base_url,
            authentication_base_url=SETTINGS.soauth_service_url,
            app_id=SETTINGS.soauth_app_id,
            key_pair_type=SETTINGS.soauth_key_pair_type,
            public_key=SETTINGS.soauth_public_key,
            client_secret=SETTINGS.soauth_client_secret,
        )

        # Add exception handlers
        def redirect_to_login(request: Request, exc):
            if request.user.is_authenticated:
                return HTMLResponse(
                    "<p>You are not able to access this due to a lack of privileges</p>",
                )
            else:
                return RedirectResponse(app.login_url)

        app.add_exception_handler(403, redirect_to_login)
        app.add_exception_handler(401, redirect_to_login)
        app.add_exception_handler(AuthenticationError, redirect_to_login)
    else:
        from soauth.toolkit.fastapi import mock_global_setup

        logger.warning(
            "Using mock authentication setup, this is not suitable for production use"
        )

        app = mock_global_setup(app=app, grants=["hippo:read", "hippo:write"])

    # This middleware (above) is responsible for keeping the user
    # information up to date in the database.

    app.add_middleware(UserMiddleware)

    return app

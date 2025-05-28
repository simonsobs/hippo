from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware

from hipposerve.service import users as user_service
from hipposerve.settings import SETTINGS


class UserMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        user_obj = request.scope.get("user")
        if user_obj:
            if request.user.is_authenticated:
                try:
                    await user_service.confirm_user(name=request.user.display_name)
                    await user_service.touch_last_access_time(
                        name=request.user.display_name
                    )
                except user_service.UserNotFound:
                    user = await user_service.create(
                        name=request.user.display_name, email=request.user.email
                    )
                    await user_service.confirm_user(name=user.name)

        return await call_next(request)


def setup_auth(app):
    if SETTINGS.auth_system == "soauth":
        from soauth.toolkit.fastapi import global_setup

        app = global_setup(
            app=app,
            app_base_url=SETTINGS.soauth_base_url,
            authentication_base_url=SETTINGS.soauth_service_url,
            app_id=SETTINGS.soauth_app_id,
            key_pair_type=SETTINGS.soauth_key_pair_type,
            public_key=SETTINGS.soauth_public_key,
            client_secret=SETTINGS.soauth_client_secret,
        )
    else:
        from soauth.toolkit.fastapi import mock_global_setup

        app = mock_global_setup(app=app, grants=["hippo:read", "hippo:write"])
    app.add_middleware(UserMiddleware)
    return app

from hipposerve.settings import SETTINGS


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

        app = mock_global_setup(app=app, grants=["test", "grant"])
    return app

"""
Server settings, uses pydantic settings models.
"""

from pwdlib import PasswordHash
from pwdlib.hashers.argon2 import Argon2Hasher
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    minio_url: str
    minio_presign_url: str | None = None
    minio_upgrade_presign_url_to_https: bool = False
    minio_secure: bool = False
    minio_cert_check: bool = False

    minio_access: str
    minio_secret: str

    mongo_uri: str

    title: str
    description: str

    hasher: PasswordHash = PasswordHash([Argon2Hasher()])

    add_cors: bool = True
    debug: bool = True

    create_test_user: bool = False
    web: bool = False
    "Serve the web frontend."
    web_root: str = "/web"

    auth_system: str | None = None
    soauth_service_url: str | None = None
    soauth_app_id: str | None = None
    soauth_public_key: str | None = None
    soauth_base_url: str | None = None
    soauth_client_secret: str | None = None
    soauth_key_pair_type: str = "Ed25519"


SETTINGS = Settings()

"""
Core client object for interacting with the hippo API.
"""

import httpx
from pydantic_settings import (
    BaseSettings,
    JsonConfigSettingsSource,
    PydanticBaseSettingsSource,
    SettingsConfigDict,
)
from rich.console import Console
from soauth.toolkit.client import SOAuth

from .caching import Cache, MultiCache

console = Console()


def Client(
    host: str,
    token_tag: str | None,
    timeout: int | None = None,
) -> httpx.Client:
    auth = SOAuth(token_tag) if token_tag else None
    return httpx.Client(base_url=host, auth=auth, timeout=httpx.Timeout(timeout or 60))


class ClientSettings(BaseSettings):
    """
    Main settings for the hippo API client. Used to configure:

    1. API access (key and host)
    2. Caching (path to cache(s))
    3. Verbosity.
    """

    host: str = "http://localhost:8000"
    "The hostname of the HIPPO service you are connected to"
    token_tag: str | None = None
    "The tag associated with the API key for the hippo API to use"
    verbose: bool = False
    "Verbosity control: set to true for extra info"
    use_multipart_upload: bool = False
    "The size of the multipart upload parts in bytes. If set to zero, no multipart uploads will be used"
    client_timeout: int = 60
    "The timeout for the client in seconds. Default is 60 seconds (up from the httpx default of 5)"

    default_readers: list[str] = []
    "Default readers for new collections and products"
    default_writers: list[str] = []
    "Default writers for new collections and products"

    caches: list[Cache] = []

    model_config = SettingsConfigDict(
        json_file=("config.json", "~/.hippo.conf"), env_prefix="hippo_"
    )

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls: BaseSettings,
        init_settings: PydanticBaseSettingsSource,
        env_settings: PydanticBaseSettingsSource,
        dotenv_settings: PydanticBaseSettingsSource,
        file_secret_settings: PydanticBaseSettingsSource,
    ) -> tuple[PydanticBaseSettingsSource, ...]:
        return (
            init_settings,
            dotenv_settings,
            env_settings,
            JsonConfigSettingsSource(settings_cls),
            file_secret_settings,
        )

    @property
    def cache(self) -> MultiCache:
        """
        Return a MultiCache object for the caches.
        """
        return MultiCache(caches=self.caches)

    @property
    def client(self) -> Client:
        """
        Return a Client object for the API.
        """
        return Client(token_tag=self.token_tag, host=self.host, timeout=self.client_timeout)

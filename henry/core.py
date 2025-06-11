from hippometa import ALL_METADATA_TYPE
from .product import LocalProduct, RemoteProduct
from hippoclient.core import ClientSettings, Client as AuthenticatedClient
from httpx import Client
from rich.console import Console


class Henry:
    settings: ClientSettings
    client: Client
    console: Console

    def __init__(self, *, settings: ClientSettings | None = None, console: Console | None = None):
        self.settings = settings or ClientSettings()
        self.console = console or Console(quiet=(not self.settings.verbose))
        self.client = AuthenticatedClient(host=self.settings.host, token_tag=self.settings.token_tag)

        return

    def new_product(
        self,
        name: str,
        description: str,
        metadata: ALL_METADATA_TYPE,
        **kwargs,
    ) -> LocalProduct:
        return LocalProduct(name=name, description=description, metadata=metadata, **kwargs)
    
    def upload_product(
        self, product: LocalProduct, skip_preflight: bool = False
    ) -> str:
        return product._upload(
            client=self.client,
            console=self.console,
            skip_preflight=skip_preflight
        )
    
    def get_product(
        self, id: str
    ) -> RemoteProduct:
        return
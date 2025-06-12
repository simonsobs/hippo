from httpx import Client
from rich.console import Console

from hippoclient.core import Client as AuthenticatedClient
from hippoclient.core import ClientSettings
from hippometa import ALL_METADATA_TYPE

from .product import LocalProduct, RemoteProduct, ProductInstance
from .collection import LocalCollection, CollectionInstance


class Henry:
    settings: ClientSettings
    client: Client
    console: Console

    def __init__(
        self, *, settings: ClientSettings | None = None, console: Console | None = None
    ):
        self.settings = settings or ClientSettings()
        self.console = console or Console(quiet=(not self.settings.verbose))
        self.client = AuthenticatedClient(
            host=self.settings.host, token_tag=self.settings.token_tag
        )

        return

    def new_product(
        self,
        name: str,
        description: str,
        metadata: ALL_METADATA_TYPE,
        **kwargs,
    ) -> LocalProduct:
        return LocalProduct(
            name=name, description=description, metadata=metadata, **kwargs
        )
    
    def new_collection(
        self,
        name: str,
        description: str,
        products: list[ProductInstance] | None = None,
        collections: list[CollectionInstance] | None = None,
    ) -> LocalCollection:
        return LocalCollection(
            name=name,
            description=description,
            products=products,
            collections=collections
        )

    def push(
        self, item: LocalProduct | LocalCollection, skip_preflight: bool = False
    ) -> str:
        return item._upload(
            client=self.client, console=self.console, skip_preflight=skip_preflight
        )


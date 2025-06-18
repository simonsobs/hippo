from httpx import Client
from rich.console import Console

from henry.source import LocalSource
from hippoclient.caching import MultiCache
from hippoclient.core import Client as AuthenticatedClient
from hippoclient.core import ClientSettings
from hippometa import ALL_METADATA_TYPE

from .collection import CollectionInstance, LocalCollection
from .product import LocalProduct, ProductInstance, RemoteProduct


class Henry:
    settings: ClientSettings
    client: Client
    console: Console
    cache: MultiCache

    def __init__(
        self,
        *,
        settings: ClientSettings | None = None,
        console: Console | None = None,
    ):
        self.settings = settings or ClientSettings()
        self.console = console or Console(quiet=(not self.settings.verbose))
        self.client = AuthenticatedClient(
            host=self.settings.host, token_tag=self.settings.token_tag
        )
        self.cache = self.settings.cache
        self.readers = self.settings.default_readers
        self.writers = self.settings.default_writers

        return

    def new_product(
        self,
        name: str,
        description: str,
        metadata: ALL_METADATA_TYPE,
        sources: dict[str, LocalSource] | None = None,
    ) -> LocalProduct:
        return LocalProduct(
            name=name, description=description, metadata=metadata, sources=sources or {}
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
            products=products or [],
            collections=collections or [],
        )

    def push(
        self, item: LocalProduct | LocalCollection, skip_preflight: bool = False
    ) -> str:
        return item._upload(
            client=self.client,
            console=self.console,
            skip_preflight=skip_preflight,
            readers=self.readers,
            writers=self.writers,
        )

    def pull_product(
        self, product_id: str, realize_sources: bool = True
    ) -> RemoteProduct:
        return RemoteProduct.pull(
            product_id=product_id,
            client=self.client,
            cache=self.cache,
            console=self.console,
            realize_sources=realize_sources,
        )

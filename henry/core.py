from pathlib import Path

from httpx import Client
from pydantic import ValidationError
from rich.console import Console

from henry.source import LocalSource
from hippoclient.caching import MultiCache
from hippoclient.core import Client as AuthenticatedClient
from hippoclient.core import ClientSettings
from hippoclient.product import (
    cache as cache_product,
)
from hippoclient.product import (
    download as download_product,
)
from hippoclient.tools import slugify as apply_slugify
from hippometa import ALL_METADATA_TYPE

from .collection import (
    CollectionInstance,
    FilteredCollection,
    LocalCollection,
    RemoteCollection,
)
from .product import LocalProduct, ProductInstance, RemoteProduct, RevisionProduct


class Henry:
    settings: ClientSettings
    client: Client
    console: Console
    cache: MultiCache
    slugify: bool

    def __init__(
        self,
        *,
        settings: ClientSettings | None = None,
        console: Console | None = None,
        slugify: bool = False,
    ):
        self.settings = settings or ClientSettings()
        self.console = console or Console(quiet=(not self.settings.verbose))
        self.client = AuthenticatedClient(
            host=self.settings.host, token_tag=self.settings.token_tag
        )
        self.cache = self.settings.cache
        self.readers = self.settings.default_readers
        self.writers = self.settings.default_writers
        self.slugify = slugify

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
        self,
        item: LocalProduct | LocalCollection | RevisionProduct | RemoteCollection,
        skip_preflight: bool = False,
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

    def read_product(
        self, directory: str | Path, allow_incomplete: bool = True
    ) -> RemoteProduct:
        return RemoteProduct.read(
            directory=directory, allow_incomplete=allow_incomplete
        )

    def pull_collection(
        self,
        collection_id: str,
        realize_sources: bool = True,
        pull_children: bool = True,
    ) -> RemoteCollection:
        return RemoteCollection.pull(
            collection_id=collection_id,
            client=self.client,
            cache=self.cache,
            console=self.console,
            pull_children=pull_children,
            realize_sources=realize_sources,
        )

    def read_collection(
        self, directory: str | Path, allow_incomplete: bool = True
    ) -> RemoteCollection | FilteredCollection:
        try:
            return RemoteCollection.read(
                directory=directory, allow_incomplete=allow_incomplete
            )
        except ValidationError:
            return FilteredCollection.read(
                directory=directory, allow_incomplete=allow_incomplete
            )

    def download_product(
        self, product_id: str, directory: str | Path, slugs: list[str] | None = None
    ) -> Path:
        return download_product(
            client=self.client,
            id=product_id,
            directory=Path(directory),
            console=self.console,
            slugs=slugs,
            slugify=self.slugify,
        )

    def realize(
        self,
        item: RemoteCollection | RemoteProduct | FilteredCollection,
        slugs: list[str] | None = None,
    ):
        """
        Realize the collection or product by ensuring that it is cached.
        """

        if isinstance(item, RemoteProduct):
            sources = cache_product(
                client=self.client,
                cache=self.cache,
                console=self.console,
                id=item.product_id,
                slugs=slugs,
            )

            item = item.model_copy(
                update={
                    "sources": {
                        slug: item.sources[slug].model_copy(
                            update={"path": path, "cached": True}
                        )
                        for slug, path in sources.items()
                    }
                }
            )
        elif isinstance(item, (RemoteCollection, FilteredCollection)):
            new_collections = [self.realize(c, slugs=slugs) for c in item.collections]
            new_products = [self.realize(p, slugs=slugs) for p in item.products]

            item = item.model_copy(
                update={"collections": new_collections, "products": new_products}
            )

        return item

    def checkout(
        self,
        item: RemoteCollection | RemoteProduct | FilteredCollection,
        slugs: list[str] | None = None,
        directory: str | Path = Path("."),
    ):
        """
        Checkout the collection or product by downloading it to the local filesystem.
        Collections are stored in a named subdirectory with collection.json metadata.
        """
        directory = Path(directory)
        directory.mkdir(parents=True, exist_ok=True)

        if isinstance(item, RemoteProduct):
            path = self.download_product(
                product_id=item.product_id,
                directory=directory,
                slugs=slugs,
            )

            return self.read_product(directory=path)
        elif isinstance(item, (RemoteCollection, FilteredCollection)):
            name = apply_slugify(item.name) if self.slugify else item.name
            directory /= name
            directory.mkdir(parents=True, exist_ok=True)

            new_collections = [
                self.checkout(child, slugs=slugs, directory=directory)
                for child in item.collections
            ]
            new_products = [
                self.checkout(product, slugs=slugs, directory=directory)
                for product in item.products
            ]

            item = item.model_copy(
                update={
                    "collections": new_collections,
                    "products": new_products,
                    "name": name,
                }
            )

            with open(directory / "collection.json", "w") as handle:
                handle.write(item.model_dump_json(indent=2, exclude_none=True))
        else:
            # Fall through for local stuff
            return item

        return item

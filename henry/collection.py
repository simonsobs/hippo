from itertools import chain
from pathlib import Path
from typing import Iterable

import httpx
from pydantic import BaseModel, Field
from rich.console import Console

from henry.product import ProductInstance, RemoteProduct
from hippoclient import collections, relationships
from hippoclient.caching import MultiCache
from hipposerve.api.models.relationships import ReadCollectionResponse

from .exceptions import (
    CollectionIncompleteError,
    PreflightFailedError,
    ProductIncompleteError,
)


class CollectionInstance(BaseModel):
    collection_id: str | None

    pass


class LocalCollection(CollectionInstance):
    """
    A local coollection, created before pushing up to HIPPO. Can include
    LocalProduct instances that also haven't been pushed up, and other
    LocalCollection instances.
    """

    collection_id: str | None = None
    name: str
    description: str
    products: list[ProductInstance] = []
    collections: list[CollectionInstance] = []
    readers: list[str] = []
    writers: list[str] = []

    def __get_global_index(self, key: int, /) -> tuple[str, int]:
        if key < 0:
            return self.__get_global_index(self.__len__() + key)
        elif key < len(self.products):
            return "p", key
        elif key < self.__len__():
            return "c", key - len(self.products)
        else:
            raise IndexError(f"Index {key} invalid for object of size {self.__len__()}")

    def __repr__(self):
        return (
            f"LocalCollection(name='{self.name}', description='{self.description}', "
            f"products=[{', '.join([x.__repr__() for x in self.products])}], "
            f"collections=[{', '.join([x.__repr__() for x in self.collections])}])"
        )

    def __str__(self):
        return (
            f"{self.name} ({self.description}) collection with {len(self.products)} "
            f"products and {len(self.collections)} child collections"
        )

    def __len__(self) -> int:
        return len(self.products) + len(self.collections)

    def __getitem__(self, key: int, /) -> CollectionInstance | ProductInstance:
        arr, index = self.__get_global_index(key)
        if arr == "p":
            return self.products[index]
        else:
            return self.collections[index]

    def __iter__(self) -> Iterable[CollectionInstance | ProductInstance]:
        return chain(self.products, self.collections)

    def __reversed__(self) -> Iterable[ProductInstance | CollectionInstance]:
        return chain(self.collections.__reversed__(), self.products.__reversed__())

    def __contains__(self, item: CollectionInstance | ProductInstance, /):
        match item:
            case CollectionInstance():
                self.collections.__contains__(item)
            case ProductInstance():
                self.products.__contains__(item)
            case _:
                raise TypeError(
                    f"Only collections or products are members of collections, found {type(item)}"
                )

    def append(self, value: CollectionInstance | ProductInstance, /):
        match value:
            case CollectionInstance():
                self.collections.append(value)
            case ProductInstance():
                self.products.append(value)
            case _:
                raise TypeError(
                    f"Only collections or products may be appended to a collection, found {type(value)}"
                )

    def extend(self, iterable: Iterable[CollectionInstance | ProductInstance], /):
        for a in iterable:
            self.append(a)

    def pop(self, key: int, /) -> CollectionInstance | ProductInstance:
        arr, index = self.__get_global_index(key)
        if arr == "p":
            return self.products.pop(index)
        else:
            return self.collections.pop(index)

    def remove(self, value, /):
        match value:
            case CollectionInstance():
                self.collections.remove(value)
            case ProductInstance():
                self.products.remove(value)
            case _:
                raise TypeError(
                    f"Only collections or products may be part of a collection, found {type(value)}"
                )

    def preflight(self):
        """
        Run a pre-flight check on this collection. This checks that:

        a) The collection has a valid name and description.
        b) Runs preflight checks for all connected products.
        c) Runs preflight checks for all connected collections.
        """

        if self.collection_id:
            # We've already flown!
            return

        for preflightable in self:
            preflightable.preflight()

        if len(self.name) < 2 or not isinstance(self.name, str):
            raise PreflightFailedError(
                f"Name: {self.name} is not a valid name; ensure it is at least 2 characters and a valid string"
            )

        if len(self.description) < 2 or not isinstance(self.description, str):
            raise PreflightFailedError(
                f"Description: {self.description} is not a valid description; ensure it is at least 2 characters and a valid string"
            )

    def _upload(
        self,
        client: httpx.Client,
        console: Console,
        skip_preflight: bool = False,
        readers: list[str] | None = None,
        writers: list[str] | None = None,
    ):
        if self.collection_id:
            # We've already been uploaded!
            return self.colleciton_id

        if not skip_preflight:
            # This runs _all_ preflight checks - for all connected collections and products.
            self.preflight()

        self.collection_id = collections.create(
            client=client,
            name=self.name,
            description=self.description,
            readers=readers,
            writers=writers,
            console=console,
        )

        product_ids_to_connect = [
            x._upload(
                client=client,
                console=console,
                readers=readers,
                writers=writers,
                skip_preflight=True,
            )
            for x in self.products
        ]

        for product_id in product_ids_to_connect:
            collections.add(
                client=client,
                id=self.collection_id,
                product=product_id,
                console=console,
            )

        # Recurse!
        child_collection_ids_to_connect = [
            x._upload(
                client=client,
                console=console,
                skip_preflight=True,
                readers=readers,
                writers=writers,
            )
            for x in self.collections
        ]

        for collection_id in child_collection_ids_to_connect:
            relationships.add_child_collection(
                client=client,
                parent=self.collection_id,
                child=collection_id,
                console=console,
            )

        return self.collection_id


class RemoteCollection(CollectionInstance):
    """
    A remote collection, created by pushing from HIPPO.
    """

    collection_id: str
    name: str
    description: str
    products: list[ProductInstance] = []
    collections: list[CollectionInstance] = []
    owner: str
    readers: list[str] = []
    writers: list[str] = []

    original_name: str
    original_description: str
    original_product_ids: set[str] = Field(default_factory=set)
    original_collection_ids: set[str] = Field(default_factory=set)

    @classmethod
    def pull(
        cls,
        collection_id: str,
        client: httpx.Client,
        cache: MultiCache,
        console: Console,
        pull_children: bool = True,
        realize_sources: bool = True,
    ) -> "RemoteCollection":
        collection = collections.read(client=client, id=collection_id, console=console)

        if realize_sources:
            # Ensure it's cached
            collections.cache(
                client=client,
                cache=cache,
                id=collection_id,
                console=console,
            )

        if pull_children:
            products = [
                RemoteProduct.pull(
                    product_id=str(x.id),
                    client=client,
                    cache=cache,
                    console=console,
                    realize_sources=realize_sources,
                )
                for x in collection.products
            ]
            child_collections = [
                RemoteCollection.pull(
                    collection_id=str(x.id),
                    client=client,
                    cache=cache,
                    console=console,
                    realize_sources=realize_sources,
                    pull_children=pull_children,
                )
                for x in collection.child_collections
            ]
        else:
            products = []
            child_collections = []

        return cls(
            collection_id=str(collection.id),
            name=collection.name,
            description=collection.description,
            products=products,
            owner=collection.owner,
            collections=child_collections,
            readers=collection.readers,
            writers=collection.writers,
            original_name=collection.name,
            original_description=collection.description,
            original_product_ids={str(p.id) for p in collection.products},
            original_collection_ids={str(c.id) for c in collection.child_collections},
        )

    @classmethod
    def read(cls, directory: Path | str, allow_incomplete: bool) -> "RemoteCollection":
        """
        Read a collection that was serialized to disk, usually with the
        `henry collection download $ID` command.
        """
        directory = Path(directory)

        with open(directory / "collection.json", "r") as handle:
            core_metadata = ReadCollectionResponse.model_validate_json(handle.read())

        products = []

        for product in core_metadata.products:
            try:
                products.append(
                    RemoteProduct.read(
                        directory / product.name, allow_incomplete=allow_incomplete
                    )
                )
            except FileNotFoundError:
                if not allow_incomplete:
                    raise CollectionIncompleteError(
                        f"Product {product.name} not found, consider re-downloading "
                        "or setting allow_incomplete=True"
                    )
            except ProductIncompleteError as e:
                if not allow_incomplete:
                    raise CollectionIncompleteError(
                        f"Collection not complete due to error reading {product.name}: {e}"
                    )

        collections = []

        for collection in core_metadata.child_collections:
            try:
                collections.append(
                    RemoteCollection.read(
                        directory / collection.name, allow_incomplete=allow_incomplete
                    )
                )
            except FileNotFoundError:
                if not allow_incomplete:
                    raise CollectionIncompleteError(
                        f"Child collection {collection.name} not found, consider "
                        "re-downloading or setting allow_incomplete=True"
                    )
            except CollectionIncompleteError as e:
                if not allow_incomplete:
                    raise e

        return cls(
            collection_id=str(core_metadata.id),
            name=core_metadata.name,
            description=core_metadata.description,
            products=products,
            owner=core_metadata.owner,
            collections=collections,
            readers=core_metadata.readers,
            writers=core_metadata.writers,
            original_name=core_metadata.name,
            original_description=core_metadata.description,
            original_product_ids={str(p.id) for p in core_metadata.products},
            original_collection_ids={
                str(c.id) for c in core_metadata.child_collections
            },
        )

    def __get_global_index(self, key: int, /) -> tuple[str, int]:
        if key < 0:
            return self.__get_global_index(self.__len__() + key)
        elif key < len(self.products):
            return "p", key
        elif key < self.__len__():
            return "c", key - len(self.products)
        else:
            raise IndexError(f"Index {key} invalid for object of size {self.__len__()}")

    def __repr__(self):
        return (
            f"RemoteCollection(name='{self.name}', description='{self.description}', "
            f"products=[{', '.join([x.__repr__() for x in self.products])}], "
            f"collections=[{', '.join([x.__repr__() for x in self.collections])}])"
        )

    def __str__(self):
        return (
            f"{self.name} ({self.description}) collection with {len(self.products)} "
            f"products and {len(self.collections)} child collections"
        )

    def __len__(self) -> int:
        return len(self.products) + len(self.collections)

    def __getitem__(self, key: int, /) -> CollectionInstance | ProductInstance:
        arr, index = self.__get_global_index(key)
        if arr == "p":
            return self.products[index]
        else:
            return self.collections[index]

    def __iter__(self) -> Iterable[CollectionInstance | ProductInstance]:
        return chain(self.products, self.collections)

    def __reversed__(self) -> Iterable[ProductInstance | CollectionInstance]:
        return chain(self.collections.__reversed__(), self.products.__reversed__())

    def __contains__(self, item: CollectionInstance | ProductInstance, /):
        match item:
            case CollectionInstance():
                self.collections.__contains__(item)
            case ProductInstance():
                self.products.__contains__(item)
            case _:
                raise TypeError(
                    f"Only collections or products are members of collections, found {type(item)}"
                )

    def append(self, value: CollectionInstance | ProductInstance, /):
        match value:
            case CollectionInstance():
                self.collections.append(value)
            case ProductInstance():
                self.products.append(value)
            case _:
                raise TypeError(
                    f"Only collections or products may be appended to a collection, found {type(value)}"
                )

    def extend(self, iterable: Iterable[CollectionInstance | ProductInstance], /):
        for a in iterable:
            self.append(a)

    def pop(self, key: int, /):
        raise RuntimeError(
            "Cannot remove items from a remote collection. If you need a custom "
            "list, create a LocalCollection with what you need instead"
        )

    def remove(self, value, /):
        raise RuntimeError(
            "Cannot remove items from a remote collection. If you need a custom "
            "list, create a LocalCollection with what you need instead"
        )

    def preflight(self):
        """
        Run a pre-flight check on this collection. This checks that:

        a) The collection has a valid name and description.
        b) Runs preflight checks for all connected products.
        c) Runs preflight checks for all connected collections.
        """

        if self.collection_id:
            # We've already flown!
            return

        for preflightable in self:
            preflightable.preflight()

        if len(self.name) < 2 or not isinstance(self.name, str):
            raise PreflightFailedError(
                f"Name: {self.name} is not a valid name; ensure it is at least 2 characters and a valid string"
            )

        if len(self.description) < 2 or not isinstance(self.description, str):
            raise PreflightFailedError(
                f"Description: {self.description} is not a valid description; ensure it is at least 2 characters and a valid string"
            )

    def _upload(
        self,
        client: httpx.Client,
        console: Console,
        skip_preflight: bool = False,
        readers: list[str] | None = None,
        writers: list[str] | None = None,
    ):
        # Cannot do the usual skip as there's no 'revision' system for
        # collections. So we must check first whether any of our children
        # actually need to be uploaded. Because we know that this is a
        # "RemoteCollection", too, there's no need to skip anything as
        # we never actually upload 'self', only children.

        if not skip_preflight:
            # This runs _all_ preflight checks - for all connected collections and products.
            self.preflight()

        for product in self.products:
            product._upload(
                client=client,
                console=console,
                skip_preflight=skip_preflight,
                readers=readers,
                writers=writers,
            )

        product_ids_to_connect = [
            p.product_id
            for p in self.products
            if p.product_id not in self.original_product_ids
        ]

        for product_id in product_ids_to_connect:
            collections.add(
                client=client,
                id=self.collection_id,
                product=product_id,
                console=console,
            )

        for collection in self.collections:
            collection._upload(
                client=client,
                console=console,
                skip_preflight=skip_preflight,
                readers=readers,
                writers=writers,
            )

        # Recurse!
        child_collection_ids_to_connect = [
            c.collection_id
            for c in self.collections
            if c.collection_id not in self.original_collection_ids
        ]

        for collection_id in child_collection_ids_to_connect:
            relationships.add_child_collection(
                client=client,
                parent=self.collection_id,
                child=collection_id,
                console=console,
            )

        return self.collection_id

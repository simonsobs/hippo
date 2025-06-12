from itertools import chain
from typing import Iterable

import httpx
from rich.console import Console

from henry.product import ProductInstance
from hippoclient import collections, relationships

from .exceptions import PreflightFailedError


class CollectionInstance:
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
    products: list[ProductInstance]
    collections: list[CollectionInstance]

    def __init__(
        self,
        name: str,
        description: str,
        products: list[ProductInstance] | None = None,
        collections: list[CollectionInstance] | None = None,
    ):
        self.name = name
        self.description = description
        self.products = products or []
        self.collections = collections or []

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
            f"products=[{", ".join([x.__repr__() for x in self.products])}], "
            f"collections=[{", ".join([x.__repr__() for x in self.collections])}])"
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
        self, client: httpx.Client, console: Console, skip_preflight: bool = False
    ):
        if self.collection_id:
            # We've already been uploaded!
            return self.colleciton_id

        if not skip_preflight:
            # This runs _all_ preflight checks - for all connected collecitons and products.
            self.preflight()

        self.collection_id = collections.create(
            client=client, name=self.name, description=self.description, console=console
        )

        product_ids_to_connect = [
            x._upload(client=client, console=console, skip_preflight=True)
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
            x._upload(client=client, console=console, skip_preflight=True)
            for x in self.collections
        ]

        for collection_id in child_collection_ids_to_connect:
            relationships.add_child_collection(
                client=client,
                parent=self.collection_id,
                child=collection_id,
                console=console,
            )

        return

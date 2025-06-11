# from abc import ABC, abstractmethod
from pathlib import Path

from henry.source import LocalSource
import httpx
from rich.console import Console
from hippoclient import product as product_client
from hippometa import ALL_METADATA_TYPE

class InvalidSlugError(KeyError):
    pass

class PreflightFailedError(Exception):
    pass

class ProductInstance():
    pass


class LocalProduct(ProductInstance):
    """
    A local product, created before pushing up to HIPPO. This includes references
    to local files that are not yet ingested into the HIPPO system.
    """
    name: str
    description: str
    metadata: ALL_METADATA_TYPE
    sources: dict[str, LocalSource]

    def __init__(self, name: str, description: str, metadata: ALL_METADATA_TYPE, **kwargs):
        self.name = name
        self.description = description
        self.metadata = metadata
        self.sources = {}

        for k, v in kwargs:
            self.add_source(slug=k, path=v)

    def __handle_key_error(self, key: str):
        if key in self.metadata.valid_slugs:
            raise InvalidSlugError(
                f"Slug {key} is valid for this metadata type, but not present in this object"
            )
        else:
            raise InvalidSlugError(
                f"Slug {key} not in valid list: {self.metadata.valid_slugs}"
            )

    def keys(self):
        return self.sources.keys()
    
    def values(self):
        return self.sources.values()
    
    def items(self):
        return self.sources.items()
    
    def get(self, key, default=None, /):
        return self.sources.get(key, default)
    
    def clear(self):
        return self.sources.clear()
    
    def setdefault(self, key, default=None, /):
        if key not in self.metadata.valid_slugs:
            self.__handle_key_error(key=key)

        return self.sources.setdefault(key, default)
    
    def pop(self, key):
        try:
            return self.sources.pop(key)
        except KeyError:
            self.__handle_key_error(key=key)
    
    def popitem(self):
        try:
            return self.sources.popitem()
        except KeyError:
            raise InvalidSlugError(
                "No slugs left to pop (gross!)"
            )
    
    def copy(self):
        new = LocalProduct(
            name=self.name,
            description=self.description,
            metadata=self.metadata
        )

        new.sources = self.sources.copy()

        return new
    
        
    def __len__(self) -> int:
        return self.sources.__len__()

    def __getitem__(self, key):
        try:
            return self.sources.__getitem__(key)
        except KeyError:
            self.__handle_key_error(key=key)

    def __setitem__(self, key, value):
        if key not in self.metadata.valid_slugs:
            self.__handle_key_error(key=key)

        if isinstance(value, LocalSource):
            self.sources.__setitem__(key, value)
        elif isinstance(value, (str, Path)):
            self.sources.__setitem__(key, LocalSource(
                path=Path(value), slug=key, description=None
            ))
        else:
            raise TypeError(
                f"Value for key '{key}' must be a LocalSource, str, or Path, not {type(value).__name__}"
            )
        
    def __delitem__(self, key):
        try:
            self.sources.__delitem__(key)
        except KeyError:
            self.__handle_key_error(key=key)

    def __missing__(self, key):
        self.__handle_key_error(key=key)

    def __iter__(self):
        return self.sources.__iter__()
    
    def __reversed__(self):
        return self.sources.__reversed__()
    
    def __contains__(self, key):
        return self.sources.__contains__(key)
    
    def __repr__(self):
        return (
            f"LocalProduct(name='{self.name}', description='{self.description}', "
            f"metadata={self.metadata.__repr__()}, "
            f"{', '.join([f'{x}={y.__repr__()}' for x, y in self.sources.items()])})"
        )
    
    def __str__(self):
        return (
            f"{self.name} ({self.description}) -- {self.metadata.__str__()} "
            f"-- Sources: {", ".join([x.__str__() for x in self.sources.values()])}"
        )

    def preflight(self):
        """
        Run a pre-flight check on this product. This checks that:

        a) The product has a valid name and description.
        b) That each source has a valid slug, name, and description.
        c) That each source's path points to an existing valid file.

        If any check fails, we raise a PreflightFailedError.
        """

        if len(self.name) < 2 or not isinstance(self.name, str):
            raise PreflightFailedError(
                f"Name: {self.name} is not a valid name; ensure it is at least 2 characters and a valid string"
            )

        if len(self.description) < 2 or not isinstance(self.description, str):
            raise PreflightFailedError(
                f"Description: {self.description} is not a valid description; ensure it is at least 2 characters and a valid string"
            )
        
        for slug, source in self.sources.items():
            if slug not in self.metadata.valid_slugs:
                raise PreflightFailedError(
                    f"Slug {slug} not valid for upload for metadata type {type(self.metadata).__name__}"
                )
            if source.slug not in self.metadata.valid_slugs:
                raise PreflightFailedError(
                    f"Slug {source.slug} not valid for upload for metadata type {type(self.metadata).__name__}"
                )
            if source.description and len(source.description) >= 2 and isinstance(source.description, str):
                raise PreflightFailedError(
                    f"Description for source {source.slug} is not valid; ensure it is at least 2 characters and a valid string"
                )
            if len(source.name) < 2 or not isinstance(source.name, str):
                raise PreflightFailedError(
                    f"Name for source {source.slug} is not valid; ensure it is at least 2 characters and a valid string"
                )
            if not source.path.exists():
                raise PreflightFailedError(
                    f"Source {source.slug} has non-existent source file at {source.path}"
                )
        
        return


    def __upload(self, client: httpx.Client, console: Console, skip_preflight: bool = False) -> str:
        if not skip_preflight:
            self.preflight()

        remote_id = product_client.create(
            client=client,
            name=self.name,
            description=self.description,
            metadata=self.metadata,
            sources={
                x: y.path for x, y in self.sources.items()
            },
            source_descriptions={
                x: y.description for x, y in self.sources.items()
            },
            console=Console
        )
        return remote_id


class RemoteProduct(ProductInstance):
    """
    A remote product, created by pulling down from HIPPO. This includes references
    to 'remote' files - either those in a cache or in-memory after download.
    """
    
    pass
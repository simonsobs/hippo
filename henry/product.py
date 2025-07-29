# from abc import ABC, abstractmethod
from pathlib import Path

import httpx
from pydantic import BaseModel, Field
from rich.console import Console

from henry.source import LocalSource, RemoteSource
from hippoclient import product as product_client
from hippoclient.caching import MultiCache
from hippoclient.product import ProductMetadata
from hippometa import ALL_METADATA_TYPE

from .exceptions import InvalidSlugError, PreflightFailedError


class ProductInstance(BaseModel):
    pass

    def _upload(
        self,
        client: httpx.Client,
        console: Console,
        skip_preflight: bool = False,
        readers: list[str] | None = None,
        writers: list[str] | None = None,
    ) -> str:
        return


class LocalProduct(ProductInstance):
    """
    A local product, created before pushing up to HIPPO. This includes references
    to local files that are not yet ingested into the HIPPO system.
    """

    product_id: str | None = None
    name: str
    description: str
    metadata: ALL_METADATA_TYPE
    sources: dict[str, LocalSource] = {}
    readers: list[str] = []
    writers: list[str] = []

    def model_post_init(self, __context):
        for k, v in self.sources.items():
            v.slug = k
            self[k] = v

        return super().model_post_init(__context)

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
            raise InvalidSlugError("No slugs left to pop (gross!)")

    def copy(self):
        new = LocalProduct(
            name=self.name, description=self.description, metadata=self.metadata
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
            self.sources.__setitem__(
                key, LocalSource(path=Path(value), slug=key, description=None)
            )
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
            f"-- Sources: {', '.join([x.__str__() for x in self.sources.values()])}"
        )

    def preflight(self):
        """
        Run a pre-flight check on this product. This checks that:

        a) The product has a valid name and description.
        b) That each source has a valid slug, name, and description.
        c) That each source's path points to an existing valid file.

        If any check fails, we raise a PreflightFailedError.
        """

        if self.product_id:
            # We've already flown!
            return

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
            if (
                not source.description
                or len(source.description) < 2
                or not isinstance(source.description, str)
            ):
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

    def _upload(
        self,
        client: httpx.Client,
        console: Console,
        skip_preflight: bool = False,
        readers: list[str] | None = None,
        writers: list[str] | None = None,
    ) -> str:
        if self.product_id:
            # We've already been uploaded
            return self.product_id

        if not skip_preflight:
            self.preflight()

        remote_id = product_client.create(
            client=client,
            name=self.name,
            description=self.description,
            metadata=self.metadata,
            sources={x: y.path for x, y in self.sources.items()},
            source_descriptions={x: y.description for x, y in self.sources.items()},
            readers=readers,
            writers=writers,
            console=console,
        )
        self.product_id = remote_id
        return remote_id


class RemoteProduct(ProductInstance):
    """
    A remote product, created by pulling down from HIPPO. This includes references
    to 'remote' files - either those in a cache or in-memory after download.
    """

    product_id: str
    name: str
    description: str
    metadata: ALL_METADATA_TYPE
    sources: dict[str, RemoteSource] = {}
    readers: list[str] = []
    writers: list[str] = []

    def model_post_init(self, __context):
        for k, v in self.sources.items():
            v.slug = k

        return super().model_post_init(__context)

    def __handle_key_error(self, key: str):
        if key in self.sources.valid_slugs:
            raise InvalidSlugError(
                f"Slug {key} is valid for this metadata type, but not present in this object"
            )
        else:
            raise InvalidSlugError(
                f"Slug {key} not in valid list: {self.metadata.valid_slugs}"
            )

    @classmethod
    def pull(
        cls,
        product_id: str,
        client: httpx.Client,
        cache: MultiCache,
        console: Console,
        realize_sources: bool = True,
    ) -> "RemoteProduct":
        product_metadata = product_client.read(
            client=client, id=product_id, console=console
        )

        if realize_sources:
            # Ensure it's cached
            product_client.cache(
                client=client,
                cache=cache,
                id=product_id,
                console=console,
            )

        # Convert the sources
        sources = {
            x: RemoteSource(
                slug=x,
                name=y.name,
                description=y.description,
                source_id=y.uuid,
                cache=cache,
                realize=realize_sources,
            )
            for x, y in product_metadata.sources.items()
        }

        return cls(
            product_id=product_id,
            name=product_metadata.name,
            description=product_metadata.description,
            metadata=product_metadata.metadata,
            sources=sources,
            readers=product_metadata.readers,
            writers=product_metadata.writers,
        )

    @classmethod
    def read(
        cls,
        directory: Path | str,
    ) -> "RemoteProduct":
        """
        Read a product that was serialized to disk, usually with the
        `henry prodcut download $ID` command.
        """
        directory = Path(directory)

        with open(directory / "product.json", "r") as handle:
            core_metadata = ProductMetadata.model_validate_json(handle.read())

        sources = {
            x: RemoteSource(
                path=directory / x / y.name,
                slug=x,
                name=y.name,
                description=y.description,
                source_id=y.uuid,
                cached=True,
                cache=None,
                realize=False,
            )
            for x, y in core_metadata.sources.items()
        }

        return cls(
            product_id=str(core_metadata.id),
            name=core_metadata.name,
            description=core_metadata.description,
            metadata=core_metadata.metadata,
            sources=sources,
            readers=core_metadata.readers,
            writers=core_metadata.writers,
        )

    def keys(self):
        return self.sources.keys()

    def values(self):
        return self.sources.values()

    def items(self):
        return self.sources.items()

    def get(self, key, default=None, /):
        return self.sources.get(key, default)

    def copy(self):
        new = RemoteProduct(
            name=self.name, description=self.description, metadata=self.metadata
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
            f"RemoteProduct(name='{self.name}', description='{self.description}', "
            f"metadata={self.metadata.__repr__()}, "
            f"{', '.join([f'{x}={y.__repr__()}' for x, y in self.sources.items()])})"
        )

    def __str__(self):
        return (
            f"{self.name} ({self.description}) -- {self.metadata.__str__()} "
            f"-- Sources: {', '.join([x.__str__() for x in self.sources.values()])}"
        )

    def create_revision(
        self, *, major: bool = False, minor: bool = False, patch: bool = False
    ) -> "RevisionProduct":
        """
        Create a revision of this product. Major, minor, and patch are mutually exclusive
        """

        if sum([major, minor, patch]) != 1:
            raise ValueError("You must choose exactly _one_ of major, minor, or patch")

        if major:
            revision_level = 0
        elif minor:
            revision_level = 1
        else:
            revision_level = 2

        return RevisionProduct(
            revision_of=self,
            revision_level=revision_level,
            readers=self.readers,
            writers=self.writers,
        )

    def preflight(self):
        """
        Preflight pass-through; used when we are adding a collection.
        """
        assert self.product_id, "Cannot preflight a RemoteProduct without a product_id"

    def _upload(self, *args, **kwargs) -> str:
        """
        Upload is not supported for RemoteProduct, as it is a read-only object.
        """
        return self.product_id


class RevisionProduct(ProductInstance):
    """
    A revision of a product, created from a RemoteProduct. Everything starts
    out empty, then if you make changes to this we push those changes to
    the upstream.
    """

    product_id: str | None = None
    revision_of: RemoteProduct

    revision_level: int = Field(ge=0, le=2)
    name: str | None = None
    description: str | None = None
    metadata: ALL_METADATA_TYPE | None = None
    sources: dict[str, LocalSource] = {}

    readers: list[str]
    writers: list[str]

    def model_post_init(self, __context):
        for k, v in self.sources.items():
            v.slug = k
            self[k] = v

        return super().model_post_init(__context)

    def __handle_key_error(self, key: str):
        if key in self.revision_of.metadata.valid_slugs:
            raise InvalidSlugError(
                f"Slug {key} is valid for this metadata type, but not present in this object"
            )
        else:
            raise InvalidSlugError(
                f"Slug {key} not in valid list: {self.revision_of.metadata.valid_slugs}"
            )

    def __setattr__(self, name, value):
        # Cannot change metadata type.
        if name == "metadata" and hasattr(self, "metadata"):
            current = self.revision_of.metadata
            if not isinstance(value, type(current)):
                raise TypeError(
                    f"Cannot change metadata {type(value)} to metadata of type {type(current)}"
                )
        super().__setattr__(name, value)

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
        if key not in self.revision_of.metadata.valid_slugs:
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
            raise InvalidSlugError("No slugs left to pop (gross!)")

    def copy(self):
        new = RevisionProduct(
            revision_of=self.revision_of,
            name=self.name,
            description=self.description,
            metadata=self.metadata,
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
        if key not in self.revision_of.metadata.valid_slugs:
            self.__handle_key_error(key=key)

        if isinstance(value, LocalSource):
            self.sources.__setitem__(key, value)
        elif isinstance(value, (str, Path)):
            self.sources.__setitem__(
                key, LocalSource(path=Path(value), slug=key, description=None)
            )
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

    def __str__(self):
        diff = self._calculate_diff()

        result = ""

        for x, y in diff.items():
            if not y:
                continue

            match y:
                case str():
                    result += (
                        f"{x.capitalize()}: '{getattr(self.revision_of, x)}' -> '{y}'\n"
                    )
                case dict():
                    result += (
                        f"{x.replace('_', ' ').capitalize()}: {', '.join(y.keys())}\n"
                    )
                case BaseModel():
                    left = getattr(self.revision_of, x).model_dump()
                    right = getattr(self, x).model_dump()
                    result += f"{x.capitalize()} diff: "
                    for key in left:
                        if left[key] != right[key]:
                            result += f"[{key}] {left[key]} -> {right[key]}  "
                    result += "\n"

        if not result:
            result = "A revision object with no changes relative to the parent product"
        else:
            result = result.strip()

        return result

    def _calculate_diff(self) -> dict:
        """
        Calculates the diff between this and the RemoteProduct for uploading.
        """

        diff = {}

        for x in ["name", "description", "metadata"]:
            if getattr(self, x) != getattr(self.revision_of, x):
                diff[x] = getattr(self, x)
            else:
                diff[x] = None

        new_sources = {}
        replace_sources = {}

        for source in self:
            if source in self.revision_of:
                replace_sources[source] = self[source]
            else:
                new_sources[source] = self[source]

        diff["new_sources"] = new_sources
        diff["replace_sources"] = replace_sources

        diff.update(
            self._claculate_reader_writer_diff(
                readers=self.readers, writers=self.writers
            )
        )

        return diff

    def _claculate_reader_writer_diff(
        self, readers: list[str], writers: list[str]
    ) -> dict:
        """
        Calculates a difference in readers and writers, if they are provided
        """

        add_readers = set(self.revision_of.readers) - set(readers or [])
        add_writers = set(self.revision_of.writers) - set(writers or [])

        remove_readers = set(readers or []) - set(self.revision_of.readers)
        remove_writers = set(writers or []) - set(self.revision_of.writers)

        diff = {
            "add_readers": add_readers or None,
            "add_writers": add_writers or None,
            "remove_readers": remove_readers or None,
            "remove_writers": remove_writers or None,
        }

        return diff

    def preflight(self):
        diff = self._calculate_diff()

        if self.product_id:
            # We've already flown!
            return

        if not any(diff.values()):
            raise PreflightFailedError(
                "No changes detected in this revision; nothing to upload"
            )

        if name := diff.get("name", None):
            if len(name) < 2 or not isinstance(name, str):
                raise PreflightFailedError(
                    f"Name: {name} is not a valid name; ensure it is at least 2 characters and a valid string"
                )

        if description := diff.get("description", None):
            if len(description) < 2 or not isinstance(description, str):
                raise PreflightFailedError(
                    f"Description: {description} is not a valid description; ensure it is at least 2 characters and a valid string"
                )

        for slug, source in self.sources.items():
            if slug not in self.revision_of.metadata.valid_slugs:
                raise PreflightFailedError(
                    f"Slug {slug} not valid for upload for metadata type {type(self.revision_of.metadata).__name__}"
                )
            if source.slug not in self.revision_of.metadata.valid_slugs:
                raise PreflightFailedError(
                    f"Slug {source.slug} not valid for upload for metadata type {type(self.revision_of.metadata).__name__}"
                )
            if (
                not source.description
                or len(source.description) < 2
                or not isinstance(source.description, str)
            ):
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

    def _upload(
        self,
        client: httpx.Client,
        console: Console,
        skip_preflight: bool = False,
        readers: list[str] | None = None,
        writers: list[str] | None = None,
    ) -> str:
        # Readers/writers are not used!

        if self.product_id:
            # We've already been uploaded
            return self.product_id

        if not skip_preflight:
            self.preflight()

        diff = self._calculate_diff()

        # Break out new and replace sources into paths and descriptions
        new_sources = diff.pop("new_sources", {})
        replace_sources = diff.pop("replace_sources", {})

        diff["new_sources"] = {x: y.path for x, y in new_sources.items()}
        diff["replace_sources"] = {x: y.path for x, y in replace_sources.items()}
        diff["new_source_descriptions"] = {
            x: y.description for x, y in new_sources.items()
        }
        diff["replace_source_descriptions"] = {
            x: y.description for x, y in replace_sources.items()
        }

        remote_id = product_client.update(
            client=client,
            id=self.revision_of.product_id,
            level=self.revision_level,
            **diff,
            console=console,
        )

        self.product_id = remote_id

        return remote_id

# from abc import ABC, abstractmethod
from pathlib import Path

from pydantic import BaseModel, Field

from hippoclient.caching import MultiCache


class SourceInstance(BaseModel):
    path: Path
    slug: str | None = None
    name: str | None = None
    description: str | None = None


class LocalSource(SourceInstance):
    def model_post_init(self, __context):
        if self.name is None:
            self.name = self.path.stem

        return super().model_post_init(__context)

    def __repr__(self):
        return (
            f"LocalSource(path={self.path.__repr__()}, slug='{self.slug}',"
            f"name='{self.name}', description='{self.description}')"
        )

    def __str__(self):
        return f"LocalSource {self.slug} ({self.name}; {self.descrpition}) representing {self.path}"


class RemoteSource(SourceInstance):
    path: Path | None = None

    source_id: str = Field(frozen=True)

    cached: bool = False
    cache: MultiCache | None = None

    realize: bool = False

    def model_post_init(self, __context):
        if self.realize:
            self.path = self.__realize()
        return super().model_post_init(__context)

    def __realize(self) -> Path:
        if self.path is not None:
            return self.path

        if self.cache is not None:
            if path := self.cache.available(self.source_id):
                self.path = path
                self.cached = True
                return self.path
            else:
                raise RuntimeError(
                    "Attempted to realize a source that was not cached; this is not yet supported"
                )
        else:
            raise AttributeError(
                "RemoteSource has no cache set; cannot realize without a cache"
            )

    def __repr__(self):
        return (
            f"RemoteSource(path={self.path.__repr__()}, slug='{self.slug}',"
            f"name='{self.name}', description='{self.description}', cached={self.cached}, "
            f"cache={self.cache.__repr__()}, source_id='{self.source_id}')"
        )

    def __str__(self):
        if self.cached:
            return f"Realized RemoteSource {self.slug} representing {self.path}"
        else:
            return f"Unrealized RemoteSource {self.slug}: {self.name}"

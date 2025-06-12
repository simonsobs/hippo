# from abc import ABC, abstractmethod
from pathlib import Path

from pydantic import BaseModel


class SourceInstance(BaseModel):
    slug: str | None = None
    description: str | None = None


class LocalSource(SourceInstance):
    path: Path
    slug: str | None = None
    name: str | None = None
    description: str | None = None

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
        return f"{self.name} ({self.description}) -- {self.slug}: {self.path}"


class RemoteSource(SourceInstance):
    pass

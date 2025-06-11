# from abc import ABC, abstractmethod
from pathlib import Path

class SourceInstance():
    slug: str
    description: str | None = None


class LocalSource(SourceInstance):

    def __init__(self, path: Path, slug: str, name: str | None = None, description: str | None = None):
        self.path = Path(path)
        self.slug = slug
        self.name = name if name else path.name
        self.description = description

    def __repr__(self):
        return (
            f"LocalSource(path={self.path.__repr__()}, slug='{self.slug}',"
            f"name='{self.name}', description='{self.description}')"
        )
    
    def __str__(self):
        return f"{self.name} ({self.description}) -- {self.slug}: {self.path}"



class RemoteSource(SourceInstance):

    def __init__(self, slug: str, description: str | None = None):
        self.slug = slug
        self.description = description



"""
Base metadata type that all metadata must inherit from
"""

from typing import ClassVar

from pydantic import BaseModel


class BaseMetadata(BaseModel):
    metadata_type: str
    valid_slugs: ClassVar[list[str]] = ["data"]

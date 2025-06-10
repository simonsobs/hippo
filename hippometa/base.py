"""
Base metadata type that all metadata must inherit from
"""

from pydantic import BaseModel, Field


class BaseMetadata(BaseModel):
    metadata_type: str
    valid_slugs: list[str] = Field(["data"], frozen=True)

    pass

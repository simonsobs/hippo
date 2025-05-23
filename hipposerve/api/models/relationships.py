"""
Models for relationships and collections.
"""

import datetime

from beanie import PydanticObjectId
from pydantic import BaseModel

from hippometa import ALL_METADATA_TYPE


class CreateCollectionRequest(BaseModel):
    """
    Request model for creating a collection.
    """

    description: str
    readers: list[str] | None = None
    writers: list[str] | None = None


class UpdateCollectionRequest(BaseModel):
    """
    Request model for updating a collection.
    """

    description: str | None = None
    owner: str | None = None
    add_readers: list[str] | None = None
    remove_readers: list[str] | None = None
    add_writers: list[str] | None = None
    remove_writers: list[str] | None = None


class ReadCollectionProductResponse(BaseModel):
    """
    Response model for reading a product in a collection.
    """

    id: PydanticObjectId
    name: str
    description: str
    owner: str
    version: str
    uploaded: datetime.datetime
    metadata: ALL_METADATA_TYPE


class ReadCollectionCollectionResponse(BaseModel):
    """
    Response model for reading a collection (i.e. a parent or child)
    as part of a collection request.
    """

    id: PydanticObjectId
    name: str
    description: str
    owner: str
    readers: list[str]
    writers: list[str]


class ReadCollectionResponse(BaseModel):
    """
    Response model for reading a collection.
    """

    id: PydanticObjectId
    name: str
    description: str
    products: list[ReadCollectionProductResponse] | None
    child_collections: list[ReadCollectionCollectionResponse] | None = None
    parent_collections: list[ReadCollectionCollectionResponse] | None = None
    readers: list[str]
    writers: list[str]
    owner: str

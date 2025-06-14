"""
Pydantic models for the product API layer.
"""

from beanie import PydanticObjectId
from pydantic import BaseModel

from hippometa import ALL_METADATA_TYPE
from hipposerve.service.product import PostUploadFile, PreUploadFile, ProductMetadata
from hipposerve.service.versioning import VersionRevision


class CreateProductRequest(BaseModel):
    name: str
    description: str
    metadata: ALL_METADATA_TYPE
    sources: dict[str, PreUploadFile]
    product_readers: list[str] = []
    product_writers: list[str] = []
    multipart_batch_size: int = 50 * 1024 * 1024


class CreateProductResponse(BaseModel):
    id: PydanticObjectId
    upload_urls: dict[str, list[str]]


class CompleteProductRequest(BaseModel):
    headers: dict[str, list[dict[str, str]]]
    sizes: dict[str, list[int]]


class ReadProductResponse(BaseModel):
    current_present: bool
    current: str | None
    requested: str
    versions: dict[str, ProductMetadata]


class ReadFilesResponse(BaseModel):
    product: ProductMetadata
    files: dict[str, PostUploadFile]


class UpdateProductRequest(BaseModel):
    name: str | None = None
    description: str | None = None
    metadata: ALL_METADATA_TYPE | None = None
    owner: str | None = None
    new_sources: dict[str, PreUploadFile] = {}
    replace_sources: dict[str, PreUploadFile] = {}
    drop_sources: list[str] = []
    level: VersionRevision | None = VersionRevision.MINOR
    add_readers: list[str] = []
    remove_readers: list[str] = []
    add_writers: list[str] = []
    remove_writers: list[str] = []


class UpdateProductResponse(BaseModel):
    version: str
    id: PydanticObjectId
    upload_urls: dict[str, list[str]]

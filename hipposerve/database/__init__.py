"""
The database access layer for hippo. Uses MongoDB and Beanie.
"""

from datetime import datetime
from enum import Enum

import pymongo
from beanie import BackLink, Document, Indexed, Link, PydanticObjectId
from pydantic import BaseModel, Field

from hippometa import ALL_METADATA_TYPE


class Privilege(Enum):
    # Product management. Note that _for now_ users can update any other
    # user's products.
    CREATE_PRODUCT = "create_products"
    LIST_PRODUCT = "list_products"
    READ_PRODUCT = "read_products"
    DOWNLOAD_PRODUCT = "download_products"
    CONFIRM_PRODUCT = "confirm_product"
    DELETE_PRODUCT = "delete_products"
    UPDATE_PRODUCT = "update_products"

    # Collection management. Note that _for now_ users can update any
    # collection
    CREATE_COLLECTION = "create_collection"
    READ_COLLECTION = "read_collection"
    UPDATE_COLLECTION = "update_collection"
    DELETE_COLLECTION = "delete_collection"
    CREATE_RELATIONSHIP = "create_relationship"
    DELETE_RELATIONSHIP = "delete_relationship"

    # User management
    CREATE_USER = "create_user"
    READ_USER = "read_user"
    UPDATE_USER = "update_user"
    DELETE_USER = "delete_user"
    UPDATE_USER_GROUP = "update_user_group"

    # Group management
    CREATE_GROUP = "create_group"
    READ_GROUP = "read_group"
    UPDATE_GROUP = "update_group"
    DELETE_GROUP = "delete_group"

    # Update Privileges
    UPDATE_PRIVILEGES = "update_privileges"


class CollectionPolicy(Enum):
    # What to do when versions are revved of products.
    # Keep track of all versions of the product in the collection.
    ALL = "all"
    # Keep track of all new versions of the product in the collection.
    # E.g. if v2 is added to a collection, v1 is _not_ but all future
    # versions will be tracked as part of that collection.
    NEW = "new"
    # Keep track of only the 'current' version of the product.
    CURRENT = "current"
    # Keep track of only a 'fixed' version of the product. So if v2 is
    # added to the collection, and v3 is created, only v2 is tracked in
    # the collection.
    FIXED = "fixed"


class ComplianceInformation(BaseModel):
    nersc_username: str | None


class Group(Document):
    name: str
    description: str = None
    access_controls: list[Privilege]


class User(Document):
    name: Indexed(str, unique=True)
    hashed_password: str
    email: str | None
    avatar_url: str | None
    gh_profile_url: str | None
    api_key: str
    privileges: list[Privilege]

    compliance: ComplianceInformation | None
    groups: list[Link[Group]] = []


class FileMetadata(BaseModel):
    """
    Object containing the metadata from a single file.
    """

    id: PydanticObjectId
    name: str
    description: str | None = None
    uploader: str
    uuid: str
    bucket: str
    size: int
    checksum: str
    available: bool = True


class File(Document, FileMetadata):
    def to_metadata(self) -> FileMetadata:
        return FileMetadata(
            id=self.id,
            name=self.name,
            description=self.description,
            uploader=self.uploader,
            uuid=self.uuid,
            bucket=self.bucket,
            size=self.size,
            checksum=self.checksum,
            available=self.available,
        )


class ProductMetadata(BaseModel):
    """
    Object containing the metadata from a single version of a product.
    """

    id: PydanticObjectId

    name: str
    description: str
    metadata: ALL_METADATA_TYPE

    uploaded: datetime
    updated: datetime

    current: bool
    version: str

    sources: list[FileMetadata]
    owner: str

    replaces: str | None

    child_of: list[PydanticObjectId]
    parent_of: list[PydanticObjectId]

    collections: list[PydanticObjectId]


class ProtectedDocument(Document):
    readers: list[str] = Field(default_factory=list)
    writers: list[str] = Field(default_factory=lambda: ["admin"])


class Product(ProtectedDocument, ProductMetadata):
    name: Indexed(str, pymongo.TEXT)

    sources: list[File]
    owner: Link[User]

    replaces: Link["Product"] | None = None

    child_of: list[Link["Product"]] = []
    parent_of: list[BackLink["Product"]] = Field(
        json_schema_extra={"original_field": "child_of"}, default=[]
    )

    collections: list[Link["Collection"]] = []
    collection_policies: list[CollectionPolicy] = []

    def to_metadata(self) -> ProductMetadata:
        return ProductMetadata(
            id=self.id,
            name=self.name,
            description=self.description,
            metadata=self.metadata,
            uploaded=self.uploaded,
            updated=self.updated,
            current=self.current,
            version=self.version,
            sources=[x.to_metadata() for x in self.sources],
            owner=self.owner.name,
            replaces=self.replaces.version if self.replaces is not None else None,
            child_of=[x.id for x in self.child_of],
            parent_of=[x.id for x in self.parent_of],
            collections=[x.id for x in self.collections],
        )


class Collection(Document):
    # TODO: Implement updated time for collections.
    name: Indexed(str, pymongo.TEXT)
    description: str
    products: list[BackLink[Product]] = Field(
        json_schema_extra={"original_field": "collections"}
    )


BEANIE_MODELS = [User, Group, File, Product, Collection]

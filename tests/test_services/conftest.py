"""
The goal of this testing module is simple: just test the
services in isolation, and do not interact at all with the
web endpoints.
"""

import io
from dataclasses import dataclass

import pytest_asyncio
import requests
from beanie import init_beanie
from motor.motor_asyncio import AsyncIOMotorClient

from hipposerve.database import BEANIE_MODELS

### -- Dependency Injection Fixtures -- ###


@pytest_asyncio.fixture(scope="session", autouse=True)
async def database(database_container):
    db = AsyncIOMotorClient(database_container["url"])
    await init_beanie(
        database=db.db_name,
        document_models=BEANIE_MODELS,
    )

    yield db


### -- Data Service Fixtures -- ###


@dataclass
class TestUser:
    display_name: str
    groups: list[str]


@pytest_asyncio.fixture(scope="session")
async def created_user():
    user = TestUser(
        display_name="test_user",
        groups=["test_user"],
    )
    yield user


@pytest_asyncio.fixture(scope="session")
async def created_database_user():
    from hipposerve.service import users

    TEST_USER_NAME = "test_database_user"
    TEST_EMAIL_ADDRESS = "bestemailaddress@ever.com"
    user = await users.create(
        name=TEST_USER_NAME,
        email=TEST_EMAIL_ADDRESS,
    )

    yield user

    await users.delete(name=TEST_USER_NAME)


@pytest_asyncio.fixture(scope="session")
async def created_full_product(database, storage, created_user):
    from hipposerve.service import product

    PRODUCT_NAME = "My Favourite Product"
    PRODUCT_DESCRIPTION = "The best product ever."
    FILE_CONTENTS = b"0x0" * 1024
    SOURCES = [
        product.PreUploadFile(
            name=f"test_{x}.txt",
            size=1024,
            checksum="eh_whatever",
        )
        for x in range(4)
    ]

    data, file_puts = await product.create(
        name=PRODUCT_NAME,
        description=PRODUCT_DESCRIPTION,
        metadata=None,
        sources=SOURCES,
        user_name=created_user.display_name,
        storage=storage,
    )

    assert not await product.confirm(data, storage)

    headers = {}
    sizes = {}

    with io.BytesIO(FILE_CONTENTS) as f:
        for file_name, put in file_puts.items():
            # Must go back to the start or we write 0 bytes!
            f.seek(0)
            headers[file_name] = [requests.put(put[0], f).headers]
            sizes[file_name] = [len(FILE_CONTENTS)]

    await product.complete(
        product=data,
        storage=storage,
        headers=headers,
        sizes=sizes,
    )

    assert await product.confirm(data, storage)

    yield await product.read_by_id(data.id, created_user.groups)

    # Go get it again just in case someone mutated, revved, etc.
    data = await product.read_by_name(
        name=data.name, version=None, groups=created_user.groups
    )

    await product.delete_tree(data, created_user.groups, storage=storage, data=True)


@pytest_asyncio.fixture(scope="session")
async def created_collection(database, created_user):
    from hipposerve.service import collection

    COLLECTION_NAME = "My Favourite Collection"
    COLLECTION_DESCRIPTION = "The best collection ever."

    data = await collection.create(
        name=COLLECTION_NAME,
        user=created_user.display_name,
        description=COLLECTION_DESCRIPTION,
    )

    yield data

    await collection.delete(
        id=data.id,
        groups=created_user.groups,
    )

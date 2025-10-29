"""
The goal of this testing module is simple: just test the
services in isolation, and do not interact at all with the
web endpoints.
"""

import io
import uuid

import pytest_asyncio
import requests
from beanie import init_beanie
from pymongo import AsyncMongoClient
from soauth.toolkit.fastapi import SOUser

import hippometa
from hipposerve.database import BEANIE_MODELS

### -- Dependency Injection Fixtures -- ###


@pytest_asyncio.fixture(scope="session", autouse=True)
async def database(database_container):
    db = AsyncMongoClient(database_container["url"])
    await init_beanie(
        database=db.db_name,
        document_models=BEANIE_MODELS,
    )

    yield db


### -- Data Service Fixtures -- ###


@pytest_asyncio.fixture(scope="session")
async def created_user():
    yield SOUser(
        is_authenticated=True,
        user_id=uuid.uuid4(),
        display_name="test_user",
        full_name="Test User",
        email="test@test_user.com",
        groups=["test_user"],
    )


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
    SOURCES = {
        "data": product.PreUploadFile(
            name="test_1.txt",
            size=1024,
            checksum="eh_whatever",
        )
    }

    data, file_puts = await product.create(
        name=PRODUCT_NAME,
        description=PRODUCT_DESCRIPTION,
        metadata=hippometa.MapSet(pixelisation="equirectangular"),
        sources=SOURCES,
        user_name=created_user.display_name,
        storage=storage,
        product_readers={created_user.display_name},
        product_writers={created_user.display_name},
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

    yield await product.read_by_id(data.id, created_user.groups, scopes=set())

    # Go get it again just in case someone mutated, revved, etc.
    data = await product.read_by_name(
        name=data.name, version=None, groups=created_user.groups, scopes=set()
    )

    await product.delete_tree(
        data, created_user.groups, storage=storage, data=True, scopes=set()
    )


@pytest_asyncio.fixture(scope="session")
async def created_collection(database, created_user):
    from hipposerve.service import collection

    COLLECTION_NAME = "My Favourite Collection"
    COLLECTION_DESCRIPTION = "The best collection ever."

    data = await collection.create(
        name=COLLECTION_NAME,
        user=created_user.display_name,
        description=COLLECTION_DESCRIPTION,
        # Provide r/w access to the user's group (same as name)
        collection_readers=[created_user.display_name],
        collection_writers=[created_user.display_name],
    )

    yield data

    await collection.delete(
        id=data.id,
        groups=created_user.groups,
    )

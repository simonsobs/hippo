import shutil

import pytest
import pytest_asyncio
from testcontainers.minio import MinioContainer
from testcontainers.mongodb import MongoDbContainer
from xprocess import ProcessStarter

from hipposerve.storage import Storage

### -- Database Fixtures -- ###


@pytest_asyncio.fixture(scope="session")
def database_container():
    kwargs = {
        "username": "root",
        "password": "password",
        "port": 27017,
        "dbname": "hippo_test",
    }

    with MongoDbContainer(**kwargs) as container:
        kwargs["url"] = container.get_connection_url()
        yield kwargs


### -- MinIO storage service fixtures -- ###


@pytest.fixture(scope="session")
def storage_container():
    with MinioContainer() as container:
        yield container.get_config()


@pytest.fixture(scope="session")
def storage(storage_container):
    yield Storage(
        url=storage_container["endpoint"],
        access_key=storage_container["access_key"],
        secret_key=storage_container["secret_key"],
    )


### -- Live server fixture -- ###
@pytest.fixture(scope="session")
def server(storage_container, database_container, xprocess):
    settings = {
        "mongo_uri": database_container["url"],
        "minio_url": storage_container["endpoint"],
        "minio_access": storage_container["access_key"],
        "minio_secret": storage_container["secret_key"],
        "title": "Test API",
        "description": "Test API Description",
        "debug": "yes",
        "add_cors": "yes",
        "create_test_user": "yes",
        "test_user_api_key": "TEST_API_KEY",
    }

    class Starter(ProcessStarter):
        pattern = "Uvicorn running on"
        args = [
            shutil.which("uvicorn"),
            "hipposerve.api.app:app",
            "--host",
            "0.0.0.0",
            "--port",
            "44776",
        ]
        timeout = 10
        max_read_lines = 100
        env = {x.upper(): y for x, y in settings.items()}

    xprocess.ensure("api_server", Starter)

    yield {**settings, "url": "http://localhost:44776"}

    xprocess.getinfo("api_server").terminate()

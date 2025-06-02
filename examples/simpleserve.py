"""
A simple hippo server example. This runs with uvicorn,
and serves the web frontend at http://localhost:8000/web.
Containers for Mongo and Minio are provided through
testcontainers; the same patterns are used in testing.
Additionally, you will want to turn off "debug",
"create_test_user", and any other non-production settings.

Once you've started up your server, you can use
the simpleupload.py script to upload any example
products. You should be able to download them and
view their metadata through the web frontend.
"""

import os

### -- Containers -- ###
# In production, you would replace these test containers
# with the actual connection information to separately
# running ones.
import uvicorn
from testcontainers.minio import MinioContainer
from testcontainers.mongodb import MongoDbContainer

database_kwargs = {
    "username": "root",
    "password": "password",
    "port": 27017,
    "dbname": "hippo_test",
}

storage_kwargs = {}


def containers_to_environment(
    database_container: MongoDbContainer, storage_container: MinioContainer
):
    """
    This is required because hippo uses a pydantic-settings
    model for configuration.
    """
    storage_config = storage_container.get_config()
    database_uri = database_container.get_connection_url()

    settings = {
        "mongo_uri": database_uri,
        "minio_url": storage_config["endpoint"],
        "minio_access": storage_config["access_key"],
        "minio_secret": storage_config["secret_key"],
        "title": "Test hippo",
        "description": "Test hippo Description",
        "debug": "yes",
        "add_cors": "yes",
        "web": "yes",
        "create_test_user": "yes",
        "auth_system": "no",
    }

    os.environ.update(settings)


def main():
    with MongoDbContainer(**database_kwargs) as database_container:
        with MinioContainer(**storage_kwargs) as storage_container:
            containers_to_environment(database_container, storage_container)

            from hipposerve.api.app import app

            config = uvicorn.Config(
                app,
                port=8000,
                reload=True,
                reload_dirs=["hipposerve/web", "hipposerve/web/templates"],
            )
            server = uvicorn.Server(config)

            try:
                server.run()
            except KeyboardInterrupt:
                exit(0)


if __name__ == "__main__":
    main()

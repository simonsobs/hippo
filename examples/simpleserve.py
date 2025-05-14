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
from subprocess import check_output

import uvicorn
from testcontainers.minio import MinioContainer
from testcontainers.mongodb import MongoDbContainer

### -- Containers -- ###

# In production, you would replace these test containers
# with the actual connection information to separately
# running ones.

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
        "auth_system": "soauth",
        "soauth_service_url": "https://ingress.simonsobs-identity.production.svc.spin.nersc.org",
        "soauth_app_id": "068248f2-5439-76de-8000-66363113504b",
        "soauth_public_key": "MCowBQYDK2VwAyEAmnENPDKYWU3P8SL0yCSsvOed7t3gMAeALsm5RKzIJfk=",
        "soauth_base_url: str": "http://localhost:8000",
        "soauth_client_secret": "glg2bduzHv9YyUTopd8SAVcwOfDS9vUzfzueXoeWm384uq8WYfdqbMN67Wy4_bdhKdfJpz2zD0dBHwemvrlHng",
        "soauth_key_pair_type": "Ed25519",
        "web_jwt_secret": check_output(["openssl", "rand", "-hex", "32"])
        .decode("utf-8")
        .strip(),
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

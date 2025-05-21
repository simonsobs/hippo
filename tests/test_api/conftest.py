import os

import pytest
from fastapi.testclient import TestClient

### -- Service Mock Fixtures -- ###


@pytest.fixture(scope="module")
def test_api_server(database_container, storage_container):
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
    }
    os.environ.update(settings)

    from hipposerve.api.app import app

    yield app


@pytest.fixture(scope="module")
def test_api_client(test_api_server):
    with TestClient(test_api_server) as client:
        yield client


### -- User Fixtures -- ###


@pytest.fixture(scope="module")
def test_api_user(test_api_client: TestClient):
    TEST_USER_NAME = "default_user"
    """
    TEST_USER_PRIVILEGES = [x.value for x in Privilege]

    response = test_api_client.put(
        f"/users/{TEST_USER_NAME}",
        json={
            "privileges": TEST_USER_PRIVILEGES,
            "password": "password",
            "compliance": None,
            "email": None,
            "avatar_url": None,
            "gh_profile_url": None,
        },
    )

    assert response.status_code == 200
    _ = CreateUserResponse.model_validate(response.json())
    """
    yield TEST_USER_NAME

    # response = test_api_client.delete(f"/users/{TEST_USER_NAME}")
    # assert response.status_code == 200

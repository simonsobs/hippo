"""
Tests the product API endpoints.
"""

import pytest_asyncio
import requests
from fastapi.testclient import TestClient

from hipposerve.api.models.product import (
    CreateProductResponse,
    PreUploadFile,
    ReadFilesResponse,
    ReadProductResponse,
    UpdateProductResponse,
)
from hipposerve.service import versioning


@pytest_asyncio.fixture(scope="function")
def test_api_product(test_api_client: TestClient, test_api_user: str):
    TEST_PRODUCT_NAME = "test_product"
    TEST_PRODUCT_DESCRIPTION = "test_description"
    TEST_PRODUCT_SOURCES = [
        PreUploadFile(name="test_file", size=9, checksum="test_checksum").model_dump(),
        PreUploadFile(name="test_file2", size=9, checksum="test_checksum").model_dump(),
    ]

    response = test_api_client.put(
        "/product/new",
        json={
            "name": TEST_PRODUCT_NAME,
            "description": TEST_PRODUCT_DESCRIPTION,
            "metadata": {"metadata_type": "simple"},
            "sources": TEST_PRODUCT_SOURCES,
        },
    )

    assert response.status_code == 200
    validated = CreateProductResponse.model_validate(response.json())
    product_id = validated.id

    # Now we have to actually upload the files.
    sizes = {x["name"]: [x["size"]] for x in TEST_PRODUCT_SOURCES}
    headers = {x["name"]: [] for x in TEST_PRODUCT_SOURCES}

    for source in TEST_PRODUCT_SOURCES:
        response = requests.put(
            validated.upload_urls[source["name"]][0],
            data=b"test_data",
            allow_redirects=True,
        )

        headers[source["name"]].append(dict(response.headers))

        assert response.status_code == 200

    response = test_api_client.post(
        f"/product/{product_id}/complete",
        json={"headers": headers, "sizes": sizes},
    )

    response.raise_for_status()

    # And check...
    response = test_api_client.post(f"/product/{product_id}/confirm")

    assert response.status_code == 200

    yield TEST_PRODUCT_NAME, product_id

    response = test_api_client.delete(
        f"/product/{product_id}/tree", params={"data": True}
    )
    assert response.status_code == 200


def test_upload_product_again(
    test_api_client: TestClient, test_api_product: tuple[str, str]
):
    response = test_api_client.put(
        "/product/new",
        json={
            "name": test_api_product[0],
            "description": "test_description",
            "metadata": {"metadata_type": "simple"},
            "sources": [
                PreUploadFile(
                    name="test_file", size=100, checksum="test_checksum"
                ).model_dump()
            ],
        },
    )

    assert response.status_code == 409


def test_read_product(
    test_api_client: TestClient,
    test_api_product: tuple[str, str],
    test_api_user: str,
):
    response = test_api_client.get(f"/product/{test_api_product[1]}/files")

    assert response.status_code == 200
    validated = ReadFilesResponse.model_validate(response.json())

    assert validated.product.name == test_api_product[0]
    assert validated.product.id == test_api_product[1]

    # Use the pre-signed url to check that the file data is b"test_data", as expected.
    for source in validated.files:
        response = requests.get(source.url)

        assert response.status_code == 200
        assert response.content == b"test_data"


def test_read_product_tree(
    test_api_client: TestClient,
    test_api_product: tuple[str, str],
    test_api_user: str,
):
    response = test_api_client.get(f"/product/{test_api_product[1]}/tree")

    assert response.status_code == 200
    validated = ReadProductResponse.model_validate(response.json())

    assert test_api_product[0] in [x.name for x in validated.versions.values()]


def test_read_product_not_found(
    test_api_client: TestClient,
):
    response = test_api_client.get("/product/" + "7" * 24)

    assert response.status_code == 404

    # Not a valid ID
    response = test_api_client.get("/product/" + "7" * 23)

    assert response.status_code == 422


def test_update_product(test_api_client: TestClient, test_api_product: tuple[str, str]):
    response = test_api_client.post(
        f"/product/{test_api_product[1]}/update",
        json={
            "description": "new_description",
            "metadata": {"metadata_type": "simple"},
            "level": versioning.VersionRevision.MAJOR.value,
        },
    )

    assert response.status_code == 200
    validated = UpdateProductResponse.model_validate(response.json())
    new_product_id = validated.id

    # Delete that new version
    response = test_api_client.delete(
        f"/product/{new_product_id}",
    )

    assert response.status_code == 200


def test_update_product_invalid_owner(
    test_api_client: TestClient, test_api_product: tuple[str, str]
):
    response = test_api_client.post(
        f"/product/{test_api_product[1]}/update",
        json={
            "description": "new_description",
            "owner": "not_exist_user",
            "level": versioning.VersionRevision.MAJOR.value,
        },
    )

    assert response.status_code == 406


def test_update_product_no_owner_change(
    test_api_client: TestClient, test_api_product: tuple[str, str]
):
    response = test_api_client.post(
        f"/product/{test_api_product[1]}/update",
        json={"description": "New description, again!"},
    )

    assert response.status_code == 200
    new_id = response.json()["id"]

    response = test_api_client.get(f"/product/{new_id}")
    validated = ReadProductResponse.model_validate(response.json())

    assert (
        validated.versions[validated.requested].description == "New description, again!"
    )

    test_api_client.delete(f"/product/{new_id}")


def test_confirm_product(
    test_api_client: TestClient, test_api_product: tuple[str, str]
):
    response = test_api_client.post(f"/product/{test_api_product[1]}/confirm")

    assert response.status_code == 200
    assert response.json() is None

    response = test_api_client.post(
        f"/product/{str(test_api_product[1])[1:] + '0'}/confirm"
    )
    assert response.status_code == 404


def test_confirm_product_product_not_existing(test_api_client):
    TEST_PRODUCT_NAME = "7" * 24
    response = test_api_client.post(f"/product/{TEST_PRODUCT_NAME}/confirm")

    assert response.status_code == 404


def test_product_search(test_api_client: TestClient, test_api_product: tuple[str, str]):
    response = test_api_client.get(f"/product/search/{test_api_product[0]}")

    assert response.status_code == 200
    assert len(response.json()) == 1

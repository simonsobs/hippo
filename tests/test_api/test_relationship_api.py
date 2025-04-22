"""
Tests for the relationship API endpoints, creating, adding to, and deleting collections,
parent/child relationships, and side-by-side relationships.
"""

import pytest_asyncio
from fastapi.testclient import TestClient


@pytest_asyncio.fixture(scope="function")
def test_api_products_for_use(test_api_client: TestClient, test_api_user: str):
    # Creates four separate metadata-only products for testing
    # the collections API with. Also creates a collection to use
    # and destroys it after the test.
    collection_name = "Test Collection"
    response = test_api_client.put(
        f"/relationships/collection/{collection_name}",
        json={"description": "test_description"},
    )

    collection_id = response.json()

    product_names = [f"Product {x}" for x in range(4)]
    product_ids = []

    for name in product_names:
        response = test_api_client.put(
            "/product/new",
            json={
                "name": name,
                "description": "test_description",
                "metadata": {"metadata_type": "simple"},
                "sources": [],
            },
        )
        assert response.status_code == 200
        product_id = response.json()["id"]
        product_ids.append(product_id)

        response = test_api_client.put(
            f"/relationships/collection/{collection_id}/{product_id}",
        )
        assert response.status_code == 200

    yield collection_name, collection_id, product_names, product_ids

    for id in product_ids:
        response = test_api_client.delete(f"/product/{id}", params={"data": True})
        assert response.status_code == 200

    response = test_api_client.delete(f"/relationships/collection/{collection_id}")
    assert response.status_code == 200


def test_read_collection(
    test_api_client: TestClient, test_api_products_for_use: tuple[str, list[str]]
):
    collection_name, collection_id, product_names, product_ids = (
        test_api_products_for_use
    )

    response = test_api_client.get(f"/relationships/collection/{collection_id}")
    assert response.status_code == 200

    assert response.json()["name"] == collection_name
    assert response.json()["description"] == "test_description"
    assert len(response.json()["products"]) == 4

    for product in response.json()["products"]:
        assert product["name"] in product_names
        assert product["description"] == "test_description"
        assert product["owner"] == "admin"


def test_create_child_relationship(test_api_client, test_api_products_for_use):
    collection_name, collection_id, product_names, product_ids = (
        test_api_products_for_use
    )

    response = test_api_client.put(
        f"/relationships/product/{product_ids[0]}/child_of/{product_ids[1]}"
    )
    assert response.status_code == 200

    response = test_api_client.get(f"/product/{product_ids[0]}")
    assert response.status_code == 200
    assert (
        product_ids[1]
        in response.json()["versions"][response.json()["requested"]]["child_of"]
    )

    response = test_api_client.get(f"/product/{product_ids[1]}")
    assert response.status_code == 200
    assert (
        product_ids[0]
        in response.json()["versions"][response.json()["requested"]]["parent_of"]
    )


def test_read_non_existent_collection(test_api_client):
    response = test_api_client.get(f"/relationships/collection/{'7' * 24}")
    assert response.status_code == 404
    assert response.json()["detail"] == "Collection not found."


def test_add_to_non_existent_collection(test_api_client):
    response = test_api_client.put(f"/relationships/collection/{'7' * 24}/{'7' * 24}")
    assert response.status_code == 404

    # Also test removal
    response = test_api_client.delete(
        f"/relationships/collection/{'7' * 24}/{'7' * 24}"
    )
    assert response.status_code == 404


def test_add_non_existent_product_to_existing_collection(
    test_api_client, test_api_products_for_use
):
    response = test_api_client.put(
        f"/relationships/collection/{test_api_products_for_use[1]}/{'7' * 24}"
    )
    assert response.status_code == 404

    # Also test removal
    response = test_api_client.delete(
        f"/relationships/collection/{test_api_products_for_use[1]}/{'7' * 24}"
    )
    assert response.status_code == 404


def test_delete_non_existent_collection(test_api_client):
    response = test_api_client.delete(f"/relationships/collection/{'7' * 24}")
    assert response.status_code == 404
    assert response.json()["detail"] == "Collection not found."


def test_add_child_product_to_non_existent_parent(test_api_client):
    response = test_api_client.put(
        f"/relationships/product/{'7' * 24}/child_of/{'7' * 24}"
    )
    assert response.status_code == 404


def test_remove_child_product_from_non_existent_parent(test_api_client):
    response = test_api_client.delete(
        f"/relationships/product/{'7' * 24}/child_of/{'7' * 24}"
    )
    assert response.status_code == 404


def test_add_child_relationship_for_collection(test_api_client):
    collection_a = test_api_client.put(
        "/relationships/collection/Collection_A",
        json={"description": "test_description"},
    ).json()

    collection_b = test_api_client.put(
        "/relationships/collection/Collection_B",
        json={"description": "test_description"},
    ).json()

    collection_c = test_api_client.put(
        "/relationships/collection/Collection_C",
        json={"description": "test_description"},
    ).json()

    # Make link A -> B -> C

    response = test_api_client.put(
        f"/relationships/collection/{collection_a}/child_of/{collection_b}"
    )
    assert response.status_code == 200

    response = test_api_client.put(
        f"/relationships/collection/{collection_b}/child_of/{collection_c}"
    )
    assert response.status_code == 200

    response = test_api_client.get(f"/relationships/collection/{collection_a}")
    assert response.status_code == 200

    assert len(response.json()["child_collections"]) == 1

    response = test_api_client.get(f"/relationships/collection/{collection_b}")
    assert response.status_code == 200

    assert response.json()["parent_collections"][0]["id"] == collection_a
    assert len(response.json()["child_collections"]) == 1

    response = test_api_client.get(f"/relationships/collection/{collection_c}")
    assert response.status_code == 200
    assert response.json()["parent_collections"][0]["id"] == collection_b

    # Now delete B, and see what happens!

    response = test_api_client.delete(f"/relationships/collection/{collection_b}")
    assert response.status_code == 200

    # We should have NO collection relationships left.
    response = test_api_client.get(f"/relationships/collection/{collection_a}")
    assert response.status_code == 200
    assert len(response.json()["child_collections"]) == 0

    response = test_api_client.get(f"/relationships/collection/{collection_c}")
    assert response.status_code == 200
    assert not response.json()["parent_collections"]

    # Clean up A and C
    response = test_api_client.delete(f"/relationships/collection/{collection_a}")
    assert response.status_code == 200

    response = test_api_client.delete(f"/relationships/collection/{collection_c}")
    assert response.status_code == 200

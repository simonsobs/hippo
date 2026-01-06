"""
Tests for collection uploads.
"""

from pytest import fixture

from henry import Henry
from hippoclient.collections import delete as delete_collection
from hippoclient.product import delete as delete_product
from hippometa import SimpleMetadata


@fixture
def collection_id(client: Henry):
    collection = client.new_collection(
        name="Test Collection A", description="A test collection for you to use!"
    )

    client.push(collection)

    yield collection.collection_id

    delete_collection(id=str(collection.collection_id), client=client.client)


def test_create_collection(collection_id):
    print(collection_id)


def test_add_product_to_existing_collection(collection_id, client: Henry):
    coll = client.pull_collection(
        collection_id, realize_sources=False, pull_children=True
    )

    product = client.new_product(
        name="Test Product",
        description="Test product to be added as a collection member after the fact",
        metadata=SimpleMetadata(),
        sources={},
    )

    coll.append(product)
    client.push(coll)

    product_id = str(product.product_id)

    re_read_coll = client.pull_collection(
        collection_id, realize_sources=True, pull_children=True
    )

    assert re_read_coll.products[0].product_id == product_id

    delete_product(client=client.client, id=product_id)

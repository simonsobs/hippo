from hippoclient import Client, collections


def test_add_reader(server):
    client = Client(
        host=server["url"],
        token_tag=None,
    )

    collection_id = collections.create(
        client=client,
        name="test_collection",
        description="test_description",
    )

    collection = collections.read(client, collection_id)
    assert "test_user" in collection.writers

    collection_id = collections.add_reader(client, collection_id, "test_user_2")
    collection = collections.read(client, collection_id)
    assert "test_user_2" in collection.readers

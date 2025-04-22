"""
An extremely simple example that creates two collections, one which is a child
collection of the other.
"""

from hippoclient import Client
from hippoclient.collections import create as create_collection
from hippoclient.relationships import add_child_collection

API_KEY = "TEST_API_KEY"
SERVER_LOCATION = "http://127.0.0.1:8000"

if __name__ == "__main__":
    client = Client(api_key=API_KEY, host=SERVER_LOCATION, verbose=True)

    child = create_collection(
        client=client,
        name="Child Collection",
        description="This is a child collection",
    )

    parent = create_collection(
        client=client,
        name="Parent Collection",
        description="This is a parent collection",
    )

    add_child_collection(client=client, parent=parent, child=child)

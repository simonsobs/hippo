"""
A simple command-line utility for uploading files
to the example hippo server running at 127.0.0.1:8000.
"""

import os

from hippoclient import Client
from hippoclient.collections import delete

API_KEY = os.getenv("HIPPO_API_KEY")
SERVER_LOCATION = os.getenv("HIPPO_HOST")

if API_KEY is None:
    API_KEY = "TEST_API_KEY"
    SERVER_LOCATION = "http://127.0.0.1:8000"


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="""Delete a product from the example hippo server.""",
    )
    parser.add_argument("id", help="The id of the product to delete")

    args = parser.parse_args()

    client = Client(api_key=API_KEY, host=SERVER_LOCATION)
    print(SERVER_LOCATION)

    delete(client=client, id=args.id)

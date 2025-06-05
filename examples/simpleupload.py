"""
A simple command-line utility for uploading files
to the example hippo server running at 127.0.0.1:8000.
"""

import os
from pathlib import Path

from hippoclient import Client
from hippoclient.product import create

API_KEY = os.getenv("HIPPO_API_KEY")
SERVER_LOCATION = os.getenv("HIPPO_HOST")

if API_KEY is None or SERVER_LOCATION is None:
    API_KEY = "TEST_API_KEY"
    SERVER_LOCATION = "http://127.0.0.1:8000"


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="""Upload a product to the example hippo server.""",
    )
    parser.add_argument("name", help="The name of the product to create")
    parser.add_argument("description", help="The description of the product")
    parser.add_argument(
        "sources", nargs="+", help="The sources (files) to upload.", type=Path
    )

    args = parser.parse_args()

    client = Client(
        api_key=API_KEY, host=SERVER_LOCATION, verbose=True, use_multipart_upload=False
    )

    create(
        client=client,
        name=args.name,
        description=args.description,
        metadata=None,
        sources=args.sources,
        source_descriptions=[None] * len(args.sources),
    )

"""
Methods for interacting with the product layer of the SOPO API.
"""

from pathlib import Path

import xxhash

from sopometa import ALL_METADATA_TYPE
from sopometa.simple import SimpleMetadata
from soposerve.api.models.product import ReadProductResponse
from soposerve.database import ProductMetadata

from .core import Client, console


def create(
    client: Client,
    name: str,
    description: str,
    metadata: ALL_METADATA_TYPE,
    sources: list[Path],
    source_descriptions: list[str | None],
) -> str:
    """
    Create a product in SOPO.

    This is a multi-stage process, where we:

    a) Check and validate the sources.
    b) Make a request to SOPO to create the product.
    c) Upload the sources to the presigned URLs.
    d) Confirm the upload to SOPO.

    Arguments
    ---------
    client: Client
        The client to use for interacting with the SOPO API.
    name : str
        The name of the product.
    description : str
        The description of the product.
    metadata : ALL_METADATA_TYPE
        The metadata of the product, as a validated pydantic model.
    sources : list[Path]
        The list of paths to the sources of the product.

    Returns
    -------
    str
        The ID of the product created.

    Raises
    ------
    httpx.HTTPStatusError
        If a request to the API fails
    """

    # Check and validate the sources.
    assert len(sources) == len(source_descriptions)

    source_metadata = []

    for source, source_description in zip(sources, source_descriptions):
        with source.open("rb") as file:
            file_info = {
                "name": source.name,
                "size": source.stat().st_size,
                "checksum": f"xxh64:{xxhash.xxh64(file.read()).hexdigest()}",
                "description": source_description,
            }
            source_metadata.append(file_info)
            if client.verbose:
                console.print("Successfully validated file:", file_info)

    # Make a request to SOPO to create the product.
    if metadata is None:
        metadata = SimpleMetadata()

    response = client.put(
        "/product/new",
        json={
            "name": name,
            "description": description,
            "metadata": metadata.model_dump(),
            "sources": source_metadata,
        },
    )

    response.raise_for_status()

    this_product_id = response.json()["id"]

    if client.verbose:
        console.print(
            f"Successfully created product {this_product_id} in remote database."
        )

    # Upload the sources to the presigned URLs.
    for source in sources:
        with source.open("rb") as file:
            if client.verbose:
                console.print("Uploading file:", source.name)

            individual_response = client.put(
                response.json()["upload_urls"][source.name], data=file
            )

            individual_response.raise_for_status()

            if client.verbose:
                console.print("Successfully uploaded file:", source.name)

    # Confirm the upload to SOPO.
    response = client.post(f"/product/{this_product_id}/confirm")

    response.raise_for_status()

    if client.verbose:
        console.print(f"Successfully completed upload of {name}.", style="bold green")

    return this_product_id


def read(client: Client, id: str) -> ReadProductResponse:
    """
    Read a product from SOPO.

    Arguments
    ---------
    client: Client
        The client to use for interacting with the SOPO API.
    id : str
        The ID of the product to read.

    Returns
    -------
    ReadProductResponse
        The response from the API.

    Raises
    ------
    httpx.HTTPStatusError
        If a request to the API fails
    """

    response = client.get(f"/product/{id}")

    response.raise_for_status()

    model = ReadProductResponse.model_validate_json(response.content)

    if client.verbose:
        console.print(
            f"Successfully read product {id} ({model.versions[model.requested].name})"
        )

    return model


def delete(client: Client, id: str) -> bool:
    """
    Delete a product from SOPO.

    Arguments
    ----------
    client: Client
        The client to use for interacting with the SOPO API.
    id : str
        The ID of the product to delete.

    Raises
    ------
    httpx.HTTPStatusError
        If a request to the API fails
    """

    response = client.delete(f"/product/{id}")

    response.raise_for_status()

    if client.verbose:
        console.print(f"Successfully deleted product {id}.", style="bold green")

    return True


def search(client: Client, text: str) -> list[ProductMetadata]:
    """
    Search for text information in products (primarily names).

    Arguments
    ----------
    client: Client
        The client to use for interacting with the SOPO API.
    text : str
        The text to search for.

    Returns
    -------
    list[ProductMetadata]
        The list of products that match the search query.

    Raises
    ------
    httpx.HTTPStatusError
        If a request to the API fails
    """

    response = client.get(f"/product/search/{text}")

    response.raise_for_status()

    models = [ProductMetadata.model_validate(x) for x in response.json()]

    if client.verbose:
        console.print(f"Successfully searched for products matching {text}.")

    return models

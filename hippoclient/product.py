"""
Methods for interacting with the product layer of the hippo API.
"""

from pathlib import Path

import xxhash
from tqdm import tqdm

from hippometa import ALL_METADATA_TYPE
from hippometa.simple import SimpleMetadata
from hipposerve.api.models.product import ReadProductResponse
from hipposerve.database import ProductMetadata
from hipposerve.service.product import PostUploadFile, PreUploadFile

from .core import Client, MultiCache, console

MULTIPART_UPLOAD_SIZE = 50 * 1024 * 1024


def create(
    client: Client,
    name: str,
    description: str,
    metadata: ALL_METADATA_TYPE,
    sources: list[Path],
    source_descriptions: list[str | None],
) -> str:
    """
    Create a product in hippo.

    This is a multi-stage process, where we:

    a) Check and validate the sources.
    b) Make a request to hippo to create the product.
    c) Upload the sources to the presigned URLs.
    d) Confirm the upload to hippo.

    Arguments
    ---------
    client: Client
        The client to use for interacting with the hippo API.
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

    # Co-erce sources to paths as they will inevitably be strings...
    sources = [Path(x) for x in sources]

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

    # Make a request to hippo to create the product.
    if metadata is None:
        metadata = SimpleMetadata()

    response = client.put(
        "/product/new",
        json={
            "name": name,
            "description": description,
            "metadata": metadata.model_dump(),
            "sources": source_metadata,
            "mutlipart_batch_size": MULTIPART_UPLOAD_SIZE,
        },
    )

    response.raise_for_status()

    this_product_id = response.json()["id"]

    if client.verbose:
        console.print(
            f"Successfully created product {this_product_id} in remote database."
        )

    responses = {}
    sizes = {}

    # Upload the sources to the presigned URLs.
    for source in sources:
        with source.open("rb") as file:
            if client.verbose:
                console.print("Uploading file:", source.name)

            upload_urls = response.json()["upload_urls"][source.name]
            headers = []
            size = []

            # We need to handle our own redirects because otherwise the head of the file will be incorrect,
            # and we will end up with Content-Length errors.

            with tqdm(
                desc="Uploading",
                total=source.stat().st_size,
                unit="B",
                unit_scale=True,
                unit_divisor=1024,
            ) as t:
                file_position = 0

                for upload_url in upload_urls:
                    retry = True

                    while retry:
                        file.seek(file_position)

                        data = file.read(MULTIPART_UPLOAD_SIZE)

                        individual_response = client.put(
                            upload_url.strip(),
                            data=data,
                            follow_redirects=True,
                        )

                        if individual_response.status_code in [301, 302, 307, 308]:
                            if client.verbose:
                                console.print(
                                    f"Redirected to {individual_response.headers['Location']} from {upload_url}"
                                )
                            upload_url = individual_response.headers["Location"]

                            continue
                        else:
                            retry = False
                            individual_response.raise_for_status()
                            break

                    headers.append(dict(individual_response.headers))
                    size.append(len(data))

                    file_position += MULTIPART_UPLOAD_SIZE
                    t.update(len(data))

            responses[source.name] = headers
            sizes[source.name] = size

            if client.verbose:
                console.print("Successfully uploaded file:", source.name)

    # Close out the upload.
    response = client.post(
        f"/product/{this_product_id}/complete",
        json={"headers": responses, "sizes": sizes},
    )

    response.raise_for_status()

    # Confirm the upload to hippo.
    response = client.post(f"/product/{this_product_id}/confirm")

    response.raise_for_status()

    if client.verbose:
        console.print(f"Successfully completed upload of {name}.", style="bold green")

    return this_product_id


def read_with_versions(client: Client, id: str) -> ReadProductResponse:
    """
    Read a product from hippo by ID. Always returns the requested version,
    without information about other versions.

    Arguments
    ---------
    client: Client
        The client to use for interacting with the hippo API.
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
        console.print(f"Successfully read product {id}")

    return model


def read(client: Client, id: str) -> ProductMetadata:
    """
    Read a product from hippo by ID. Always returns the requested version,
    without information about other versions.

    Arguments
    ---------
    client: Client
        The client to use for interacting with the hippo API.
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

    model = read_with_versions(client, id)

    # This model includes version history. We don't want that.
    model = model.versions[model.requested]

    if client.verbose:
        console.print(f"Successfully read product ({model.name})")

    return model


def update(
    client: Client,
    id: str,
    name: str | None,
    description: str | None,
    level: int,
    metadata: ALL_METADATA_TYPE | None,
    new_sources: list[PreUploadFile] = [],
    replace_sources: list[PreUploadFile] = [],
    drop_sources: list[str] = [],
) -> bool:
    """
    Update a product in hippo.

    Arguments
    ----------
    client: Client
        The client to use for interacting with the hippo API.
    id : str
        The ID of the product to update.
    name : str | None
        The new name of the product.
    description : str | None
        The new description of the product.
    level : int
        The new version level where 0 is major, 1 is minor, and 2 is patch.
    metadata : ALL_METADATA_TYPE
        The new product metadata to update.
    new_sources : list[PreUploadFile]
        A list of new sources to add to the product.
    replace_sources : list[PreUploadFile]
        A list of sources to replace in a product.
    drop_sources : list[str]
        A list of source IDs to delete from a product.

    Raises
    ------
    httpx.HTTPStatusError
        If a request to the API fails
    """

    response = client.post(
        f"/product/{id}/update",
        json={
            "name": name,
            "description": description,
            "level": level,
            "metadata": metadata,
            "new_sources": new_sources,
            "replace_sources": replace_sources,
            "drop_sources": drop_sources,
        },
    )

    response.raise_for_status()

    if client.verbose:
        console.print(f"Successfully updated product {id}.", style="bold green")

    return True


def delete(client: Client, id: str) -> bool:
    """
    Delete a product from hippo.

    Arguments
    ----------
    client: Client
        The client to use for interacting with the hippo API.
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
        The client to use for interacting with the hippo API.
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
        console.print(f"Successfully searched for products matching {text}")

    return models


def cache(client: Client, cache: MultiCache, id: str) -> list[Path]:
    """
    Cache a product from hippo.

    Arguments
    ----------
    client: Client
        The client to use for interacting with the hippo API.
    cache: MultiCache
        The cache to use for storing the product.
    id : str
        The ID of the product to cache.

    Returns
    -------
    list[Path]
        The list of paths to the cached sources.

    Raises
    ------
    httpx.HTTPStatusError
        If a request to the API fails
    CacheNotWriteableError
        If the cache is not writeable
    """

    response = client.get(f"/product/{id}/files")

    response.raise_for_status()

    post_upload_files = [
        PostUploadFile.model_validate(x) for x in response.json()["files"]
    ]

    if client.verbose:
        console.print(f"Successfully read product {id}")

    response_paths = []

    for file in post_upload_files:
        # See if it's already cached.
        try:
            cached = cache.available(file.uuid)
            response_paths.append(cached)

            if client.verbose:
                console.print(f"Found cached file {file.name}", style="green")

            continue
        except FileNotFoundError:
            if client.verbose:
                console.print(
                    f"File {file.name} ({file.uuid}) not found in cache", style="red"
                )
            cached = None

        cached = cache.get(
            id=file.uuid,
            path=file.object_name,
            checksum=file.checksum,
            size=file.size,
            presigned_url=file.url,
        )

        response_paths.append(cached)

        if client.verbose:
            console.print(f"Cached file {file.name} ({file.uuid})", style="yellow")

    return response_paths


def uncache(client: Client, cache: MultiCache, id: str) -> None:
    """
    Clear the cache of a product.

    Arguments
    ----------
    client: Client
        The client to use for interacting with the hippo API.
    cache: MultiCache
        The cache to use for storing the product.
    id : str
        The ID of the product to remove from the cache.
    """

    product = read(client, id)

    for vid, version in product.versions.items():
        for source in version.sources:
            cache.remove(source.uuid)

            if client.verbose:
                console.print(f"Removed file {source.name} ({source.uuid}) from cache")

    return

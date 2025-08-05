"""
Methods for interacting with the product layer of the hippo API.
"""

from pathlib import Path

from httpx import Client, Response
from rich.console import Console
from tqdm import tqdm

from hippoclient.downloads import downloader, file_info
from hippometa import ALL_METADATA_TYPE
from hippometa.simple import SimpleMetadata
from hipposerve.api.models.product import ReadProductResponse
from hipposerve.database import ProductMetadata
from hipposerve.service.product import PostUploadFile, PreUploadFile

from .core import MultiCache

MULTIPART_UPLOAD_SIZE = 50 * 1024 * 1024


def __upload_sources(
    initial_response: Response,
    client: Client,
    sources: dict[str, PreUploadFile],
    this_product_id: str,
    console: Console | None = None,
) -> dict[str, list[dict[str, str]]]:
    responses = {}
    sizes = {}

    # Upload the sources to the presigned URLs.
    for source in sources.values():
        with source.open("rb") as file:
            if console:
                console.print("Uploading file:", source.name)

            upload_urls = initial_response.json()["upload_urls"][source.name]
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
                            content=data,
                            follow_redirects=True,
                            auth=None,
                            # Blocks are 50 MB so may timeout on slow connections
                            # (httpx defaults to 5 seconds)
                            timeout=120.0,
                        )

                        if individual_response.status_code in [301, 302, 307, 308]:
                            if console:
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

            if console:
                console.print("Successfully uploaded file:", source.name)

    # Close out the upload.
    response = client.post(
        f"/product/{this_product_id}/complete",
        json={"headers": responses, "sizes": sizes},
    )

    response.raise_for_status()

    return response.json()


def create(
    client: Client,
    name: str,
    description: str,
    metadata: ALL_METADATA_TYPE,
    sources: dict[str, Path],
    source_descriptions: dict[str, str | None],
    readers: list[str] | None = None,
    writers: list[str] | None = None,
    console: Console | None = None,
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
    sources : dict[str, Path]
        The list of paths to the sources of the product keyed by their slug.
    source_descriptions : dict[str, str | None]
        The descriptions of the sources keyed by their slug.
    readers : list[str] | None, optional
        A list of groups that can read the product.
    writers : list[str] | None, optional
        A list of groups that can write to the product.
    console : Console, optional
        The rich console to print to.

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
    sources = {x: Path(y) for x, y in sources.items()}

    source_metadata = {}

    for slug in sources:
        filename = sources[slug]
        desc = source_descriptions[slug]

        source_metadata[slug] = file_info(filename, desc)

        if console:
            console.print("Successfully validated file:", source_metadata[slug])

    # Make a request to hippo to create the product.
    if metadata is None:
        metadata = SimpleMetadata()

    content = {
        "name": name,
        "description": description,
        "metadata": metadata.model_dump(mode="json"),
        "sources": source_metadata,
        "mutlipart_batch_size": MULTIPART_UPLOAD_SIZE,
    }

    if readers is not None:
        content["product_readers"] = readers
    if writers is not None:
        content["product_writers"] = writers

    response = client.put("/product/new", json=content)

    response.raise_for_status()

    this_product_id = response.json()["id"]

    __upload_sources(
        initial_response=response,
        client=client,
        sources=sources,
        this_product_id=this_product_id,
        console=console,
    )

    if console:
        console.print(
            f"Successfully created product {this_product_id} in remote database."
        )

    # Confirm the upload to hippo.
    response = client.post(f"/product/{this_product_id}/confirm")

    response.raise_for_status()

    if console:
        console.print(f"Successfully completed upload of {name}.", style="bold green")

    return this_product_id


def read_with_versions(
    client: Client, id: str, console: Console | None = None
) -> ReadProductResponse:
    """
    Read a product from hippo by ID. Always returns the requested version,
    without information about other versions.

    Arguments
    ---------
    client: Client
        The client to use for interacting with the hippo API.
    id : str
        The ID of the product to read.
    console : Console, optional
        The rich console to print to.

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

    if console:
        console.print(f"Successfully read product {id}")

    return model


def read(client: Client, id: str, console: Console | None = None) -> ProductMetadata:
    """
    Read a product from hippo by ID. Always returns the requested version,
    without information about other versions.

    Arguments
    ---------
    client: Client
        The client to use for interacting with the hippo API.
    id : str
        The ID of the product to read.
    console : Console, optional
        The rich console to print to.

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

    if console:
        console.print(f"Successfully read product ({model.name})")

    return model


def update(
    client: Client,
    id: str,
    name: str | None,
    description: str | None,
    level: int,
    metadata: ALL_METADATA_TYPE | None,
    new_sources: dict[str, Path] | None = None,
    new_source_descriptions: dict[str, str | None] | None = None,
    replace_sources: dict[str, Path] | None = None,
    replace_source_descriptions: dict[str, str | None] | None = None,
    drop_sources: list[str] | None = None,
    add_readers: list[str] | None = None,
    remove_readers: list[str] | None = None,
    add_writers: list[str] | None = None,
    remove_writers: list[str] | None = None,
    console: Console | None = None,
) -> str:
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
    new_sources : dict[str, Path] | None
        A list of new sources to add to the product.
    new_source_descriptions : dict[str, str | None] | None
        A list of descriptions for the new sources keyed by their slug.
    replace_sources : dict[str, Path] | None
        A list of sources to replace in a product.
    replace_source_descriptions : dict[str, str | None] | None
        A list of descriptions for the sources to replace keyed by their slug.
    drop_sources : list[str]
        A list of source IDs to delete from a product.
    console : Console, optional
        The rich console to print to.

    Returns
    -------
    str
        The ID of the updated product.

    Raises
    ------
    httpx.HTTPStatusError
        If a request to the API fails
    """

    new_source_metadata = {}

    for slug in (new_sources or {}).keys():
        filename = new_sources[slug]
        desc = new_source_descriptions[slug]

        new_source_metadata[slug] = file_info(filename, desc)

        if console:
            console.print("Successfully validated file:", new_source_metadata[slug])

    replace_source_metadata = {}
    for slug in (replace_sources or {}).keys():
        filename = replace_sources[slug]
        desc = replace_source_descriptions[slug]

        replace_source_metadata[slug] = file_info(filename, desc)

        if console:
            console.print("Successfully validated file:", replace_source_metadata[slug])

    response = client.post(
        f"/product/{id}/update",
        json={
            "name": name,
            "description": description,
            "level": level,
            "metadata": metadata.model_dump() if metadata else None,
            "new_sources": new_source_metadata,
            "replace_sources": replace_source_metadata,
            "drop_sources": drop_sources or [],
            "add_readers": add_readers or [],
            "remove_readers": remove_readers or [],
            "add_writers": add_writers or [],
            "remove_writers": remove_writers or [],
        },
    )

    response.raise_for_status()

    this_product_id = response.json()["id"]

    __upload_sources(
        initial_response=response,
        client=client,
        sources={**(new_sources or {}), **(replace_sources or {})},
        this_product_id=this_product_id,
        console=console,
    )

    if console:
        console.print(f"Successfully updated product {id}.", style="bold green")

    return this_product_id


def delete(client: Client, id: str, console: Console | None = None) -> bool:
    """
    Delete a product from hippo.

    Arguments
    ----------
    client: Client
        The client to use for interacting with the hippo API.
    id : str
        The ID of the product to delete.
    console : Console, optional
        The rich console to print to.

    Raises
    ------
    httpx.HTTPStatusError
        If a request to the API fails
    """

    response = client.delete(f"/product/{id}")

    response.raise_for_status()

    if console:
        console.print(f"Successfully deleted product {id}.", style="bold green")

    return True


def search(
    client: Client, text: str, console: Console | None = None
) -> list[ProductMetadata]:
    """
    Search for text information in products (primarily names).

    Arguments
    ----------
    client: Client
        The client to use for interacting with the hippo API.
    text : str
        The text to search for.
    console : Console, optional
        The rich console to print to.

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

    if console:
        console.print(f"Successfully searched for products matching {text}")

    return models


def cache(
    client: Client, cache: MultiCache, id: str, console: Console | None = None
) -> list[Path]:
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
    console : Console, optional
        The rich console to print to.

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

    post_upload_files = {
        x: PostUploadFile.model_validate(y) for x, y in response.json()["files"].items()
    }

    if console:
        console.print(f"Successfully read product {id}")

    response_paths = []

    for file in post_upload_files.values():
        # See if it's already cached.
        try:
            cached = cache.available(file.uuid)
            response_paths.append(cached)

            if console:
                console.print(f"Found cached file {file.name}", style="green")

            continue
        except FileNotFoundError:
            if console:
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

        if console:
            console.print(f"Cached file {file.name} ({file.uuid})", style="yellow")

    return response_paths


def download(
    client: Client,
    id: str,
    directory: Path,
    console: Console | None = None,
    slugs: list[str] | None = None,
) -> Path:
    """
    Download a product from HIPPO onto the local filesystem, storing the data
    in the provided 'directory'. Data is stored as follows:

    directory/Product Name
        product.json < Metadata for this product
        slug/
          file.fits
        data/
          file2.fits

    So inside the provided directory, we create a new directory with the product's
    name. In there, each slug is stored in its own directory.

    Arguments
    ----------
    client: Client
        The client to use for interacting with the hippo API.
    id : str
        The ID of the product to download.
    console : Console, optional
        The rich console to print to.
    slugs : list[str], optional
        Only download specific slugs.

    Returns
    -------
    Path
        The path to the cached sources.

    Raises
    ------
    httpx.HTTPStatusError
        If a request to the API fails
    FileNotFoundError
        If the directory does not exist or is not a directory.
    """

    response = client.get(f"/product/{id}/files")

    response.raise_for_status()

    post_upload_files = {
        x: PostUploadFile.model_validate(y) for x, y in response.json()["files"].items()
    }

    metadata = ProductMetadata.model_validate(response.json()["product"])

    if console:
        console.print(f"Successfully read product {id}")

    product_directory = directory / metadata.name

    # Raises FileNotFoundError if `directory` does not exist.
    product_directory.mkdir(exist_ok=True, parents=False)

    with open(product_directory / "product.json", "w") as handle:
        handle.write(metadata.model_dump_json(indent=2))

        if console:
            console.print(f"Successfully wrote metadata for product {metadata.name}")

    for source_slug, source_data in post_upload_files.items():
        if slugs and source_slug not in slugs:
            continue

        slug_directory = product_directory / source_slug
        slug_directory.mkdir(exist_ok=True)
        slug_path = slug_directory / source_data.name

        # Check if it's already there and if it matches our checksum
        if slug_path.exists():
            if file_info(slug_path)["checksum"] == source_data.checksum:
                if console:
                    console.print(f"Valid {source_slug} already exists at {slug_path}")
                continue

        downloader(
            presigned_url=source_data.url,
            output_destination=slug_path,
            console=console,
        )

        if console:
            console.print(f"Downloaded slug {source_slug} to {slug_path}")

    return product_directory


def uncache(
    client: Client, cache: MultiCache, id: str, console: Console | None = None
) -> None:
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
    console : Console, optional
        The rich console to print to.
    """

    product = read(client, id)

    for source in product.sources.values():
        cache.remove(source.uuid)

        if console:
            console.print(f"Removed file {source.name} ({source.uuid}) from cache")

    return


def product_add_reader(
    client: Client, id: str, group: str, console: Console | None = None
) -> str:
    response = client.post(
        f"/product/{id}/update",
        json={
            "level": None,
            "add_readers": [group],
        },
    )

    response.raise_for_status()
    this_product_id = response.json()["id"]
    if console:
        console.print(
            f"Successfully added {group} to product {id} readers.", style="bold green"
        )

    return this_product_id


def product_remove_reader(
    client: Client, id: str, group: str, console: Console | None = None
) -> str:
    response = client.post(
        f"/product/{id}/update",
        json={
            "level": None,
            "remove_readers": [group],
        },
    )

    response.raise_for_status()
    this_product_id = response.json()["id"]
    if console:
        console.print(
            f"Successfully removed {group} from product {id} readers.",
            style="bold green",
        )

    return this_product_id


def product_add_writer(
    client: Client, id: str, group: str, console: Console | None = None
) -> str:
    response = client.post(
        f"/product/{id}/update",
        json={
            "level": None,
            "add_writers": [group],
        },
    )

    response.raise_for_status()
    this_product_id = response.json()["id"]
    if console:
        console.print(
            f"Successfully added {group} to product {id} writers.", style="bold green"
        )

    return this_product_id


def product_remove_writer(
    client: Client, id: str, group: str, console: Console | None = None
) -> str:
    response = client.post(
        f"/product/{id}/update",
        json={
            "level": None,
            "remove_writers": [group],
        },
    )

    response.raise_for_status()
    this_product_id = response.json()["id"]
    if console:
        console.print(
            f"Successfully removed {group} from product {id} writers.",
            style="bold green",
        )

    return this_product_id

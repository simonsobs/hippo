"""
Methods for interacting with the collections layer of the hippo API
"""

from pathlib import Path

from httpx import Client
from rich.console import Console

from hipposerve.api.models.relationships import ReadCollectionResponse

from .core import MultiCache
from .product import cache as cache_product
from .product import download as download_product
from .product import uncache as uncache_product
from .tools import slugify as apply_slugify


def create(
    client: Client,
    name: str,
    description: str,
    readers: list[str] | None = None,
    writers: list[str] | None = None,
    console: Console | None = None,
) -> str:
    """
    Create a new collection in hippo.

    Arguments
    ---------
    client : Client
        The client to use for interacting with the hippo API.
    name : str
        The name of the collection.
    description : str
        The description of the collection.
    readers : list[str], optional
        A list of groups that can read the collection.
    writers : list[str], optional
        A list of groups that can write to the collection.
    console : Console, optional
        The Console to use to print to.

    Returns
    -------
    str
        The ID of the collection created.

    Raises
    ------
    httpx.HTTPStatusError
        If a request to the API fails
    """

    content = {"description": description}

    if readers is not None:
        content["readers"] = readers
    if writers is not None:
        content["writers"] = writers

    response = client.put(f"/relationships/collection/{name}", json=content)

    response.raise_for_status()

    if console:
        console.print(f"Successfully created collection {name}.", style="bold green")

    return response.json()


def read(
    client: Client, id: str, console: Console | None = None
) -> ReadCollectionResponse:
    """
    Read a collection from hippo.

    Arguments
    ---------
    client: Client
        The client to use for interacting with the hippo API.
    id : str
        The id of the collection to read.
    console : Console, optional
        The Console to use to print to.

    Returns
    -------
    ReadCollectionResponse
        The response from the API.

    Raises
    ------
    httpx.HTTPStatusError
        If a request to the API fails
    """

    response = client.get(f"/relationships/collection/{id}")

    response.raise_for_status()

    model = ReadCollectionResponse.model_validate_json(response.content)

    if console:
        console.print(f"Successfully read collection {model.name} ({id})")

    return model


def add_reader(
    client: Client, id: str, group: str, console: Console | None = None
) -> str:
    response = client.post(
        f"/relationships/collection/{id}", json={"add_readers": [group]}
    )
    response.raise_for_status()
    if console:
        console.print(f"Successfully added {group} to collection {id} readers.")
    this_collection_id = response.json()
    return this_collection_id


def remove_reader(
    client: Client, id: str, group: str, console: Console | None = None
) -> str:
    response = client.post(
        f"/relationships/collection/{id}", json={"remove_readers": [group]}
    )
    response.raise_for_status()
    if console:
        console.print(f"Successfully removed {group} from collection {id} readers.")
    this_collection_id = response.json()
    return this_collection_id


def add_writer(
    client: Client, id: str, group: str, console: Console | None = None
) -> str:
    response = client.post(
        f"/relationships/collection/{id}", json={"add_writers": [group]}
    )
    response.raise_for_status()
    if console:
        console.print(f"Successfully added {group} to collection {id} writers.")
    this_collection_id = response.json()
    return this_collection_id


def remove_writer(
    client: Client, id: str, group: str, console: Console | None = None
) -> str:
    response = client.post(
        f"/relationships/collection/{id}", json={"remove_writers": [group]}
    )
    response.raise_for_status()
    if console:
        console.print(f"Successfully removed {group} from collection {id} writers.")
    this_collection_id = response.json()
    return this_collection_id


def search(
    client: Client, name: str, console: Console | None = None
) -> list[ReadCollectionResponse]:
    """
    Search for collections in hippo.

    Arguments
    ---------
    client: Client
        The client to use for interacting with the hippo API.
    name : str
        The name of the collection to search for.
    console: Console, optional
        The rich console to print to.

    Returns
    -------
    list[ReadCollectionResponse]
        The response from the API.

    Raises
    ------
    httpx.HTTPStatusError
        If a request to the API fails
    """

    response = client.get(f"/relationships/collection/search/{name}")

    response.raise_for_status()

    models = [ReadCollectionResponse.model_validate(x) for x in response.json()]

    if console:
        console.print(f"Successfully searched for collection {name}")

    return models


def add(client: Client, id: str, product: str, console: Console | None = None) -> bool:
    """
    Add a product to a collection in hippo.

    Arguments
    ---------
    client: Client
        The client to use for interacting with the hippo API.
    id : str
        The id of the collection to add the product to.
    product : str
        The id of the product to add to the collection.
    console: Console, optional
        The rich console to print to.

    Raises
    ------
    httpx.HTTPStatusError
        If a request to the API fails
    """

    response = client.put(f"/relationships/collection/{id}/{product}")

    response.raise_for_status()

    if console:
        console.print(
            f"Successfully added product {product} to collection {id}.",
            style="bold green",
        )

    return True


def remove(
    client: Client, id: str, product: str, console: Console | None = None
) -> bool:
    """
    Remove a product from a collection in hippo.

    Arguments
    ---------
    client: Client
        The client to use for interacting with the hippo API.
    name : str
        The id of the collection to remove the product from.
    product : str
        The id of the product to remove from the collection.
    console: Console, optional
        The rich console to print to.

    Raises
    ------
    httpx.HTTPStatusError
        If a request to the API fails
    """

    response = client.delete(f"/relationships/collection/{id}/{product}")

    response.raise_for_status()

    if console:
        console.print(
            f"Successfully removed product {product} from collection {id}.",
            style="bold green",
        )

    return True


def delete(client: Client, id: str, console: Console | None = None) -> bool:
    """
    Delete a collection from hippo.

    Arguments
    ----------
    client: Client
        The client to use for interacting with the hippo API.
    id : str
        The name of the collection to delete.
    console: Console, optional
        The rich console to print to.

    Raises
    ------
    httpx.HTTPStatusError
        If a request to the API fails
    """

    response = client.delete(f"/relationships/collection/{id}")

    response.raise_for_status()

    if console:
        console.print(f"Successfully deleted collection {id}.", style="bold green")

    return True


def cache(
    client: Client, multi_cache: MultiCache, id: str, console: Console | None = None
) -> list[Path]:
    """
    Cache a collection from hippo.

    Arguments
    ---------
    client: Client
        The client to use for interacting with the hippo API.
    cache : MultiCache
        The cache to use for storing the collection.
    id : str
        The id of the collection to cache.
    console: Console, optional
        The rich console to print to.

    Returns
    -------
    list[Path]
        The paths to the cached files.

    Raises
    ------
    httpx.HTTPStatusError
        If a request to the API fails
    CacheNotWriteableError
        If the cache is not writeable
    """

    collection = read(client, id)

    paths = []

    for product in collection.products:
        paths += cache_product(client, multi_cache, str(product.id))

    for child in collection.child_collections:
        paths += cache(client, multi_cache, str(child.id))

    return paths


def download(
    client: Client,
    id: str,
    directory: Path,
    console: Console | None = None,
    slugify: bool = False,
) -> Path:
    """
    Download a collection from HIPPO onto the local filesystem, storing the data
    in the provided 'directory'. Data is stored as follows:

    directory/Collection Name
      collection.json < Metadata for this collection
      Product Name/
        ... < See product.download
      Child Collection/
        collection.json
        Product Name/
          ... < See product.download

    Inside the provided directory, we create a new directory with the collection name.
    In there we store each product and child collection recursively, and store
    the metadata for the collection as `collection.json`.

    Arguments
    ---------
    client: Client
        The client to use for interacting with the hippo API
    id: str
        The ID of the collection to download.
    directory: Path
        The directory to download the collection into.
    console : Console, optional
        The rich console to print to.
    slugify : bool, optional
        Whether to convert names to valid 'slugs'.

    Returns
    -------
    Path
        The path to the cached collection.

    Raises
    ------
    httpx.HTTPStatusError
        If a request to the API fails
    FileNotFoundError
        If the directory does not exist or is not a directory.
    """

    collection = read(client, id)

    if slugify:
        collection.name = apply_slugify(collection.name)

    collection_directory = directory / collection.name

    collection_directory.mkdir(exist_ok=True, parents=False)

    with open(collection_directory / "collection.json", "w") as handle:
        handle.write(collection.model_dump_json(indent=2))

        if console:
            console.print(
                f"Successfully wrote metadata for collection {collection.name}"
            )

    for product in collection.products:
        download_product(
            client=client,
            id=product.id,
            directory=collection_directory,
            console=console,
            slugify=slugify,
        )

    for child in collection.child_collections:
        download(
            client=client,
            id=child.id,
            directory=collection_directory,
            console=console,
            slugify=slugify,
        )

    return collection_directory


def uncache(
    client: Client, cache: MultiCache, id: str, console: Console | None = None
) -> None:
    """
    Remove a collection from local caches.

    Arguments
    ---------
    client: Client
        The client to use for interacting with the hippo API.
    cache : MultiCache
        The cache to use for storing the collection.
    id : str
        The id of the collection to uncache.
    console: Console, optional
        The rich console to print to.

    Raises
    ------
    CacheNotWriteableError
        If the cache is not writeable
    """

    collection = read(client, id)

    for product in collection.products:
        uncache_product(client, cache, product.id)

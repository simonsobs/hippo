"""
Methods for interacting with the collections layer of the hippo API
"""

from pathlib import Path

from hipposerve.api.models.relationships import ReadCollectionResponse

from .core import Client, MultiCache, console
from .product import cache as cache_product
from .product import uncache as uncache_product


def create(
    client: Client,
    name: str,
    description: str,
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

    Returns
    -------
    str
        The ID of the collection created.

    Raises
    ------
    httpx.HTTPStatusError
        If a request to the API fails
    """

    response = client.put(
        f"/relationships/collection/{name}", json={"description": description}
    )

    response.raise_for_status()

    if client.verbose:
        console.print(f"Successfully created collection {name}.", style="bold green")

    return response.json()


def read(
    client: Client,
    id: str,
) -> ReadCollectionResponse:
    """
    Read a collection from hippo.

    Arguments
    ---------
    client: Client
        The client to use for interacting with the hippo API.
    id : str
        The id of the collection to read.

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

    if client.verbose:
        console.print(f"Successfully read collection {model.name} ({id})")

    return model


def add_reader(client: Client, id: str, user: str) -> str:
    response = client.post(
        f"/relationships/collection/{id}", json={"add_readers": [user]}
    )
    response.raise_for_status()
    if client.verbose:
        console.print(f"Successfully added {user} to collection {id} readers.")
    this_collection_id = response.json()
    return this_collection_id


def remove_reader(client: Client, id: str, user: str) -> str:
    response = client.post(
        f"/relationships/collection/{id}", json={"remove_readers": [user]}
    )
    response.raise_for_status()
    if client.verbose:
        console.print(f"Successfully removed {user} from collection {id} readers.")
    this_collection_id = response.json()
    return this_collection_id


def add_writer(client: Client, id: str, user: str) -> str:
    response = client.post(
        f"/relationships/collection/{id}", json={"add_writers": [user]}
    )
    response.raise_for_status()
    if client.verbose:
        console.print(f"Successfully added {user} to collection {id} writers.")
    this_collection_id = response.json()
    return this_collection_id


def remove_writer(client: Client, id: str, user: str) -> str:
    response = client.post(
        f"/relationships/collection/{id}", json={"remove_writers": [user]}
    )
    response.raise_for_status()
    if client.verbose:
        console.print(f"Successfully removed {user} from collection {id} writers.")
    this_collection_id = response.json()
    return this_collection_id


def search(client: Client, name: str) -> list[ReadCollectionResponse]:
    """
    Search for collections in hippo.

    Arguments
    ---------
    client: Client
        The client to use for interacting with the hippo API.
    name : str
        The name of the collection to search for.

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

    if client.verbose:
        console.print(f"Successfully searched for collection {name}")

    return models


def add(client: Client, id: str, product: str) -> bool:
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

    Raises
    ------
    httpx.HTTPStatusError
        If a request to the API fails
    """

    response = client.put(f"/relationships/collection/{id}/{product}")

    response.raise_for_status()

    if client.verbose:
        console.print(
            f"Successfully added product {product} to collection {id}.",
            style="bold green",
        )

    return True


def remove(client: Client, id: str, product: str) -> bool:
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

    Raises
    ------
    httpx.HTTPStatusError
        If a request to the API fails
    """

    response = client.delete(f"/relationships/collection/{id}/{product}")

    response.raise_for_status()

    if client.verbose:
        console.print(
            f"Successfully removed product {product} from collection {id}.",
            style="bold green",
        )

    return True


def delete(client: Client, id: str) -> bool:
    """
    Delete a collection from hippo.

    Arguments
    ----------
    client: Client
        The client to use for interacting with the hippo API.
    id : str
        The name of the collection to delete.

    Raises
    ------
    httpx.HTTPStatusError
        If a request to the API fails
    """

    response = client.delete(f"/relationships/collection/{id}")

    response.raise_for_status()

    if client.verbose:
        console.print(f"Successfully deleted collection {id}.", style="bold green")

    return True


def cache(client: Client, cache: MultiCache, id: str) -> list[Path]:
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
        paths += cache_product(client, cache, product.id)

    return paths


def uncache(client: Client, cache: MultiCache, id: str) -> None:
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

    Raises
    ------
    CacheNotWriteableError
        If the cache is not writeable
    """

    collection = read(client, id)

    for product in collection.products:
        uncache_product(client, cache, product.id)

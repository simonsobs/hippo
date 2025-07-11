"""
Methods for adding and removing child relationships between products.
"""

from httpx import Client
from rich.console import Console


def add_child(
    client: Client, parent: str, child: str, console: Console | None = None
) -> bool:
    """
    Add a child relationship between two products.

    Arguments
    ---------
    client : Client
        The client to use for interacting with the hippo API.
    parent : str
        The ID of the parent product.
    child : str
        The ID of the child product.
    console : Console, optional
        The rich console to print to.

    Returns
    -------
    bool
        True if the relationship was added successfully.

    Raises
    ------
    httpx.HTTPStatusError
        If a request to the API fails
    """

    response = client.put(f"/relationships/product/{child}/child_of/{parent}")

    response.raise_for_status()

    if console:
        console.print(
            f"Successfully added child relationship between {parent} and {child}.",
            style="bold green",
        )

    return True


def remove_child(
    client: Client, parent: str, child: str, console: Console | None = None
) -> bool:
    """
    Remove a child relationship between two products.

    Arguments
    ---------
    client : Client
        The client to use for interacting with the hippo API.
    parent : str
        The ID of the parent product.
    child : str
        The ID of the child product.
    console : Console, optional
        The rich console to print to.

    Returns
    -------
    bool
        True if the relationship was removed successfully.

    Raises
    ------
    httpx.HTTPStatusError
        If a request to the API fails
    """

    response = client.delete(f"/relationships/product/{child}/child_of/{parent}")

    response.raise_for_status()

    if console:
        console.print(
            f"Successfully removed child relationship between {parent} and {child}.",
            style="bold green",
        )

    return True


def add_child_collection(
    client: Client, parent: str, child: str, console: Console | None = None
) -> bool:
    """
    Add a child relationship between a collection and another collection.

    Arguments
    ---------
    client : Client
        The client to use for interacting with the hippo API.
    parent : str
        The ID of the parent collection.
    child : str
        The ID of the child collection.
    console : Console, optional
        The rich console to print to.

    Returns
    -------
    bool
        True if the relationship was added successfully.

    Raises
    ------
    httpx.HTTPStatusError
        If a request to the API fails
    """

    response = client.put(f"/relationships/collection/{parent}/child_of/{child}")

    response.raise_for_status()

    if console:
        console.print(
            f"Successfully added child relationship between {parent} and {child}.",
            style="bold green",
        )

    return True


def remove_child_collection(
    client: Client, parent: str, child: str, console: Console | None = None
) -> bool:
    """
    Remove a child relationship between a collection and another collection.

    Arguments
    ---------
    client : Client
        The client to use for interacting with the hippo API.
    parent : str
        The ID of the parent collection.
    child : str
        The ID of the child collection.
    console : Console, optional
        The rich console to print to.

    Returns
    -------
    bool
        True if the relationship was removed successfully.

    Raises
    ------
    httpx.HTTPStatusError
        If a request to the API fails
    """

    response = client.delete(f"/relationships/collection/{child}/child_of/{parent}")

    response.raise_for_status()

    if console:
        console.print(
            f"Successfully removed child relationship between {parent} and {child}.",
            style="bold green",
        )

    return True

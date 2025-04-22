"""
A CLI interface to the hippo client.
"""

import rich
import typer

import hippoclient as sc

from . import helper
from .core import ClientSettings, MultiCache
from .textedit import edit_product

CLIENT: sc.Client
CACHE: MultiCache
CONSOLE = rich.console.Console()

# Meta-setup
APP = typer.Typer()
product_app = typer.Typer(help="Commands for dealing directly with products")
APP.add_typer(product_app, name="product")
collection_app = typer.Typer(help="Commands for dealing with collections")
APP.add_typer(collection_app, name="collection")
cache_app = typer.Typer(
    help="Maintenance commands for the cache. There are also tools for cache management in the product and collection commands."
)
APP.add_typer(cache_app, name="cache")


@product_app.command("read")
def product_read(id: str):
    """
    Read the information of a product by its ID. You can find the relationship
    between product names and IDs through the product search command.
    """
    global CLIENT, CONSOLE

    product = sc.product.read_with_versions(client=CLIENT, id=id)

    product_extracted_version = product.versions[product.requested]

    CONSOLE.print(product_extracted_version.name, style="bold underline color(3)")
    CONSOLE.print(
        "\nVersions: "
        + helper.render_version_list(
            product.versions, product.current, product.requested
        )
    )
    CONSOLE.print(
        rich.markdown.Markdown(product_extracted_version.description.strip("\n"))
    )
    CONSOLE.print(product_extracted_version.metadata)
    CONSOLE.print(helper.render_source_list(product_extracted_version.sources, CACHE))
    CONSOLE.print("\n" + "Relationships" + "\n", style="bold color(2)")
    CONSOLE.print("Collections: " + ", ".join(product_extracted_version.collections))
    if len(product_extracted_version.parent_of) > 0:
        CONSOLE.print("Children: " + ", ".join(product_extracted_version.parent_of))
    if len(product_extracted_version.child_of) > 0:
        CONSOLE.print("Parents: " + ", ".join(product_extracted_version.child_of))


@product_app.command("delete")
def product_delete(id: str):
    """
    Delete a product by its ID.
    """
    global CLIENT
    return sc.product.delete(client=CLIENT, id=id)


@product_app.command("search")
def product_search(text: str):
    """
    Search for products by name.
    """
    global CLIENT, CONSOLE

    response = sc.product.search(client=CLIENT, text=text)

    table = helper.render_product_metadata_list(response)

    CONSOLE.print(table)


@product_app.command("cache")
def product_cache(id: str):
    """
    Cache a product by its ID.
    """
    global CLIENT, CACHE

    response = sc.product.cache(client=CLIENT, cache=CACHE, id=id)

    CONSOLE.print(f"Cached product {id} including {len(response)} files")


@product_app.command("uncache")
def product_uncache(id: str):
    """
    Uncache a product by its ID.
    """
    global CACHE

    sc.product.uncache(client=CLIENT, cache=CACHE, id=id)

    CONSOLE.print(f"Uncached product {id}")


@product_app.command("edit")
def product_edit(id: str):
    """
    Edit a product by its ID.
    """
    global CLIENT

    edit_product(client=CLIENT, id=id)


@collection_app.command("read")
def collection_read(id: str):
    """
    Read the information of a collection by its name.
    """
    global CLIENT, CONSOLE

    collection = sc.collections.read(client=CLIENT, id=id)

    table = helper.render_product_metadata_list(collection.products)

    CONSOLE.print(collection.name + "\n", style="bold underline color(3)")
    CONSOLE.print(rich.markdown.Markdown(collection.description.strip("\n")))
    CONSOLE.print("\n")
    CONSOLE.print(table)


@collection_app.command("search")
def collection_search(name: str):
    """
    Search for collections by name.
    """
    global CLIENT, CONSOLE

    collections = sc.collections.search(client=CLIENT, name=name)

    table = helper.render_collection_metadata_list(collections)

    CONSOLE.print(table)


@collection_app.command("cache")
def collection_cache(id: str):
    """
    Cache a collection by its name.
    """
    global CLIENT, CACHE

    response = sc.collections.cache(client=CLIENT, cache=CACHE, id=id)

    CONSOLE.print(f"Cached collection {id} including {len(response)} files")


@collection_app.command("uncache")
def collection_uncache(id: str):
    """
    Uncache a collection by its name.
    """
    global CACHE

    sc.collections.uncache(client=CLIENT, cache=CACHE, id=id)

    CONSOLE.print(f"Uncached collection {id}")


@cache_app.command("clear")
def cache_clear(uuid: str):
    """
    Clear the cache of a single file, labelled by its UUID (note that product IDs don't work here).
    """
    global CACHE

    for cache in CACHE.caches:
        if cache.writeable:
            sc.caching.clear_single(cache=cache, id=id)
            CONSOLE.print(f"Cleared cache {cache.path} of {id}")


@cache_app.command("clear-all")
def cache_clear_all():
    """
    Clear all caches of all files.
    """
    global CACHE

    for cache in CACHE.caches:
        if cache.writeable:
            sc.caching.clear_all(cache=cache)
            CONSOLE.print(f"Cleared cache {cache.path}")


def main():
    settings = ClientSettings()

    global CLIENT, APP, CACHE

    CLIENT = settings.client
    CACHE = settings.cache

    APP()

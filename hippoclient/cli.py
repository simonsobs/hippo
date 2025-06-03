"""
A CLI interface to the hippo client.
"""

from typing import Annotated

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
dev_app = typer.Typer(
    help="Developer commands, mainly used for running and testing servers during hippo development. For regular use, you can ignore these."
)
APP.add_typer(dev_app, name="dev")


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
    CONSOLE.print(
        "Collections: "
        + ", ".join(str(c) for c in product_extracted_version.collections)
    )
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


@product_app.command("add-reader")
def product_add_reader(id: str, user: str):
    """
    Set the visibility level of a product.
    Example:
    $ hippo product add-reader <product-id> <user>
    """

    global CLIENT
    updated_id = sc.product.product_add_reader(client=CLIENT, id=id, user=user)
    CONSOLE.print(f"Added {user} to {id} readers. New id is {updated_id}")


@product_app.command("remove-reader")
def product_remove_reader(id: str, user: str):
    """
    Set the visibility level of a product.
    Example:
    $ hippo product remove-reader <product-id> <user>
    """

    global CLIENT
    updated_id = sc.product.product_remove_reader(client=CLIENT, id=id, user=user)
    CONSOLE.print(f"Removed {user} from {id} readers. New id is {updated_id}")


@product_app.command("add-writer")
def product_add_writer(id: str, user: str):
    """
    Set the visibility level of a product.
    Example:
    $ hippo product add-writer <product-id> <user>
    """

    global CLIENT
    updated_id = sc.product.product_add_writer(client=CLIENT, id=id, user=user)
    CONSOLE.print(f"Added {user} to {id} writers. New id is {updated_id}")


@product_app.command("remove-writer")
def product_remove_writer(id: str, user: str):
    """
    Set the visibility level of a product.
    Example:
    $ hippo product remove-writer <product-id> <user>
    """

    global CLIENT
    updated_id = sc.product.product_remove_writer(client=CLIENT, id=id, user=user)
    CONSOLE.print(f"Removed {user} from {id} writers. New id is {updated_id}")


@collection_app.command("add-reader")
def collection_add_reader(id: str, user: str):
    """
    Add a reader to a collection.
    """
    global CLIENT
    updated_id = sc.collections.add_reader(client=CLIENT, id=id, user=user)
    CONSOLE.print(f"Added {user} to readers. Collection ID is {updated_id}")


@collection_app.command("remove-reader")
def collection_remove_reader(id: str, user: str):
    """
    Remove a reader from a collection.
    """
    global CLIENT
    updated_id = sc.collections.remove_reader(client=CLIENT, id=id, user=user)
    CONSOLE.print(f"Removed {user} from readers. Collection ID is {updated_id}")


@collection_app.command("add-writer")
def collection_add_writer(id: str, user: str):
    """
    Add a writer to a collection.
    """
    global CLIENT
    updated_id = sc.collections.add_writer(client=CLIENT, id=id, user=user)
    CONSOLE.print(f"Added {user} to writers. Collection ID is {updated_id}")


@collection_app.command("remove-writer")
def collection_remove_writer(id: str, user: str):
    """
    Remove a writer from a collection.
    """
    global CLIENT
    updated_id = sc.collections.remove_writer(client=CLIENT, id=id, user=user)
    CONSOLE.print(f"Removed {user} from writers. Collection ID is {updated_id}")


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


@dev_app.command("serve")
def dev_serve():
    """
    Run a hippo development server, without spinning up dependencies (i.e. you
    will need to have mongo and minio running with appropriate environments set).
    """

    import uvicorn

    from hipposerve.api.app import app

    config = uvicorn.Config(
        app,
        port=8000,
        reload=True,
        reload_dirs=["hipposerve/web", "hipposerve/web/templates"],
    )
    server = uvicorn.Server(config)

    try:
        server.run()
    except KeyboardInterrupt:
        exit(0)


@dev_app.command("run")
def dev_run(
    with_soauth: Annotated[
        bool,
        typer.Option(
            help="Run with SOAuth integration? If not, all requests are mock-authenticated"
        ),
    ] = False,
):
    """
    Run a hippo development server, spinning up dependencies (i.e. we create
    temporary servers and set defaults for all variables that we can).
    """

    import os

    import uvicorn
    from testcontainers.minio import MinioContainer
    from testcontainers.mongodb import MongoDbContainer

    database_kwargs = {
        "username": "root",
        "password": "password",
        "port": 27017,
        "dbname": "hippo_test",
    }

    storage_kwargs = {}

    with MongoDbContainer(**database_kwargs) as database_container:
        with MinioContainer(**storage_kwargs) as storage_container:
            storage_config = storage_container.get_config()
            database_uri = database_container.get_connection_url()

            settings = {
                "mongo_uri": database_uri,
                "minio_url": storage_config["endpoint"],
                "minio_access": storage_config["access_key"],
                "minio_secret": storage_config["secret_key"],
                "title": "Test hippo",
                "description": "Test hippo Description",
                "debug": "yes",
                "add_cors": "yes",
                "web": "yes",
                "auth_system": "soauth" if with_soauth else "None",
            }

            os.environ.update(settings)

            # HIPPO must be imported _after_ updating settings.
            from hipposerve.api.app import app

            config = uvicorn.Config(
                app,
                port=8000,
                reload=True,
                reload_dirs=["hipposerve/web", "hipposerve/web/templates"],
            )
            server = uvicorn.Server(config)

            try:
                server.run()
            except KeyboardInterrupt:
                exit(0)

    return


def main():
    settings = ClientSettings()

    global CLIENT, APP, CACHE

    CLIENT = settings.client
    CACHE = settings.cache

    APP()

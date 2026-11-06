"""
Tests for realizing and checking out products and collections.
"""

import pytest

from henry.source import LocalSource
from hippoclient import collections, product
from hippoclient.caching import MultiCache
from hippometa import MapSet


@pytest.fixture
def remote_collection(client, cache, tmp_path):
    client.cache = MultiCache(caches=[cache])
    products = []
    for name in ["Root product", "Child product"]:
        sources = {}
        for slug in ["map", "ivar"]:
            path = tmp_path / f"{name}-{slug}.txt"
            path.write_text(f"{name} {slug}")
            sources[slug] = LocalSource(path=path, description=f"Test {slug}")
        products.append(
            client.new_product(
                name=name,
                description="A test map product",
                metadata=MapSet(pixelisation="healpix", telescope=name),
                sources=sources,
            )
        )

    child = client.new_collection(
        name="Child collection", description="Nested maps", products=products[1:]
    )
    collection = client.new_collection(
        name="Root collection",
        description="Maps to realize and check out",
        products=products[:1],
        collections=[child],
    )
    client.push(collection)

    yield client.pull_collection(collection.collection_id, realize_sources=False)

    collections.delete(client.client, collection.collection_id)
    collections.delete(client.client, child.collection_id)
    for p in products:
        product.delete(client.client, p.product_id)


@pytest.mark.parametrize("slugs", [None, ["map"], []])
def test_realize_product(remote_collection, client, slugs):
    item = remote_collection.products[0]

    assert client.realize(item, slugs=slugs) is item

    for slug, source in item.sources.items():
        if slugs is None or slug in slugs:
            path = client.cache.available(source.source_id)
            assert path.read_text() == f"Root product {slug}"
        else:
            with pytest.raises(FileNotFoundError):
                client.cache.available(source.source_id)


@pytest.mark.parametrize("filtered", [False, True])
def test_realize_collection(remote_collection, client, filtered):
    item = remote_collection
    if filtered:
        item = item.filter(metadata_filter={"telescope": "Child product"})

    assert client.realize(item, slugs=["map"]) is item

    child = remote_collection.collections[0].products[0]
    assert client.cache.available(child.sources["map"].source_id).exists()
    root_source = remote_collection.products[0].sources["map"]
    if filtered:
        with pytest.raises(FileNotFoundError):
            client.cache.available(root_source.source_id)
    else:
        assert client.cache.available(root_source.source_id).exists()


@pytest.mark.parametrize("slugs", [None, ["map"], []])
def test_checkout_product(remote_collection, client, tmp_path, slugs):
    item = remote_collection.products[0]
    directory = tmp_path / "checkout" / "products"

    checked_out = client.checkout(item, slugs=slugs, directory=str(directory))

    assert checked_out.product_id == item.product_id
    assert checked_out.metadata == item.metadata
    assert checked_out.version == item.version
    assert checked_out.readers == item.readers
    assert checked_out.writers == item.writers
    assert (directory / item.name / "product.json").exists()
    for slug, source in checked_out.sources.items():
        if slugs is None or slug in slugs:
            assert source.cached
            assert source.path.read_text() == f"Root product {slug}"
        else:
            assert not source.cached
            assert not source.path.exists()


@pytest.mark.parametrize("slugify", [False, True])
@pytest.mark.parametrize("slugs", [None, ["map"]])
def test_checkout_collection(remote_collection, client, tmp_path, slugify, slugs):
    client.slugify = slugify
    directory = tmp_path / "checkout"

    assert (
        client.checkout(remote_collection, directory=directory, slugs=slugs)
        is remote_collection
    )

    directory /= "root-collection" if slugify else "Root collection"
    root_name = "root-product" if slugify else "Root product"
    child_name = "child-collection" if slugify else "Child collection"
    product_name = "child-product" if slugify else "Child product"
    root = remote_collection.products[0]
    child = remote_collection.collections[0].products[0]
    assert root.sources["map"].path.parent.parent == directory / root_name
    assert (
        child.sources["map"].path.parent.parent == directory / child_name / product_name
    )
    assert child.sources["map"].path.read_text() == "Child product map"

    downloaded = client.read_collection(directory, allow_incomplete=slugs is not None)
    assert downloaded.collection_id == remote_collection.collection_id
    assert len(downloaded.products) == 1
    assert len(downloaded.collections) == 1
    assert downloaded.products[0].version == root.version
    assert downloaded.collections[0].products[0].product_id == child.product_id
    assert downloaded.collections[0].products[0].sources["ivar"].cached == (
        slugs is None
    )


@pytest.mark.parametrize("slugify", [False, True])
def test_checkout_filtered_collection(remote_collection, client, tmp_path, slugify):
    client.slugify = slugify
    filtered = remote_collection.filter(metadata_filter={"telescope": "Child product"})
    directory = tmp_path / "checkout"

    assert client.checkout(filtered, directory=directory, slugs=["map"]) is filtered

    directory /= "root-collection" if slugify else "Root collection"
    product_name = "child-product" if slugify else "Child product"
    assert {path.name for path in directory.iterdir()} == {
        product_name,
        "collection.json",
    }
    assert filtered[0].sources["map"].path.read_text() == "Child product map"
    assert not filtered[0].sources["ivar"].path.exists()

    downloaded = client.read_collection(directory)
    assert downloaded.collection_id == filtered.collection_id
    assert [p.product_id for p in downloaded] == [filtered[0].product_id]
    assert downloaded.collections == []


def test_checkout_empty_filtered_collection(remote_collection, client, tmp_path):
    filtered = remote_collection.filter(required_slugs="missing")

    assert client.checkout(filtered, directory=tmp_path) is filtered

    directory = tmp_path / "Root collection"
    assert {path.name for path in directory.iterdir()} == {"collection.json"}
    assert list(client.read_collection(directory, allow_incomplete=False)) == []


@pytest.mark.parametrize("mode", ["id", "response", "instance"])
@pytest.mark.parametrize("slugify", [False, True])
def test_download_collection(remote_collection, client, tmp_path, mode, slugify):
    if mode == "response":
        metadata = collections.read(client.client, remote_collection.collection_id)
        directory = collections.download_direct(
            collection=metadata,
            client=client.client,
            directory=tmp_path,
            console=client.console,
            slugify=slugify,
        )
        assert metadata.name == remote_collection.name
    elif mode == "instance":
        directory = collections.download_instance(
            collection=remote_collection,
            client=client.client,
            directory=tmp_path,
            console=client.console,
            slugify=slugify,
        )
        assert remote_collection.name == "Root collection"
    else:
        directory = collections.download(
            client=client.client,
            id=remote_collection.collection_id,
            directory=tmp_path,
            console=client.console,
            slugify=slugify,
        )

    downloaded = client.read_collection(directory, allow_incomplete=False)

    assert downloaded.collection_id == remote_collection.collection_id
    assert downloaded.products[0].sources["map"].path.read_text() == "Root product map"
    child = downloaded.collections[0].products[0]
    assert child.sources["ivar"].path.read_text() == "Child product ivar"


def test_realize_and_checkout_local_product(client, tmp_path):
    item = client.new_product(
        name="Local product",
        description="A local map",
        metadata=MapSet(pixelisation="healpix"),
    )

    assert client.realize(item) is item
    assert client.checkout(item, directory=tmp_path) is item

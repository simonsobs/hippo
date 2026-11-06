"""
Tests for realizing and checking out products and collections.
"""

import pytest

from henry.source import LocalSource, RemoteSource
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

    realized = client.realize(item, slugs=slugs)

    assert realized is not item
    assert realized.product_id == item.product_id
    assert realized.metadata == item.metadata
    assert realized.version == item.version
    assert set(realized.sources) == (set(item.sources) if slugs is None else set(slugs))

    for slug, source in item.sources.items():
        if slugs is None or slug in slugs:
            path = client.cache.available(source.source_id)
            assert path.read_text() == f"Root product {slug}"
            realized_source = realized.sources[slug]
            assert isinstance(realized_source, RemoteSource)
            assert realized_source.source_id == source.source_id
            assert realized_source.slug == slug
            assert realized_source.description == source.description
            assert realized_source.cached
            assert realized_source.path == path
        else:
            with pytest.raises(FileNotFoundError):
                client.cache.available(source.source_id)
        assert source.path is None
        assert not source.cached


@pytest.mark.parametrize("filtered", [False, True])
@pytest.mark.parametrize("slugs", [None, ["map"], []])
def test_realize_collection(remote_collection, client, filtered, slugs):
    item = remote_collection
    if filtered:
        item = item.filter(metadata_filter={"telescope": "Child product"})

    realized = client.realize(item, slugs=slugs)

    assert realized is not item
    assert realized.collection_id == item.collection_id
    if filtered:
        assert realized.collections == []
        realized_products = realized.products
    else:
        assert len(realized.collections) == 1
        assert realized.collections[0] is not item.collections[0]
        realized_products = realized.products + realized.collections[0].products

    originals = remote_collection.products + remote_collection.collections[0].products
    originals_by_id = {p.product_id: p for p in originals}
    assert {p.product_id for p in realized_products} == (
        {originals[1].product_id} if filtered else set(originals_by_id)
    )
    for realized_product in realized_products:
        original = originals_by_id[realized_product.product_id]
        assert realized_product is not original
        assert set(realized_product.sources) == (
            set(original.sources) if slugs is None else set(slugs)
        )
        for slug, source in realized_product.sources.items():
            assert isinstance(source, RemoteSource)
            assert source.source_id == original.sources[slug].source_id
            assert source.cached
            assert source.path == client.cache.available(source.source_id)
            assert source.path.read_text() == f"{original.name} {slug}"

    for original in originals:
        for slug, source in original.sources.items():
            assert source.path is None
            assert not source.cached
            if (not filtered or original is originals[1]) and (
                slugs is None or slug in slugs
            ):
                assert client.cache.available(source.source_id).exists()
            else:
                with pytest.raises(FileNotFoundError):
                    client.cache.available(source.source_id)


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
@pytest.mark.parametrize("slugs", [None, ["map"], []])
def test_checkout_collection(remote_collection, client, tmp_path, slugify, slugs):
    client.slugify = slugify
    directory = tmp_path / "checkout"

    checked_out = client.checkout(remote_collection, directory=directory, slugs=slugs)

    assert checked_out is not remote_collection
    assert checked_out.collection_id == remote_collection.collection_id
    assert checked_out.collections[0] is not remote_collection.collections[0]

    directory /= "root-collection" if slugify else "Root collection"
    root_name = "root-product" if slugify else "Root product"
    child_name = "child-collection" if slugify else "Child collection"
    product_name = "child-product" if slugify else "Child product"
    root = checked_out.products[0]
    child = checked_out.collections[0].products[0]
    assert root.sources["map"].path.parent.parent == directory / root_name
    assert (
        child.sources["map"].path.parent.parent == directory / child_name / product_name
    )
    for checked_product, original in [
        (root, remote_collection.products[0]),
        (child, remote_collection.collections[0].products[0]),
    ]:
        assert checked_product is not original
        assert checked_product.product_id == original.product_id
        for slug, source in checked_product.sources.items():
            selected = slugs is None or slug in slugs
            assert source.cached == selected
            assert source.path.exists() == selected
            if selected:
                assert source.path.read_text() == f"{original.name} {slug}"
            assert original.sources[slug].path is None

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

    checked_out = client.checkout(filtered, directory=directory, slugs=["map"])

    assert checked_out is not filtered
    assert checked_out.collection_id == filtered.collection_id
    assert checked_out.collections == []

    directory /= "root-collection" if slugify else "Root collection"
    product_name = "child-product" if slugify else "Child product"
    assert {path.name for path in directory.iterdir()} == {
        product_name,
        "collection.json",
    }
    assert checked_out[0] is not filtered[0]
    assert checked_out[0].sources["map"].cached
    assert checked_out[0].sources["map"].path.read_text() == "Child product map"
    assert not checked_out[0].sources["ivar"].cached
    assert not checked_out[0].sources["ivar"].path.exists()
    assert all(source.path is None for source in filtered[0].sources.values())

    downloaded = client.read_collection(directory)
    assert downloaded.collection_id == filtered.collection_id
    assert [p.product_id for p in downloaded] == [filtered[0].product_id]
    assert downloaded.collections == []


def test_checkout_empty_filtered_collection(remote_collection, client, tmp_path):
    filtered = remote_collection.filter(required_slugs="missing")

    checked_out = client.checkout(filtered, directory=tmp_path)

    assert checked_out is not filtered
    assert checked_out.collection_id == filtered.collection_id
    assert list(checked_out) == []

    directory = tmp_path / "Root collection"
    assert {path.name for path in directory.iterdir()} == {"collection.json"}
    assert list(client.read_collection(directory, allow_incomplete=False)) == []


def test_realize_and_checkout_local_product(client, tmp_path):
    item = client.new_product(
        name="Local product",
        description="A local map",
        metadata=MapSet(pixelisation="healpix"),
    )

    assert client.realize(item) is item
    assert client.checkout(item, directory=tmp_path) is item

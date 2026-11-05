"""
Tests for client-side collection filtering.
"""

import pytest

from henry.collection import FilteredCollection, LocalCollection, RemoteCollection
from henry.product import LocalProduct
from henry.source import LocalSource
from hippometa import MapSet, NumericMetadata, SimpleMetadata


@pytest.fixture
def collection(tmp_path):
    simple = LocalProduct(
        name="Simple product",
        description="A product with a data source",
        metadata=SimpleMetadata(),
        sources={"data": LocalSource(path=tmp_path / "data.txt")},
    )
    numeric = LocalProduct(
        name="Numeric product",
        description="A product without sources",
        metadata=NumericMetadata(value=42),
    )
    map_product = LocalProduct(
        name="Map product",
        description="A product with map and ivar sources",
        metadata=MapSet(pixelisation="healpix", telescope="SO"),
        sources={
            "map": LocalSource(path=tmp_path / "map.fits"),
            "ivar": LocalSource(path=tmp_path / "ivar.fits"),
        },
    )
    grandchild = LocalCollection(
        name="Grandchild", description="Nested maps", products=[map_product]
    )
    child = LocalCollection(
        name="Child",
        description="Nested products",
        products=[numeric],
        collections=[grandchild],
    )
    return LocalCollection(
        collection_id="test-collection",
        name="Test collection",
        description="A collection with nested products",
        products=[simple],
        collections=[child],
        readers=["reader"],
        writers=["writer"],
    )


def test_filter_includes_child_products(collection):
    filtered = collection.filter()

    assert isinstance(filtered, FilteredCollection)
    assert {p.name for p in filtered} == {
        "Simple product",
        "Numeric product",
        "Map product",
    }
    assert filtered.collections == []
    assert filtered.collection_id == collection.collection_id
    assert filtered.name == collection.name
    assert filtered.description == collection.description
    assert filtered.readers == collection.readers
    assert filtered.writers == collection.writers
    assert len(collection.products) == 1
    assert len(collection.collections) == 1


def test_filter_metadata_type(collection):
    filtered = collection.filter(metadata_type=NumericMetadata)

    assert len(filtered) == 1
    assert filtered[0].metadata == NumericMetadata(value=42)


def test_filter_required_slug(collection):
    filtered = collection.filter(required_slugs="data")

    assert list(filtered) == collection.products


def test_filter_requires_all_slugs(collection):
    filtered = collection.filter(required_slugs=["map", "ivar"])

    assert [p.name for p in filtered] == ["Map product"]
    assert len(collection.filter(required_slugs=["map", "data"])) == 0


def test_filter_metadata_values(collection):
    filtered = collection.filter(
        metadata_filter={"pixelisation": "healpix", "telescope": "SO"}
    )

    assert [p.name for p in filtered] == ["Map product"]
    assert len(collection.filter(metadata_filter={"value": 0})) == 0
    assert (
        len(
            collection.filter(
                metadata_filter={"pixelisation": "healpix", "telescope": "ACT"}
            )
        )
        == 0
    )
    assert [
        p.name for p in collection.filter(metadata_filter={"instrument": None})
    ] == ["Map product"]


def test_filter_combines_criteria(collection):
    filtered = collection.filter(
        metadata_type=MapSet,
        required_slugs="map",
        metadata_filter={"telescope": "SO"},
    )

    assert [p.name for p in filtered] == ["Map product"]
    assert (
        len(collection.filter(metadata_type=NumericMetadata, required_slugs="data"))
        == 0
    )


def test_filter_further(collection):
    filtered = collection.filter(required_slugs="data")
    narrowed = filtered.filter(metadata_type=NumericMetadata)

    assert len(narrowed) == 0
    assert list(filtered) == collection.products


def test_filter_empty_criteria(collection):
    assert list(collection.filter(required_slugs=[], metadata_filter={})) == list(
        collection.filter()
    )


def test_filter_unsaved_collection():
    collection = LocalCollection(name="Empty", description="An unsaved collection")

    filtered = collection.filter()

    assert filtered.collection_id is None
    assert list(filtered) == []


def test_filter_remote_collection(collection):
    remote = RemoteCollection(
        collection_id=collection.collection_id,
        name=collection.name,
        description=collection.description,
        products=collection.products,
        collections=collection.collections,
        owner="test-user",
        readers=collection.readers,
        writers=collection.writers,
        original_name=collection.name,
        original_description=collection.description,
    )

    filtered = remote.filter(metadata_type=NumericMetadata)

    assert [p.name for p in filtered] == ["Numeric product"]
    assert filtered.owner == remote.owner
    assert filtered.collection_id == remote.collection_id


def test_filter_product_without_metadata():
    product = LocalProduct(name="No metadata", description="A product", metadata=None)
    collection = LocalCollection(
        collection_id="test-collection",
        name="Test collection",
        description="Products without metadata",
        products=[product],
    )

    assert list(collection.filter()) == [product]
    assert len(collection.filter(metadata_type=SimpleMetadata)) == 0
    assert len(collection.filter(metadata_filter={"value": 42})) == 0
    assert len(collection.filter(metadata_filter={"missing": None})) == 0


def test_filtered_collection_sequence(collection):
    filtered = collection.filter()
    products = list(filtered)

    assert len(filtered) == 3
    assert filtered[0] == products[0]
    assert filtered[-1] == products[-1]
    assert list(reversed(filtered)) == products[::-1]
    assert collection.products[0] in filtered
    assert collection.collections[0] not in filtered

    with pytest.raises(IndexError):
        filtered[len(filtered)]

    with pytest.raises(IndexError):
        filtered[-len(filtered) - 1]


def test_filtered_empty_collection_index(collection):
    filtered = collection.filter(required_slugs="missing")

    assert len(filtered) == 0
    with pytest.raises(IndexError):
        filtered[-1]

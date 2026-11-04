from types import SimpleNamespace

import pytest
from fastapi import Request
from starlette.authentication import AuthCredentials

from hipposerve.api.product import read_product, read_tree
from hipposerve.api.relationships import read_collection
from hipposerve.service import collection, product
from hipposerve.service.auth import AuthenticationError


@pytest.mark.asyncio(loop_scope="session")
async def test_public_access_and_pinned_products(storage):
    owner = "publicaclowner"
    admin_scopes = {"hippo:admin"}
    public_collection = await collection.create(
        name="publicaclcollection",
        user=owner,
        description="Public collection",
        collection_readers=["public"],
        collection_writers=["public"],
    )
    private_collection = await collection.create(
        name="privateaclcollection",
        user=owner,
        description="Private collection",
        collection_writers=["public"],
    )
    public_product, _ = await product.create(
        name="publicaclproduct",
        description="Public product",
        metadata=None,
        sources={},
        user_name=owner,
        storage=storage,
        product_readers=["public"],
        product_writers=["public"],
    )
    private_product, _ = await product.create(
        name="privateaclproduct",
        description="Private product",
        metadata=None,
        sources={},
        user_name=owner,
        storage=storage,
        product_writers=["public"],
    )
    try:
        await product.add_collection(public_product, [owner], set(), public_collection)
        await product.add_collection(private_product, [owner], set(), public_collection)

        read_collection = await collection.read(public_collection.id, [], set())
        assert {item.id for item in read_collection.products} == {public_product.id}
        assert (await product.read_by_id(public_product.id, [], set())).id == (
            public_product.id
        )
        assert {
            item.id for item in await collection.search_by_owner(owner, [], set())
        } == {public_collection.id}
        assert {
            item.id for item in await product.search_by_owner(owner, [], set())
        } == {public_product.id}

        with pytest.raises(AuthenticationError):
            await collection.read(private_collection.id, [], set())
        with pytest.raises(AuthenticationError):
            await product.read_by_id(private_product.id, [], set())
        with pytest.raises(AuthenticationError):
            await collection.delete(public_collection.id, ["public"], set())
        with pytest.raises(AuthenticationError):
            await product.pin(public_product, ["public"], set())

        await product.pin(private_product, [owner], set())
        for groups, scopes in (([owner], set()), ([], admin_scopes)):
            pinned_ids = {item.id for item in await product.read_pinned(groups, scopes)}
            assert private_product.id in pinned_ids
            assert public_product.id not in pinned_ids
        assert private_product.id not in {
            item.id for item in await product.read_pinned([], set())
        }
    finally:
        await public_product.delete()
        await private_product.delete()
        await public_collection.delete()
        await private_collection.delete()


@pytest.mark.asyncio(loop_scope="session")
async def test_public_relationship_responses_hide_private_records(
    storage, server, monkeypatch
):
    for key in (
        "minio_url",
        "minio_access",
        "minio_secret",
        "mongo_uri",
        "title",
        "description",
    ):
        monkeypatch.setenv(key.upper(), server[key])

    from hipposerve.web import collection_view, product_view

    owner = "relationshipowner"
    records = []
    try:
        for name, readers in (
            ("relationship-anchor", ["public"]),
            ("relationship-visible", ["public"]),
            ("relationship-private", []),
        ):
            item = await collection.create(
                name=name,
                user=owner,
                description=f"{name} description",
                collection_readers=readers,
            )
            records.append(item)

        anchor, visible, private = records
        for parent, child in ((anchor, visible), (anchor, private), (private, anchor)):
            await collection.add_child(parent.id, child.id, [owner], set())

        public_product, _ = await product.create(
            name="relationship-product",
            description="",
            metadata=None,
            sources={},
            user_name=owner,
            storage=storage,
            product_readers=["public"],
        )
        records.append(public_product)
        private_product, _ = await product.create(
            name="relationship-private-product",
            description="",
            metadata=None,
            sources={},
            user_name=owner,
            storage=storage,
        )
        records.append(private_product)

        await product.add_collection(public_product, [owner], set(), visible)
        await product.add_collection(public_product, [owner], set(), private)
        await product.add_relationship(
            public_product, private_product, [owner], set(), "child"
        )
        await product.add_relationship(
            private_product, public_product, [owner], set(), "child"
        )

        for groups in (set(), {owner}):
            request = Request(
                {
                    "type": "http",
                    "auth": AuthCredentials(["hippo:read"]),
                    "user": SimpleNamespace(display_name="reader", groups=groups),
                }
            )
            response = await read_collection(anchor.id, request)
            assert {child.id for child in response.child_collections} == (
                {visible.id, private.id} if groups else {visible.id}
            )
            assert [parent.id for parent in response.parent_collections] == (
                [private.id] if groups else []
            )
            assert (private.description in response.model_dump_json()) == bool(groups)

            collection_page = await collection_view(request, anchor.id)
            assert visible.name.encode() in collection_page.body
            assert (str(private.id).encode() in collection_page.body) == bool(groups)
            assert (private.name.encode() in collection_page.body) == bool(groups)

            direct = await read_product(public_product.id, request)
            history = await read_tree(public_product.id, request)
            for result in (direct, history):
                metadata = result.versions[public_product.version]
                assert set(metadata.collections) == (
                    {visible.id, private.id} if groups else {visible.id}
                )
                expected_product_links = [private_product.id] if groups else []
                assert metadata.child_of == expected_product_links
                assert metadata.parent_of == expected_product_links

            product_page = await product_view(request, public_product.id)
            assert visible.name.encode() in product_page.body
            assert (str(private.id).encode() in product_page.body) == bool(groups)
            assert (private_product.name.encode() in product_page.body) == bool(groups)
    finally:
        for item in reversed(records):
            await item.delete()

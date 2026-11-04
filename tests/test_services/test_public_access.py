import pytest

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

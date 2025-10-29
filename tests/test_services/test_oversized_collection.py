"""
Test suite to reproduce and validate the MongoDB 16MB document limit error
that occurs in production when reading collections with many linked products.
"""

import io

import pytest
import requests

import hippometa
from hipposerve.database import Collection, Product
from hipposerve.service import collection as collection_sc
from hipposerve.service import product as product_sc


async def create_custom_collection_with_large_products(
    name: str,
    num_products: int,
    target_fac: int,
    user_name: str,
    user_groups: list[str],
    storage,
) -> Collection:
    """
    Create a collection with custom number of products

    Args:
        name: Collection name
        num_products: Number of products to create
        target_fac: Target factor multiple
        user_name:Username
        user_groups: User groups
        storage: Storage
    """

    # Create the collection
    coll = await collection_sc.create(
        name=name,
        user=user_name,
        description=f"Test collection with {num_products} products)",
        collection_readers=user_groups,
        collection_writers=user_groups,
    )
    FILE_CONTENTS = b"0x0" * 1024 * target_fac
    SOURCES = {
        "data": product_sc.PreUploadFile(
            name="test_1.txt",
            size=1024,
            checksum="meh",
        )
    }
    # Add products
    for i in range(num_products):
        prod, file_puts = await product_sc.create(
            name=f"{name}_product_{i:03d}",
            description=f" Product {i} with normal metadata for collection {name}",
            metadata=hippometa.MapSet(pixelisation="equirectangular"),
            sources=SOURCES,
            user_name=user_name,
            storage=storage,
            product_readers=user_groups,
            product_writers=user_groups,
        )
        headers = {}
        sizes = {}

        with io.BytesIO(FILE_CONTENTS) as f:
            for file_name, put in file_puts.items():
                f.seek(0)
                headers[file_name] = [requests.put(put[0], f).headers]
                sizes[file_name] = [len(FILE_CONTENTS)]

        await product_sc.complete(
            product=prod,
            storage=storage,
            headers=headers,
            sizes=sizes,
        )
        # Add to collection
        await product_sc.add_collection(
            product=prod, access_groups=user_groups, collection=coll, scopes=set()
        )

    return coll


async def cleanup_test_collections(collection_ids: list[str], storage):
    """
    Clean up test collections and their associated products.
    """
    for coll_id in collection_ids:
        try:
            products = await Product.find({"collections": coll_id}).to_list()
            for prod in products:
                await product_sc.delete_tree(
                    prod, ["admin"], storage, data=True, scopes=set()
                )
            await Collection.find_one(Collection.id == coll_id).delete()

        except Exception as e:
            print(f"Cleanup failed: {e}")


@pytest.mark.asyncio(loop_scope="session")
async def test_oversized_collection_fails_with_fetch_links(
    database, created_user, storage
):
    """
    Reproduce the production error by creating 200 products.
    """

    try:
        massive_coll = await create_custom_collection_with_large_products(
            name="Massive_Test_Collection_200_Products",
            num_products=200,
            target_fac=1,
            user_name=created_user.display_name,
            user_groups=created_user.groups,
            storage=storage,
        )
        collection_obj = await collection_sc.read(
            id=massive_coll.id, groups=created_user.groups
        )
        assert collection_obj.products is not None

    finally:
        await cleanup_test_collections([str(massive_coll.id)], storage)

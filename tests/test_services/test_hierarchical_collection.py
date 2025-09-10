"""
Test suite to reproduce and validate the MongoDB 16MB document limit error
that occurs when reading collections with hierarchical parent-child relationships.
"""

import io

import pytest
import requests

import hippometa
from hipposerve.database import Collection, Product
from hipposerve.service import collection as collection_sc
from hipposerve.service import product as product_sc


async def create_hierarchical_collection_with_relationships(
    name: str,
    num_parents: int,
    children_per_parent: int,
    user_name: str,
    user_groups: list[str],
    storage,
) -> Collection:
    """
    Create a collection with hierarchical parent-child relationships

    Args:
        name: Collection name
        num_parents: Number of parent products to create
        children_per_parent: Number of child products per parent
        user_name: Username
        user_groups: User groups
        storage: Storage
    """

    # Create the collection
    coll = await collection_sc.create(
        name=name,
        user=user_name,
        description=f"Test collection with {num_parents} parents, each having {children_per_parent} children",
        collection_readers=user_groups,
        collection_writers=user_groups,
    )

    FILE_CONTENTS = b"0x0" * 1024 * 1
    SOURCES = {
        "data": product_sc.PreUploadFile(
            name="test_1.txt",
            size=1024,
            checksum="meh",
        )
    }

    # Create parent products and add them to the collection
    parent_products = []
    for i in range(num_parents):
        parent_prod, file_puts = await product_sc.create(
            name=f"{name}_parent_{i:03d}",
            description=f"Parent product {i} for hierarchical collection {name}",
            metadata=hippometa.MapSet(pixelisation="equirectangular"),
            sources=SOURCES,
            user_name=user_name,
            storage=storage,
            product_readers=user_groups,
            product_writers=user_groups,
        )
        parent_products.append(parent_prod)

        # Upload file data for parent
        headers = {}
        sizes = {}
        with io.BytesIO(FILE_CONTENTS) as f:
            for file_name, put in file_puts.items():
                f.seek(0)
                headers[file_name] = [requests.put(put[0], f).headers]
                sizes[file_name] = [len(FILE_CONTENTS)]

        await product_sc.complete(
            product=parent_prod,
            storage=storage,
            headers=headers,
            sizes=sizes,
        )

        # Add parent to collection
        await product_sc.add_collection(
            product=parent_prod, access_groups=user_groups, collection=coll
        )

    # Create child products and establish parent-child relationships
    child_products = []
    for parent_idx, parent_prod in enumerate(parent_products):
        for child_idx in range(children_per_parent):
            child_prod, file_puts = await product_sc.create(
                name=f"{name}_child_{parent_idx:03d}_{child_idx:03d}",
                description=f"Child product {child_idx} of parent {parent_idx} for collection {name}",
                metadata=hippometa.MapSet(pixelisation="equirectangular"),
                sources=SOURCES,
                user_name=user_name,
                storage=storage,
                product_readers=user_groups,
                product_writers=user_groups,
            )
            child_products.append(child_prod)

            # Upload file data for child
            headers = {}
            sizes = {}
            with io.BytesIO(FILE_CONTENTS) as f:
                for file_name, put in file_puts.items():
                    f.seek(0)
                    headers[file_name] = [requests.put(put[0], f).headers]
                    sizes[file_name] = [len(FILE_CONTENTS)]

            await product_sc.complete(
                product=child_prod,
                storage=storage,
                headers=headers,
                sizes=sizes,
            )

            # Establish parent-child relationship
            await product_sc.add_relationship(
                source=child_prod,
                destination=parent_prod,
                access_groups=user_groups,
                type="child",
            )

    return coll


async def cleanup_hierarchical_collection(collection_id: str, storage):
    """
    Clean up hierarchical collection and all associated products.
    """
    try:
        collection_products = await Product.find(
            {"collections": collection_id}
        ).to_list()
        all_products = []
        for prod in collection_products:
            all_products.append(prod.id)
            for child in prod.parent_of:
                child_product = await Product.find_one(Product.id == child.id)
                if child_product:
                    all_products.append(child_product.id)

        for prod_id in all_products:
            prod = await Product.find_one(Product.id == prod_id)
            if prod:
                await product_sc.delete_tree(prod, ["admin"], storage, data=True)

        await Collection.find_one(Collection.id == collection_id).delete()

    except Exception as e:
        print(f"Cleanup failed: {e}")


@pytest.mark.asyncio(loop_scope="session")
async def test_hierarchical_collection_fails_with_relationships_parentproduct200_childproduct0(
    database, created_user, storage
):
    """
    Reproduce the production error by creating a hierarchical collection
    with 200 parent products, each having 0 children (200 products total).
    """

    try:
        hierarchical_coll = await create_hierarchical_collection_with_relationships(
            name="Hierarchical_Test_Collection",
            num_parents=200,
            children_per_parent=0,
            user_name=created_user.display_name,
            user_groups=created_user.groups,
            storage=storage,
        )
        collection_obj = await collection_sc.read(
            id=hierarchical_coll.id, groups=created_user.groups
        )
        assert collection_obj.products is not None

    finally:
        await cleanup_hierarchical_collection(str(hierarchical_coll.id), storage)


@pytest.mark.asyncio(loop_scope="session")
async def test_hierarchical_collection_fails_with_relationships_parentproduct20_childproduct10(
    database, created_user, storage
):
    """
    Reproduce the production error by creating a hierarchical collection
    with 20 parent products, each having 10 children (200 products total).
    """

    try:
        hierarchical_coll = await create_hierarchical_collection_with_relationships(
            name="Hierarchical_Test_Collection",
            num_parents=20,
            children_per_parent=10,
            user_name=created_user.display_name,
            user_groups=created_user.groups,
            storage=storage,
        )
        collection_obj = await collection_sc.read(
            id=hierarchical_coll.id, groups=created_user.groups
        )
        assert len(collection_obj.products) == 20
        assert len(collection_obj.products[0].parent_of) == 10
        assert (
            collection_obj.products[19].parent_of[0].name
            == "Hierarchical_Test_Collection_child_019_000"
        )

    finally:
        await cleanup_hierarchical_collection(str(hierarchical_coll.id), storage)

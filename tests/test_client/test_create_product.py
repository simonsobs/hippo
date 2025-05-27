"""
Tests the create and upload product flow, to test e.g. multipart uploads.
"""

import random

from hippoclient import product
from hippoclient.core import Client
from hippometa import SimpleMetadata


def test_upload_no_multipart(server, tmp_path):
    client = Client(
        token_tag=None,
        host=server["url"],
        verbose=True,
        use_multipart_upload=False,
    )

    with open(tmp_path / "test.bin", "wb") as f:
        for _ in range(64):  # 64MB
            f.write(random.randbytes(1024 * 1024))

    id = product.create(
        client=client,
        name="test_product",
        description="test_description",
        metadata=SimpleMetadata(),
        sources=[tmp_path / "test.bin"],
        source_descriptions=[None],
    )

    product.delete(client, id)


def test_upload_with_multipart(server, tmp_path):
    client = Client(
        token_tag=None,
        host=server["url"],
        verbose=True,
        use_multipart_upload=True,
    )

    with open(tmp_path / "test.bin", "wb") as f:
        for _ in range(64):  # 64MB
            f.write(random.randbytes(1024 * 1024))

    id = product.create(
        client=client,
        name="test_product",
        description="test_description",
        metadata=SimpleMetadata(),
        sources=[tmp_path / "test.bin"],
        source_descriptions=[None],
    )

    product.delete(client, id)


def test_groups_update_add_reader(server, tmp_path):
    client = Client(
        token_tag=None,
        host=server["url"],
        verbose=True,
        use_multipart_upload=False,
    )

    with open(tmp_path / "test.bin", "wb") as f:
        for _ in range(64):  # 64MB
            f.write(random.randbytes(1024 * 1024))

    id = product.create(
        client=client,
        name="test_product",
        description="test_description",
        metadata=SimpleMetadata(),
        sources=[tmp_path / "test.bin"],
        source_descriptions=[None],
    )

    updated_id = product.product_add_reader(
        client=client,
        id=id,
        user="test_group",
    )
    product.delete(client, id)

    updated_id_2 = product.product_add_writer(
        client=client,
        id=updated_id,
        user="test_group",
    )

    product.delete(client, updated_id)

    updated_id_3 = product.product_remove_reader(
        client=client,
        id=updated_id_2,
        user="test_group",
    )
    product.delete(client, updated_id_2)

    updated_id_4 = product.product_remove_writer(
        client=client,
        id=updated_id_3,
        user="test_group",
    )
    product.delete(client, updated_id_3)
    product.delete(client, updated_id_4)

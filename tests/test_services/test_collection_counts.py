"""Regression coverage for counts of products in related collections."""

import re

import pytest
from fastapi import Request
from soauth.toolkit.starlette import SOUser
from starlette.authentication import AuthCredentials

from hipposerve.service import collection, product


@pytest.mark.asyncio(loop_scope="session")
@pytest.mark.parametrize(
    ("groups", "scopes", "child_count"),
    [([], [], 3), (["count-team"], [], 5), ([], ["hippo:admin"], 6)],
)
async def test_related_collection_product_counts(
    database, storage, monkeypatch, groups, scopes, child_count
):
    # Import the web frontend with standalone test settings, without a live server.
    for key, value in {
        "MINIO_URL": "localhost:9000",
        "MINIO_ACCESS": "test",
        "MINIO_SECRET": "test",
        "MONGO_URI": "mongodb://localhost:27017",
        "TITLE": "Test",
        "DESCRIPTION": "Test",
    }.items():
        monkeypatch.setenv(key, value)

    from hipposerve.web import collection_view

    owner = "count-owner"
    records = []
    try:
        for name in ("anchor", "parent", "child", "empty", "hidden"):
            item = await collection.create(
                name=f"count-{name}",
                user=owner,
                description="",
                collection_readers=[] if name == "hidden" else ["public"],
            )
            records.append(item)
        anchor, parent, child, empty, hidden = records
        for source, destination in (
            (parent, anchor),
            (anchor, child),
            (anchor, empty),
            (anchor, hidden),
        ):
            await collection.add_child(source.id, destination.id, [owner], set())

        for i, (readers, writers) in enumerate(
            [(["public"], [])] * 3
            + [(["count-team"], []), ([], ["count-team"]), ([], ["public"])]
        ):
            item, _ = await product.create(
                name=f"count-product-{i}",
                description="",
                metadata=None,
                sources={},
                user_name=owner,
                storage=storage,
                product_readers=readers,
                product_writers=writers,
            )
            records.append(item)
            await product.add_collection(item, [owner], set(), child)
            if i == 0:
                # Shared memberships and duplicate links must not inflate counts.
                await product.add_collection(item, [owner], set(), parent)
                await product.add_collection(item, [owner], set(), child)
            if i == 5:
                await product.add_collection(item, [owner], set(), hidden)

        counts = await collection.product_counts([parent, child, empty], groups, scopes)
        assert counts == {parent.id: 1, child.id: child_count, empty.id: 0}
        assert await collection.product_counts([], groups, scopes) == {}
        for related in (parent, child, empty):
            direct = await collection.read(related.id, groups, scopes)
            assert counts[related.id] == len(direct.products)

        request = Request(
            {
                "type": "http",
                "auth": AuthCredentials(scopes),
                "user": SOUser(groups=set(groups)),
            }
        )
        page = await collection_view(request, anchor.id)
        rows = dict(
            re.findall(
                r'<td><a href="/web/collections/([a-f0-9]+)">.*?</a></td>'
                r'\s*<td class="small">(\d+)</td>',
                page.body.decode(),
            )
        )
        expected = {str(id): str(count) for id, count in counts.items()}
        if "hippo:admin" in scopes:
            expected[str(hidden.id)] = "1"
        assert rows == expected
        assert (str(hidden.id).encode() in page.body) == ("hippo:admin" in scopes)
    finally:
        for item in reversed(records):
            await item.delete()

"""
Tests the cache functionality.
"""

from pathlib import Path

import pytest


def test_add_file_to_cache(cache):
    """
    Test adding a file to the cache.
    """
    keys = dict(
        id="123456789012345678901234",
        path="test.txt",
        checksum="12345678901234567890123456789012",
        size=123,
    )

    cache._add(**keys)

    cache._mark_available(keys["id"])

    assert str(cache._get(keys["id"])) == str(cache.path / Path(keys["path"]))

    cache._mark_unavailable(keys["id"])

    cache._remove(keys["id"])


def test_add_real_file_to_cache(cache):
    """
    Test adding a real file to the cache
    """

    path = cache.get(
        id="abcdefghijk",
        path="my/path/to/file.png",
        checksum="not-a-real-checksum",
        size=1234,
        presigned_url="https://picsum.photos/200/300",
    )

    assert path.exists()

    assert str(path) == str(cache.path / Path("my/path/to/file.png"))

    # Now get it back again
    path = cache.available(
        id="abcdefghijk",
    )

    assert path.exists()


def test_unavailable(cache):
    with pytest.raises(FileNotFoundError):
        cache.available("not-a-real-id")

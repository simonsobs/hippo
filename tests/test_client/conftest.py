"""
Fixtures for the caching client tests.
"""

from pathlib import Path

import pytest

from henry.core import ClientSettings, Henry
from hippoclient.caching import Cache


@pytest.fixture
def cache(tmp_path):
    cache = Cache(path=Path(tmp_path))

    assert cache.writeable

    yield cache

    for id in cache.complete_id_list:
        cache._remove(id)


@pytest.fixture
def client(server):
    client = Henry(settings=ClientSettings(host=server["url"], verbose=True))

    yield client

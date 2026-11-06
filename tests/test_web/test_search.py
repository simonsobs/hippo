import importlib
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from starlette.authentication import AuthCredentials


@pytest.fixture
def metadata_search(monkeypatch):
    settings = {
        "MINIO_URL": "localhost:9000",
        "MINIO_ACCESS": "test",
        "MINIO_SECRET": "test",
        "MONGO_URI": "mongodb://localhost:27017",
        "TITLE": "Test",
        "DESCRIPTION": "Test",
    }
    for key, value in settings.items():
        monkeypatch.setenv(key, value)

    search = importlib.import_module("hipposerve.web.search")
    search_by_metadata = AsyncMock(
        return_value=[
            SimpleNamespace(id="test-product", name="ACT map", description="A map")
        ]
    )
    monkeypatch.setattr(search.product, "search_by_metadata", search_by_metadata)

    app = FastAPI()
    app.include_router(search.router, prefix="/web")

    @app.middleware("http")
    async def authenticate(request, call_next):
        request.scope["user"] = SimpleNamespace(
            display_name="test_user", groups=["test_group"]
        )
        request.scope["auth"] = AuthCredentials(["test_scope"])
        return await call_next(request)

    with TestClient(app) as client:
        yield client, search_by_metadata


@pytest.mark.parametrize(
    ("query", "expected_filters"),
    [
        (
            "metadata_type=MapSet&telescope=act",
            {"telescope": {"$regex": "act", "$options": "i"}},
        ),
        (
            "metadata_type=BeamMetadata&telescope=act",
            {"telescope": {"$regex": "act", "$options": "i"}},
        ),
        (
            "metadata_type=ArchiveMetadata&archive_type=zip",
            {"archive_type": {"$regex": "zip", "$options": "i"}},
        ),
        ("metadata_type=CatalogMetadata&file_type=fits", {"file_type": "fits"}),
        ("metadata_type=NumericMetadata", {}),
        ("metadata_type=SimpleMetadata", {}),
        (
            "metadata_type=CameraMetadata&date=2026-11-06",
            {"date": {"$regex": "2026-11-06", "$options": "i"}},
        ),
        (
            "metadata_type=MapSet&tags=coadd,%20night",
            {"tags": {"$in": ["coadd", "night"]}},
        ),
        (
            "metadata_type=MapSet&telescope=act&q=maps&filter_on=products",
            {"telescope": {"$regex": "act", "$options": "i"}},
        ),
    ],
)
def test_metadata_search_results(metadata_search, query, expected_filters):
    client, search_by_metadata = metadata_search

    response = client.get(f"/web/searchmetadata/results?{query}")

    assert response.status_code == 200
    assert "Showing 1 result" in response.text
    assert "href='/web/products/test-product'" in response.text
    assert "ACT map" in response.text
    search_by_metadata.assert_awaited_once_with(
        expected_filters, ["test_group"], scopes=["test_scope"]
    )

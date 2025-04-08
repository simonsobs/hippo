"""
Tests the group API endpoints.
"""

from fastapi.testclient import TestClient

from hipposerve.api.models.groups import (
    ReadGroupResponse,
)
from hipposerve.service.groups import Privilege


def test_create_group(test_api_client: TestClient, test_api_user: str):
    response = test_api_client.put(
        "/groups/test_group",
        json={
            "description": "test_description",
            "privileges": [
                Privilege.CREATE_GROUP.value,
            ],
        },
    )

    assert response.status_code == 200


def test_read_group(test_api_client: TestClient, test_api_user: str):
    response = test_api_client.get(f"/groups/{test_api_user}")

    assert response.status_code == 200
    validated = ReadGroupResponse.model_validate(response.json())

    assert validated.name == test_api_user

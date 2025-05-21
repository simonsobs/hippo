"""
Tests the group API endpoints.
"""

"""
from fastapi.testclient import TestClient

from hipposerve.api.models.groups import (
    ReadGroupResponse,
    UpdateGroupAccessResponse,
    UpdateGroupDescriptionResponse,
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


def test_update_group_access(test_api_client: TestClient, test_api_user: str):
    response = test_api_client.post(
        f"/groups/{test_api_user}/updateaccess",
        json={
            "remove_access_control": [
                Privilege.CREATE_GROUP.value,
            ],
        },
    )
    assert response.status_code == 200
    validated = UpdateGroupAccessResponse.model_validate(response.json())
    assert Privilege.CREATE_GROUP not in validated.access_controls

    response = test_api_client.post(
        f"/groups/{test_api_user}/updateaccess",
        json={
            "add_access_control": [
                Privilege.CREATE_GROUP.value,
            ],
        },
    )

    assert response.status_code == 200
    validated = UpdateGroupAccessResponse.model_validate(response.json())

    assert Privilege.CREATE_GROUP in validated.access_controls


def test_update_group_description(test_api_client: TestClient, test_api_user: str):
    response = test_api_client.post(
        f"/groups/{test_api_user}/updatedescription",
        json={
            "description": "new_description",
        },
    )
    assert response.status_code == 200
    validated = UpdateGroupDescriptionResponse.model_validate(response.json())
    assert validated.description == "new_description"


def test_delete_group(test_api_client: TestClient, test_api_user: str):
    # Create a group to delete
    response = test_api_client.put(
        "/groups/test_group",
        json={
            "description": "test_description",
            "privileges": [
                Privilege.CREATE_GROUP.value,
            ],
        },
    )
    response = test_api_client.delete(f"/groups/{test_api_user}")

    assert response.status_code == 200
"""

"""
Tests the functions in the group service.
"""

import pytest

from hipposerve.database import Privilege
from hipposerve.service import groups


@pytest.mark.asyncio(loop_scope="session")
async def test_create_user_group(created_user):
    # Test creating a group with the user name
    group_description = "A test group"

    new_group = await groups.create(
        name=created_user.name,
        description=group_description,
        user_list=[created_user.name],
        access_control=[Privilege.CREATE_GROUP],
    )

    # Assert the group was created correctly
    assert new_group.name == created_user.name
    assert new_group.description == group_description
    assert new_group.user_list == [created_user.name]


@pytest.mark.asyncio(loop_scope="session")
async def test_read_group(created_group):
    # Test reading a group by name
    this_group = await groups.read(name=created_group.name)
    assert this_group.name == created_group.name

    # Test reading a group by id
    this_group = await groups.read_by_id(id=created_group.id)
    assert this_group.name == created_group.name


@pytest.mark.asyncio(loop_scope="session")
async def test_update_group(created_group):
    # Test updating a group
    new_description = "A new description"
    new_users = ["test_user A"]

    updated_group = await groups.update(
        name=created_group.name,
        description=new_description,
        user_list=new_users,
    )

    assert updated_group.description == new_description
    assert updated_group.user_list == new_users
    assert updated_group.name == created_group.name

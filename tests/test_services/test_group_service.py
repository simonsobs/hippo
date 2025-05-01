"""
Tests the functions in the group service.
"""

import pytest

from hipposerve.database import Privilege
from hipposerve.service import groups


@pytest.mark.asyncio(loop_scope="session")
async def test_read_group(created_group):
    # Test reading a group by name
    this_group = await groups.read_by_name(name=created_group.name)
    assert this_group.name == created_group.name
    assert this_group.id == created_group.id

    # Test reading a group by id
    this_group = await groups.read_by_id(id=created_group.id)
    assert this_group.name == created_group.name


@pytest.mark.asyncio(loop_scope="session")
async def test_update_group(created_group):
    # Test updating a group
    new_description = "A new description"

    updated_group = await groups.update_desciption(
        name=created_group.name,
        description=new_description,
    )

    assert updated_group.description == new_description

    updated_group = await groups.update_access_control(
        name=created_group.name,
        remove_access_control=[Privilege.DOWNLOAD_PRODUCT],
    )

    assert Privilege.DOWNLOAD_PRODUCT not in updated_group.access_controls

    updated_group = await groups.update_access_control(
        name=created_group.name,
        add_access_control=[Privilege.DOWNLOAD_PRODUCT],
    )
    assert Privilege.DOWNLOAD_PRODUCT in updated_group.access_controls

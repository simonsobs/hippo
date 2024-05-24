"""
Tests the functions in the user service.
"""

import pytest

from soposerve.service import users


@pytest.mark.asyncio(scope="session")
async def test_read_user(created_user):
    this_user = await users.read(name=created_user.name)
    assert this_user.name == created_user.name

@pytest.mark.asyncio(scope="session")
async def test_update_user(created_user):
    this_user = await users.update(
        name=created_user.name,
        privileges=[users.Privilege.DOWNLOAD],
        refresh_key=True
    )

    assert this_user.name == created_user.name
    assert this_user.privileges == [users.Privilege.DOWNLOAD]

    this_user = await users.update(
        name=created_user.name,
        privileges=[users.Privilege.LIST],
        refresh_key=False
    )

    assert this_user.name == created_user.name
    assert this_user.privileges == [users.Privilege.LIST]

@pytest.mark.asyncio(scope="session")
async def test_read_user_not_found():
    with pytest.raises(users.UserNotFound):
        await users.read(name="non_existent_user")
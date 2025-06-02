"""
Tests the functions in the user service.
"""

import pytest

from hipposerve.service import users


@pytest.mark.asyncio(loop_scope="session")
async def test_read_user(created_database_user):
    this_user = await users.read(name=created_database_user.name)
    assert this_user.name == created_database_user.name
    this_user = await users.read_by_id(id=created_database_user.id)
    assert this_user.name == created_database_user.name
    assert this_user.last_access_time is not None


@pytest.mark.asyncio(loop_scope="session")
async def test_read_user_not_found():
    with pytest.raises(users.UserNotFound):
        await users.read(name="non_existent_user")

    with pytest.raises(users.UserNotFound):
        await users.read_by_id(id="7" * 24)

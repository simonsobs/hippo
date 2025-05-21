"""
Facilities for creating and updating users.
"""

from beanie import PydanticObjectId

from hipposerve.database import User
from hipposerve.service.utils import current_utc_time


# TODO: Centralised exceptions?
class UserNotFound(Exception):
    pass


class AuthenticationError(Exception):
    pass


async def create(
    name: str,
    email: str | None,
) -> User:
    user = User(
        name=name,
        email=email,
        last_access_time=current_utc_time(),
    )
    await user.create()

    return user


async def read(name: str) -> User:
    result = await User.find(User.name == name, fetch_links=True).first_or_none()

    if result is None:
        raise UserNotFound

    return result


async def read_by_id(id: PydanticObjectId) -> User:
    result = await User.get(id, fetch_links=True)

    if result is None:
        raise UserNotFound

    return result


async def delete(name: str):
    user = await read(name=name)
    await user.delete()

    return

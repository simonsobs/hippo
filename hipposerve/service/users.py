"""
Facilities for creating and updating users.
"""

import secrets

from beanie import PydanticObjectId
from pwdlib import PasswordHash

from hipposerve.database import ComplianceInformation, Privilege, User

# TODO: Settings
API_KEY_BYTES = 128
PASSWORD_BYTES = 32


def API_KEY():
    return secrets.token_urlsafe(API_KEY_BYTES)


def EMPTY_PASSWORD():
    return secrets.token_urlsafe(PASSWORD_BYTES)


# TODO: Centralised exceptions?
class UserNotFound(Exception):
    pass


class AuthenticationError(Exception):
    pass


async def create(
    name: str,
    password: str | None,
    email: str | None,
    avatar_url: str | None,
    gh_profile_url: str | None,
    privileges: list[Privilege],
    hasher: PasswordHash,
    compliance: ComplianceInformation | None,
) -> User:
    if password is None:
        # When using GitHub auth we don't have a password.
        hashed_password = hasher.hash(EMPTY_PASSWORD())
    else:
        hashed_password = hasher.hash(password)

    user = User(
        name=name,
        hashed_password=hashed_password,
        email=email,
        avatar_url=avatar_url,
        gh_profile_url=gh_profile_url,
        api_key=API_KEY(),
        privileges=privileges,
        compliance=compliance,
    )

    await user.create()

    return user


async def read(name: str) -> User:
    result = await User.find(User.name == name).first_or_none()

    if result is None:
        raise UserNotFound

    return result


async def read_by_id(id: PydanticObjectId) -> User:
    result = await User.get(id)

    if result is None:
        raise UserNotFound

    return result


async def update(
    name: str,
    hasher: PasswordHash,
    password: str | None,
    privileges: list[Privilege] | None,
    compliance: ComplianceInformation | None,
    refresh_key: bool = False,
) -> User:
    user = await read(name=name)

    if privileges is not None:
        await user.set({User.privileges: privileges})

    if refresh_key:
        await user.set({User.api_key: API_KEY()})

    if password is not None:
        hashed_password = hasher.hash(password)
        await user.set({User.hashed_password: hashed_password})

    if compliance is not None:
        await user.set({User.compliance: compliance})

    return user


async def delete(name: str):
    user = await read(name=name)
    await user.delete()

    return


### --- Security --- ###


async def user_from_api_key(api_key: str) -> User:
    result = await User.find(User.api_key == api_key).first_or_none()

    if result is None:
        raise UserNotFound

    return result


async def read_with_password_verification(
    name: str, password: str, hasher: PasswordHash
) -> User:
    user = await read(name=name)

    if hasher.verify(password, user.hashed_password):
        return user
    else:
        raise UserNotFound

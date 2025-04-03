"""
Functionalities for creating and updating groups.
"""

from beanie import PydanticObjectId

from hipposerve.database import Group, Privilege


class GroupNotCreated(Exception):
    pass


class GroupNotFound(Exception):
    pass


async def create(
    name: str,
    description: str | None,
    access_control: list[Privilege] | None,
) -> Group:
    group = Group(
        name=name,
        description=description,
        access_controls=access_control,
    )

    await group.create()

    return group


async def read_by_name(name: str) -> Group:
    result = await Group.find(Group.name == name).first_or_none()

    if result is None:
        raise GroupNotFound

    return result


async def read_by_id(id: PydanticObjectId) -> Group:
    result = await Group.get(id)

    if result is None:
        raise GroupNotFound

    return result


async def update(
    name: str,
    description: str | None,
    access_control: list[Privilege] | None,
) -> Group:
    group = await read_by_name(name=name)

    if description is not None:
        await group.set({Group.description: description})

    if access_control is not None:
        await group.set({Group.access_controls: access_control})

    return group


async def delete(name: str):
    group = await read_by_name(name=name)
    await group.delete()

    return

"""
Functionalities for creating and updating groups.
"""

from beanie import PydanticObjectId

from hipposerve.database import AccessControl, Group


class GroupNotFound(Exception):
    pass


async def create(
    name: str,
    description: str | None,
    user_list: list[str] = [],
    access_control: dict[AccessControl, bool] = {},
) -> Group:
    try:
        group = Group(
            name=name,
            description=description,
            user_list=user_list,
            access_controls=access_control,
        )

        await group.create()

        return group
    except Exception as e:
        raise RuntimeError("Failed to create group: " + str(e)) from e


async def read(name: str) -> Group:
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
    user_list: list[str] | None,
    access_control: dict[AccessControl, bool] | None,
) -> Group:
    group = await read(name=name)

    if description is not None:
        await group.set({Group.description: description})

    if user_list is not None:
        await group.set({Group.user_list: user_list})

    if access_control is not None:
        await group.set({Group.access_controls: access_control})

    return group


async def delete(name: str):
    group = await read(name=name)
    await group.delete()

    return

"""
Functionalities for creating and updating groups.
"""

from beanie import PydanticObjectId

from hipposerve.database import Group, Privilege


class GroupNotFound(Exception):
    pass


async def create(
    name: str,
    description: str | None,
    access_control: list[Privilege],
) -> Group:
    group = Group(
        name=name,
        description=description,
        access_controls=access_control,
    )

    await group.create()

    return group


async def create_common_group(
    name: str,
) -> Group:
    group = Group(
        name=name,
        description="Default group for all users",
        access_controls=[
            Privilege.LIST_PRODUCT,
            Privilege.DOWNLOAD_PRODUCT,
            Privilege.READ_PRODUCT,
            Privilege.READ_COLLECTION,
        ],
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


async def update_desciption(
    name: str,
    description: str | None,
) -> Group:
    group = await read_by_name(name=name)

    if description is not None:
        await group.set({Group.description: description})

    return group


async def update_access_control(
    name: str,
    add_access_control: list[Privilege] | None = None,
    remove_access_control: list[Privilege] | None = None,
) -> Group:
    group = await read_by_name(name=name)

    if add_access_control is not None:
        group.access_controls.extend(add_access_control)

    if remove_access_control is not None:
        for privilege in remove_access_control:
            group.access_controls.remove(privilege)

    await group.set({Group.access_controls: group.access_controls})

    return group


async def delete(name: str):
    group = await read_by_name(name=name)
    await group.delete()

    return

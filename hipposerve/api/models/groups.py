"""
Request and response models for the groups endpoints.
"""

from pydantic import BaseModel

from hipposerve.service.users import Privilege


class CreateGroupRequest(BaseModel):
    privileges: list[Privilege]
    description: str | None


class CreateGroupResponse(BaseModel):
    group_name: str


class ReadGroupResponse(BaseModel):
    name: str
    privileges: list[Privilege]
    description: str | None


class UpdateGroupAccessRequest(BaseModel):
    add_access_control: list[Privilege] | None = None
    remove_access_control: list[Privilege] | None = None


class UpdateGroupAccessResponse(BaseModel):
    access_controls: list[Privilege]


class UpdateGroupDescriptionRequest(BaseModel):
    description: str | None = None


class UpdateGroupDescriptionResponse(BaseModel):
    description: str

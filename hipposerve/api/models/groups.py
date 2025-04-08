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

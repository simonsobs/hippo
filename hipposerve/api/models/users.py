"""
Request and response models for the users endpoints.
"""

from pydantic import BaseModel

from hipposerve.database import ComplianceInformation
from hipposerve.service.users import Privilege


class CreateUserRequest(BaseModel):
    privileges: list[Privilege]
    password: str | None
    compliance: ComplianceInformation | None
    email: str | None
    avatar_url: str | None
    gh_profile_url: str | None


class CreateUserResponse(BaseModel):
    api_key: str | None


class ReadUserResponse(BaseModel):
    name: str
    privileges: list[Privilege]
    compliance: ComplianceInformation | None


class UpdateUserRequest(BaseModel):
    privileges: list[Privilege] | None = None
    refresh_key: bool = False
    password: str | None = None
    compliance: ComplianceInformation | None = None
    add_groups: list[str] | None = None
    remove_groups: list[str] | None = None


class UpdateUserResponse(BaseModel):
    api_key: str | None
    compliance: ComplianceInformation | None = None

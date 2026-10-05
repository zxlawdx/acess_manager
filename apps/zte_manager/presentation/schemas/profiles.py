from typing import Any

from pydantic import BaseModel, Field


class ProfileRequest(BaseModel):
    attendant: str
    wifi: dict[str, dict[str, Any]] = Field(default_factory=dict)
    dns: dict[str, Any] = Field(default_factory=dict)


class NamedPresetRequest(BaseModel):
    attendant: str = Field(min_length=1, max_length=100)
    name: str = Field(min_length=1, max_length=60)


class NamedPresetSaveRequest(NamedPresetRequest):
    wifi: dict[str, dict[str, Any]] = Field(default_factory=dict)
    dns: dict[str, Any] = Field(default_factory=dict)


class TR069ProviderSaveRequest(BaseModel):
    profile: dict[str, Any] = Field(default_factory=dict)


class TR069ProviderDeleteRequest(BaseModel):
    name: str = Field(min_length=1, max_length=60)


class TR069ProviderApplyRequest(BaseModel):
    name: str = Field(min_length=1, max_length=60)
    wan_name: str = Field(min_length=1, max_length=120)
    password: str | None = Field(default=None, max_length=256)
    connection_request_password: str | None = Field(default=None, max_length=256)
    confirm: bool = False


class AttendantRequest(BaseModel):
    attendant: str

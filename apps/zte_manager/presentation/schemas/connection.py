from typing import Literal

from pydantic import BaseModel, Field


class HuaweiCliRequest(BaseModel):
    enabled: bool = False
    transport: Literal["auto", "ssh", "telnet"] = "auto"
    username: str | None = None
    password: str | None = None
    port: int | None = Field(default=None, ge=1, le=65535)
    timeout: float = Field(default=3.0, gt=0, le=30)


class ConnectRequest(BaseModel):
    ip: str
    model_hint: str | None = None
    username: str
    password: str
    https: bool = False
    attendant: str | None = None
    huawei_cli: HuaweiCliRequest | None = None


class AdminPasswordRequest(BaseModel):
    new_password: str = Field(
        min_length=1,
        max_length=256,
    )

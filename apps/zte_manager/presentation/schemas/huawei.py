from typing import Any

from pydantic import BaseModel, Field


class HuaweiIPv4FilterRuleRequest(BaseModel):
    instance_or_domain: str | int | None = None
    name: str = Field(min_length=1, max_length=128)
    protocol: str = Field(min_length=1, max_length=32)
    direction: str = Field(min_length=1, max_length=32)
    lan_start_ip: str = Field(default="", max_length=64)
    lan_end_ip: str = Field(default="", max_length=64)
    wan_start_ip: str = Field(default="", max_length=64)
    wan_end_ip: str = Field(default="", max_length=64)
    lan_tcp_port: str = Field(default="", max_length=16)
    lan_udp_port: str = Field(default="", max_length=16)
    wan_tcp_port: str = Field(default="", max_length=16)
    wan_udp_port: str = Field(default="", max_length=16)


class HuaweiFeatureUpdateRequest(BaseModel):
    feature: str = Field(min_length=1, max_length=64)
    config: dict[str, Any] = Field(default_factory=dict)


class HuaweiIPv4FilterDeleteRequest(BaseModel):
    instance_or_domain: str | int

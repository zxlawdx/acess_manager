from typing import Any

from pydantic import BaseModel, Field


class UpnpRequest(BaseModel):
    enabled: bool | None = None
    wan: str | None = None
    wan_ipv6: str | None = None
    advertisement_period: int | None = Field(default=None, ge=4, le=1440)
    ttl: int | None = Field(default=None, ge=1, le=255)


class DnsRequest(BaseModel):
    domain_name: str | None = None
    ipv4_1: str | None = None
    ipv4_2: str | None = None
    ipv6_1: str | None = None
    ipv6_2: str | None = None
    hosts: list[dict[str, Any]] = Field(default_factory=list)


class DhcpBasicRequest(BaseModel):
    enabled: bool | None = None
    dhcp_enable: bool | None = None
    l2_relay_enable: bool | None = None
    option125_enable: bool | None = None
    min_address: str | None = None
    max_address: str | None = None
    dns_source: str | None = None
    dns1: str | None = None
    dns2: str | None = None
    lease_time: int | None = Field(default=None, ge=60)
    ipv4_dns_origin: str | None = None


class DhcpReservationRequest(BaseModel):
    id: str | None = None
    name: str = Field(min_length=1, max_length=64)
    ip: str = Field(min_length=7, max_length=45)
    mac: str = Field(min_length=11, max_length=32)


class ResourceIdRequest(BaseModel):
    id: str = Field(min_length=1)
    confirm: bool = False


class PortForwardRequest(BaseModel):
    id: str | None = None
    name: str = Field(default="", max_length=64)
    enabled: bool = True
    protocol: str = "TCP"
    interface: str | None = None
    all_interfaces: bool = True
    external_port: int = Field(ge=1, le=65535)
    external_port_end: int | None = Field(default=None, ge=1, le=65535)
    internal_client: str
    internal_port: int = Field(ge=1, le=65535)
    internal_port_end: int | None = Field(default=None, ge=1, le=65535)
    remote_host: str | None = None
    remote_host_end: str | None = None
    description: str | None = Field(default=None, max_length=128)
    confirm: bool = False


class DmzRequest(BaseModel):
    id: str | None = None
    enabled: bool = False
    internal_client: str = ""
    wan: str | None = None
    confirm: bool = False

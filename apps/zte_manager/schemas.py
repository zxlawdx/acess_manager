from typing import Any

from pydantic import BaseModel, Field


class ConnectRequest(BaseModel):
    ip: str
    username: str
    password: str
    https: bool = False
    attendant: str | None = None


class WifiRadioRequest(BaseModel):
    band: str | None = None
    auto_channel: bool | None = None
    channel: int | None = None
    standard: str | None = None
    country: str | None = None
    bandwidth: str | None = None
    sgi: bool | None = None
    beacon_interval: int | None = Field(
        default=None,
        ge=100,
        le=1000
    )
    tx_power: str | None = None
    sideband: str | None = None


class WifiSSIDRequest(BaseModel):
    ssid_id: str | None = None
    enabled: bool | None = None
    ssid: str | None = None
    password: str | None = None
    broadcast: bool | None = None
    hidden: bool | None = None
    isolation: bool | None = None
    max_clients: int | None = Field(
        default=None,
        ge=1,
        le=64
    )
    encryption: str | None = None


class AdminPasswordRequest(BaseModel):
    new_password: str = Field(
        min_length=1,
        max_length=256
    )


class RadioPowerRequest(BaseModel):
    band: str
    enabled: bool


class BandSteeringRequest(BaseModel):
    enabled: bool


class WpsRequest(BaseModel):
    band: str
    mode: str


class UpnpRequest(BaseModel):
    enabled: bool | None = None
    wan: str | None = None
    wan_ipv6: str | None = None
    advertisement_period: int | None = Field(
        default=None,
        ge=4,
        le=1440
    )
    ttl: int | None = Field(
        default=None,
        ge=1,
        le=255
    )


class DnsRequest(BaseModel):
    domain_name: str | None = None
    ipv4_1: str | None = None
    ipv4_2: str | None = None
    ipv6_1: str | None = None
    ipv6_2: str | None = None
    hosts: list[dict[str, Any]] = Field(
        default_factory=list
    )


class PingRequest(BaseModel):
    host: str = "8.8.8.8"
    interface: str = ""
    ip_version: str = "IPv4"


class TracerouteRequest(BaseModel):
    host: str = "8.8.8.8"
    interface: str = ""
    max_hops: int = Field(
        default=30,
        ge=1,
        le=64
    )
    timeout: int = Field(
        default=5000,
        ge=2000,
        le=10000
    )
    protocol: str = "ICMP"
    ip_version: str = "IPv4"


class ProfileRequest(BaseModel):
    attendant: str
    wifi: dict[str, dict[str, Any]] = Field(
        default_factory=dict
    )
    dns: dict[str, Any] = Field(
        default_factory=dict
    )


class AttendantRequest(BaseModel):
    attendant: str

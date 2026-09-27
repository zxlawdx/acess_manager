"""Vendor-neutral runtime contract. The existing model/device_adapters/base.py
remains the legacy *feature catalogue*, NOT the authenticated runtime driver.
New manufacturers implement this protocol without being imported by API routes.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping, Protocol, runtime_checkable


@dataclass(frozen=True, slots=True)
class Credentials:
    host: str
    username: str
    password: str = field(repr=False)
    https: bool = False


@dataclass(frozen=True, slots=True)
class SessionContext:
    id: str
    host: str = field(repr=False)
    model: str | None = None
    firmware: str | None = None
    writable: bool = False


@dataclass(frozen=True, slots=True)
class DeviceInfo:
    manufacturer: str | None = None
    model: str | None = None
    firmware: str | None = None
    serial: str | None = field(default=None, repr=False)


@runtime_checkable
class DeviceAdapter(Protocol):
    """Each method executes against one serialized authenticated device session.

    get_lan_config/set_lan_config cover a supported LAN feature (initially DHCP),
    not arbitrary LAN-IP changes. verify_change must return True only after a
    fresh device read matches an explicit, operation-specific expected state.
    """

    def authenticate(self, credentials: Credentials) -> SessionContext: ...
    def read_info(self) -> DeviceInfo: ...
    def get_lan_config(self) -> Mapping[str, Any]: ...
    def set_lan_config(self, config: Mapping[str, Any]) -> Any: ...
    def get_wifi_config(self) -> Mapping[str, Any]: ...
    def set_wifi_config(self, config: Mapping[str, Any]) -> Any: ...
    def verify_change(
        self, operation: str, expected_state: Mapping[str, Any]
    ) -> bool: ...
    def close(self) -> None: ...

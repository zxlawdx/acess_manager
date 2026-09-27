"""Best-effort, allowlisted inventory updates independent from authentication."""
from __future__ import annotations

import logging
from collections.abc import Mapping
from typing import Any, Protocol

logger = logging.getLogger(__name__)


class DeviceRepository(Protocol):
    def upsert_device(self, data: dict[str, Any]) -> Any: ...


def _field(value: Any, limit: int) -> str | None:
    if not isinstance(value, str):
        return None
    text = value.strip()
    # Forbid line breaks, control characters and excessively long metadata.
    if not text or len(text) > limit or any(ord(char) < 32 for char in text):
        return None
    return text


def _first(info: Mapping[str, Any], keys: tuple[str, ...], limit: int) -> str | None:
    for key in keys:
        found = _field(info.get(key), limit)
        if found is not None:
            return found
    return None


class DeviceRegistrar:
    """Inventory must never prevent an authenticated technician from working.

    Never copy arbitrary router payloads or passwords into SQLite metadata.
    Logging contains only operation codes / exception types, never identifiers.
    """

    def __init__(self, repository: DeviceRepository) -> None:
        self._repository = repository

    def register(
        self, *, host: str | None, device_info: Mapping[str, Any] | None,
        adapter_name: str | None, attendant: str | None = None,
    ) -> bool:
        try:
            info = device_info if isinstance(device_info, Mapping) else {}
            safe_host = _field(host, 255)
            serial = _first(info, ("serial", "serial_number", "sn", "SerialNumber"), 128)
            mac = _first(info, ("mac", "mac_address", "MACAddress"), 32)
            if not (serial or mac or safe_host):
                logger.warning("inventory_register_skipped reason=missing_identity")
                return False

            # This is an ALLOWLIST; nested data from the firmware is never stored.
            record: dict[str, Any] = {
                "key": serial or mac or safe_host,
                "host": safe_host,
                "model": _first(info, ("modelo", "model"), 128),
                "serial": serial,
                "mac": mac,
                "firmware": _first(info, ("firmware", "software"), 128),
                "status": "online",
                "metadata": {
                    "adapter": _field(adapter_name, 80),
                    "attendant": _field(attendant, 80),
                },
            }
            self._repository.upsert_device(record)
            return True
        except Exception as exc:
            logger.warning(
                "inventory_register_failed error_type=%s",
                type(exc).__name__,
            )
            return False

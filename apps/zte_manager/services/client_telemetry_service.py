from __future__ import annotations

import time
from collections.abc import Mapping
from threading import RLock
from typing import Any

from apps.zte_manager.model.telemetry import (
    ClientTelemetry,
    ClientTrafficRateCalculator,
)
from apps.zte_manager.services.provider_router import ProviderRouter


def _first(row: Mapping[str, Any], *keys: str) -> Any:
    for key in keys:
        if key in row and row[key] not in (None, ""):
            return row[key]
    return None


def _as_int(value: Any) -> int | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        return int(float(str(value).strip()))
    except (TypeError, ValueError):
        return None


def _as_bool(value: Any) -> bool | None:
    if value is None:
        return None
    if isinstance(value, bool):
        return value
    normalized = str(value).strip().casefold()
    if normalized in {"1", "true", "yes", "on", "online", "up", "connected"}:
        return True
    if normalized in {"0", "false", "no", "off", "offline", "down", "disconnected"}:
        return False
    return None


def _rows(value: Any) -> list[Mapping[str, Any]]:
    if isinstance(value, list):
        return [item for item in value if isinstance(item, Mapping)]
    if isinstance(value, Mapping):
        for key in ("clients", "items", "data", "rows", "devices"):
            nested = value.get(key)
            if isinstance(nested, list):
                return [item for item in nested if isinstance(item, Mapping)]
        # A single client-shaped object is also a valid one-row result.
        if any(key in value for key in ("mac", "MAC", "mac_address", "ip", "IP")):
            return [value]
    return []


def normalize_client(
    row: Mapping[str, Any],
    *,
    connection_type: str,
) -> ClientTelemetry:
    return ClientTelemetry(
        mac=_first(row, "mac", "mac_address", "macAddress", "MAC", "MacAddress"),
        hostname=_first(row, "hostname", "host_name", "hostName", "HostName", "name"),
        ip=_first(row, "ip", "ip_address", "ipAddress", "IP", "IpAddress"),
        interface=_first(row, "interface", "ifname", "port", "Interface"),
        connection_type=(
            _first(row, "connection_type", "connectionType", "type")
            or connection_type
        ),
        ssid=_first(row, "ssid", "SSID", "ssid_name", "ssidName"),
        band=_first(row, "band", "Band", "radio_band"),
        rx_bytes=_as_int(_first(
            row,
            "rx_bytes", "rxBytes", "receive_bytes", "received_bytes", "BytesReceived",
        )),
        tx_bytes=_as_int(_first(
            row,
            "tx_bytes", "txBytes", "transmit_bytes", "sent_bytes", "BytesSent",
        )),
        rssi=_as_int(_first(row, "rssi", "RSSI", "signal", "signal_dbm")),
        snr=_as_int(_first(row, "snr", "SNR")),
        online=_as_bool(_first(row, "online", "status", "connected", "active")),
        connected_seconds=_as_int(_first(
            row,
            "connected_seconds", "connectedSeconds", "uptime", "online_time",
        )),
    )


class ClientTelemetryService:
    """Normalize client rows and derive traffic rates without vendor branching."""

    def __init__(self) -> None:
        self._rates = ClientTrafficRateCalculator()
        self._session_key: str | None = None
        self._lock = RLock()

    def _activate_session(self, status: Mapping[str, Any]) -> str:
        key = "|".join(str(status.get(name) or "") for name in (
            "vendor", "host", "device_id", "session_revision",
        ))
        with self._lock:
            if key != self._session_key:
                self._rates.clear()
                self._session_key = key
        return key

    @staticmethod
    def _read(runtime: Any, method_name: str, *, refresh: bool) -> list[Mapping[str, Any]]:
        try:
            value = ProviderRouter.invoke(runtime, method_name, refresh=refresh)
        except AttributeError:
            return []
        return _rows(value)

    def collect(self, device_service: Any, *, refresh: bool = False) -> dict[str, Any]:
        status = device_service.status()
        session_key = self._activate_session(status)
        runtime = device_service.active_service
        sampled_at = time.monotonic()

        normalized: list[ClientTelemetry] = []
        for kind, method in (("wifi", "wifi_clients"), ("lan", "lan_clients")):
            for row in self._read(runtime, method, refresh=refresh):
                client = normalize_client(row, connection_type=kind)
                identity = client.mac or client.ip or client.interface
                if identity:
                    client = self._rates.enrich(
                        client,
                        sampled_at=sampled_at,
                        key=f"{session_key}|{kind}|{identity}",
                    )
                normalized.append(client)

        return {
            "vendor": status.get("vendor"),
            "model": status.get("model"),
            "mode": status.get("mode"),
            "clients": [client.as_dict() for client in normalized],
        }


client_telemetry_service = ClientTelemetryService()

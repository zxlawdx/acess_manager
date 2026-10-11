from __future__ import annotations

from dataclasses import asdict, dataclass, replace
from threading import RLock
from typing import Any


@dataclass(frozen=True)
class PonStatus:
    """Vendor-neutral PON registration state."""

    registration: str | None = None
    o_state: str | None = None
    mode: str | None = None
    onu_id: str | None = None
    online: bool | None = None
    configuration_mode: str | None = None
    source_transport: str | None = None
    source_endpoint: str | None = None
    source_command: str | None = None

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class PonStatistics:
    """Vendor-neutral GPON/EPON packet and protocol counters."""

    rx_unicast_packets: int | None = None
    tx_unicast_packets: int | None = None
    rx_broadcast_packets: int | None = None
    tx_broadcast_packets: int | None = None
    rx_multicast_packets: int | None = None
    tx_multicast_packets: int | None = None
    dropped_packets: int | None = None
    tx_ploam: int | None = None
    tx_omci: int | None = None
    tx_gem: int | None = None
    bip_errors: int | None = None
    rx_ploam_right: int | None = None
    rx_ploam_wrong: int | None = None
    rx_ploam_drop: int | None = None
    rx_omci: int | None = None
    rx_gem: int | None = None
    rx_multicast_gem: int | None = None
    rx_omci_overflow: int | None = None
    tx_octets: int | None = None
    tx_packets: int | None = None
    rx_octets: int | None = None
    rx_packets: int | None = None
    rx_oversize: int | None = None
    rx_undersize: int | None = None
    source_transport: str | None = None
    source_command: str | None = None

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class OpticalTelemetry:
    """Normalized DOM/optical telemetry with explicit engineering units."""

    link_status: str | None = None
    tx_power_dbm: float | None = None
    rx_power_dbm: float | None = None
    voltage_mv: float | None = None
    temperature_c: float | None = None
    bias_ma: float | None = None
    rf_rx_power_dbm: float | None = None
    rf_output_power_dbmv: float | None = None
    source_transport: str | None = None
    source_endpoint: str | None = None
    source_command: str | None = None
    signature: str | None = None

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class DeviceResourceTelemetry:
    """Runtime resource telemetry; intentionally separate from optical/PON."""

    cpu_used_percent: float | None = None
    memory_used_percent: float | None = None
    uptime_seconds: int | None = None
    current_time: str | None = None
    source_transport: str | None = None
    source_command: str | None = None

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class ClientTelemetry:
    """Normalized client telemetry shared by every vendor workspace.

    Unknown values stay ``None``. In particular, ``0`` is a real counter/rate
    and must never be used as a substitute for data the equipment did not
    expose.
    """

    mac: str | None = None
    hostname: str | None = None
    ip: str | None = None
    interface: str | None = None
    connection_type: str | None = None
    ssid: str | None = None
    band: str | None = None
    rx_bytes: int | None = None
    tx_bytes: int | None = None
    rx_rate_bps: int | None = None
    tx_rate_bps: int | None = None
    rssi: int | None = None
    snr: int | float | None = None
    online: bool | None = None
    connected_seconds: int | None = None

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class ClientTrafficSnapshot:
    rx_bytes: int
    tx_bytes: int
    sampled_at: float


class ClientTrafficRateCalculator:
    """Derive bps only from two valid monotonic counter snapshots.

    The first observation has no rate. Counter reset/wrap or non-positive time
    deltas reset the baseline and also return ``None``. A genuine zero byte
    delta over positive time is returned as rate ``0``.
    """

    def __init__(self) -> None:
        self._snapshots: dict[str, ClientTrafficSnapshot] = {}
        self._lock = RLock()

    def clear(self) -> None:
        with self._lock:
            self._snapshots.clear()

    def rates(
        self,
        key: str,
        *,
        rx_bytes: int | None,
        tx_bytes: int | None,
        sampled_at: float,
    ) -> tuple[int | None, int | None]:
        identity = str(key or "").strip().casefold()
        if not identity or rx_bytes is None or tx_bytes is None:
            return None, None
        if rx_bytes < 0 or tx_bytes < 0:
            return None, None

        current = ClientTrafficSnapshot(
            rx_bytes=int(rx_bytes),
            tx_bytes=int(tx_bytes),
            sampled_at=float(sampled_at),
        )
        with self._lock:
            previous = self._snapshots.get(identity)
            self._snapshots[identity] = current

        if previous is None:
            return None, None

        delta_t = current.sampled_at - previous.sampled_at
        delta_rx = current.rx_bytes - previous.rx_bytes
        delta_tx = current.tx_bytes - previous.tx_bytes
        if delta_t <= 0 or delta_rx < 0 or delta_tx < 0:
            return None, None

        return (
            int((delta_rx * 8) / delta_t),
            int((delta_tx * 8) / delta_t),
        )

    def enrich(
        self,
        client: ClientTelemetry,
        *,
        sampled_at: float,
        key: str | None = None,
    ) -> ClientTelemetry:
        identity = key or client.mac or client.ip or client.interface
        if not identity:
            return client
        rx_rate, tx_rate = self.rates(
            identity,
            rx_bytes=client.rx_bytes,
            tx_bytes=client.tx_bytes,
            sampled_at=sampled_at,
        )
        return replace(
            client,
            rx_rate_bps=rx_rate,
            tx_rate_bps=tx_rate,
        )

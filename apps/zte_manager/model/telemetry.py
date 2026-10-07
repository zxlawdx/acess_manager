from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any


@dataclass(frozen=True)
class PonStatus:
    """Vendor-neutral PON registration state.

    Status is deliberately separate from counters/statistics because the two
    surfaces have different volatility, transport availability and cache
    semantics on ONTs.
    """

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

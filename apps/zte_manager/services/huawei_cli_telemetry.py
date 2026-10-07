from __future__ import annotations

import re
from typing import Any

from apps.zte_manager.model.telemetry import (
    DeviceResourceTelemetry,
    OpticalTelemetry,
    PonStatistics,
    PonStatus,
)


DISPLAY_ONU_INFO = "display onu info"
DISPLAY_OPTIC = "display optic"
DISPLAY_SYSINFO = "display sysinfo"
DISPLAY_PON_STATISTICS = "display pon statistics"

# Deliberately no "clear pon statistics": reading telemetry must not mutate the
# device or reset counters.
HUAWEI_CLI_TELEMETRY_COMMANDS = (
    DISPLAY_ONU_INFO,
    DISPLAY_OPTIC,
    DISPLAY_SYSINFO,
    DISPLAY_PON_STATISTICS,
)


def _number(value: object) -> float | None:
    text = str(value or "").strip()
    if not text or text in {"--", "-", "N/A", "n/a"}:
        return None
    try:
        return float(text)
    except ValueError:
        return None


def _integer(value: object) -> int | None:
    number = _number(value)
    return int(number) if number is not None else None


def _kv_lines(source: str) -> dict[str, str]:
    result: dict[str, str] = {}
    for raw in str(source or "").splitlines():
        line = raw.strip()
        if not line or line.casefold().startswith("wap>"):
            continue
        match = re.match(r"^([^:=]+?)\s*[:=]\s*(.*?)\s*$", line)
        if not match:
            continue
        key = " ".join(match.group(1).split()).casefold()
        value = match.group(2).strip()
        result[key] = value
    return result


def _first_token(value: str | None) -> str | None:
    text = str(value or "").strip()
    return text.split()[0] if text else None


def parse_wap_optical(source: str, *, transport: str) -> OpticalTelemetry:
    values = _kv_lines(source)
    if not any(key in values for key in ("rxpower", "txpower", "linkstatus")):
        raise RuntimeError("Saída WAP de óptica não reconhecida.")
    return OpticalTelemetry(
        link_status=_first_token(values.get("linkstatus")),
        voltage_mv=_number(_first_token(values.get("voltage"))),
        bias_ma=_number(_first_token(values.get("bias"))),
        temperature_c=_number(_first_token(values.get("temperature"))),
        rx_power_dbm=_number(_first_token(values.get("rxpower"))),
        tx_power_dbm=_number(_first_token(values.get("txpower"))),
        rf_rx_power_dbm=_number(_first_token(values.get("rfrxpower"))),
        rf_output_power_dbmv=_number(_first_token(values.get("rfoutputpower"))),
        source_transport=transport,
        source_command=DISPLAY_OPTIC,
        signature="wap:display-optic",
    )


def parse_wap_resources(source: str, *, transport: str) -> DeviceResourceTelemetry:
    values = _kv_lines(source)
    cpu = _number(_first_token(values.get("cpuused")))
    memory = _number(_first_token(values.get("memused")))
    if cpu is None and memory is None:
        raise RuntimeError("Saída WAP de recursos não reconhecida.")
    return DeviceResourceTelemetry(
        cpu_used_percent=cpu,
        memory_used_percent=memory,
        current_time=values.get("curtime"),
        source_transport=transport,
        source_command=DISPLAY_SYSINFO,
    )


_PON_FIELDS: dict[str, str] = {
    "rx unicast packets": "rx_unicast_packets",
    "tx unicast packets": "tx_unicast_packets",
    "rx broadcast packets": "rx_broadcast_packets",
    "tx broadcast packets": "tx_broadcast_packets",
    "rx multicast packets": "rx_multicast_packets",
    "tx multicast packets": "tx_multicast_packets",
    "dropped packets": "dropped_packets",
    "tx ploam": "tx_ploam",
    "tx omci": "tx_omci",
    "tx gem": "tx_gem",
    "bip err": "bip_errors",
    "rx ploam right": "rx_ploam_right",
    "rx ploam wrong": "rx_ploam_wrong",
    "rx ploam drop": "rx_ploam_drop",
    "rx omci": "rx_omci",
    "rx gem": "rx_gem",
    "rx mc gem": "rx_multicast_gem",
    "rx multicast gem": "rx_multicast_gem",
    "rx omci overflow": "rx_omci_overflow",
    "tx octets": "tx_octets",
    "tx packets": "tx_packets",
    "rx octets": "rx_octets",
    "rx packets": "rx_packets",
    "rx oversize": "rx_oversize",
    "rx undersize": "rx_undersize",
}


def parse_wap_pon_statistics(source: str, *, transport: str) -> PonStatistics:
    values = _kv_lines(source)
    parsed: dict[str, Any] = {}
    for source_name, field_name in _PON_FIELDS.items():
        raw = _first_token(values.get(source_name))
        if raw is not None:
            parsed[field_name] = _integer(raw)
    if not any(value is not None for value in parsed.values()):
        raise RuntimeError("Saída WAP de estatísticas PON não reconhecida.")
    return PonStatistics(
        **parsed,
        source_transport=transport,
        source_command=DISPLAY_PON_STATISTICS,
    )


def parse_wap_pon_status(source: str, *, transport: str) -> PonStatus:
    text = str(source or "")
    match = re.search(r"(?i)\bstatus\s*[:=]\s*([A-Z0-9_-]+)", text)
    status = match.group(1).upper() if match else None
    if not status:
        raise RuntimeError("Saída WAP de estado ONU não reconhecida.")
    online = status in {"O5", "O5AUTH", "ONLINE", "UP"}
    return PonStatus(
        registration=status,
        o_state=status if status.startswith("O") else None,
        online=online,
        source_transport=transport,
        source_command=DISPLAY_ONU_INFO,
    )


class HuaweiCliTelemetryReader:
    """Collect read-only WAP telemetry from an already authenticated transport."""

    def __init__(self, transport) -> None:
        self.transport = transport

    @property
    def transport_name(self) -> str:
        return str(getattr(self.transport, "name", "cli"))

    def optical(self) -> OpticalTelemetry:
        return parse_wap_optical(
            self.transport.run(DISPLAY_OPTIC),
            transport=self.transport_name,
        )

    def resources(self) -> DeviceResourceTelemetry:
        return parse_wap_resources(
            self.transport.run(DISPLAY_SYSINFO),
            transport=self.transport_name,
        )

    def pon_statistics(self) -> PonStatistics:
        return parse_wap_pon_statistics(
            self.transport.run(DISPLAY_PON_STATISTICS),
            transport=self.transport_name,
        )

    def pon_status(self) -> PonStatus:
        return parse_wap_pon_status(
            self.transport.run(DISPLAY_ONU_INFO),
            transport=self.transport_name,
        )

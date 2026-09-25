"""Actual F6201B diagnostic orchestration.

No artificial operator checks: independent firmware-confirmed GET readings,
real native diagnostic POSTs, explicit opt-in Wi-Fi auto-channel action and
measured speedtest. Failure of one stage never claims another succeeded.
The caller owns ZTEService._lock for the entire sequence.
"""
from __future__ import annotations

from collections.abc import Callable

MODES = {
    "general": ("device_info", "pon_optical", "wan", "dns", "wifi_clients",
                "wifi_radios", "lan_ports", "wifi_ssids"),
    "no_internet": ("device_info", "pon_optical", "wan", "dns", "lan_ports"),
    "wifi": ("device_info", "wifi_ssids", "wifi_radios", "wifi_clients",
             "band_steering", "wps"),
    "drops": ("device_info", "pon_optical", "wan", "wifi_clients",
              "wifi_radios"),
    "low_speed": ("device_info", "wan", "lan_ports", "wifi_radios",
                  "wifi_clients"),
}
READ_SECTIONS = {
    "device_info": "device", "pon_optical": "optical", "wan": "wan",
    "dns": "dns", "wifi_clients": "wifi_clients", "wifi_radios": "wifi_radios",
    "lan_ports": "lan_ports", "wifi_ssids": "wifi_ssids",
    "band_steering": "band_steering", "wps": "wps",
}


def _problem(exc: Exception) -> str:
    """Never return raw router XML, credentials or HTTP response bodies."""
    return {
        "ValueError": "Parâmetros ou recurso indisponível neste firmware.",
        "PermissionError": "A sessão da ONT não autorizou esta operação.",
        "TimeoutError": "A ONT não confirmou novo resultado no tempo esperado.",
    }.get(type(exc).__name__, "Não foi possível confirmar esta operação.")


def run_f6201b_support(
    *, config: dict, firmware: str,
    read_section: Callable[[str], dict], ping: Callable[[dict], dict],
    traceroute: Callable[[dict], dict], speedtest: Callable[[dict], dict],
    optimize: Callable[[], dict],
    dns_lookup: Callable[[str], dict] | None = None,
) -> dict:
    """Dependency-injected stages facilitate no-router contract tests."""
    mode = config.get("mode") or "general"
    if mode not in MODES:
        raise ValueError("Tipo de diagnóstico não reconhecido.")
    report = {
        "mode": mode, "model": "F6201B", "firmware": firmware,
        "source": "backend_authenticated_ont", "sections": {},
        "firmware_readings": {}, "errors": {}, "performed": [],
        "findings": [], "remediations": [], "status": "info",
    }
    for feature in MODES[mode]:
        section = READ_SECTIONS[feature]
        try:
            entry = read_section(section).get("sections", {}).get(section)
            if not entry or entry.get("available") is not True:
                report["errors"][feature] = "A ONT não confirmou esta leitura."
            else:
                report["firmware_readings"][section] = entry
                report["performed"].append({
                    "operation": "leitura", "target": feature,
                    "verified": True,
                })
        except Exception as exc:
            report["errors"][feature] = _problem(exc)

    # One full diagnostic click executes ping. Dashboard/quick GET does not
    # secretly send active router POSTs.
    if config.get("run_ping", True):
        try:
            value = ping({"host": config.get("ping_host") or "1.1.1.1"})
            report["sections"]["ping"] = value
            report["performed"].append({
                "operation": "ping", "target": "ONT",
                "verified": value.get("verified", False),
            })
        except Exception as exc:
            report["errors"]["ping"] = _problem(exc)

    # The captured F6201B firmware does not prove a native nslookup POST.
    # An optional OS-level lookup is reported explicitly as PC, never
    # misrepresented as the ONT's own DNS resolver.
    if config.get("run_ping", True) and dns_lookup is not None:
        try:
            value = dns_lookup(config.get("dns_host") or "cloudflare.com")
            report["sections"]["dns_lookup"] = value
            report["performed"].append({
                "operation": "dns_lookup_pc", "target": "PC do atendente",
                "verified": bool(value.get("verified")),
            })
        except Exception as exc:
            report["errors"]["dns_lookup_pc"] = _problem(exc)

    if config.get("include_traceroute"):
        try:
            value = traceroute({
                "host": config.get("ping_host") or "1.1.1.1",
                "max_hops": config.get("max_hops", 30),
                "timeout": config.get("trace_timeout", 5000),
                "protocol": config.get("protocol", "ICMP"),
            })
            report["sections"]["traceroute"] = value
            report["performed"].append({
                "operation": "traceroute", "target": "ONT",
                "verified": value.get("verified", False),
            })
        except Exception as exc:
            report["errors"]["traceroute"] = _problem(exc)

    if config.get("include_speedtest"):
        try:
            value = speedtest(config)
            report["sections"]["speedtest"] = value
            report["performed"].append({
                "operation": "speedtest",
                "target": str(value.get("source") or "workstation"),
                "verified": value.get("download_mbps") is not None,
            })
        except Exception as exc:
            report["errors"]["speedtest"] = _problem(exc)

    # This setting explicitly changes radio configuration and may disconnect
    # clients. It is executed ONLY if the checkbox was checked.
    if config.get("auto_optimize_wifi"):
        try:
            value = optimize()
            report["remediations"].append(value)
            report["performed"].append({
                "operation": "wifi_auto_optimization",
                "target": "2.4GHz/5GHz",
                "verified": value.get("verified") is True,
                "noop": value.get("noop", False),
            })
            if value.get("success") is not True:
                report["errors"]["auto_optimize_wifi"] = (
                    "A ONT não confirmou todas as alterações de canal."
                )
        except Exception as exc:
            report["errors"]["auto_optimize_wifi"] = _problem(exc)

    report["summary"] = (
        str(len(report["firmware_readings"])) + " leituras confirmadas, " +
        str(len(report["performed"])) + " operações registradas"
    )
    report["status"] = "warning" if report["errors"] else "ok"
    return report

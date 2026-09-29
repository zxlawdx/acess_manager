"""Operation-specific proof for currently implemented ZTE DHCP and SSID writers.

Other writers remain ACCEPTED/UNCERTAIN until their exact firmware readback
schema is mapped and tested. Do not infer proof from before != after.
"""
from __future__ import annotations

from collections.abc import Mapping
from typing import Any


_DHCP_FIELDS = {
    "enabled": "ServerEnable", "min_address": "MinAddress",
    "max_address": "MaxAddress", "dns_source": "DnsServerSource",
    "dns1": "DNSServer1", "dns2": "DNSServer2", "lease_time": "LeaseTime",
}
_WIFI_FIELDS = {
    "enabled": "ativo", "ssid": "ssid", "broadcast": "broadcast",
    "isolation": "isolamento", "max_clients": "max_clientes",
    "encryption": "seguranca",
}


def _action_verified(response: Any) -> bool:
    # Current zte_wifi.set_ssid_config and zte_network_management.set_dhcp_basic
    # each perform their own field-specific firmware readback.
    return isinstance(response, Mapping) and response.get("success") is True and response.get("verified") is True


def verify_dhcp(config: Mapping[str, Any], before: Any, response: Any, after: Any) -> bool:
    if not _action_verified(response) or not isinstance(after, Mapping):
        return False
    basic = after.get("basic")
    dns = after.get("lan_dns")
    if not isinstance(basic, Mapping):
        return False
    checked = 0
    for requested, firmware_key in _DHCP_FIELDS.items():
        if requested not in config:
            continue
        expected = ("1" if bool(config[requested]) else "0") if requested == "enabled" else str(config[requested])
        if str(basic.get(firmware_key)) != expected:
            return False
        checked += 1
    if "ipv4_dns_origin" in config:
        if not isinstance(dns, Mapping) or str(dns.get("Ipv4DnsOrigin")) != str(config["ipv4_dns_origin"]):
            return False
        checked += 1
    return checked > 0


def verify_ssid(
    ssid_id: str, config: Mapping[str, Any],
    before: Any, response: Any, after: Any,
) -> bool:
    if not _action_verified(response) or not isinstance(after, list):
        return False
    # Secret PSK is verified inside zte_wifi._verify_ssid by a protected
    # readback; this outer reader deliberately uses reveal_password=False.
    selected = next(
        (item for item in after if isinstance(item, Mapping) and str(item.get("id")) == str(ssid_id)),
        None,
    )
    if not isinstance(selected, Mapping):
        return False
    checked = 0
    for field, canonical in _WIFI_FIELDS.items():
        if field not in config:
            continue
        expected = int(config[field]) if field == "max_clients" else config[field]
        if selected.get(canonical) != expected:
            return False
        checked += 1
    if "password" in config:
        # Internal writer already confirmed PSK against unmasked firmware read;
        # never compare masked placeholders or expose the password in history.
        checked += 1
    return checked > 0


def verify_channel_choice(
    band: str, config: Mapping[str, Any],
    before: Any, response: Any, after: Any,
) -> bool:
    """Confirm the exact channel/Auto setting in a *fresh* ZTE readback.

    Do not assert unrelated radio parameters or infer success from HTTP 200.
    This verifier is for channel-only remediation, not the entire Wi-Fi form.
    """
    if (not isinstance(response, Mapping)
            or response.get("success") is not True
            or not isinstance(after, list)):
        return False
    expected = next((
        radio for radio in after
        if isinstance(radio, Mapping)
        and str(radio.get("banda", radio.get("band", ""))).lower() == band.lower()
    ), None)
    if not isinstance(expected, Mapping):
        return False
    actual_auto = expected.get("canal_automatico", expected.get("auto_channel"))
    if isinstance(actual_auto, str):
        actual_auto = actual_auto.strip().lower() in {"true", "1", "on"}
    if "auto_channel" in config:
        if actual_auto is None or bool(actual_auto) != bool(config["auto_channel"]):
            return False
    if config.get("auto_channel") is True:
        # The actual RF channel can still change while Auto is enabled.
        return actual_auto is True
    if config.get("channel") not in (None, "", "Auto"):
        try:
            return int(expected.get("canal", expected.get("channel"))) == int(config["channel"])
        except (TypeError, ValueError):
            return False
    return False

from __future__ import annotations

from typing import Any

from apps.zte_manager.infrastructure.huawei.diagnostic_result import (
    decode_huawei_diagnostic_result,
)
from apps.zte_manager.services.huawei_eg8041_family_runtime import (
    HuaweiEG8041FamilyRuntimeService,
)


class HuaweiEG8041FamilyProvider(HuaweiEG8041FamilyRuntimeService):
    """Generic feature-API adapter for runtime-promoted EG8041 capabilities."""

    FAMILY_RUNTIME_FEATURES = frozenset({
        "device_info",
        "wan",
        "optical",
        "wifi_basic",
        "wifi_radio",
        "wifi_advanced",
        "wifi_channel_discovery",
        "ethernet_info",
        "clients",
        "dhcp",
        "dns",
        "dmz",
        "tr069_url",
        "lan_ipv4",
        "firewall_level",
        "diagnostics.ping",
        "diagnostics.traceroute",
        "speed_test",
    })

    _LABELS = {
        "device_info": "Device information",
        "wan": "WAN services",
        "optical": "Optical status",
        "wifi_basic": "Wi-Fi basic",
        "wifi_radio": "Wi-Fi radio",
        "wifi_advanced": "Wi-Fi advanced",
        "wifi_channel_discovery": "Wi-Fi channel discovery",
        "ethernet_info": "Ethernet ports",
        "clients": "Connected clients",
        "dhcp": "DHCP",
        "dns": "DNS",
        "dmz": "DMZ",
        "tr069_url": "TR-069",
        "lan_ipv4": "LAN IPv4",
        "firewall_level": "Firewall",
        "diagnostics.ping": "Native ONT ping",
        "diagnostics.traceroute": "Native ONT traceroute",
        "speed_test": "Speed-test WebUI surface",
    }

    @staticmethod
    def _decode_diagnostic_result(source: object) -> tuple[str, str]:
        """Decode the physically observed EG8041 polling response grammar.

        The X6 firmware emits GetPing/GetRoute frames as concatenated quoted
        JavaScript strings. The base Huawei transport historically understood
        only one quoted literal, so a real ``Complete`` frame was kept polling
        until timeout. Keep the characterization at the EG8041 family boundary
        while the generic Huawei parser remains conservative for other families.
        """

        return decode_huawei_diagnostic_result(source)

    def _family_feature_reader(self, feature: str):
        readers = {
            "device_info": lambda refresh=False: self.device_status(refresh=refresh),
            "wan": lambda refresh=False: self.wan_status(refresh=refresh),
            "optical": lambda refresh=False: self.optical_status(refresh=refresh),
            "wifi_basic": lambda refresh=False: self.wifi_networks(refresh=refresh),
            "wifi_radio": lambda refresh=False: self.wifi_radios(refresh=refresh),
            "wifi_advanced": lambda refresh=False: self.wifi_configuration_descriptor(),
            "wifi_channel_discovery": lambda refresh=False: {
                "2.4ghz": self.wifi_channels("2.4GHz", country="BR"),
                "5ghz": self.wifi_channels("5GHz", country="BR"),
            },
            "ethernet_info": lambda refresh=False: self.lan_ports(refresh=refresh),
            "clients": lambda refresh=False: self.clients(refresh=refresh),
            "dhcp": lambda refresh=False: self.dhcp_status(refresh=refresh),
            "dns": lambda refresh=False: self.dns_status(refresh=refresh),
            "dmz": lambda refresh=False: self.dmz_status(refresh=refresh),
            "tr069_url": lambda refresh=False: self.tr069_management_status(refresh=refresh),
            "lan_ipv4": lambda refresh=False: self.lan_ipv4_status(refresh=refresh),
            "firewall_level": lambda refresh=False: self.firewall_level_status(refresh=refresh),
            "speed_test": lambda refresh=False: self.mapped_read_feature("speed_test"),
        }
        return readers.get(feature)

    def _feature_reader(self, feature: str):
        reader = self._family_feature_reader(feature)
        if reader is not None:
            return reader
        return super()._feature_reader(feature)

    def _diagnostic_contract(self, feature: str) -> dict[str, Any]:
        return {
            "feature": feature,
            "provider": "huawei",
            "transport": "webui",
            "start_route": (
                "/diagnostics/ping"
                if feature == "diagnostics.ping"
                else "/diagnostics/traceroute"
            ),
            "native": True,
            "family": self.family_descriptor,
        }

    def probe_capabilities(self, features=None) -> dict:
        requested = list(features or self._capabilities.keys() or ["ipv4_filter"])
        family = [item for item in requested if item in self.FAMILY_RUNTIME_FEATURES]
        regular = [item for item in requested if item not in self.FAMILY_RUNTIME_FEATURES]
        result = super().probe_capabilities(regular) if regular else {
            "adapter": "huawei-webui",
            "vendor": self.vendor,
            "profile": self.profile_key,
            "features": [],
        }

        for feature in family:
            operations = dict(self._capabilities.get(feature) or {})
            error = None
            if feature.startswith("diagnostics."):
                available = bool(operations.get("read") or operations.get("write"))
            else:
                reader = self._family_feature_reader(feature)
                try:
                    if reader is None:
                        raise ValueError("family reader unavailable")
                    reader(refresh=True)
                    available = True
                    operations.update({
                        "read": True,
                        "supported": True,
                        "state": (
                            "WRITE_SUPPORTED"
                            if operations.get("write") or operations.get("update")
                            else "READ_SUPPORTED"
                        ),
                    })
                    self._capabilities[feature] = operations
                except Exception as exc:
                    available = False
                    error = type(exc).__name__
                    operations.update({
                        "read": False,
                        "supported": False,
                        "state": "UNKNOWN",
                    })
                    self._capabilities[feature] = operations
            result["features"].append({
                "feature": feature,
                "label": self._LABELS.get(feature, feature),
                "available": available,
                "status": "confirmed" if available else "inconclusive",
                "probeable": not feature.startswith("diagnostics."),
                "writable": bool(operations.get("write") or operations.get("update")),
                "dangerous": bool(operations.get("write") or operations.get("update")),
                "verified": bool(operations.get("verified")),
                "physical_validation": bool(operations.get("physical_validation")),
                "operations": operations,
                "error": error,
            })
        result["family"] = self.family_descriptor
        return result

    def read_capability(
        self,
        feature: str,
        *,
        refresh: bool = False,
    ) -> dict:
        if feature not in self.FAMILY_RUNTIME_FEATURES:
            return super().read_capability(feature, refresh=refresh)
        operations = dict(self._capabilities.get(feature) or {})
        if not (operations.get("read") or operations.get("write")):
            raise ValueError(f"Capability Huawei {feature} ainda não confirmada.")

        if feature.startswith("diagnostics."):
            data: object = self._diagnostic_contract(feature)
        else:
            reader = self._family_feature_reader(feature)
            if reader is None:
                raise ValueError(f"Reader Huawei ausente para {feature}.")
            data = reader(refresh=refresh)
        return {
            "feature": feature,
            "label": self._LABELS.get(feature, feature),
            "available": True,
            "writable": bool(operations.get("write") or operations.get("update")),
            "objects": {"items": data},
            "capability": operations,
            "family": self.family_descriptor,
            "protocol": self.protocol,
        }

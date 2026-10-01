from __future__ import annotations

import re
from dataclasses import dataclass, field

from .base import DeviceAdapter, FeatureSpec


@dataclass(frozen=True)
class HuaweiIPv4FilterCapability:
    read: bool = False
    create: bool = False
    update: bool = False
    delete: bool = False
    verified: bool = False

    def as_dict(self) -> dict[str, bool]:
        return {
            "read": self.read,
            "create": self.create,
            "update": self.update,
            "delete": self.delete,
            "verified": self.verified,
        }


@dataclass(frozen=True)
class HuaweiProfile:
    key: str
    model: str
    aliases: tuple[str, ...]
    ipv4_filter: HuaweiIPv4FilterCapability
    captured_features: dict[str, dict[str, object]] = field(
        default_factory=dict
    )

    @property
    def vendor(self) -> str:
        return "huawei"

    @property
    def verified(self) -> bool:
        return self.ipv4_filter.verified


class HuaweiEG8041X7Profile(HuaweiProfile):
    def __init__(self) -> None:
        super().__init__(
            key="huawei_eg8041x7_10",
            model="EG8041X7-10",
            aliases=(
                "EG8041X7-10",
                "Huawei EG8041X7-10",
                "EG8041X7 10",
                "EG8041X7_10",
                "EG8041X710",
            ),
            ipv4_filter=HuaweiIPv4FilterCapability(
                read=True,
                create=True,
                update=True,
                delete=True,
                verified=True,
            ),
            captured_features={
                "wan": {"read": True, "write": False, "verified": True},
                "optical": {"read": True, "write": False, "verified": True},
                "layer3": {"read": True, "update": True, "verified": True},
                "lan_ipv4": {"read": True, "update": True, "verified": True},
                "ipv6_lan": {"read": True, "update": True, "verified": True},
                "dhcp": {"read": True, "update": True, "verified": True},
                "dhcp_static": {"read": True, "update": True, "verified": True},
                "dns": {"read": True, "update": True, "verified": True},
                "dns_host": {"read": True, "update": True, "verified": True},
                "dmz": {"read": True, "update": True, "verified": True},
                "wifi_basic": {"read": True, "update": True, "verified": True},
                "wifi_radio": {"read": True, "update": True, "verified": True},
                "tr069_url": {"read": True, "update": True, "verified": True},
                "firewall_level": {"read": True, "update": True, "verified": True},
                "alg": {"read": True, "update": True, "verified": True},
                "igmp": {"read": True, "update": True, "verified": True},
                "dos": {"read": True, "update": True, "verified": True},
                "ipv6_firewall": {
                    "read": True, "update": True, "verified": True,
                },
                "internet_control": {
                    "read": True, "update": True, "verified": True,
                },
            },
        )


class HuaweiUnknownProfile(HuaweiProfile):
    def __init__(self, model: str | None = None) -> None:
        display = canonical_huawei_model(model) or "Huawei"
        super().__init__(
            key="huawei_unknown",
            model=display,
            aliases=(),
            ipv4_filter=HuaweiIPv4FilterCapability(),
        )


KNOWN_HUAWEI_PROFILES: tuple[HuaweiProfile, ...] = (
    HuaweiEG8041X7Profile(),
)


# Features present in the captured WebUI/menu but not yet end-to-end
# integrated. Their presence is evidence of observation, not permission to
# invent a parser or mutation.
HUAWEI_EG8041X7_OBSERVED_ONLY: dict[str, dict[str, object]] = {
    "wifi_schedule": {
        "label": "Wi-Fi Schedule",
        "state": "OBSERVED_ONLY",
        "write_state": "NOT_YET_VALIDATED",
        "endpoints": ["/html/amp/wifische/WlanSchedule.asp"],
    },
    "wifi_cover": {
        "label": "Wi-Fi Cover / Home Network",
        "state": "OBSERVED_ONLY",
        "write_state": "NOT_YET_VALIDATED",
        "endpoints": [
            "/html/amp/wificovercfg/wifiCover.asp",
            "/html/amp/wificoverinfo/wlancoverinfo.asp",
        ],
    },
    "easymesh_topology": {
        "label": "EasyMesh topology",
        "state": "OBSERVED_ONLY",
        "write_state": "NOT_YET_VALIDATED",
        "endpoints": ["/html/amp/wlaninfo/easymeshTopo.asp"],
    },
    "port_isolation": {
        "label": "Port Isolation",
        "state": "OBSERVED_ONLY",
        "write_state": "NOT_YET_VALIDATED",
        "endpoints": ["/html/bbsp/portinfo/portisolate.asp"],
        "note": "set.cgi was observed, but functional parameters were not proven.",
    },
    "ipv6_filter": {
        "label": "IPv6 Filtering",
        "state": "OBSERVED_ONLY",
        "write_state": "NOT_YET_VALIDATED",
        "endpoints": ["/html/bbsp/ipv6ipincoming/ipv6ipincoming.asp"],
    },
    "ipv6_port_mapping": {
        "label": "IPv6 Port Mapping",
        "state": "OBSERVED_ONLY",
        "write_state": "NOT_YET_VALIDATED",
        "endpoints": ["/html/bbsp/ipv6portmapping/ipv6portmapping.asp"],
    },
    "upnp": {
        "label": "UPnP",
        "state": "OBSERVED_ONLY",
        "write_state": "NOT_YET_VALIDATED",
        "endpoints": ["/html/bbsp/upnp/upnp.asp"],
    },
    "ddns": {
        "label": "DDNS",
        "state": "OBSERVED_ONLY",
        "write_state": "NOT_YET_VALIDATED",
        "endpoints": ["/html/bbsp/ddns/ddns.asp"],
    },
    "routing": {
        "label": "Routing / Static Route / Service Route",
        "state": "OBSERVED_ONLY",
        "write_state": "NOT_YET_VALIDATED",
        "endpoints": [
            "/html/bbsp/route/route.asp",
            "/html/bbsp/routeinfo/routeinfo.asp",
            "/html/bbsp/staticroute/staticroute.asp",
            "/html/bbsp/serviceroute/serviceroute.asp",
        ],
    },
    "port_mapping": {
        "label": "Port Mapping / Trigger",
        "state": "OBSERVED_ONLY",
        "write_state": "NOT_YET_VALIDATED",
        "endpoints": [
            "/html/bbsp/portmapping/portmapping.asp",
            "/html/bbsp/porttrigger/porttrigger.asp",
        ],
    },
    "mac_filter": {
        "label": "MAC filtering",
        "state": "OBSERVED_ONLY",
        "write_state": "NOT_YET_VALIDATED",
        "endpoints": [
            "/html/bbsp/macfilter/macfilter.asp",
            "/html/bbsp/wlanmacfilter/wlanmacfilter.asp",
        ],
    },
    "parental_control": {
        "label": "Parental control",
        "state": "OBSERVED_ONLY",
        "write_state": "NOT_YET_VALIDATED",
        "endpoints": [
            "/html/bbsp/parentalctrl/parentalctrlmac.asp",
            "/html/bbsp/parentalctrl/parentalctrlstatus.asp",
        ],
    },
    "port_acl": {
        "label": "Port ACL",
        "state": "OBSERVED_ONLY",
        "write_state": "NOT_YET_VALIDATED",
        "endpoints": ["/html/bbsp/portacl/newacl.asp"],
    },
    "sntp": {
        "label": "SNTP",
        "state": "OBSERVED_ONLY",
        "write_state": "NOT_YET_VALIDATED",
        "endpoints": ["/html/ssmp/sntp/sntp.asp"],
    },
    "reboot": {
        "label": "Reboot",
        "state": "OBSERVED_ONLY",
        "write_state": "NOT_YET_VALIDATED",
        "endpoints": ["/html/ssmp/reboot/reboot.asp"],
    },
    "firmware": {
        "label": "Firmware upgrade",
        "state": "OBSERVED_ONLY",
        "write_state": "NOT_YET_VALIDATED",
        "endpoints": ["/html/ssmp/fireware/firmware.asp"],
    },
    "config_backup": {
        "label": "Configuration file",
        "state": "OBSERVED_ONLY",
        "write_state": "NOT_YET_VALIDATED",
        "endpoints": ["/html/ssmp/cfgfile/cfgfile.asp"],
    },
    "security_check": {
        "label": "Security Check",
        "state": "OBSERVED_ONLY",
        "write_state": "NOT_YET_VALIDATED",
        "endpoints": ["/html/ssmp/securitycheck/securitycheck.asp"],
    },
    "led": {
        "label": "LED configuration",
        "state": "OBSERVED_ONLY",
        "write_state": "NOT_YET_VALIDATED",
        "endpoints": ["/html/ssmp/ledcfg/ledcfg.asp"],
    },
    "collect": {
        "label": "Support collection",
        "state": "OBSERVED_ONLY",
        "write_state": "NOT_YET_VALIDATED",
        "endpoints": ["/html/ssmp/collect/collectInfo.asp"],
    },
    "qos_smart": {
        "label": "QoS Smart / statistics",
        "state": "OBSERVED_ONLY",
        "write_state": "NOT_YET_VALIDATED",
        "endpoints": ["/html/bbsp/qossmart/qossmart.asp"],
    },
    "dscp_to_pbit": {
        "label": "DSCP to P-bit",
        "state": "OBSERVED_ONLY",
        "write_state": "WRITE_CAPTURED",
        "endpoints": ["/html/bbsp/dscptopbit/dscptopbit.asp"],
        "note": "Mutation observed, but not in the physically reproduced 21-write suite.",
    },
    "speed_test": {
        "label": "Section speed test",
        "state": "OBSERVED_ONLY",
        "write_state": "NOT_YET_VALIDATED",
        "endpoints": ["/html/ssmp/Sectionspeed/Sectionspeed.asp"],
    },
    "diagnostics_webui": {
        "label": "WebUI diagnostics",
        "state": "OBSERVED_ONLY",
        "write_state": "NOT_YET_VALIDATED",
        "endpoints": [
            "/html/bbsp/maintenance/diagnosecommon.asp",
            "/html/ssmp/maintain/smartdiagnose.asp",
        ],
    },
}


HUAWEI_EG8041X7_FULLY_INTEGRATED = frozenset({
    "ipv4_filter",
    "wan",
    "optical",
    "dhcp",
    "dns",
    "dmz",
    "wifi_basic",
    "wifi_radio",
    "tr069_url",
    "firewall_level",
    "alg",
    "igmp",
    "dos",
    "ipv6_firewall",
    "internet_control",
})


def _compact_huawei_model(model: str | None) -> str:
    value = str(model or "").strip().upper()
    value = re.sub(r"\bHUAWEI\b", " ", value)
    return re.sub(r"[^A-Z0-9]+", "", value)


def canonical_huawei_model(model: str | None) -> str:
    compact = _compact_huawei_model(model)
    if not compact:
        return ""

    for profile in KNOWN_HUAWEI_PROFILES:
        if compact in {
            _compact_huawei_model(profile.model),
            *(_compact_huawei_model(alias) for alias in profile.aliases),
        }:
            return profile.model

    value = str(model or "").strip()
    value = re.sub(r"(?i)^\s*huawei\s+", "", value)
    value = re.sub(r"[\s_]+", "-", value)
    return value.upper().strip("-")


def resolve_huawei_profile(
    model: str | None,
    *,
    unknown: bool = True,
) -> HuaweiProfile | None:
    compact = _compact_huawei_model(model)
    if compact:
        for profile in KNOWN_HUAWEI_PROFILES:
            aliases = {
                _compact_huawei_model(profile.model),
                *(_compact_huawei_model(alias) for alias in profile.aliases),
            }
            if compact in aliases:
                return profile

    return HuaweiUnknownProfile(model) if unknown else None


def huawei_profile_key(model: str | None) -> str:
    profile = resolve_huawei_profile(model)
    return profile.key if profile is not None else "huawei_unknown"


def huawei_ipv4_filter_capability(
    model: str | None,
) -> HuaweiIPv4FilterCapability:
    profile = resolve_huawei_profile(model)
    if profile is None:
        return HuaweiIPv4FilterCapability()
    return profile.ipv4_filter


def is_known_huawei_model(model: str | None) -> bool:
    profile = resolve_huawei_profile(model, unknown=False)
    return profile is not None


class HuaweiWebAdapter(DeviceAdapter):
    family = "Huawei WebUI"
    name = "huawei-webui"

    def __init__(
        self,
        model: str | None = None,
        firmware: str | None = None,
        *,
        profile: HuaweiProfile | None = None,
    ) -> None:
        self.profile = profile or resolve_huawei_profile(model)
        super().__init__(
            model=(self.profile.model if self.profile else model),
            firmware=firmware,
        )

    @property
    def features(self) -> dict[str, FeatureSpec]:
        capability = (
            self.profile.ipv4_filter
            if self.profile is not None
            else HuaweiIPv4FilterCapability()
        )
        features = {
            "ipv4_filter": FeatureSpec(
                key="ipv4_filter",
                label="IPv4 Filtering",
                writable=(
                    capability.create
                    or capability.update
                    or capability.delete
                ),
                dangerous=False,
                notes=(
                    "CRUD validado fisicamente para EG8041X7-10. "
                    "Outros modelos Huawei permanecem sem escrita "
                    "até existir validação física própria."
                ),
            )
        }
        labels = {
            "wan": "WAN / PPPoE",
            "optical": "Sinal óptico",
            "layer3": "LAN Layer 3",
            "lan_ipv4": "LAN IPv4",
            "ipv6_lan": "LAN IPv6 / RA / DHCPv6",
            "dhcp": "DHCP",
            "dhcp_static": "DHCP Static",
            "dns": "DNS",
            "dns_host": "DNS Hosts",
            "dmz": "DMZ",
            "wifi_basic": "Wi-Fi / SSID",
            "wifi_radio": "Wi-Fi / Rádio",
            "tr069_url": "TR-069 URL",
            "firewall_level": "Firewall",
            "alg": "ALG",
            "igmp": "IGMP",
            "dos": "DoS Protection",
            "ipv6_firewall": "IPv6 Firewall",
            "internet_control": "Internet Control",
        }
        for key, operations in (
            (self.profile.captured_features.items())
            if self.profile is not None
            else ()
        ):
            features[key] = FeatureSpec(
                key=key,
                label=labels.get(key, key.replace("_", " ").title()),
                writable=bool(
                    operations.get("create")
                    or operations.get("update")
                    or operations.get("delete")
                    or operations.get("write")
                ),
                dangerous=key in {
                    "layer3", "lan_ipv4", "ipv6_lan",
                    "dhcp", "dhcp_static", "dns_host",
                    "wifi_basic", "wifi_radio",
                    "tr069_url", "firewall_level",
                    "ipv6_firewall", "internet_control",
                },
                notes=(
                    "Endpoint/payload exercitado na EG8041X7-10 de laboratório; "
                    "mutations do Access Manager exigem releitura antes de confirmar."
                ),
            )
        return features

    def describe(self) -> dict:
        data = super().describe()
        capability = (
            self.profile.ipv4_filter
            if self.profile is not None
            else HuaweiIPv4FilterCapability()
        )
        feature = data["features"]["ipv4_filter"]
        feature["operations"] = capability.as_dict()
        feature["verified"] = capability.verified
        data["profile"] = (
            self.profile.key if self.profile is not None else "huawei_unknown"
        )
        data["observed_only"] = (
            {
                key: {
                    inner_key: (
                        list(inner_value)
                        if isinstance(inner_value, tuple)
                        else inner_value
                    )
                    for inner_key, inner_value in spec.items()
                }
                for key, spec in HUAWEI_EG8041X7_OBSERVED_ONLY.items()
            }
            if self.profile is not None
            and self.profile.key == "huawei_eg8041x7_10"
            else {}
        )
        return data

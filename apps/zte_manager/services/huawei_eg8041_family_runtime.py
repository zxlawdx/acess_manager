from __future__ import annotations

import ipaddress
import re
from copy import deepcopy
from typing import Any, Callable

from apps.zte_manager.infrastructure.huawei.negotiating_client import (
    HuaweiNegotiatingWebClient,
)
from apps.zte_manager.infrastructure.huawei.protocol import HuaweiProtocolFamily
from apps.zte_manager.infrastructure.huawei.wifi import (
    eg8041_family_wifi_capabilities,
    eg8041_family_wifi_defaults,
)
from apps.zte_manager.model.device_adapters.huawei_registry import (
    canonical_registered_huawei_model,
    resolve_huawei_model_knowledge,
)
from apps.zte_manager.model.diagnostics import (
    NativePingResult,
    NativeTracerouteResult,
    TracerouteHop,
)
from apps.zte_manager.model.telemetry import DeviceResourceTelemetry
from apps.zte_manager.model.wifi import WifiConfigurationDescriptor
from apps.zte_manager.services.huawei_captured_features import (
    WLAN_ADV_API_PAGE,
    WLAN_ADV_COMMON_PAGE,
    WLAN_LIST_PAGE,
    _record_domain,
)
from apps.zte_manager.services.huawei_eg8041x7_runtime import (
    HuaweiEG8041X7CapturedFeatureService,
)
from apps.zte_manager.services.huawei_telemetry_runtime import (
    HuaweiTelemetryRuntimeService,
)


class HuaweiEG8041FamilyCapturedFeatureService(
    HuaweiEG8041X7CapturedFeatureService
):
    """Shared AMP/BBSP feature semantics proven across EG8041 X6/X7.

    The previous class name remains available for compatibility. Runtime family
    characterization decides whether this implementation can be attached to a
    session; this class never decides support from a marketing model name.
    """


class HuaweiEG8041FamilyRuntimeService(HuaweiTelemetryRuntimeService):
    """Runtime for Huawei AMP/BBSP/BREBG2-compatible ONTs.

    EG8041X7 keeps its existing operational profile and physical write
    validation. EG8041X6 and future candidates start with no inherited write
    permissions. They receive capabilities only after safe runtime evidence and
    parser success.
    """

    _EG8041_MODELS = frozenset({"EG8041X6-10", "EG8041X7-10"})
    _DEVICE_PAGE = "/html/ssmp/deviceinfo/deviceinfo.asp"
    _PING_DNS_PATH = "/html/bbsp/maintenance/GetPingDnsResult.asp"

    def __init__(self, **kwargs) -> None:
        kwargs.setdefault("client_factory", HuaweiNegotiatingWebClient)
        super().__init__(**kwargs)
        self._family_compatible = False
        self._family_descriptor: dict[str, object] = {
            "protocol_family": "unknown",
            "firmware_family": "unknown",
            "cfg_mode": None,
            "compatible": False,
            "evidence": [],
        }
        self._discovered_channels: dict[str, tuple[str, ...]] = {}

    @property
    def family_descriptor(self) -> dict[str, object]:
        return deepcopy(self._family_descriptor)

    @property
    def capabilities(self) -> dict[str, dict]:
        data = super().capabilities
        if not self._family_compatible:
            # HuaweiWifiDomainRuntimeService historically published the X7
            # static Wi-Fi descriptor to every Huawei model. The family runtime
            # removes that optimistic advertisement unless family evidence was
            # actually proven.
            data.pop("wifi", None)
            return data

        allow_family_write = self.model in self._EG8041_MODELS
        data["wifi"] = eg8041_family_wifi_capabilities(
            channels_2g=self._discovered_channels.get("2.4ghz"),
            channels_5g=self._discovered_channels.get("5ghz"),
            write=allow_family_write,
        ).as_dict()
        data["family"] = self.family_descriptor
        return data

    @staticmethod
    def _safe_cfg_mode(source: str) -> str | None:
        text = str(source or "")
        patterns = (
            r"\bCfgMode\s*(?:=|:)\s*['\"]?([A-Za-z0-9_-]+)",
            r"\bX_HW_CfgMode\s*(?:=|:)\s*['\"]?([A-Za-z0-9_-]+)",
        )
        for pattern in patterns:
            match = re.search(pattern, text, re.I)
            if match:
                return match.group(1).upper()
        return None

    def _wifi_family_signature(self) -> tuple[bool, list[str]]:
        captured = self._require_captured()
        pages: list[str] = []
        for band in ("2.4GHz", "5GHz"):
            _display, _instance, _basic, advanced = captured._wifi_pages(band)
            pages.append(advanced)
        chunks: list[str] = []
        records: list[dict[str, Any]] = []
        for page in (*pages, WLAN_LIST_PAGE, WLAN_ADV_COMMON_PAGE, WLAN_ADV_API_PAGE):
            try:
                html, parsed = captured._records(page)
            except Exception:
                continue
            chunks.append(html)
            records.extend(parsed)
        combined = "\n".join(chunks)
        domains = {_record_domain(item) for item in records}
        signatures = (
            "InternetGatewayDevice.LANDevice.1.WLANConfiguration.1",
            "InternetGatewayDevice.LANDevice.1.WLANConfiguration.5",
            "InternetGatewayDevice.LANDevice.1.WiFi.Radio.1",
            "InternetGatewayDevice.LANDevice.1.WiFi.Radio.2",
        )
        evidence = []
        for signature in signatures:
            if signature in combined or any(
                domain == signature or domain.startswith(signature + ".")
                for domain in domains
            ):
                evidence.append(f"object:{signature}")
        return len(evidence) == len(signatures), evidence

    def _characterize_family(self) -> None:
        protocol = self.protocol
        protocol_family = str(protocol.get("family") or "unknown")
        evidence = [str(item) for item in protocol.get("evidence") or () if item]
        cfg_mode = None
        try:
            device_source = self._client.get_page(self._DEVICE_PAGE) if self._client else ""
            cfg_mode = self._safe_cfg_mode(device_source)
            if cfg_mode:
                evidence.append(f"cfg-mode:{cfg_mode}")
        except Exception:
            device_source = ""

        signature_ok = False
        signature_evidence: list[str] = []
        if protocol_family == HuaweiProtocolFamily.AMP_BBSP.value:
            try:
                signature_ok, signature_evidence = self._wifi_family_signature()
            except Exception:
                signature_ok = False
        evidence.extend(signature_evidence)

        canonical = canonical_registered_huawei_model(self.model) or str(self.model or "")
        is_eg8041 = canonical in self._EG8041_MODELS
        cfg_compatible = cfg_mode == "BREBG2"
        # For EG8041 the local evidence establishes the BREBG2 family, but the
        # live session must still prove AMP/BBSP + exact Wi-Fi object shape.
        compatible = bool(
            protocol_family == HuaweiProtocolFamily.AMP_BBSP.value
            and signature_ok
            and (is_eg8041 or cfg_compatible)
        )

        self._family_compatible = compatible
        self._family_descriptor = {
            "protocol_family": protocol_family,
            "firmware_family": "BREBG2-like" if compatible else "unknown",
            "cfg_mode": cfg_mode,
            "compatible": compatible,
            "model": canonical or None,
            "evidence": list(dict.fromkeys(evidence)),
        }

        if not compatible or self._client is None:
            return

        # Replace the generic reader with the shared family specialization.
        # No capabilities are copied from the X7 operational profile.
        self._captured = HuaweiEG8041FamilyCapturedFeatureService(
            self._client,
            model=self.model,
        )

    @staticmethod
    def _ops(
        *,
        read: bool,
        update: bool = False,
        verified: bool = False,
        physical_validation: bool = False,
        evidence: str = "runtime_probe",
        state: str | None = None,
    ) -> dict[str, object]:
        if state is None:
            state = "WRITE_SUPPORTED" if update else "READ_SUPPORTED" if read else "UNKNOWN"
        return {
            "read": bool(read),
            "update": bool(update),
            "write": bool(update),
            "verified": bool(verified),
            "supported": bool(read or update),
            "physical_validation": bool(physical_validation),
            "evidence": evidence,
            "state": state,
        }

    def _probe_reader(self, feature: str, reader: Callable[[], object]) -> bool:
        try:
            reader()
        except Exception:
            self._capabilities[feature] = self._ops(read=False, state="UNKNOWN")
            return False
        physical = bool(
            self.model == "EG8041X6-10"
            and feature in {
                "device_info", "wifi_radio", "wifi_channel_discovery", "wan",
                "diagnostics.ping", "diagnostics.traceroute",
            }
        )
        self._capabilities[feature] = self._ops(
            read=True,
            physical_validation=physical,
            evidence=(
                "LOCAL_FIRMWARE_OBSERVED+runtime_probe"
                if physical
                else "runtime_probe"
            ),
        )
        return True

    def _discover_channels(self) -> None:
        for band, key in (("2.4GHz", "2.4ghz"), ("5GHz", "5ghz")):
            try:
                rows = super().wifi_channels(band=band, country="BR")
                values = []
                for row in rows or []:
                    for channel in row.get("canais") or []:
                        value = str(channel)
                        if value not in values:
                            values.append(value)
                if values:
                    self._discovered_channels[key] = tuple(("auto", *values))
                    self._capabilities["wifi_channel_discovery"] = self._ops(
                        read=True,
                        physical_validation=(self.model == "EG8041X6-10"),
                        evidence=(
                            "LOCAL_FIRMWARE_OBSERVED+runtime_probe"
                            if self.model == "EG8041X6-10"
                            else "runtime_probe"
                        ),
                    )
            except Exception:
                self._capabilities["wifi_channel_discovery"] = self._ops(
                    read=False,
                    state="UNKNOWN",
                )

    def _promote_family_capabilities(self) -> None:
        if not self._family_compatible:
            return

        probes: tuple[tuple[str, Callable[[], object]], ...] = (
            ("device_info", lambda: self.device_status(refresh=True)),
            ("wan", lambda: self.wan_status(refresh=True)),
            ("optical", lambda: self.optical_status(refresh=True)),
            ("wifi_basic", lambda: self.wifi_networks(refresh=True)),
            ("wifi_radio", lambda: self.wifi_radios(refresh=True)),
            ("ethernet_info", lambda: self.lan_ports(refresh=True)),
            ("clients", lambda: self.clients(refresh=True)),
            ("dhcp", lambda: self.dhcp_status(refresh=True)),
            ("dns", lambda: self.dns_status(refresh=True)),
            ("dmz", lambda: self.dmz_status(refresh=True)),
            ("tr069_url", lambda: self.tr069_management_status(refresh=True)),
            ("lan_ipv4", lambda: self.lan_ipv4_status(refresh=True)),
            ("firewall_level", lambda: self.firewall_level_status(refresh=True)),
        )
        for feature, reader in probes:
            self._probe_reader(feature, reader)

        self._discover_channels()

        # The exact EG8041 Wi-Fi object graph and mutation CGI are shared. A
        # write remains readback-gated and is not labelled physically verified
        # on X6 merely because the POST surface was captured.
        if self._capabilities.get("wifi_radio", {}).get("read"):
            self._capabilities["wifi_radio"].update({
                "update": True,
                "write": True,
                "verified": self.model == "EG8041X7-10",
                "physical_validation": self.model == "EG8041X7-10",
                "write_validation": (
                    "readback_required"
                    if self.model == "EG8041X6-10"
                    else "physically_validated"
                ),
                "state": "WRITE_SUPPORTED",
            })
            self._capabilities["wifi_advanced"] = dict(
                self._capabilities["wifi_radio"]
            )

        # Native diagnostics were physically exercised on both local EG8041
        # variants. Runtime does not auto-run them during connect; capability
        # evidence is the exact family signature plus local physical record.
        if self.model in self._EG8041_MODELS:
            physical = True
            self._capabilities["diagnostics.ping"] = self._ops(
                read=True,
                update=True,
                verified=True,
                physical_validation=physical,
                evidence="LOCAL_FIRMWARE_OBSERVED+VALIDATED_PHYSICALLY",
            )
            self._capabilities["diagnostics.traceroute"] = self._ops(
                read=True,
                update=True,
                verified=True,
                physical_validation=physical,
                evidence="LOCAL_FIRMWARE_OBSERVED+VALIDATED_PHYSICALLY",
            )

        # Section-speed pages are observable, but start/task creation is not
        # characterized. Never turn page presence into a mutation permission.
        try:
            self.mapped_read_feature("speed_test")
        except Exception:
            self._capabilities["speed_test"] = self._ops(read=False, state="UNKNOWN")
        else:
            self._capabilities["speed_test"] = {
                **self._ops(read=True, state="READ_SUPPORTED"),
                "start": "UNKNOWN",
            }

    def connect(self, *args, **kwargs):
        result = super().connect(*args, **kwargs)
        self._characterize_family()
        self._promote_family_capabilities()
        result["family"] = self.family_descriptor
        client_descriptor = getattr(self._client, "transport_descriptor", None)
        if callable(client_descriptor):
            result["transport"] = client_descriptor()
        result["capabilities"] = self.capabilities
        return result

    def disconnect(self) -> None:
        super().disconnect()
        self._family_compatible = False
        self._family_descriptor = {
            "protocol_family": "unknown",
            "firmware_family": "unknown",
            "cfg_mode": None,
            "compatible": False,
            "evidence": [],
        }
        self._discovered_channels = {}

    def wifi_configuration_descriptor(self) -> dict[str, Any]:
        if not self._family_compatible:
            return super().wifi_configuration_descriptor()
        descriptor = WifiConfigurationDescriptor(
            current=self.normalized_wifi_configuration(),
            defaults=eg8041_family_wifi_defaults(),
            capabilities=eg8041_family_wifi_capabilities(
                channels_2g=self._discovered_channels.get("2.4ghz"),
                channels_5g=self._discovered_channels.get("5ghz"),
                write=self.model in self._EG8041_MODELS,
            ),
        )
        return descriptor.as_dict()

    def wan_status(self, *, refresh: bool = False):
        rows = super().wan_status(refresh=refresh)
        enriched = []
        for row in rows or []:
            item = dict(row)
            item.setdefault("object_path", item.get("id") or "")
            item.setdefault("display_name", item.get("nome") or "")
            item.setdefault("connection_type", item.get("wan_type") or "")
            item.setdefault("service_type", item.get("services") or "")
            item.setdefault("ipv4", item.get("ip") or "")
            item.setdefault("dns", [
                value for value in (item.get("dns1"), item.get("dns2")) if value
            ])
            item.setdefault("default_route", None)
            item.setdefault("rx_bytes", None)
            item.setdefault("tx_bytes", None)
            item.setdefault("rx_packets", None)
            item.setdefault("tx_packets", None)
            item.setdefault("rx_errors", None)
            item.setdefault("tx_errors", None)
            item.setdefault("drops", None)
            enriched.append(item)
        return enriched

    @staticmethod
    def _normalize_mac(value: object) -> str:
        compact = re.sub(r"[^0-9A-Fa-f]", "", str(value or ""))
        if len(compact) != 12:
            return ""
        return ":".join(compact[index:index + 2] for index in range(0, 12, 2)).upper()

    @staticmethod
    def _merge_known(base: dict, incoming: dict) -> dict:
        result = dict(base)
        for key, value in incoming.items():
            if value not in (None, "", [], {}):
                if result.get(key) in (None, "", [], {}):
                    result[key] = value
                elif key in {"status", "online"}:
                    result[key] = value
        return result

    def clients(self, *, refresh: bool = False) -> list[dict]:
        lan = super().lan_clients(refresh=refresh)
        wifi = super().wifi_clients(refresh=refresh)
        merged: dict[str, dict] = {}
        for source, connection_type in ((lan, "lan"), (wifi, "wifi")):
            for row in source or []:
                mac = self._normalize_mac(row.get("mac"))
                if not mac:
                    continue
                normalized = {
                    "hostname": row.get("hostname") or "",
                    "ip": row.get("ip") or row.get("ipv4") or "",
                    "mac": mac,
                    "interface": row.get("interface") or "",
                    "connection_type": row.get("connection_type") or connection_type,
                    "online": row.get("status") or "",
                    "lease": row.get("lease") or "",
                    "band": row.get("band") or row.get("banda") or "",
                    "radio": row.get("radio") or row.get("ssid") or "",
                }
                merged[mac] = self._merge_known(merged.get(mac, {}), normalized)
        return list(merged.values())

    def web_resource_telemetry(self, *, refresh: bool = False) -> dict[str, Any]:
        device = self.device_status(refresh=refresh)

        def number(value):
            if value in (None, ""):
                return None
            match = re.search(r"-?\d+(?:\.\d+)?", str(value))
            return float(match.group(0)) if match else None

        memory = number(device.get("memoria_percent"))
        uptime = number(device.get("uptime"))
        cpu_data = device.get("cpu") if isinstance(device.get("cpu"), dict) else {}
        cpu = number(cpu_data.get("used_percent") or device.get("cpu_percent"))
        telemetry = DeviceResourceTelemetry(
            cpu_used_percent=cpu,
            memory_used_percent=memory,
            uptime_seconds=int(uptime) if uptime is not None else None,
            source_transport="webui",
        )
        data = telemetry.as_dict()
        if all(data.get(key) is None for key in ("cpu_used_percent", "memory_used_percent", "uptime_seconds")):
            raise ValueError("Resource telemetry not present in this WebUI response")
        return data

    @staticmethod
    def _parse_resolved_ip(source: str) -> str | None:
        text = str(source or "")
        for candidate in re.findall(r"[0-9A-Fa-f:.]+", text):
            value = candidate.strip(".:")
            try:
                ipaddress.ip_address(value)
            except ValueError:
                continue
            return value
        return None

    def ping(self, config):
        result = super().ping(config)
        resolved_ip = None
        client = self._client
        if client is not None:
            try:
                dns_result = client.post_read(
                    self._PING_DNS_PATH,
                    {},
                    referer=self._DIAGNOSTICS_PAGE,
                )
                resolved_ip = self._parse_resolved_ip(dns_result)
            except Exception:
                resolved_ip = None

        normalized = NativePingResult(
            target=str(result.get("host") or ""),
            resolved_ip=resolved_ip,
            interface=str(result.get("interface") or "") or None,
            packets_sent=(
                (result.get("sucesso") or 0) + (result.get("falha") or 0)
                if result.get("sucesso") is not None and result.get("falha") is not None
                else None
            ),
            packets_received=result.get("sucesso"),
            packet_loss_percent=result.get("perda_percentual"),
            min_ms=result.get("minimo_ms"),
            avg_ms=result.get("medio_ms"),
            max_ms=result.get("maximo_ms"),
            status=str(result.get("diagnostics_state") or "unknown"),
            error=(None if result.get("success") else str(result.get("diagnostics_state") or "failed")),
        ).as_dict()
        return {**result, **normalized, "normalized": normalized}

    @staticmethod
    def _hop_hostname(line: str, address: str) -> str | None:
        text = str(line or "").strip()
        if not text or not address:
            return None
        prefix = text.split(address, 1)[0].strip()
        prefix = re.sub(r"^\d+\s+", "", prefix).strip()
        if prefix and prefix not in {"*", address}:
            return prefix.split()[0]
        return None

    def traceroute(self, config):
        result = super().traceroute(config)
        normalized_hops = []
        compatible_hops = []
        for row in result.get("hops") or []:
            address = str(row.get("ip") or "")
            hop = TracerouteHop(
                index=int(row.get("numero") or 0),
                address=address or None,
                hostname=self._hop_hostname(str(row.get("linha") or ""), address),
                rtt_samples_ms=tuple(float(value) for value in row.get("latencias_ms") or ()),
                timeout=bool(row.get("timeout")),
                error=("timeout" if row.get("timeout") else None),
            ).as_dict()
            normalized_hops.append(hop)
            compatible_hops.append({**row, **hop})

        normalized = NativeTracerouteResult(
            target=str(result.get("host") or ""),
            interface=str(result.get("interface") or "") or None,
            status=str(result.get("diagnostics_state") or "unknown"),
            hops=tuple(
                TracerouteHop(
                    index=item["index"],
                    address=item.get("address"),
                    hostname=item.get("hostname"),
                    rtt_samples_ms=tuple(item.get("rtt_samples_ms") or ()),
                    timeout=bool(item.get("timeout")),
                    error=item.get("error"),
                )
                for item in normalized_hops
            ),
            error=(None if result.get("success") else str(result.get("diagnostics_state") or "failed")),
        ).as_dict()
        return {
            **result,
            "target": normalized["target"],
            "status": normalized["status"],
            "hops": compatible_hops,
            "normalized": normalized,
        }

    def _profile_changed_requirements(self, profile: dict) -> set[str]:
        current = self.current_configuration()
        requirements: set[str] = set()
        if (profile.get("wifi") or {}) != (current.get("wifi") or {}):
            requirements.add("wifi_radio")
        desired_dns = dict(profile.get("dns") or {})
        current_dns = dict(current.get("dns") or {})
        if desired_dns and any(current_dns.get(key) != value for key, value in desired_dns.items()):
            requirements.add("dns")
        return requirements

    def _apply_profile_payload(self, profile: dict, *, operation: str, target: str) -> dict:
        if self._family_compatible and self.model != "EG8041X7-10":
            requirements = self._profile_changed_requirements(profile)
            supported = []
            unsupported = []
            for feature in sorted(requirements):
                operations = self._capabilities.get(feature) or {}
                if operations.get("update") or operations.get("write"):
                    supported.append(feature)
                else:
                    unsupported.append(feature)
            if unsupported:
                return {
                    "success": False,
                    "verified": False,
                    "preflight": True,
                    "supported": supported,
                    "unsupported": unsupported,
                    "steps": [],
                    "detail": (
                        "O perfil exige operações que esta sessão Huawei não "
                        "comprovou como graváveis; nenhuma alteração foi enviada."
                    ),
                }
        return super()._apply_profile_payload(profile, operation=operation, target=target)

    def capability_catalog(self) -> dict:
        data = super().capability_catalog()
        data["family"] = self.family_descriptor
        features = data.setdefault("features", {})
        labels = {
            "device_info": "Device information",
            "wifi_advanced": "Wi-Fi advanced radio",
            "wifi_channel_discovery": "Wi-Fi channel discovery",
            "clients": "Normalized clients",
            "diagnostics.ping": "Native ONT ping",
            "diagnostics.traceroute": "Native ONT traceroute",
        }
        for key, operations in self._capabilities.items():
            if key in features or key in {"wifi", "family"}:
                continue
            if not isinstance(operations, dict) or "state" not in operations:
                continue
            features[key] = {
                "key": key,
                "label": labels.get(key, key.replace("_", " ").title()),
                "writable": bool(operations.get("write") or operations.get("update")),
                "dangerous": bool(operations.get("write") or operations.get("update")),
                "operations": dict(operations),
                "verified": bool(operations.get("verified")),
                "physically_validated": bool(operations.get("physical_validation")),
                "state": str(operations.get("state") or "UNKNOWN"),
                "evidence_states": [str(operations.get("evidence") or "runtime_probe")],
            }
        data.setdefault("state_definitions", {}).update({
            "READ_SUPPORTED": "Safe reader returned a recognizable parsed result.",
            "WRITE_SUPPORTED": "Writer exists but still obeys write-once + readback policy.",
            "UNKNOWN": "Runtime evidence was insufficient; support is not assumed.",
        })
        return data

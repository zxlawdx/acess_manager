from __future__ import annotations

from threading import Lock
from typing import Any

from apps.zte_manager.infrastructure.huawei.diagnostic_result import (
    decode_huawei_diagnostic_result,
)
from apps.zte_manager.services.automatic_diagnostic_service import (
    AutomaticDiagnosticService,
    DiagnosticThresholds,
)
from apps.zte_manager.services.huawei_captured_features import _record_domain
from apps.zte_manager.services.huawei_eg8041_family_runtime import (
    HuaweiEG8041FamilyRuntimeService,
)
from apps.zte_manager.services.support_diagnostic_service import (
    SupportDiagnosticOptions,
    SupportDiagnosticService,
)


class _HuaweiDiagnosticCapabilityFacade:
    """Expose only read-only firmware-health readers used by the generic engine."""

    def __init__(self, provider: "HuaweiEG8041FamilyProvider") -> None:
        self.provider = provider

    def read(self, feature: str):
        if feature == "tr069":
            return self.provider.tr069_management_status()
        if feature == "sntp":
            return {
                "available": False,
                "reason": "Huawei SNTP ainda não foi caracterizado neste runtime.",
            }
        raise ValueError(f"Capability de diagnóstico Huawei desconhecida: {feature}")


class _HuaweiDiagnosticTarget:
    """Provider view used by the generic diagnostic engine.

    The dashboard explicitly asks for ``run_ping=false``. This proxy prevents
    the generic collector from starting an active ONT ping in that mode while
    delegating all passive readers to the authenticated Huawei provider.
    """

    def __init__(
        self,
        provider: "HuaweiEG8041FamilyProvider",
        *,
        active_ping: bool,
    ) -> None:
        self.provider = provider
        self.active_ping = active_ping

    def __getattr__(self, name: str):
        return getattr(self.provider, name)

    def ping(self, config):
        if not self.active_ping:
            raise RuntimeError("active_ping_disabled")
        return self.provider.ping(config)


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

    _WIFI_SECRET_FIELDS = (
        "PreSharedKey",
        "KeyPassphrase",
        "WPAKey",
        "WPA2Key",
        "WPA3Key",
        "PSK",
        "Key",
    )

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        # Kept separate from the Huawei session RLock so the UI can poll local
        # progress while the sequential WebUI collectors are running.
        self._support_progress_lock = Lock()
        self._support_progress_state = {
            "running": False,
            "stage": "idle",
            "completed": 0,
            "total": 0,
        }

    @staticmethod
    def _decode_diagnostic_result(source: object) -> tuple[str, str]:
        """Decode the physically observed EG8041 polling response grammar."""
        return decode_huawei_diagnostic_result(source)

    # ------------------------------------------------------------------
    # Generic diagnostic compatibility aliases

    def channel_status(self):
        return self.wifi_radios()

    def available_channels(
        self,
        band: str | None = None,
        bandwidth: str | None = None,
        country: str = "BRI",
    ):
        return self.wifi_channels(
            band=band,
            bandwidth=bandwidth,
            country=country,
        )

    @staticmethod
    def wifi_neighbor_scan(band: str) -> dict[str, Any]:
        # No Huawei neighbor scan has been characterized locally yet. Returning
        # an explicit unavailable reading lets the generic analyzer stay honest
        # without failing the complete diagnostic.
        return {
            "band": band,
            "available": False,
            "networks": [],
        }

    @staticmethod
    def nslookup(_hostname: str):
        raise RuntimeError("Huawei native NsLookup ainda não foi caracterizado.")

    @staticmethod
    def native_speedtest(server_url: str | None = None):
        # SpeedTestService will use the explicitly allowed workstation fallback.
        raise RuntimeError("Huawei native speed test ainda não foi caracterizado.")

    @staticmethod
    def _diagnostic_thresholds(config: dict) -> DiagnosticThresholds:
        return DiagnosticThresholds(
            optical_rx_min=config.get("optical_rx_min", -27.0),
            optical_rx_max=config.get("optical_rx_max", -8.0),
            wifi_rssi_warning=config.get("wifi_rssi_warning", -70),
            wifi_rssi_bad=config.get("wifi_rssi_bad", -80),
            expected_lan_mbps=config.get("expected_lan_mbps", 1000),
            ping_warning_ms=config.get("ping_warning_ms", 80.0),
        )

    @staticmethod
    def _support_options(config: dict) -> SupportDiagnosticOptions:
        return SupportDiagnosticOptions(
            mode=config.get("mode", "general"),
            affected_mac=config.get("affected_mac"),
            affected_ip=config.get("affected_ip"),
            ping_host=config.get("ping_host", "1.1.1.1"),
            dns_host=config.get("dns_host", "cloudflare.com"),
            include_traceroute=bool(config.get("include_traceroute", False)),
            include_speedtest=bool(config.get("include_speedtest", True)),
            allow_speedtest_fallback=bool(
                config.get("allow_speedtest_fallback", True)
            ),
            speedtest_provider=config.get("speedtest_provider", "native_auto"),
            speedtest_base_url=config.get("speedtest_base_url"),
            expected_download_mbps=config.get("expected_download_mbps"),
            expected_upload_mbps=config.get("expected_upload_mbps"),
        )

    def automatic_diagnostic(self, config: dict) -> dict:
        target = _HuaweiDiagnosticTarget(
            self,
            active_ping=bool(config.get("run_ping", True)),
        )
        report = AutomaticDiagnosticService(target).run(
            ping_host=config.get("ping_host", "8.8.8.8"),
            include_traceroute=bool(config.get("include_traceroute", False)),
            thresholds=self._diagnostic_thresholds(config),
        )
        report.update({
            "provider": "huawei",
            "model": self.model,
            "family": self.family_descriptor,
        })
        return report

    def _set_support_progress(
        self,
        stage: str,
        completed: int,
        total: int,
        *,
        running: bool = True,
    ) -> None:
        with self._support_progress_lock:
            self._support_progress_state = {
                "running": running,
                "stage": stage,
                "completed": int(completed),
                "total": int(total),
            }

    def support_progress(self) -> dict:
        with self._support_progress_lock:
            return dict(self._support_progress_state)

    def support_diagnostic(self, config: dict) -> dict:
        with self._support_progress_lock:
            if self._support_progress_state.get("running"):
                raise RuntimeError("Já existe um diagnóstico Huawei em execução.")
            self._support_progress_state = {
                "running": True,
                "stage": "preparing",
                "completed": 0,
                "total": 1,
            }

        failed = True
        try:
            target = _HuaweiDiagnosticTarget(
                self,
                active_ping=bool(config.get("run_ping", True)),
            )
            engine = SupportDiagnosticService(
                target,
                _HuaweiDiagnosticCapabilityFacade(self),
            )
            report = engine.run(
                self._support_options(config),
                self._diagnostic_thresholds(config),
                progress=lambda stage, completed, total: self._set_support_progress(
                    stage,
                    completed,
                    total,
                ),
            )
            report.update({
                "provider": "huawei",
                "model": self.model,
                "family": self.family_descriptor,
                "automatic_mutation_performed": False,
            })
            if config.get("auto_optimize_wifi"):
                report.setdefault("notes", []).append(
                    "O diagnóstico Huawei é somente leitura: nenhuma otimização "
                    "automática foi aplicada sem uma recomendação caracterizada."
                )
            failed = False
            return report
        finally:
            state = self.support_progress()
            self._set_support_progress(
                "failed" if failed else "completed",
                state.get("total", 1),
                state.get("total", 1),
                running=False,
            )

    # ------------------------------------------------------------------
    # Explicit Wi-Fi password reveal

    @staticmethod
    def _valid_wifi_secret(value: object) -> str:
        text = str(value or "").strip()
        if not text or text.startswith("InternetGatewayDevice."):
            return ""
        if set(text) <= {"*", "•", "·"}:
            return ""
        if 8 <= len(text) <= 63:
            return text
        if len(text) == 64 and all(char in "0123456789abcdefABCDEF" for char in text):
            return text
        return ""

    def _wifi_password_for_band(self, band: str) -> str:
        captured = self._require_captured()
        _display, instance, _page, _adv = captured._wifi_pages(band)
        record, records = captured._wifi_basic_record(band)
        base_domain = (
            "InternetGatewayDevice.LANDevice.1."
            f"WLANConfiguration.{instance}"
        )
        psk_domain = f"{base_domain}.PreSharedKey.1"

        candidates = [record, *records]
        # Prefer the dedicated PreSharedKey object, then the WLAN record itself.
        candidates.sort(
            key=lambda row: 0
            if _record_domain(row) == psk_domain
            else 1
            if _record_domain(row) == base_domain
            else 2
        )
        for row in candidates:
            domain = _record_domain(row)
            relevant = (
                domain in {"", base_domain, psk_domain}
                or domain.startswith(base_domain + ".PreSharedKey.")
            )
            if not relevant:
                continue
            for key in self._WIFI_SECRET_FIELDS:
                secret = self._valid_wifi_secret(row.get(key))
                if secret:
                    return secret
            constructor = str(row.get("_constructor") or "").casefold()
            if "preshared" in constructor or "psk" in constructor:
                for value in reversed(row.get("_args") or []):
                    secret = self._valid_wifi_secret(value)
                    if secret:
                        return secret
        return ""

    def wifi_networks(
        self,
        reveal_password: bool = False,
        *,
        refresh: bool = False,
    ) -> list[dict]:
        if not reveal_password:
            return super().wifi_networks(
                reveal_password=False,
                refresh=refresh,
            )

        # Never store cleartext Wi-Fi keys in the normalized session snapshot.
        networks = self._require_captured().wifi_networks(reveal_password=False)
        revealed = 0
        result: list[dict] = []
        for network in networks:
            row = dict(network)
            password = self._wifi_password_for_band(str(row.get("banda") or ""))
            row["password"] = password
            row["password_hidden"] = not bool(password)
            if password:
                revealed += 1
            result.append(row)
        if result and not revealed:
            raise RuntimeError(
                "Este firmware/login não expôs a senha Wi-Fi atual para leitura."
            )
        return result

    # ------------------------------------------------------------------

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

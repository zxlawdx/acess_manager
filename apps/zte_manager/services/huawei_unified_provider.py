from __future__ import annotations

import re
from copy import deepcopy
from typing import Any, Callable

from apps.zte_manager.infrastructure.huawei.protocol import HuaweiAuthFlow
from apps.zte_manager.services.huawei_eg8041_family_provider import (
    HuaweiEG8041FamilyProvider,
)
from apps.zte_manager.services.huawei_eg8145v5_family_runtime import (
    HuaweiEG8145V5FamilyRuntime,
    HuaweiEG8145FamilyProfile,
    ordered_phase2_profiles,
)
from apps.zte_manager.services.huawei_hg8145x6_runtime import (
    HG8145X6_OPTICAL_CANDIDATE_PAGES,
    HuaweiHG8145X6CapturedFeatureService,
)
from apps.zte_manager.services.huawei_hg8245h_runtime import (
    HuaweiHG8245HApiRuntime,
)
from apps.zte_manager.services.huawei_telemetry_runtime import (
    HuaweiTelemetryRuntimeService,
)


class HuaweiUnifiedProvider(HuaweiEG8041FamilyProvider):
    """Production Huawei provider with evidence-driven runtime strategies.

    EG8041 keeps the existing family runtime. HG8145X6 uses the read-only
    ONTWatch-derived contract. EG8145V5/HN8010TS use one shared RandCount
    session plus model-specific read schemas. HG8245H Phase 3 adds the modern
    SesTokenInfo /api/ family while preserving legacy RandCount fallback.
    Model names are hints; authenticated endpoint/parser evidence decides which
    specialization is attached.
    """

    FAMILY_RUNTIME_FEATURES = frozenset({
        *HuaweiEG8041FamilyProvider.FAMILY_RUNTIME_FEATURES,
        "wifi_traffic",
        "resource_telemetry",
        "optical_telemetry",
    })
    _LABELS = {
        **HuaweiEG8041FamilyProvider._LABELS,
        "wifi_traffic": "Per-SSID Wi-Fi traffic counters",
        "resource_telemetry": "Device resource telemetry",
        "optical_telemetry": "Optical telemetry",
    }
    _HG8145X6_COMPACT = frozenset({"HG8145X6", "HG8145X610"})

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        self._phase2_runtime: HuaweiEG8145V5FamilyRuntime | None = None
        self._phase2_profile: HuaweiEG8145FamilyProfile | None = None
        self._phase3_runtime: HuaweiHG8245HApiRuntime | None = None

    @classmethod
    def _is_hg8145x6_model(cls, model: object) -> bool:
        value = re.sub(r"\bHUAWEI\b", " ", str(model or "").upper())
        compact = re.sub(r"[^A-Z0-9]+", "", value)
        return compact in cls._HG8145X6_COMPACT

    @property
    def _hg8145x6_active(self) -> bool:
        return isinstance(self._captured, HuaweiHG8145X6CapturedFeatureService)

    @property
    def _phase2_active(self) -> bool:
        return self._phase2_runtime is not None and self._phase2_profile is not None

    @property
    def _phase3_active(self) -> bool:
        return self._phase3_runtime is not None

    @property
    def capabilities(self) -> dict[str, dict]:
        data = super().capabilities
        if not self._hg8145x6_active and not self._phase2_active and not self._phase3_active:
            return data

        # Generic EG8041 Wi-Fi descriptors contain family-specific write/radio
        # assumptions. Specialized read-only runtimes publish only capabilities
        # proven by their authenticated endpoint/parser signatures.
        data.pop("wifi", None)
        data["family"] = self.family_descriptor
        return data

    def _force_specialized_read_only(
        self,
        evidence: str,
        *,
        preserve_existing_reads: bool = True,
    ) -> None:
        for feature, current in list(self._capabilities.items()):
            if not isinstance(current, dict):
                continue
            operations = dict(current)
            for key in ("create", "update", "delete", "write", "start"):
                if key in operations:
                    operations[key] = False
            if not preserve_existing_reads and "read" in operations:
                operations["read"] = False
            operations["verified"] = False
            operations["physical_validation"] = False
            operations["state"] = (
                "READ_SUPPORTED" if operations.get("read") else "UNKNOWN"
            )
            operations["evidence"] = evidence
            self._capabilities[feature] = operations

        for feature in (
            "wifi_basic",
            "wifi_radio",
            "wifi_advanced",
            "wifi_channel_discovery",
            "wifi_traffic",
        ):
            self._capabilities[feature] = self._ops(
                read=False,
                update=False,
                verified=False,
                physical_validation=False,
                evidence=evidence,
                state="UNKNOWN",
            )

    def _force_hg8145x6_read_only(self) -> None:
        self._force_specialized_read_only("hg8145x6_no_write_evidence")

    def _promote_specialized_reader(
        self,
        feature: str,
        reader: Callable[[], object],
        *,
        endpoint_evidence: str,
        physically_validated: bool = False,
    ) -> None:
        try:
            reader()
        except Exception:
            self._capabilities[feature] = self._ops(
                read=False,
                update=False,
                verified=False,
                physical_validation=False,
                evidence=f"runtime_probe_failed:{endpoint_evidence}",
                state="UNKNOWN",
            )
            return
        self._capabilities[feature] = self._ops(
            read=True,
            update=False,
            verified=True,
            physical_validation=physically_validated,
            evidence=(
                f"physical+runtime_probe:{endpoint_evidence}"
                if physically_validated
                else f"reference+runtime_probe:{endpoint_evidence}"
            ),
            state="READ_SUPPORTED",
        )

    def _promote_hg8145x6_reader(
        self,
        feature: str,
        reader: Callable[[], object],
        *,
        endpoint_evidence: str,
        physically_validated: bool = False,
    ) -> None:
        self._promote_specialized_reader(
            feature,
            reader,
            endpoint_evidence=endpoint_evidence,
            physically_validated=physically_validated,
        )

    @staticmethod
    def _signature_selects_hg8145x6(
        signature: dict[str, Any],
        *,
        model_hint_matches: bool,
    ) -> bool:
        if not bool(signature.get("compatible")):
            return False
        if model_hint_matches:
            return True
        return bool(signature.get("strong_fingerprint"))

    def _probe_hg8145x6_candidate(
        self,
    ) -> tuple[HuaweiHG8145X6CapturedFeatureService, dict[str, Any]] | None:
        if self._client is None:
            return None
        candidate = HuaweiHG8145X6CapturedFeatureService(
            self._client,
            model=self.model,
        )
        try:
            signature = candidate.source_signature()
        except Exception:
            return None
        if not self._signature_selects_hg8145x6(
            signature,
            model_hint_matches=self._is_hg8145x6_model(self.model),
        ):
            return None
        return candidate, signature

    def _configure_hg8145x6_runtime(
        self,
        captured: HuaweiHG8145X6CapturedFeatureService,
        signature: dict[str, Any],
    ) -> None:
        self._phase2_runtime = None
        self._phase2_profile = None
        self._phase3_runtime = None
        self._captured = captured
        self._clear_session_snapshot()
        self._family_compatible = bool(signature.get("compatible"))
        self._family_descriptor = {
            "protocol_family": str((self.protocol or {}).get("family") or "unknown"),
            "firmware_family": "HG8145X6/V5R022-like",
            "cfg_mode": None,
            "compatible": self._family_compatible,
            "model": self.model,
            "model_hint_match": self._is_hg8145x6_model(self.model),
            "strong_fingerprint": bool(signature.get("strong_fingerprint")),
            "source": HuaweiHG8145X6CapturedFeatureService.SOURCE,
            "evidence": list(signature.get("evidence") or []),
            "endpoints": deepcopy(signature.get("endpoints") or {}),
        }
        self._force_hg8145x6_read_only()
        if not self._family_compatible:
            return

        self._promote_hg8145x6_reader(
            "device_info",
            lambda: self.device_status(refresh=True),
            endpoint_evidence="deviceinfo.asp",
            physically_validated=True,
        )
        self._promote_hg8145x6_reader(
            "wan",
            lambda: self.wan_status(refresh=True),
            endpoint_evidence="wan_list_cache_wan.asp",
            physically_validated=True,
        )
        self._promote_hg8145x6_reader(
            "wifi_basic",
            lambda: self.wifi_networks(refresh=True),
            endpoint_evidence="wlan_list.asp",
            physically_validated=True,
        )
        self._promote_hg8145x6_reader(
            "clients",
            lambda: self.clients(refresh=True),
            endpoint_evidence="getassociateddeviceinfo.asp",
            physically_validated=True,
        )
        self._promote_hg8145x6_reader(
            "wifi_traffic",
            lambda: self.wifi_traffic(refresh=True),
            endpoint_evidence="wlaninfo.asp",
            physically_validated=True,
        )
        self._promote_hg8145x6_reader(
            "resource_telemetry",
            lambda: self.resource_telemetry(refresh=True),
            endpoint_evidence="deviceinfo.asp:dev_uptime/cpuUsed/memUsed",
            physically_validated=True,
        )
        self._promote_hg8145x6_reader(
            "optical_telemetry",
            lambda: self.optical_status(refresh=True),
            endpoint_evidence="|".join(HG8145X6_OPTICAL_CANDIDATE_PAGES),
            physically_validated=False,
        )

    # ------------------------------------------------------------------
    # Phase 2: EG8145V5 + HN8010TS

    def _probe_phase2_candidate(
        self,
    ) -> tuple[HuaweiEG8145V5FamilyRuntime, HuaweiEG8145FamilyProfile, dict[str, Any]] | None:
        if self._client is None:
            return None
        if getattr(self._client, "auth_flow", None) not in {
            HuaweiAuthFlow.RAND_COUNT,
            HuaweiAuthFlow.RAND_COUNT.value,
        }:
            return None

        for profile in ordered_phase2_profiles(self.model):
            candidate = HuaweiEG8145V5FamilyRuntime(self._client, profile)
            try:
                signature = candidate.source_signature()
            except Exception:
                continue
            if bool(signature.get("compatible")) and bool(signature.get("strong_fingerprint")):
                return candidate, profile, signature
        return None

    def _configure_phase2_runtime(
        self,
        runtime: HuaweiEG8145V5FamilyRuntime,
        profile: HuaweiEG8145FamilyProfile,
        signature: dict[str, Any],
    ) -> None:
        self._phase3_runtime = None
        self._phase2_runtime = runtime
        self._phase2_profile = profile
        self._family_compatible = bool(signature.get("compatible"))
        self.model = profile.canonical_model
        self.model_verified = True
        self.model_source = "runtime_deviceinfo"
        self._device_info.update({
            "fabricante": "Huawei",
            "modelo": profile.canonical_model,
        })
        self._clear_session_snapshot()
        self._family_descriptor = {
            "protocol_family": str((self.protocol or {}).get("family") or "unknown"),
            "firmware_family": f"{profile.canonical_model}-reference-read",
            "cfg_mode": None,
            "compatible": self._family_compatible,
            "model": profile.canonical_model,
            "strong_fingerprint": bool(signature.get("strong_fingerprint")),
            "source": signature.get("source") or profile.source,
            "evidence": list(signature.get("evidence") or []),
            "endpoints": deepcopy(signature.get("endpoints") or {}),
            "physical_validation": False,
            "phase": 2,
        }
        self._force_specialized_read_only("phase2_read_only_no_write_capture")
        if not self._family_compatible:
            return

        self._promote_specialized_reader(
            "device_info",
            lambda: self.device_status(refresh=True),
            endpoint_evidence=profile.device_info.path,
        )
        self._promote_specialized_reader(
            "clients",
            lambda: self.clients(refresh=True),
            endpoint_evidence="|".join(item.path for item in profile.client_endpoints),
        )
        self._promote_specialized_reader(
            "resource_telemetry",
            lambda: self.resource_telemetry(refresh=True),
            endpoint_evidence=f"{profile.device_info.path}:cpuUsed/memUsed/dev_uptime",
        )
        if profile.optical is not None:
            self._promote_specialized_reader(
                "optical",
                lambda: self.optical_status(refresh=True),
                endpoint_evidence=profile.optical.path,
            )
            self._promote_specialized_reader(
                "optical_telemetry",
                lambda: self.optical_telemetry(refresh=True),
                endpoint_evidence=profile.optical.path,
            )

    # ------------------------------------------------------------------
    # Phase 3: HG8245H modern /api/ runtime

    def _probe_phase3_candidate(
        self,
    ) -> tuple[HuaweiHG8245HApiRuntime, dict[str, Any]] | None:
        if self._client is None:
            return None
        if getattr(self._client, "auth_flow", None) not in {
            HuaweiAuthFlow.API_SES_TOKEN,
            HuaweiAuthFlow.API_SES_TOKEN.value,
        }:
            return None
        runtime = HuaweiHG8245HApiRuntime(self._client)
        try:
            signature = runtime.source_signature()
        except Exception:
            return None
        if not bool(signature.get("compatible")) or not bool(signature.get("strong_fingerprint")):
            return None
        return runtime, signature

    def _configure_phase3_runtime(
        self,
        runtime: HuaweiHG8245HApiRuntime,
        signature: dict[str, Any],
    ) -> None:
        self._phase3_runtime = runtime
        self._phase2_runtime = None
        self._phase2_profile = None
        # A modern /api/ session must not inherit AMP/BBSP readers, mapped
        # pages, IPv4-filter probes or writers from the legacy Huawei provider.
        self._captured = None
        self._mapped = None
        self._ipv4_filter = None
        self._family_compatible = bool(signature.get("compatible"))
        self.model = HuaweiHG8245HApiRuntime.MODEL
        self.model_verified = True
        self.model_source = "runtime_api_deviceinfo"
        self._device_info = {
            "fabricante": "Huawei",
            "modelo": self.model,
        }
        self._clear_session_snapshot()
        self._family_descriptor = {
            "protocol_family": "api_sestoken",
            "firmware_family": "HG8245H-api",
            "cfg_mode": None,
            "compatible": self._family_compatible,
            "model": self.model,
            "strong_fingerprint": bool(signature.get("strong_fingerprint")),
            "source": signature.get("source") or HuaweiHG8245HApiRuntime.SOURCE,
            "evidence": list(signature.get("evidence") or []),
            "endpoints": deepcopy(signature.get("endpoints") or {}),
            "physical_validation": False,
            "phase": 3,
        }
        self._force_specialized_read_only(
            "phase3_hg8245h_api_read_only",
            preserve_existing_reads=False,
        )
        self._capabilities["reboot"] = self._ops(
            read=False,
            update=False,
            verified=False,
            physical_validation=False,
            evidence="phase3_reboot_requires_physical_validation",
            state="UNKNOWN",
        )
        if not self._family_compatible:
            return
        self._promote_specialized_reader(
            "device_info",
            lambda: self.device_status(refresh=True),
            endpoint_evidence=HuaweiHG8245HApiRuntime.DEVICE_INFO_PATH,
        )

    def connect(self, *args, **kwargs):
        result = HuaweiTelemetryRuntimeService.connect(self, *args, **kwargs)

        # Protocol family wins over marketing model hints. An authenticated
        # API SesToken session is resolved before any AMP/BBSP specialization.
        phase3_candidate = self._probe_phase3_candidate()
        if phase3_candidate is not None:
            runtime, signature = phase3_candidate
            self._configure_phase3_runtime(runtime, signature)
        else:
            hg_candidate = self._probe_hg8145x6_candidate()
            if hg_candidate is not None:
                captured, signature = hg_candidate
                self._configure_hg8145x6_runtime(captured, signature)
            else:
                phase2_candidate = self._probe_phase2_candidate()
                if phase2_candidate is not None:
                    runtime, profile, signature = phase2_candidate
                    self._configure_phase2_runtime(runtime, profile, signature)
                else:
                    self._phase3_runtime = None
                    self._phase2_runtime = None
                    self._phase2_profile = None
                    self._characterize_family()
                    self._promote_family_capabilities()

        result.update({
            "model": self.model,
            "model_verified": self.model_verified,
            "model_source": self.model_source,
            "device": self.device_info,
            "family": self.family_descriptor,
            "capabilities": self.capabilities,
            "provider": type(self).__name__,
        })
        client_descriptor = getattr(self._client, "transport_descriptor", None)
        if callable(client_descriptor):
            result["transport"] = client_descriptor()
        return result

    def disconnect(self) -> None:
        self._phase3_runtime = None
        self._phase2_runtime = None
        self._phase2_profile = None
        super().disconnect()

    # ------------------------------------------------------------------
    # Specialized read surfaces

    def device_status(self, *, refresh: bool = False) -> dict[str, Any]:
        if self._phase3_active:
            def load_phase3():
                runtime = self._phase3_runtime
                if runtime is None:
                    raise RuntimeError("Runtime Phase-3 não está ativo.")
                details = runtime.device_status(refresh=refresh)
                raw_uptime = details.get("uptime")
                uptime_days = None
                try:
                    if raw_uptime not in (None, ""):
                        uptime_days = int(float(raw_uptime)) // 86400
                except (TypeError, ValueError):
                    uptime_days = None
                return {
                    **details,
                    "host": self.current_host,
                    "profile": self.profile_key,
                    "provider": type(self).__name__,
                    "model_verified": self.model_verified,
                    "capabilities": self.capabilities,
                    "uptime_dias": uptime_days,
                }

            with self._lock:
                return self._snapshot_read("device", load_phase3, refresh=refresh)

        if not self._phase2_active:
            return super().device_status(refresh=refresh)

        def load_phase2():
            runtime = self._phase2_runtime
            if runtime is None:
                raise RuntimeError("Runtime Phase-2 não está ativo.")
            details = runtime.device_status()
            raw_uptime = details.get("uptime")
            uptime_days = None
            try:
                if raw_uptime not in (None, ""):
                    uptime_days = int(float(raw_uptime)) // 86400
            except (TypeError, ValueError):
                uptime_days = None
            return {
                **details,
                "host": self.current_host,
                "profile": self.profile_key,
                "provider": type(self).__name__,
                "model_verified": self.model_verified,
                "capabilities": self.capabilities,
                "uptime_dias": uptime_days,
            }

        with self._lock:
            return self._snapshot_read("device", load_phase2, refresh=refresh)

    def _phase3_read_unavailable(self, feature: str):
        if self._phase3_active:
            raise RuntimeError(
                f"{feature} não foi caracterizado para o runtime HG8245H /api/ Phase-3."
            )

    def wifi_traffic(self, *, refresh: bool = False) -> list[dict[str, Any]]:
        self._phase3_read_unavailable("Contadores Wi-Fi")
        if not self._hg8145x6_active:
            raise RuntimeError(
                "Contadores Wi-Fi ONTWatch estão caracterizados apenas para o "
                "runtime HG8145X6 confirmado por fingerprint."
            )
        captured = self._require_captured()
        return self._snapshot_read(
            "wifi_traffic",
            captured.wifi_traffic,
            refresh=refresh,
        )

    def resource_telemetry(self, *, refresh: bool = False) -> dict[str, Any]:
        self._phase3_read_unavailable("Telemetria de recursos")
        if self._phase2_active:
            runtime = self._phase2_runtime
            if runtime is None:
                raise RuntimeError("Runtime Phase-2 não está ativo.")
            return self._snapshot_read(
                "resource_telemetry",
                runtime.resource_telemetry,
                refresh=refresh,
            )
        if self._hg8145x6_active:
            data = self.web_resource_telemetry(refresh=refresh)
            self._promote_read(
                "resource_telemetry",
                source="webui_probe",
                evidence="HG8145X6:deviceinfo.asp",
            )
            return data
        return super().resource_telemetry(refresh=refresh)

    def clients(self, *, refresh: bool = False) -> list[dict]:
        self._phase3_read_unavailable("Clientes")
        if self._phase2_active:
            runtime = self._phase2_runtime
            if runtime is None:
                raise RuntimeError("Runtime Phase-2 não está ativo.")
            return self._snapshot_read("phase2_clients", runtime.clients, refresh=refresh)
        if not self._hg8145x6_active:
            return super().clients(refresh=refresh)

        wifi = self.wifi_clients(refresh=refresh)
        rows: list[dict[str, Any]] = []
        for item in wifi or []:
            rows.append({
                "hostname": item.get("hostname") or "",
                "ip": item.get("ip") or "",
                "mac": self._normalize_mac(item.get("mac")) or item.get("mac") or "",
                "interface": item.get("interface") or "",
                "connection_type": "wifi",
                "online": item.get("status") or "Online",
                "lease": item.get("lease") or "",
                "band": item.get("band") or item.get("banda") or "",
                "radio": item.get("radio") or item.get("ssid") or "",
                "ssid": item.get("ssid") or "",
                "wlan_index": item.get("wlan_index"),
                "rssi": item.get("rssi"),
                "noise": item.get("noise"),
                "snr": item.get("snr"),
                "signal_quality": item.get("signal_quality"),
                "rx_rate": item.get("rx_rate"),
                "tx_rate": item.get("tx_rate"),
                "mode": item.get("mode") or "",
                "uptime": item.get("uptime"),
                "antenna": item.get("antenna") or "",
                "source": item.get("source") or "",
            })
        return rows

    def wan_status(self, *, refresh: bool = False):
        self._phase3_read_unavailable("WAN")
        return super().wan_status(refresh=refresh)

    def lan_clients(self, *, refresh: bool = False):
        self._phase3_read_unavailable("Clientes LAN")
        if not self._phase2_active:
            return super().lan_clients(refresh=refresh)
        return [
            row for row in self.clients(refresh=refresh)
            if row.get("connection_type") == "lan"
        ]

    def wifi_clients(self, *, refresh: bool = False):
        self._phase3_read_unavailable("Clientes Wi-Fi")
        if not self._phase2_active:
            return super().wifi_clients(refresh=refresh)
        return [
            row for row in self.clients(refresh=refresh)
            if row.get("connection_type") == "wifi"
        ]

    def optical_status(self, *, refresh: bool = False):
        self._phase3_read_unavailable("Óptica")
        if not self._phase2_active:
            return super().optical_status(refresh=refresh)
        runtime = self._phase2_runtime
        profile = self._phase2_profile
        if runtime is None or profile is None or profile.optical is None:
            raise RuntimeError(
                "Óptica Phase-2 não foi confirmada para este modelo/firmware."
            )
        return self._snapshot_read("optical", runtime.optical_status, refresh=refresh)

    def optical_telemetry(self, *, refresh: bool = False) -> dict[str, Any]:
        self._phase3_read_unavailable("Telemetria óptica")
        if not self._phase2_active:
            return super().optical_telemetry(refresh=refresh)
        runtime = self._phase2_runtime
        profile = self._phase2_profile
        if runtime is None or profile is None or profile.optical is None:
            raise RuntimeError(
                "Telemetria óptica Phase-2 não foi confirmada para este modelo/firmware."
            )
        return self._snapshot_read(
            "optical_telemetry",
            runtime.optical_telemetry,
            refresh=refresh,
        )

    def wifi_networks(
        self,
        reveal_password: bool = False,
        *,
        refresh: bool = False,
    ) -> list[dict]:
        self._phase3_read_unavailable("Wi-Fi")
        if self._phase2_active:
            raise RuntimeError(
                "Wi-Fi EG8145V5/HN8010TS ainda não possui endpoint/schema "
                "Phase-2 confirmado para leitura ou escrita."
            )
        if self._hg8145x6_active:
            return self._snapshot_read(
                "wifi_networks",
                lambda: self._require_captured().wifi_networks(False),
                refresh=refresh,
            )
        return super().wifi_networks(
            reveal_password=reveal_password,
            refresh=refresh,
        )

    # Explicit write guards. Generic Huawei service owns physically validated
    # EG8041 writers; Phase 2/3 fail before reaching them.
    def _specialized_block_write(self):
        if self._phase3_active:
            raise RuntimeError(
                "O runtime HG8245H /api/ Phase-3 é somente leitura; nenhuma "
                "mutação foi fisicamente validada."
            )
        if self._phase2_active:
            raise RuntimeError(
                "Este runtime Phase-2 é somente leitura; nenhuma captura física "
                "de mutação foi validada para EG8145V5/HN8010TS."
            )

    def set_ssid_config(self, ssid_id, config):
        self._specialized_block_write()
        return super().set_ssid_config(ssid_id, config)

    def set_wifi_radio(self, band, config):
        self._specialized_block_write()
        return super().set_wifi_radio(band, config)

    def set_radio_power(self, band, enabled):
        self._specialized_block_write()
        return super().set_radio_power(band, enabled)

    def set_wifi_schedule(self, config):
        self._specialized_block_write()
        return super().set_wifi_schedule(config)

    def set_wps(self, band, mode):
        self._specialized_block_write()
        return super().set_wps(band, mode)

    def set_band_steering(self, enabled):
        self._specialized_block_write()
        return super().set_band_steering(enabled)

    def configure_band_steering(self, config):
        self._specialized_block_write()
        return super().configure_band_steering(config)

    def reboot(self):
        if self._phase3_active:
            raise RuntimeError(
                "Reboot HG8245H Phase-3 permanece desabilitado até validação "
                "física do endpoint, framing e efeito real."
            )
        return super().reboot()

    def _family_feature_reader(self, feature: str):
        if feature == "wifi_traffic":
            return lambda refresh=False: self.wifi_traffic(refresh=refresh)
        if feature == "resource_telemetry":
            return lambda refresh=False: self.resource_telemetry(refresh=refresh)
        if feature == "optical_telemetry":
            return lambda refresh=False: self.optical_telemetry(refresh=refresh)
        return super()._family_feature_reader(feature)

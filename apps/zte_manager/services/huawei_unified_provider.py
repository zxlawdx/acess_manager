from __future__ import annotations

import re
from copy import deepcopy
from typing import Any, Callable

from apps.zte_manager.services.huawei_eg8041_family_provider import (
    HuaweiEG8041FamilyProvider,
)
from apps.zte_manager.services.huawei_hg8145x6_runtime import (
    HG8145X6_OPTICAL_CANDIDATE_PAGES,
    HuaweiHG8145X6CapturedFeatureService,
)
from apps.zte_manager.services.huawei_telemetry_runtime import (
    HuaweiTelemetryRuntimeService,
)


class HuaweiUnifiedProvider(HuaweiEG8041FamilyProvider):
    """Production Huawei provider with evidence-driven runtime strategies.

    EG8041 keeps the existing family runtime. HG8145X6 uses the read-only
    ONTWatch-derived endpoint contract only after a runtime signature confirms
    it. Model names are hints, never sufficient permission to select a protocol
    or promote a capability.
    """

    FAMILY_RUNTIME_FEATURES = frozenset({
        *HuaweiEG8041FamilyProvider.FAMILY_RUNTIME_FEATURES,
        "wifi_traffic",
    })
    _LABELS = {
        **HuaweiEG8041FamilyProvider._LABELS,
        "wifi_traffic": "Per-SSID Wi-Fi traffic counters",
    }
    _HG8145X6_COMPACT = frozenset({"HG8145X6", "HG8145X610"})

    @classmethod
    def _is_hg8145x6_model(cls, model: object) -> bool:
        value = re.sub(r"\bHUAWEI\b", " ", str(model or "").upper())
        compact = re.sub(r"[^A-Z0-9]+", "", value)
        return compact in cls._HG8145X6_COMPACT

    @property
    def _hg8145x6_active(self) -> bool:
        return isinstance(self._captured, HuaweiHG8145X6CapturedFeatureService)

    @property
    def capabilities(self) -> dict[str, dict]:
        data = super().capabilities
        if not self._hg8145x6_active:
            return data

        # The generic EG8041 Wi-Fi descriptor contains radio/write assumptions
        # that ONTWatch never established for HG8145X6. Keep only capabilities
        # promoted by authenticated read probes for this runtime signature.
        data.pop("wifi", None)
        data["family"] = self.family_descriptor
        return data

    def _force_hg8145x6_read_only(self) -> None:
        for feature, current in list(self._capabilities.items()):
            if not isinstance(current, dict):
                continue
            operations = dict(current)
            for key in ("create", "update", "delete", "write", "start"):
                if key in operations:
                    operations[key] = False
            if operations.get("read"):
                operations["state"] = "READ_SUPPORTED"
            else:
                operations["state"] = "UNKNOWN"
            # Existing verification bits may refer to another family/profile.
            operations["verified"] = False
            operations["physical_validation"] = False
            self._capabilities[feature] = operations

        # Explicitly neutralize dangerous cross-family write/radio promotions.
        # HG8145X6 writes need their own physical browser capture.
        for feature in (
            "wifi_radio",
            "wifi_advanced",
            "wifi_channel_discovery",
        ):
            self._capabilities[feature] = self._ops(
                read=False,
                update=False,
                verified=False,
                physical_validation=False,
                evidence="hg8145x6_no_write_evidence",
                state="UNKNOWN",
            )

    def _promote_hg8145x6_reader(
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
                else f"runtime_probe:{endpoint_evidence}"
            ),
            state="READ_SUPPORTED",
        )

    @staticmethod
    def _signature_selects_hg8145x6(
        signature: dict[str, Any],
        *,
        model_hint_matches: bool,
    ) -> bool:
        if not bool(signature.get("compatible")):
            return False
        # A known/validated model hint still needs endpoint compatibility.
        if model_hint_matches:
            return True
        # Unknown/misreported model strings require a full ONTWatch-like
        # signature before this adapter is selected.
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

        # These paths were physically validated by the user's HG8145X6 flow.
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
        # Optical surfaces are read-only candidates from research. They become
        # readable only when the connected firmware returns recognized data;
        # they are not labeled physically validated until a real response is
        # observed and recorded for this firmware.
        self._promote_hg8145x6_reader(
            "optical_telemetry",
            lambda: self.optical_status(refresh=True),
            endpoint_evidence="|".join(HG8145X6_OPTICAL_CANDIDATE_PAGES),
            physically_validated=False,
        )

    def connect(self, *args, **kwargs):
        # Initial authentication/telemetry remains shared. Runtime-specific
        # endpoint readers are selected only after the authenticated session
        # exists, so model strings never decide the auth flow by themselves.
        result = HuaweiTelemetryRuntimeService.connect(self, *args, **kwargs)

        hg_candidate = self._probe_hg8145x6_candidate()
        if hg_candidate is not None:
            captured, signature = hg_candidate
            self._configure_hg8145x6_runtime(captured, signature)
        else:
            # Preserve the pre-existing EG8041 family characterization. This
            # path remains authoritative for X6/X7 captures and other existing
            # runtime-compatible candidates.
            self._characterize_family()
            self._promote_family_capabilities()

        result["family"] = self.family_descriptor
        client_descriptor = getattr(self._client, "transport_descriptor", None)
        if callable(client_descriptor):
            result["transport"] = client_descriptor()
        result["capabilities"] = self.capabilities
        result["provider"] = type(self).__name__
        return result

    def wifi_traffic(self, *, refresh: bool = False) -> list[dict[str, Any]]:
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

    def wifi_networks(
        self,
        reveal_password: bool = False,
        *,
        refresh: bool = False,
    ) -> list[dict]:
        if self._hg8145x6_active:
            # No physical password-reveal evidence for this firmware profile.
            return self._snapshot_read(
                "wifi_networks",
                lambda: self._require_captured().wifi_networks(False),
                refresh=refresh,
            )
        return super().wifi_networks(
            reveal_password=reveal_password,
            refresh=refresh,
        )

    def _family_feature_reader(self, feature: str):
        if feature == "wifi_traffic":
            return lambda refresh=False: self.wifi_traffic(refresh=refresh)
        return super()._family_feature_reader(feature)

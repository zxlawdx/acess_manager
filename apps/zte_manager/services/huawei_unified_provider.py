from __future__ import annotations

import re
from copy import deepcopy
from typing import Any, Callable

from apps.zte_manager.services.huawei_eg8041_family_provider import (
    HuaweiEG8041FamilyProvider,
)
from apps.zte_manager.services.huawei_hg8145x6_runtime import (
    HuaweiHG8145X6CapturedFeatureService,
)
from apps.zte_manager.services.huawei_telemetry_runtime import (
    HuaweiTelemetryRuntimeService,
)


class HuaweiUnifiedProvider(HuaweiEG8041FamilyProvider):
    """Production Huawei provider with model-specific read strategies.

    EG8041 keeps the existing family runtime. HG8145X6 uses the read-only
    ONTWatch-derived endpoint contract instead of inheriting EG8041/X7 WLAN
    assumptions. This prevents evidence from one Huawei family from being
    treated as universal while keeping one provider boundary for DeviceService.
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
        return self._is_hg8145x6_model(self.model)

    @property
    def capabilities(self) -> dict[str, dict]:
        data = super().capabilities
        if not self._hg8145x6_active:
            return data

        # The generic EG8041 Wi-Fi descriptor contains radio/write assumptions
        # that ONTWatch never established for HG8145X6. Keep only capabilities
        # promoted by authenticated read probes for this model.
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

        # Explicitly neutralize the dangerous cross-family radio promotion from
        # the legacy family runtime. HG8145X6 writes need their own capture.
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
                evidence="ontwatch_no_write_evidence",
                state="UNKNOWN",
            )

    def _promote_hg8145x6_reader(
        self,
        feature: str,
        reader: Callable[[], object],
        *,
        endpoint_evidence: str,
    ) -> None:
        try:
            reader()
        except Exception:
            self._capabilities[feature] = self._ops(
                read=False,
                update=False,
                verified=False,
                physical_validation=False,
                evidence=f"ONTWATCH_SOURCE_CODE+probe_failed:{endpoint_evidence}",
                state="UNKNOWN",
            )
            return
        self._capabilities[feature] = self._ops(
            read=True,
            update=False,
            verified=False,
            physical_validation=False,
            evidence=f"ONTWATCH_SOURCE_CODE+runtime_probe:{endpoint_evidence}",
            state="READ_SUPPORTED",
        )

    def _configure_hg8145x6_runtime(self) -> None:
        if self._client is None:
            return
        self._captured = HuaweiHG8145X6CapturedFeatureService(
            self._client,
            model=self.model,
        )
        self._clear_session_snapshot()
        signature = self._captured.source_signature()
        self._family_compatible = bool(signature.get("compatible"))
        self._family_descriptor = {
            "protocol_family": str((self.protocol or {}).get("family") or "unknown"),
            "firmware_family": "HG8145X6/V5R022-like",
            "cfg_mode": None,
            "compatible": self._family_compatible,
            "model": self.model,
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
        )
        self._promote_hg8145x6_reader(
            "wan",
            lambda: self.wan_status(refresh=True),
            endpoint_evidence="wan_list_cache_wan.asp",
        )
        self._promote_hg8145x6_reader(
            "wifi_basic",
            lambda: self.wifi_networks(refresh=True),
            endpoint_evidence="wlan_list.asp",
        )
        self._promote_hg8145x6_reader(
            "clients",
            lambda: self.clients(refresh=True),
            endpoint_evidence="getassociateddeviceinfo.asp",
        )
        self._promote_hg8145x6_reader(
            "wifi_traffic",
            lambda: self.wifi_traffic(refresh=True),
            endpoint_evidence="wlaninfo.asp",
        )
        self._promote_hg8145x6_reader(
            "resource_telemetry",
            lambda: self.resource_telemetry(refresh=True),
            endpoint_evidence="deviceinfo.asp:dev_uptime/cpuUsed/memUsed",
        )

    def connect(self, *args, **kwargs):
        # Bypass EG8041FamilyRuntimeService.connect for the initial login. That
        # method probes EG8041-specific WLAN pages before the model-specific
        # strategy is selected. Baseline Huawei telemetry remains shared.
        result = HuaweiTelemetryRuntimeService.connect(self, *args, **kwargs)

        if self._hg8145x6_active:
            self._configure_hg8145x6_runtime()
        else:
            # Preserve the pre-existing production path for EG8041 and other
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
                "Contadores Wi-Fi ONTWatch estão caracterizados apenas para HG8145X6."
            )
        captured = self._require_captured()
        if not isinstance(captured, HuaweiHG8145X6CapturedFeatureService):
            raise RuntimeError("Reader HG8145X6 não está ativo nesta sessão.")
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
                evidence="ONTWATCH_SOURCE_CODE:deviceinfo.asp",
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
            # ONTWatch does not establish password-reveal semantics. Do not
            # reuse the EG8041 PSK reader just because the object names look
            # similar.
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

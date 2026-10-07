from __future__ import annotations

from typing import Any
from urllib.parse import urlparse

from apps.zte_manager.infrastructure.huawei.cli import (
    HuaweiCliOptions,
    HuaweiCliUnavailable,
    create_huawei_cli_transport,
)
from apps.zte_manager.model.device_adapters.huawei_registry import (
    resolve_huawei_model_knowledge,
)
from apps.zte_manager.model.telemetry import PonStatus
from apps.zte_manager.services.huawei_cli_telemetry import HuaweiCliTelemetryReader
from apps.zte_manager.services.huawei_pon import HuaweiPonStateReader
from apps.zte_manager.services.huawei_telemetry import HuaweiOpticalTelemetryReader
from apps.zte_manager.services.huawei_wifi_domain_runtime import (
    HuaweiWifiDomainRuntimeService,
)


class HuaweiTelemetryRuntimeService(HuaweiWifiDomainRuntimeService):
    """Huawei runtime with evidence-driven WebUI/optional-CLI telemetry.

    WebUI remains the preferred transport. CLI is opt-in, read-only and only
    created when the operator supplies explicit settings and the requested port
    is already reachable. No service/firewall/config-tree mutation occurs here.
    """

    TELEMETRY_FEATURES = frozenset({
        "optical_telemetry",
        "pon_status",
        "pon_statistics",
        "resource_telemetry",
    })

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        self._optical_telemetry_reader: HuaweiOpticalTelemetryReader | None = None
        self._cli_options = HuaweiCliOptions()
        self._cli_transport = None
        self._cli_reader: HuaweiCliTelemetryReader | None = None
        self._cli_error: str | None = None
        self._model_knowledge: dict[str, object] | None = None

    @staticmethod
    def _read_operations(
        *,
        available: bool,
        source: str,
        evidence: str,
    ) -> dict[str, object]:
        return {
            "read": bool(available),
            "write": False,
            "verified": False,
            "state": "READ_SUPPORTED" if available else "UNKNOWN",
            "source": source,
            "evidence": evidence,
            "physical_validation": False,
        }

    def _promote_read(self, feature: str, *, source: str, evidence: str) -> None:
        self._capabilities[feature] = self._read_operations(
            available=True,
            source=source,
            evidence=evidence,
        )

    def _mark_unknown(self, feature: str, *, source: str, evidence: str) -> None:
        if bool((self._capabilities.get(feature) or {}).get("read")):
            return
        self._capabilities[feature] = self._read_operations(
            available=False,
            source=source,
            evidence=evidence,
        )

    def _canonicalize_researched_identity(self, model_hint: str | None) -> None:
        knowledge = (
            resolve_huawei_model_knowledge(self.model)
            or resolve_huawei_model_knowledge(model_hint)
        )
        if knowledge is None:
            self._model_knowledge = None
            return

        self._model_knowledge = knowledge.public()
        # Knowledge recognition is not verification. Only normalize identity
        # for unknown operational profiles; EG8041's validated profile remains
        # authoritative.
        if self.profile_key == "huawei_unknown":
            self.model = knowledge.canonical_model
            self.model_verified = False
            if self.model_source in {None, "unknown"}:
                self.model_source = "knowledge_registry"
            self._device_info["modelo"] = self.model

    @property
    def transports(self) -> dict[str, object]:
        cli = self._cli_options.public()
        cli.update({
            "available": self._cli_reader is not None,
            "selected": (
                str(getattr(self._cli_transport, "name", "")) or None
            ),
            "error": self._cli_error,
        })
        return {
            "webui": {"available": self._client is not None, "preferred": True},
            "cli": cli,
        }

    def _cli_host(self) -> str:
        if self._client is not None:
            parsed = urlparse(self._client.base_url)
            if parsed.hostname:
                return parsed.hostname
        raw = str(self.current_host or "")
        if "://" in raw:
            parsed = urlparse(raw)
            if parsed.hostname:
                return parsed.hostname
        return raw.split("/", 1)[0].split(":", 1)[0]

    def _configure_cli(self) -> None:
        self._cli_transport = None
        self._cli_reader = None
        self._cli_error = None
        if not self._cli_options.enabled:
            return
        try:
            self._cli_transport = create_huawei_cli_transport(
                self._cli_host(),
                self._cli_options,
            )
            self._cli_reader = HuaweiCliTelemetryReader(self._cli_transport)
        except Exception as exc:
            # CLI is optional enrichment; WebUI connection remains valid.
            self._cli_error = type(exc).__name__
            self._cli_transport = None
            self._cli_reader = None

    def _read_optical_telemetry_model(self):
        if self._client is None:
            raise RuntimeError("Huawei WebUI não está conectada.")
        if self._optical_telemetry_reader is None:
            self._optical_telemetry_reader = HuaweiOpticalTelemetryReader(self._client)
        try:
            result = self._optical_telemetry_reader.read()
            self._promote_read(
                "optical_telemetry",
                source="webui_probe",
                evidence=result.source_endpoint or "webui:opticinfo",
            )
            return result
        except Exception:
            if self._cli_reader is None:
                raise
        result = self._cli_reader.optical()
        self._promote_read(
            "optical_telemetry",
            source="cli_probe",
            evidence=f"{result.source_transport}:{result.source_command}",
        )
        return result

    def optical_telemetry(self, *, refresh: bool = False) -> dict[str, Any]:
        with self._lock:
            key = "optical_telemetry"
            cached = self._snapshot_cached(key)
            if cached is not None and not refresh:
                return cached
            result = self._read_optical_telemetry_model().as_dict()
            self._snapshot_store(key, result)
            return result

    def _read_normalized_pon_status_model(self) -> PonStatus:
        if self._client is not None:
            try:
                raw = HuaweiPonStateReader(self._client).read()
                result = PonStatus(
                    registration=raw.get("registration_status"),
                    o_state=(
                        str(raw.get("registration_status"))
                        if str(raw.get("registration_status") or "").upper().startswith("O")
                        else None
                    ),
                    mode=raw.get("pon_mode"),
                    onu_id=raw.get("onu_id"),
                    online=raw.get("online"),
                    configuration_mode=raw.get("configuration_mode"),
                    source_transport="webui",
                    source_endpoint=raw.get("source_endpoint"),
                )
                self._promote_read(
                    "pon_status",
                    source="webui_probe",
                    evidence=str(raw.get("source_endpoint") or "webui:pon-state"),
                )
                return result
            except Exception:
                pass
        if self._cli_reader is None:
            raise HuaweiCliUnavailable(
                "PON status normalizado não foi confirmado via WebUI e CLI não está disponível."
            )
        result = self._cli_reader.pon_status()
        self._promote_read(
            "pon_status",
            source="cli_probe",
            evidence=f"{result.source_transport}:{result.source_command}",
        )
        return result

    def normalized_pon_status(self, *, refresh: bool = False) -> dict[str, Any]:
        with self._lock:
            key = "pon_status"
            cached = self._snapshot_cached(key)
            if cached is not None and not refresh:
                return cached
            result = self._read_normalized_pon_status_model().as_dict()
            self._snapshot_store(key, result)
            return result

    def pon_statistics(self, *, refresh: bool = False) -> dict[str, Any]:
        with self._lock:
            key = "pon_statistics"
            cached = self._snapshot_cached(key)
            if cached is not None and not refresh:
                return cached
            if self._cli_reader is None:
                raise HuaweiCliUnavailable(
                    "Estatísticas PON requerem CLI explicitamente habilitada e disponível."
                )
            result = self._cli_reader.pon_statistics()
            self._promote_read(
                key,
                source="cli_probe",
                evidence=f"{result.source_transport}:{result.source_command}",
            )
            data = result.as_dict()
            self._snapshot_store(key, data)
            return data

    def resource_telemetry(self, *, refresh: bool = False) -> dict[str, Any]:
        with self._lock:
            key = "resource_telemetry"
            cached = self._snapshot_cached(key)
            if cached is not None and not refresh:
                return cached
            if self._cli_reader is None:
                raise HuaweiCliUnavailable(
                    "Telemetria CPU/memória requer CLI explicitamente habilitada e disponível."
                )
            result = self._cli_reader.resources()
            self._promote_read(
                key,
                source="cli_probe",
                evidence=f"{result.source_transport}:{result.source_command}",
            )
            data = result.as_dict()
            self._snapshot_store(key, data)
            return data

    def _probe_telemetry(self) -> None:
        probes = (
            ("optical_telemetry", self.optical_telemetry, "webui_or_cli"),
            ("pon_status", self.normalized_pon_status, "webui_or_cli"),
        )
        if self._cli_reader is not None:
            probes += (
                ("pon_statistics", self.pon_statistics, "cli"),
                ("resource_telemetry", self.resource_telemetry, "cli"),
            )
        for feature, reader, source in probes:
            try:
                reader(refresh=True)
            except Exception:
                self._mark_unknown(
                    feature,
                    source=f"{source}_probe",
                    evidence="probe_inconclusive",
                )

    def connect(self, *args, **kwargs):
        huawei_cli = kwargs.pop("huawei_cli", None)
        model_hint = kwargs.get("model_hint")
        requested_cli = HuaweiCliOptions.from_mapping(huawei_cli)
        # HuaweiService.connect calls self.disconnect() before creating a fresh
        # WebUI session. Restore the operator's CLI options only after that
        # lifecycle completes so secrets are still cleared on real disconnect.
        result = super().connect(*args, **kwargs)
        self._cli_options = requested_cli
        self._canonicalize_researched_identity(model_hint)
        self._optical_telemetry_reader = (
            HuaweiOpticalTelemetryReader(self._client)
            if self._client is not None
            else None
        )
        self._configure_cli()
        self._probe_telemetry()
        result.update({
            "model": self.model,
            "model_verified": self.model_verified,
            "model_source": self.model_source,
            "device": self.device_info,
            "model_knowledge": self._model_knowledge,
            "transports": self.transports,
            "capabilities": self.capabilities,
        })
        return result

    def disconnect(self) -> None:
        transport = self._cli_transport
        self._cli_reader = None
        self._cli_transport = None
        if transport is not None:
            try:
                transport.close()
            except Exception:
                pass
        self._cli_options = HuaweiCliOptions()
        self._cli_error = None
        self._optical_telemetry_reader = None
        self._model_knowledge = None
        super().disconnect()

    def _feature_reader(self, feature: str):
        readers = {
            "optical_telemetry": self.optical_telemetry,
            "pon_status": self.normalized_pon_status,
            "pon_statistics": self.pon_statistics,
            "resource_telemetry": self.resource_telemetry,
        }
        if feature in readers:
            return readers[feature]
        return super()._feature_reader(feature)

    def capability_catalog(self) -> dict:
        data = super().capability_catalog()
        labels = {
            "optical_telemetry": "Optical telemetry",
            "pon_status": "PON status",
            "pon_statistics": "PON statistics",
            "resource_telemetry": "Device resource telemetry",
        }
        for feature in self.TELEMETRY_FEATURES:
            operations = dict(self._capabilities.get(feature) or {})
            if not operations:
                continue
            available = bool(operations.get("read"))
            data.setdefault("features", {})[feature] = {
                "key": feature,
                "label": labels[feature],
                "writable": False,
                "dangerous": False,
                "notes": (
                    "Telemetria read-only promovida somente após probe e parser "
                    "reconhecido; nenhuma permissão deriva do nome do modelo."
                ),
                "operations": operations,
                "verified": False,
                "evidence_states": ["READ_SUPPORTED"] if available else ["UNKNOWN"],
                "state": "READ_SUPPORTED" if available else "UNKNOWN",
            }
        data["transports"] = self.transports
        data["model_knowledge"] = self._model_knowledge
        return data

    def probe_capabilities(self, features=None) -> dict:
        requested = list(features or self._capabilities.keys() or ["ipv4_filter"])
        telemetry = [item for item in requested if item in self.TELEMETRY_FEATURES]
        regular = [item for item in requested if item not in self.TELEMETRY_FEATURES]
        result = super().probe_capabilities(regular) if regular else {
            "adapter": "huawei-webui",
            "vendor": self.vendor,
            "profile": self.profile_key,
            "features": [],
        }
        labels = {
            "optical_telemetry": "Optical telemetry",
            "pon_status": "PON status",
            "pon_statistics": "PON statistics",
            "resource_telemetry": "Device resource telemetry",
        }
        for feature in telemetry:
            reader = self._feature_reader(feature)
            error = None
            try:
                reader(refresh=True)
                available = True
            except Exception as exc:
                available = False
                error = type(exc).__name__
                self._mark_unknown(
                    feature,
                    source="explicit_probe",
                    evidence="probe_inconclusive",
                )
            result["features"].append({
                "feature": feature,
                "label": labels[feature],
                "available": available,
                "status": "confirmed" if available else "inconclusive",
                "probeable": True,
                "writable": False,
                "dangerous": False,
                "verified": False,
                "operations": dict(self._capabilities.get(feature) or {}),
                "error": error,
            })
        result["transports"] = self.transports
        result["model_knowledge"] = self._model_knowledge
        return result

    def read_capability(
        self,
        feature: str,
        *,
        refresh: bool = False,
    ) -> dict:
        if feature not in self.TELEMETRY_FEATURES:
            return super().read_capability(feature, refresh=refresh)
        with self._lock:
            operations = dict(self._capabilities.get(feature) or {})
            if not operations.get("read"):
                raise ValueError(
                    f"Capability Huawei {feature} ainda não confirmada."
                )
            data = self._feature_reader(feature)(refresh=refresh)
            return {
                "feature": feature,
                "available": True,
                "writable": False,
                "objects": {"items": data},
                "capability": operations,
                "protocol": self.protocol,
                "transports": self.transports,
                "model_knowledge": self._model_knowledge,
            }

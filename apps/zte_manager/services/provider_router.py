from __future__ import annotations

import inspect
import ipaddress
from dataclasses import dataclass
from typing import Any, Callable, Iterable

from apps.zte_manager.infrastructure.huawei.affinity_client import (
    HuaweiAffinityNegotiatingWebClient,
)
from apps.zte_manager.model.device_adapters.huawei import is_known_huawei_model
from apps.zte_manager.model.device_adapters.huawei_registry import (
    is_recognized_huawei_model,
)
from apps.zte_manager.services.huawei_affinity_provider import (
    HuaweiAffinityUnifiedProvider,
)
from apps.zte_manager.services.huawei_service import HuaweiService
from apps.zte_manager.services.zte_service import ZTEService, zte_service
from apps.zte_manager.vendors.huawei import HuaweiWorkspace


@dataclass(frozen=True)
class ProviderConnection:
    vendor: str
    service: Any
    result: dict[str, Any]
    provider_name: str
    workspace: Any = None


class ProviderRouter:
    """The single runtime boundary allowed to choose a vendor provider.

    DeviceService owns orchestration/session state; ProviderRouter owns vendor
    detection, provider selection and provider-specific compatibility shapes.
    Controllers must never choose Huawei vs ZTE themselves.
    """

    def __init__(
        self,
        *,
        zte_provider: ZTEService | None = None,
        huawei_factory: Callable[[], Any] = HuaweiAffinityUnifiedProvider,
        huawei_client_type=HuaweiAffinityNegotiatingWebClient,
        huawei_model_predicates: Iterable[Callable[[str | None], bool]] | None = None,
        vendor_probe: Callable[..., bool] | None = None,
    ) -> None:
        self.zte_provider = zte_provider or zte_service
        self.huawei_factory = huawei_factory
        self.huawei_client_type = huawei_client_type
        self.huawei_model_predicates = tuple(
            huawei_model_predicates
            or (is_known_huawei_model, is_recognized_huawei_model)
        )
        self.vendor_probe = vendor_probe

    def detect_vendor(
        self,
        host: str,
        *,
        https: bool = False,
        model_hint: str | None = None,
    ) -> str:
        if any(predicate(model_hint) for predicate in self.huawei_model_predicates):
            return "huawei"

        if self._should_probe_vendor(host):
            probe = self.vendor_probe or self.huawei_client_type.looks_like_huawei
            if bool(probe(host, https=https)):
                return "huawei"

        return "zte"

    def connect(
        self,
        *,
        current_session: Any = None,
        ip: str,
        username: str,
        password: str,
        https: bool = False,
        attendant: str | None = None,
        model_hint: str | None = None,
        huawei_cli: dict | None = None,
    ) -> ProviderConnection:
        vendor = self.detect_vendor(
            ip,
            https=https,
            model_hint=model_hint,
        )

        if vendor == "huawei":
            return self._connect_huawei(
                current_session=current_session,
                ip=ip,
                username=username,
                password=password,
                https=https,
                attendant=attendant,
                model_hint=model_hint,
                huawei_cli=huawei_cli,
            )

        return self._connect_zte(
            current_session=current_session,
            ip=ip,
            username=username,
            password=password,
            https=https,
            attendant=attendant,
            model_hint=model_hint,
        )

    def _connect_huawei(self, *, current_session: Any = None, **kwargs) -> ProviderConnection:
        if current_session is not None and current_session.vendor == "huawei":
            service = current_session.service
            workspace = current_session.workspace or HuaweiWorkspace(service)
        else:
            if current_session is not None and current_session.service is not None:
                current_session.service.disconnect()
            elif getattr(self.zte_provider, "connected", False):
                self.zte_provider.disconnect()
            service = self.huawei_factory()
            workspace = HuaweiWorkspace(service)

        if kwargs.get("huawei_cli") is None:
            kwargs.pop("huawei_cli", None)

        result = workspace.connect(**kwargs)
        provider_name = (
            "HuaweiService"
            if isinstance(service, HuaweiService)
            else type(service).__name__
        )
        return ProviderConnection(
            vendor="huawei",
            service=service,
            result=result,
            provider_name=provider_name,
            workspace=workspace,
        )

    def _connect_zte(self, *, current_session: Any = None, **kwargs) -> ProviderConnection:
        if current_session is not None and current_session.vendor == "huawei":
            runtime = current_session.workspace or current_session.service
            if runtime is not None:
                runtime.disconnect()

        service = self.zte_provider
        result = service.connect(**kwargs)
        return ProviderConnection(
            vendor="zte",
            service=service,
            result=result,
            provider_name=type(service).__name__,
        )

    @staticmethod
    def _should_probe_vendor(host: str) -> bool:
        raw = str(host or "").strip()
        if "://" in raw:
            raw = raw.split("://", 1)[1]
        raw = raw.split("/", 1)[0]
        if raw.startswith("[") and "]" in raw:
            raw = raw[1:raw.index("]")]
        elif raw.count(":") == 1:
            raw = raw.split(":", 1)[0]

        try:
            address = ipaddress.ip_address(raw)
        except ValueError:
            return True

        management_probe_networks = (
            ipaddress.ip_network("10.0.0.0/8"),
            ipaddress.ip_network("172.16.0.0/12"),
            ipaddress.ip_network("192.168.0.0/16"),
            ipaddress.ip_network("100.64.0.0/10"),
        )
        return any(address in network for network in management_probe_networks)

    @staticmethod
    def capabilities(service: Any, fallback: dict[str, dict] | None = None) -> dict[str, dict]:
        value = getattr(service, "capabilities", None)
        if value is None:
            return {
                key: dict(item)
                for key, item in (fallback or {}).items()
            }
        return {
            key: dict(item)
            for key, item in value.items()
        }

    @staticmethod
    def writes_enabled(vendor: str | None, service: Any) -> bool:
        if vendor == "huawei":
            return bool(getattr(service, "writes_enabled", False))
        if vendor == "zte":
            backend = getattr(service, "_zte", None)
            return bool(getattr(backend, "writes_enabled", False))
        return False

    @staticmethod
    def invoke(service: Any, method_name: str, *args, **kwargs):
        """Call a provider method while forwarding only supported kwargs."""

        method = getattr(service, method_name)
        if not kwargs:
            return method(*args)

        signature = inspect.signature(method)
        parameters = signature.parameters.values()
        if any(param.kind is inspect.Parameter.VAR_KEYWORD for param in parameters):
            return method(*args, **kwargs)

        accepted = {
            name: value
            for name, value in kwargs.items()
            if name in signature.parameters
        }
        return method(*args, **accepted)

    @staticmethod
    def _huawei_catalog(status: dict[str, Any]) -> dict[str, Any]:
        capabilities = status.get("capabilities") or {}
        model = status.get("model") or "Huawei"
        return {
            "models": [{
                "model": model,
                "family": "huawei_webui",
                "candidate_features": list(capabilities.keys()),
            }]
        }

    def discovery_bootstrap(self, status: dict[str, Any], service: Any) -> dict[str, Any]:
        """Normalize discovery metadata without controller-side vendor branching."""

        if status.get("vendor") == "huawei":
            model = status.get("model") or "Huawei"
            return {
                **status,
                "model": model,
                "detected_model": model,
                "native_diagnostics_available": True,
                "catalog": self._huawei_catalog(status),
                "reason": None,
            }

        profile = status.get("profile")
        native_profiles = {
            "zte-f670l-thinklua",
            "zte-f6600p-thinklua",
            "zte-f6201b-thinklua",
        }
        return {
            **status,
            "detected_model": status.get("model"),
            "native_diagnostics_available": bool(
                status.get("connected")
                and status.get("model_verified")
                and profile in native_profiles
            ),
            "catalog": self.invoke(service, "multimodel_catalog"),
            "reason": (
                None if status.get("connected")
                else "Conecte-se a uma ONT para detectar recursos."
            ),
        }

    def multimodel_catalog(self, status: dict[str, Any], service: Any) -> dict[str, Any]:
        if status.get("vendor") == "huawei":
            return self._huawei_catalog(status)
        return self.invoke(service, "multimodel_catalog")

    def multimodel_diagnostic(
        self,
        status: dict[str, Any],
        service: Any,
        requested: str | None = None,
        section: str | None = None,
    ) -> dict[str, Any]:
        if status.get("vendor") == "huawei":
            return {
                "model": status.get("model"),
                "family": "huawei_webui",
                "read_only": True,
                "sections": {},
                "reason": (
                    "Use Detectar recursos: Huawei possui probe nativo por capability "
                    "e não usa o diagnóstico ThinkLua."
                ),
            }
        return self.invoke(service, "multimodel_diagnostic", requested, section)

    def multimodel_mesh(
        self,
        status: dict[str, Any],
        service: Any,
        model: str | None = None,
    ) -> dict[str, Any]:
        if status.get("vendor") == "huawei":
            return {
                "available": False,
                "vendor": "huawei",
                "model": status.get("model"),
                "reason": "Resumo Mesh ThinkLua não se aplica à sessão Huawei.",
            }
        return self.invoke(service, "multimodel_mesh", model)

    def multimodel_probe(
        self,
        status: dict[str, Any],
        service: Any,
        model: str | None = None,
        count: int = 4,
        start: int = 0,
    ) -> dict[str, Any]:
        if status.get("vendor") != "huawei":
            return self.invoke(service, "multimodel_probe", model, count, start)

        catalog = self.invoke(service, "capability_catalog")
        features = []
        for key, spec in (catalog.get("features") or {}).items():
            operations = spec.get("operations") or {}
            writable = any(
                operations.get(name)
                for name in ("create", "update", "delete", "write")
            )
            features.append({
                "feature": key,
                "label": spec.get("label") or key,
                "status": (
                    "detected"
                    if operations.get("read") and operations.get("verified")
                    else "not_tested"
                ),
                "available": bool(operations.get("read")),
                "read": bool(operations.get("read")),
                "write": bool(writable),
                "partial": bool(operations.get("partial")),
                "readback": (
                    "FULLY_INTEGRATED" in (spec.get("evidence_states") or [])
                ),
                "verified": bool(operations.get("verified")),
            })
        return {
            "model": status.get("model"),
            "family": "huawei_webui",
            "capabilities": features,
            "candidate_features": [],
            "reason": None,
        }

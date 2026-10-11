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


@dataclass(frozen=True)
class ProviderConnection:
    vendor: str
    service: Any
    result: dict[str, Any]
    provider_name: str


class ProviderRouter:
    """The single runtime boundary allowed to choose a vendor provider.

    DeviceService owns orchestration/session state; ProviderRouter owns vendor
    detection, provider selection and provider-specific connection arguments.
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
        else:
            if current_session is not None and current_session.service is not None:
                current_session.service.disconnect()
            elif getattr(self.zte_provider, "connected", False):
                self.zte_provider.disconnect()
            service = self.huawei_factory()

        if kwargs.get("huawei_cli") is None:
            kwargs.pop("huawei_cli", None)

        result = service.connect(**kwargs)
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
        )

    def _connect_zte(self, *, current_session: Any = None, **kwargs) -> ProviderConnection:
        if current_session is not None and current_session.vendor == "huawei":
            if current_session.service is not None:
                current_session.service.disconnect()

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
        """Call a provider method while forwarding only supported kwargs.

        This removes vendor conditionals such as the historical Huawei-only
        ``refresh`` forwarding. Provider signatures remain authoritative.
        """

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

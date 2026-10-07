from __future__ import annotations

import ipaddress
import logging
from dataclasses import dataclass, field
from typing import Any

from apps.zte_manager.infrastructure.huawei import HuaweiFamilyAwareWebClient
from apps.zte_manager.model.device_adapters.huawei import is_known_huawei_model
from apps.zte_manager.model.device_adapters.huawei_registry import (
    is_recognized_huawei_model,
)
from apps.zte_manager.services.huawei_service import HuaweiService
from apps.zte_manager.services.huawei_telemetry_runtime import (
    HuaweiTelemetryRuntimeService,
)
from apps.zte_manager.services.error_policy import ProviderFeatureUnavailable
from apps.zte_manager.services.zte_service import ZTEService, zte_service

logger = logging.getLogger(__name__)


@dataclass
class DeviceSession:
    vendor: str
    model: str | None
    profile: str | None
    provider: str
    service: Any = field(repr=False)
    capabilities: dict[str, dict] = field(default_factory=dict)
    model_verified: bool = False
    host: str | None = None
    attendant: str | None = None
    session_revision: str | None = None

    def public(self) -> dict:
        return {
            "vendor": self.vendor,
            "model": self.model,
            "profile": self.profile,
            "provider": self.provider,
            "capabilities": {
                key: dict(value)
                for key, value in self.capabilities.items()
            },
            "model_verified": self.model_verified,
            "host": self.host,
            "attendant": self.attendant,
            "session_revision": self.session_revision,
        }


class DeviceService:
    """Vendor-neutral runtime dispatcher.

    The active provider is a real ZTEService or HuaweiService instance. Huawei
    behavior never runs inside ZTEService.
    """

    def __init__(
        self,
        *,
        zte_provider: ZTEService | None = None,
        huawei_factory=HuaweiTelemetryRuntimeService,
        huawei_client_type=HuaweiFamilyAwareWebClient,
    ) -> None:
        self._zte_service = zte_provider or zte_service
        self._huawei_factory = huawei_factory
        self._huawei_client_type = huawei_client_type
        self._session: DeviceSession | None = None

    def __getattr__(self, name: str):
        """Delegate public provider surface to the active service.

        Missing methods/attributes are an explicit capability gap. An active
        Huawei session can never fall through to the ZTE provider.
        """
        if name.startswith("_"):
            raise AttributeError(name)

        service = self.active_service
        missing = object()
        target = getattr(service, name, missing)
        if target is missing:
            status = self.status()
            raise ProviderFeatureUnavailable(
                vendor=status.get("vendor"),
                model=status.get("model"),
            )
        return target

    @property
    def session(self) -> DeviceSession | None:
        return self._session

    @property
    def connected(self) -> bool:
        return bool(
            self._session is not None
            and self._session.service.connected
        )

    @property
    def active_service(self):
        if self._session is not None:
            return self._session.service
        # Before /connect, the historical ZTE provider remains the default
        # object so legacy tests/local callers keep their normal session error.
        # An active Huawei session always wins and can never fall back to ZTE.
        return self._zte_service

    @property
    def vendor(self) -> str | None:
        if self._session is not None:
            return self._session.vendor
        if self._zte_service.connected:
            return "zte"
        return None

    def connect(
        self,
        ip: str,
        username: str,
        password: str,
        *,
        https: bool = False,
        attendant: str | None = None,
        model_hint: str | None = None,
        huawei_cli: dict | None = None,
    ) -> dict:
        # Knowledge-registry recognition routes the request to the Huawei
        # provider, but does not grant an operational profile/capability. The
        # Huawei runtime still requires auth + real endpoint probes.
        manual_huawei = (
            is_known_huawei_model(model_hint)
            or is_recognized_huawei_model(model_hint)
        )
        detected_huawei = False

        if (
            not manual_huawei
            and self._should_probe_vendor(ip)
        ):
            detected_huawei = (
                self._huawei_client_type
                .looks_like_huawei(
                    ip,
                    https=https,
                )
            )

        if manual_huawei or detected_huawei:
            return self._connect_huawei(
                ip=ip,
                username=username,
                password=password,
                https=https,
                attendant=attendant,
                model_hint=model_hint,
                huawei_cli=huawei_cli,
            )

        # Huawei-only CLI options must never leak into ZTE providers.
        return self._connect_zte(
            ip=ip,
            username=username,
            password=password,
            https=https,
            attendant=attendant,
            model_hint=model_hint,
        )

    @staticmethod
    def _should_probe_vendor(host: str) -> bool:
        raw = str(host or "").strip()
        if "://" in raw:
            raw = raw.split("://", 1)[1]
        raw = raw.split("/", 1)[0].split(":", 1)[0]
        try:
            address = ipaddress.ip_address(raw)
        except ValueError:
            return True

        private_networks = (
            ipaddress.ip_network("10.0.0.0/8"),
            ipaddress.ip_network("172.16.0.0/12"),
            ipaddress.ip_network("192.168.0.0/16"),
        )
        return any(
            address in network
            for network in private_networks
        )

    def _connect_huawei(self, **kwargs) -> dict:
        if (
            self._session is not None
            and self._session.vendor == "huawei"
        ):
            service = self._session.service
        else:
            if self._session is not None:
                self.disconnect()
            elif self._zte_service.connected:
                self._zte_service.disconnect()
            service = self._huawei_factory()

        # Legacy/injected HuaweiService providers predate optional CLI support.
        # Do not change their call contract when the operator did not request
        # CLI. The default telemetry runtime receives the explicit mapping when
        # present and remains the only provider that interprets it.
        if kwargs.get("huawei_cli") is None:
            kwargs.pop("huawei_cli", None)
        result = service.connect(**kwargs)
        provider_name = (
            "HuaweiService"
            if isinstance(service, HuaweiService)
            else type(service).__name__
        )
        result["provider"] = provider_name
        self._session = DeviceSession(
            vendor="huawei",
            model=result.get("model"),
            profile=result.get("profile"),
            provider=provider_name,
            service=service,
            capabilities=result.get("capabilities") or {},
            model_verified=bool(
                result.get("model_verified")
            ),
            host=result.get("host"),
            attendant=result.get("attendant"),
            session_revision=result.get("session_revision"),
        )
        logger.info(
            "device_provider_selected vendor=huawei provider=%s profile=%s",
            provider_name,
            result.get("profile") or "huawei_unknown",
        )
        return result

    def _connect_zte(self, **kwargs) -> dict:
        if (
            self._session is not None
            and self._session.vendor == "huawei"
        ):
            self.disconnect()

        result = self._zte_service.connect(**kwargs)
        if self._zte_service.connected:
            self._session = DeviceSession(
                vendor="zte",
                model=result.get("model"),
                profile=result.get("adapter"),
                provider=type(self._zte_service).__name__,
                service=self._zte_service,
                capabilities={},
                model_verified=bool(
                    result.get("model_verified")
                ),
                host=result.get("host"),
                attendant=result.get("attendant"),
                session_revision=result.get("session_revision"),
            )
        logger.info(
            "device_provider_selected vendor=zte provider=%s",
            type(self._zte_service).__name__,
        )
        return result

    def disconnect(self) -> None:
        if self._session is not None:
            self._session.service.disconnect()
            self._session = None
            return
        if self._zte_service.connected:
            self._zte_service.disconnect()

    def status(self) -> dict:
        if self._session is None:
            if self._zte_service.connected:
                return {
                    "connected": True,
                    "vendor": "zte",
                    "model": self._zte_service._selected_model,
                    "profile": (
                        self._zte_service._adapter.name
                        if self._zte_service._adapter
                        else None
                    ),
                    "provider": type(self._zte_service).__name__,
                    "capabilities": {},
                    "model_verified": self._zte_service._model_verified,
                    "host": self._zte_service.current_host,
                    "attendant": self._zte_service.current_attendant,
                    "session_revision": self._zte_service._session_revision,
                    "writes_enabled": bool(
                        getattr(
                            self._zte_service._zte,
                            "writes_enabled",
                            False,
                        )
                    ),
                }
            return {
                "connected": False,
                "vendor": None,
                "model": None,
                "profile": None,
                "provider": None,
                "capabilities": {},
                "model_verified": False,
                "host": None,
                "attendant": None,
                "session_revision": None,
                "writes_enabled": False,
            }

        service = self._session.service
        self._session.capabilities = (
            service.capabilities
            if self._session.vendor == "huawei"
            else self._session.capabilities
        )
        data = self._session.public()
        data["connected"] = bool(service.connected)
        data["writes_enabled"] = bool(
            getattr(service, "writes_enabled", False)
            if self._session.vendor == "huawei"
            else getattr(
                self._zte_service._zte,
                "writes_enabled",
                False,
            )
        )
        return data

    def capability_catalog(self):
        return self.active_service.capability_catalog()

    def probe_capabilities(self, features=None):
        return self.active_service.probe_capabilities(features)

    def capability_shape(self, feature, *, refresh=False):
        if self.vendor == "huawei":
            return self.active_service.capability_shape(
                feature,
                refresh=refresh,
            )
        return self.active_service.capability_shape(feature)

    def read_capability(self, feature, *, refresh=False):
        if self.vendor == "huawei":
            return self.active_service.read_capability(
                feature,
                refresh=refresh,
            )
        return self.active_service.read_capability(feature)

    def _require_huawei(self) -> HuaweiService:
        if (
            self._session is None
            or self._session.vendor != "huawei"
            or not isinstance(
                self._session.service,
                HuaweiService,
            )
        ):
            raise RuntimeError(
                "A sessão atual não pertence a uma ONT Huawei."
            )
        return self._session.service

    def list_ipv4_filters(self, *, refresh=False):
        result = self._require_huawei().list_ipv4_filters(
            refresh=refresh
        )
        # Do not erase DHCP/DNS/Wi-Fi/etc. capabilities merely because the
        # IPv4 filter panel refreshed. The previous replacement caused the
        # Huawei sidebar/discovery state to collapse to one feature.
        self._session.capabilities = {
            **(self._session.capabilities or {}),
            "ipv4_filter": dict(
                result.get("capability") or {}
            ),
        }
        return result

    def create_ipv4_filter(self, config):
        return self._require_huawei().create_ipv4_filter(config)

    def update_ipv4_filter(
        self,
        instance_or_domain,
        config,
    ):
        return self._require_huawei().update_ipv4_filter(
            instance_or_domain,
            config,
        )

    def delete_ipv4_filter(self, instance_or_domain):
        return self._require_huawei().delete_ipv4_filter(
            instance_or_domain
        )

    def huawei_session_snapshot(self):
        return self._require_huawei().session_snapshot()

    def warm_huawei_session_snapshot(self, *, refresh=False):
        return self._require_huawei().warm_session_snapshot(
            refresh=refresh
        )

    def generate_attendance(self, diagnostic_id=None):
        return self.active_service.generate_attendance(
            diagnostic_id
        )

    def capture_snapshot(self, reason="manual"):
        return self.active_service.capture_snapshot(reason)

    def history(self, limit=50):
        return self.active_service.history(limit)


device_service = DeviceService()

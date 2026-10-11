from __future__ import annotations

import logging
from typing import Any

from apps.zte_manager.infrastructure.huawei.affinity_client import (
    HuaweiAffinityNegotiatingWebClient,
)
from apps.zte_manager.model.session import DeviceSession
from apps.zte_manager.services.error_policy import ProviderFeatureUnavailable
from apps.zte_manager.services.huawei_affinity_provider import (
    HuaweiAffinityUnifiedProvider,
)
from apps.zte_manager.services.provider_router import ProviderRouter
from apps.zte_manager.services.zte_service import ZTEService, zte_service

logger = logging.getLogger(__name__)


class DeviceService:
    """Provider-neutral runtime dispatcher.

    Vendor detection and provider selection live in :class:`ProviderRouter`.
    This class owns only active-session orchestration and the compatibility
    facade consumed by the current API while workspaces are migrated.
    """

    def __init__(
        self,
        *,
        zte_provider: ZTEService | None = None,
        huawei_factory=HuaweiAffinityUnifiedProvider,
        huawei_client_type=HuaweiAffinityNegotiatingWebClient,
        provider_router: ProviderRouter | None = None,
    ) -> None:
        # Compatibility aliases are intentionally retained because existing
        # production-transport regressions assert these defaults explicitly.
        self._huawei_factory = huawei_factory
        self._huawei_client_type = huawei_client_type
        self._provider_router = provider_router or ProviderRouter(
            zte_provider=zte_provider or zte_service,
            huawei_factory=huawei_factory,
            huawei_client_type=huawei_client_type,
        )
        self._zte_service = self._provider_router.zte_provider
        self._session: DeviceSession | None = None

    def __getattr__(self, name: str):
        """Delegate public provider surface to the active service.

        Missing methods/attributes are an explicit capability gap. An active
        non-ZTE session can never fall through to the ZTE provider.
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
            and self._session.service is not None
            and self._session.service.connected
        )

    @property
    def active_service(self):
        if self._session is not None and self._session.service is not None:
            return self._session.service
        # Before /connect, the historical ZTE provider remains the default
        # object so legacy tests/local callers keep their normal session error.
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
        connection = self._provider_router.connect(
            current_session=self._session,
            ip=ip,
            username=username,
            password=password,
            https=https,
            attendant=attendant,
            model_hint=model_hint,
            huawei_cli=huawei_cli,
        )

        result = connection.result
        result["provider"] = connection.provider_name

        if getattr(connection.service, "connected", False):
            self._session = DeviceSession.from_connection(
                vendor=connection.vendor,
                provider=connection.provider_name,
                service=connection.service,
                result=result,
            )
        else:
            self._session = None

        logger.info(
            "device_provider_selected vendor=%s provider=%s profile=%s mode=%s",
            connection.vendor,
            connection.provider_name,
            (
                self._session.profile
                if self._session is not None
                else None
            ),
            (
                self._session.mode
                if self._session is not None
                else None
            ),
        )
        return result

    @staticmethod
    def _should_probe_vendor(host: str) -> bool:
        """Compatibility alias; routing policy itself lives in ProviderRouter."""

        return ProviderRouter._should_probe_vendor(host)

    def disconnect(self) -> None:
        if self._session is not None:
            service = self._session.service
            if service is not None:
                service.disconnect()
            self._session = None
            return
        if self._zte_service.connected:
            self._zte_service.disconnect()

    def status(self) -> dict:
        if self._session is None:
            if self._zte_service.connected:
                verified = bool(self._zte_service._model_verified)
                return {
                    "connected": True,
                    "vendor": "zte",
                    "model": self._zte_service._selected_model,
                    "firmware": None,
                    "hardware": None,
                    "protocol_family": None,
                    "profile": (
                        self._zte_service._adapter.name
                        if self._zte_service._adapter
                        else None
                    ),
                    "provider": type(self._zte_service).__name__,
                    "capabilities": {},
                    "device_id": None,
                    "mode": "supported" if verified else "partial",
                    "model_verified": verified,
                    "host": self._zte_service.current_host,
                    "attendant": self._zte_service.current_attendant,
                    "session_revision": self._zte_service._session_revision,
                    "writes_enabled": self._provider_router.writes_enabled(
                        "zte",
                        self._zte_service,
                    ),
                }
            return {
                "connected": False,
                "vendor": None,
                "model": None,
                "firmware": None,
                "hardware": None,
                "protocol_family": None,
                "profile": None,
                "provider": None,
                "capabilities": {},
                "device_id": None,
                "mode": None,
                "model_verified": False,
                "host": None,
                "attendant": None,
                "session_revision": None,
                "writes_enabled": False,
            }

        service = self._session.service
        self._session.capabilities = self._provider_router.capabilities(
            service,
            self._session.capabilities,
        )
        data = self._session.public()
        data["connected"] = bool(getattr(service, "connected", False))
        data["writes_enabled"] = self._provider_router.writes_enabled(
            self._session.vendor,
            service,
        )
        return data

    def capability_catalog(self):
        return self._provider_router.invoke(
            self.active_service,
            "capability_catalog",
        )

    def probe_capabilities(self, features=None):
        return self._provider_router.invoke(
            self.active_service,
            "probe_capabilities",
            features,
        )

    def capability_shape(self, feature, *, refresh=False):
        return self._provider_router.invoke(
            self.active_service,
            "capability_shape",
            feature,
            refresh=refresh,
        )

    def read_capability(self, feature, *, refresh=False):
        return self._provider_router.invoke(
            self.active_service,
            "read_capability",
            feature,
            refresh=refresh,
        )

    def discovery_bootstrap(self):
        return self._provider_router.discovery_bootstrap(
            self.status(),
            self.active_service,
        )

    def multimodel_catalog(self):
        return self._provider_router.multimodel_catalog(
            self.status(),
            self.active_service,
        )

    def multimodel_diagnostic(self, requested=None, section=None):
        return self._provider_router.multimodel_diagnostic(
            self.status(),
            self.active_service,
            requested,
            section,
        )

    def multimodel_mesh(self, model=None):
        return self._provider_router.multimodel_mesh(
            self.status(),
            self.active_service,
            model,
        )

    def multimodel_probe(self, model=None, count=4, start=0):
        return self._provider_router.multimodel_probe(
            self.status(),
            self.active_service,
            model,
            count,
            start,
        )

    def _require_huawei(self) -> Any:
        """Compatibility helper for Huawei-only routes during migration.

        Selection is capability/surface based rather than another vendor
        routing decision. These routes will move under the Huawei workspace in
        the next migration phase.
        """

        service = self.active_service
        required = (
            "list_ipv4_filters",
            "create_ipv4_filter",
            "update_ipv4_filter",
            "delete_ipv4_filter",
        )
        if not all(hasattr(service, name) for name in required):
            raise RuntimeError(
                "A sessão atual não expõe o gerenciamento IPv4 Filter da Huawei."
            )
        return service

    def list_ipv4_filters(self, *, refresh=False):
        result = self._require_huawei().list_ipv4_filters(
            refresh=refresh
        )
        if self._session is not None:
            # Do not erase DHCP/DNS/Wi-Fi/etc. capabilities merely because the
            # IPv4 filter panel refreshed.
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
        return self._provider_router.invoke(
            self.active_service,
            "session_snapshot",
        )

    def warm_huawei_session_snapshot(self, *, refresh=False):
        return self._provider_router.invoke(
            self.active_service,
            "warm_session_snapshot",
            refresh=refresh,
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

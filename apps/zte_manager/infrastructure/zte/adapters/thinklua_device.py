"""Authenticated ZTE driver: single-session adapter behind the neutral Protocol.

ZTEService attaches its *existing* authenticated ZTE instance; attaching
NEVER creates a second HTTP session or invokes login/logout. Standalone
authenticate() remains available to future connection coordinators.
"""
from __future__ import annotations

import logging
from collections.abc import Callable, Mapping
from threading import RLock
from typing import Any
from uuid import uuid4

from apps.zte_manager.application.contracts.device import (
    Credentials, DeviceInfo, SessionContext,
)
from apps.zte_manager.infrastructure.zte.firmware_policy import FirmwarePolicy

logger = logging.getLogger(__name__)

_WIFI_PROOF_FIELDS = frozenset({
    "ssid", "ativo", "oculto", "broadcast",
    "max_clientes", "isolamento", "seguranca",
})


class DeviceNotAuthenticated(RuntimeError):
    """No usable authenticated transport is attached."""


class DeviceWriteNotApproved(PermissionError):
    """The exact hardware/firmware combination is not approved for writing."""


def _matches(actual: Mapping[str, Any], expected: Mapping[str, Any]) -> bool:
    if not expected:
        return False
    for key, value in expected.items():
        if key not in actual:
            return False
        if isinstance(value, Mapping):
            if not isinstance(actual[key], Mapping) or not _matches(actual[key], value):
                return False
        elif actual[key] != value:
            return False
    return True


def _identity(raw: Mapping[str, Any]) -> DeviceInfo:
    return DeviceInfo(
        manufacturer=raw.get("fabricante"),
        model=raw.get("modelo"),
        firmware=raw.get("firmware"),
        serial=raw.get("serial"),
    )


class ThinkLuaDeviceAdapter:
    """Driver for the legacy ThinkLua transport, not Vue/F6201B captured writes.

    FirmwarePolicy is an explicit reviewed version allowlist + operator approval,
    *not* a technician-role permission system.
    """

    def __init__(
        self,
        client_factory: Callable[..., Any] | None = None,
        *,
        firmware_policy: FirmwarePolicy | None = None,
    ) -> None:
        if client_factory is None:
            from apps.zte_manager.model.zte import ZTE
            client_factory = ZTE
        self._factory = client_factory
        self._policy = (
            firmware_policy if firmware_policy is not None
            else FirmwarePolicy.from_environment()
        )
        self._lock = RLock()
        self._client: Any | None = None
        self._context: SessionContext | None = None
        self._identity: DeviceInfo | None = None
        self._owns_client = False

    @property
    def session_context(self) -> SessionContext | None:
        return self._context

    def attach_authenticated(
        self, client: Any, *, host: str, device_info: Mapping[str, Any],
        revision: str | None = None, owns_client: bool = False,
    ) -> SessionContext:
        """Bind an ALREADY authenticated session; no extra login/GET/POST.

        ZTEService owns its transport. Driver.close() must not close that
        transport behind ZTEService's back.
        """
        if not isinstance(device_info, Mapping):
            raise TypeError("Identidade inválida do equipamento.")
        with self._lock:
            if self._client is not client:
                self.close()
            info = _identity(device_info)
            writable = self._policy.permits(
                info.manufacturer, info.model, info.firmware
            )
            self._client = client
            self._identity = info
            self._owns_client = owns_client
            self._context = SessionContext(
                id=revision or uuid4().hex,
                host=host,
                model=info.model,
                firmware=info.firmware,
                writable=writable,
            )
            return self._context

    def authenticate(self, credentials: Credentials) -> SessionContext:
        if not credentials.host.strip() or not credentials.username.strip():
            raise ValueError("Informe o host e o usuário do equipamento.")
        with self._lock:
            self.close()
            client = self._factory(
                ip=credentials.host, username=credentials.username,
                password=credentials.password, https=credentials.https,
            )
            try:
                if not client.login():
                    raise DeviceNotAuthenticated("Autenticação negada.")
            except Exception as exc:
                try:
                    client.session.close()
                except Exception:
                    logger.warning("zte_auth_local_close_failed")
                logger.warning("zte_auth_failed error_type=%s", type(exc).__name__)
                raise DeviceNotAuthenticated(
                    "Falha ao autenticar no equipamento."
                ) from None

            try:
                raw = client.device_status() or {}
                if not isinstance(raw, Mapping):
                    raw = {}
            except Exception as exc:
                logger.warning(
                    "zte_identity_read_failed error_type=%s", type(exc).__name__
                )
                raw = {}
            return self.attach_authenticated(
                client, host=credentials.host, device_info=raw,
                owns_client=True,
            )

    def _require(self) -> Any:
        if self._client is None or self._context is None:
            raise DeviceNotAuthenticated("Nenhum equipamento autenticado.")
        return self._client

    def _matches_bound_identity(self, current: Mapping[str, Any]) -> bool:
        bound = self._identity
        if bound is None or not bound.model or not bound.firmware:
            return False
        return (
            current.get("modelo") == bound.model
            and current.get("firmware") == bound.firmware
            and (not bound.serial or current.get("serial") == bound.serial)
            and (
                not bound.manufacturer
                or current.get("fabricante") == bound.manufacturer
            )
        )

    def assert_session_identity(self) -> None:
        """Safe GET preflight; call before preparing a ThinkLua write form."""
        with self._lock:
            client = self._require()
            if self._context is None or not self._context.writable:
                raise DeviceWriteNotApproved(
                    "Modelo/firmware sem aprovação explícita de escrita."
                )
            try:
                current = client.device_status() or {}
            except Exception as exc:
                logger.warning(
                    "zte_prewrite_identity_failed error_type=%s",
                    type(exc).__name__,
                )
                raise DeviceWriteNotApproved(
                    "Identidade indisponível; escrita bloqueada."
                ) from None
            if not isinstance(current, Mapping) or not self._matches_bound_identity(current):
                raise DeviceWriteNotApproved(
                    "A identidade ou o firmware mudou; reconecte."
                )
            if not self._policy.permits(
                current.get("fabricante"), current.get("modelo"),
                current.get("firmware"),
            ):
                raise DeviceWriteNotApproved(
                    "Firmware sem aprovação para escrita."
                )
            if getattr(client, "writes_enabled", True) is False:
                raise DeviceWriteNotApproved("Sessão de descoberta somente leitura.")

    def _assert_write(self) -> Any:
        self.assert_session_identity()
        return self._require()

    def read_device_status(self) -> dict[str, Any]:
        """Preserve legacy JSON shape (uptime/CPU/etc.) for existing routes."""
        with self._lock:
            result = self._require().device_status() or {}
            if not isinstance(result, dict):
                raise ValueError("Resposta de identidade inválida.")
            return result

    def read_info(self) -> DeviceInfo:
        return _identity(self.read_device_status())

    def get_lan_config(self) -> Mapping[str, Any]:
        """LAN feature implemented in this driver is DHCP, not LAN IP changes."""
        with self._lock:
            return self._require().dhcp_status()

    def set_lan_config(self, config: Mapping[str, Any]) -> Any:
        with self._lock:
            return self._assert_write().set_dhcp_basic(dict(config))

    def get_wifi_config(self) -> Mapping[str, Any]:
        with self._lock:
            return {"networks": self._require().wifi_networks(reveal_password=False)}

    def set_wifi_config(self, config: Mapping[str, Any]) -> Any:
        ssid_id = config.get("ssid_id")
        changes = config.get("changes")
        if not isinstance(ssid_id, str) or not ssid_id or not isinstance(changes, Mapping):
            raise ValueError("Informe ssid_id e changes para alterar o SSID.")
        with self._lock:
            return self._assert_write().set_ssid_config(ssid_id, dict(changes))

    def verify_change(
        self, operation: str, expected_state: Mapping[str, Any]
    ) -> bool:
        if not isinstance(expected_state, Mapping):
            return False
        try:
            with self._lock:
                client = self._require()
                if self._context is None or not self._context.writable:
                    return False
                current = client.device_status() or {}
                if not isinstance(current, Mapping) or not self._matches_bound_identity(current):
                    return False
                if not self._policy.permits(
                    current.get("fabricante"), current.get("modelo"),
                    current.get("firmware"),
                ):
                    return False

                if operation == "lan.dhcp":
                    allowed = frozenset({"basic", "lan_dns"})
                    if not expected_state or not set(expected_state).issubset(allowed):
                        return False
                    return _matches(client.dhcp_status(), expected_state)

                if operation == "wifi.ssid":
                    ssid_id = expected_state.get("id")
                    proof = {key: value for key, value in expected_state.items() if key != "id"}
                    if not isinstance(ssid_id, str) or not ssid_id:
                        return False
                    if not proof or not set(proof).issubset(_WIFI_PROOF_FIELDS):
                        # Never compare a password to a masked network read.
                        return False
                    networks = client.wifi_networks(reveal_password=False)
                    item = next(
                        (entry for entry in networks
                         if isinstance(entry, Mapping) and entry.get("id") == ssid_id),
                        None,
                    )
                    return isinstance(item, Mapping) and _matches(item, proof)
                return False
        except Exception as exc:
            logger.warning(
                "zte_verify_failed error_type=%s", type(exc).__name__
            )
            return False

    def close(self) -> None:
        with self._lock:
            client = self._client
            owns_client = self._owns_client
            self._client = None
            self._context = None
            self._identity = None
            self._owns_client = False
            if client is not None and owns_client:
                try:
                    client.session.close()
                except Exception as exc:
                    logger.warning(
                        "zte_local_close_failed error_type=%s",
                        type(exc).__name__,
                    )

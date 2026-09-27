"""Authenticated ZTE ThinkLua runtime driver implementing vendor-neutral protocol.

No route imports this class yet. ZTEService remains the backward-compatible
facade until connection coordination is extracted in Phase 2.
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
from apps.zte_manager.model.device_adapters import (
    F6600PAdapter, F670LAdapter, select_adapter,
)

logger = logging.getLogger(__name__)

_WIFI_PROOF_FIELDS = frozenset({
    "ssid", "ativo", "oculto", "broadcast",
    "max_clientes", "isolamento", "seguranca",
})


class DeviceNotAuthenticated(RuntimeError):
    pass


class DeviceWriteNotApproved(PermissionError):
    pass


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


class ThinkLuaDeviceAdapter:
    """One local HTTP session per driver; writes only on identified legacy families.

    Firmware/model-specific forms live in the existing zte_configuration
    gateway. Unknown models are usable for inspection but never auto-approved
    for writing after a successful read-only probe.
    """

    def __init__(self, client_factory: Callable[..., Any] | None = None) -> None:
        if client_factory is None:
            from apps.zte_manager.model.zte import ZTE
            client_factory = ZTE
        self._factory = client_factory
        self._lock = RLock()
        self._client: Any | None = None
        self._context: SessionContext | None = None
        self._identity: DeviceInfo | None = None

    def authenticate(self, credentials: Credentials) -> SessionContext:
        if not credentials.host.strip() or not credentials.username.strip():
            raise ValueError("Informe o host e o usuário do equipamento.")
        with self._lock:
            self.close()  # Local close only: never disconnect another admin remotely.
            client = self._factory(
                ip=credentials.host, username=credentials.username,
                password=credentials.password, https=credentials.https,
            )
            try:
                if not client.login():
                    raise DeviceNotAuthenticated("A autenticação na ONT falhou.")
            except Exception as exc:
                try:
                    client.session.close()
                except Exception:
                    pass
                logger.warning("zte_auth_failed error_type=%s", type(exc).__name__)
                raise DeviceNotAuthenticated("Falha ao autenticar no equipamento.") from None

            try:
                raw = client.device_status() or {}
                if not isinstance(raw, Mapping):
                    raw = {}
            except Exception as exc:
                logger.warning("zte_identity_read_failed error_type=%s", type(exc).__name__)
                raw = {}

            info = DeviceInfo(
                manufacturer=raw.get("fabricante"), model=raw.get("modelo"),
                firmware=raw.get("firmware"), serial=raw.get("serial"),
            )
            catalog = select_adapter(info.model, info.firmware)
            writable = bool(info.model) and isinstance(
                catalog, (F6600PAdapter, F670LAdapter),
            )
            self._client = client
            self._identity = info
            self._context = SessionContext(
                id=uuid4().hex, host=credentials.host, model=info.model,
                firmware=info.firmware, writable=writable,
            )
            return self._context

    def _require(self) -> Any:
        if self._client is None or self._context is None:
            raise DeviceNotAuthenticated("Nenhum equipamento autenticado.")
        return self._client

    def _assert_write(self) -> Any:
        client = self._require()
        if self._context is None or not self._context.writable:
            raise DeviceWriteNotApproved(
                "Firmware/modelo sem adaptador de escrita homologado."
            )
        # An old VPN/port forward can point to another device mid-session.
        try:
            current = client.device_status() or {}
        except Exception as exc:
            logger.warning("zte_prewrite_identity_failed error_type=%s", type(exc).__name__)
            raise DeviceWriteNotApproved("Identidade indisponível; escrita bloqueada.") from None
        if (
            current.get("modelo") != self._identity.model
            or (
                self._identity.serial
                and current.get("serial") != self._identity.serial
            )
        ):
            raise DeviceWriteNotApproved("A identidade da ONT mudou; reconecte.")
        return client

    def read_info(self) -> DeviceInfo:
        with self._lock:
            current = self._require().device_status() or {}
            return DeviceInfo(
                manufacturer=current.get("fabricante"),
                model=current.get("modelo"),
                firmware=current.get("firmware"),
                serial=current.get("serial"),
            )

    def get_lan_config(self) -> Mapping[str, Any]:
        """Phase-1 supported LAN feature is DHCP, not the LAN gateway address."""
        with self._lock:
            return self._require().dhcp_status()

    def set_lan_config(self, config: Mapping[str, Any]) -> Any:
        with self._lock:
            return self._assert_write().set_dhcp_basic(dict(config))

    def get_wifi_config(self) -> Mapping[str, Any]:
        with self._lock:
            return {"networks": self._require().wifi_networks(reveal_password=False)}

    def set_wifi_config(self, config: Mapping[str, Any]) -> Any:
        ssid_id, changes = config.get("ssid_id"), config.get("changes")
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
                # Read the identity as well as the data so a switched VPN
                # cannot let another ONT accidentally satisfy a comparison.
                current = client.device_status() or {}
                if (
                    self._identity is None
                    or not self._identity.model
                    or current.get("modelo") != self._identity.model
                    or (self._identity.serial and current.get("serial") != self._identity.serial)
                ):
                    return False

                if operation == "lan.dhcp":
                    # Explicit nested firmware keys, e.g. basic.ServerEnable.
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
                        # Password cannot be compared to a deliberately masked read.
                        return False
                    networks = client.wifi_networks(reveal_password=False)
                    item = next(
                        (x for x in networks
                         if isinstance(x, Mapping) and x.get("id") == ssid_id),
                        None,
                    )
                    return isinstance(item, Mapping) and _matches(item, proof)
                return False
        except Exception as exc:
            logger.warning("zte_verify_failed error_type=%s", type(exc).__name__)
            return False

    def close(self) -> None:
        with self._lock:
            client = self._client
            self._client = None
            self._context = None
            self._identity = None
            if client is not None:
                try:
                    client.session.close()
                except Exception as exc:
                    logger.warning(
                        "zte_local_close_failed error_type=%s", type(exc).__name__,
                    )

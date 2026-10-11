from __future__ import annotations

from copy import deepcopy
from typing import Any

from apps.zte_manager.services.error_policy import NotAuthorized


class DeploymentWriteBlocked(NotAuthorized):
    code = "DEPLOYMENT_READ_ONLY"
    user_message = (
        "Equipamento em modo de homologação: alterações estão bloqueadas até "
        "a capability ser validada."
    )


class DeploymentWorkspace:
    """Strict read-only workspace for equipment not yet homologated."""

    vendor = "deployment"
    _SAFE_EXACT = frozenset({
        "capability_catalog", "probe_capabilities", "capability_shape",
        "read_capability", "device_status", "current_configuration",
        "wan_status", "wifi_networks", "get_radios", "clients",
        "lan_status", "dns_status", "dhcp_status", "optical_telemetry",
        "pon_status", "pon_statistics", "resource_telemetry",
        "session_snapshot", "mapped_catalog", "mapped_read_feature",
        "mapped_read_request", "history", "profiles", "get_profile",
        "multimodel_catalog", "multimodel_probe", "multimodel_diagnostic",
        "multimodel_mesh",
    })
    _SAFE_PREFIXES = ("get_", "list_", "read_", "probe_", "inspect_", "show_")

    def __init__(self, provider: Any, *, vendor_hint: str | None = None) -> None:
        self._provider = provider
        self.vendor_hint = str(vendor_hint or "unknown").casefold()

    @property
    def provider(self) -> Any:
        return self._provider

    @property
    def connected(self) -> bool:
        return bool(getattr(self._provider, "connected", False))

    @property
    def writes_enabled(self) -> bool:
        return False

    @staticmethod
    def _read_only_capabilities(value: dict | None) -> dict:
        result = deepcopy(value or {})
        for spec in result.values():
            if not isinstance(spec, dict):
                continue
            for operation in ("write", "create", "update", "delete", "reboot"):
                if operation in spec:
                    spec[operation] = False
            operations = spec.get("operations")
            if isinstance(operations, dict):
                for operation in ("write", "create", "update", "delete", "reboot"):
                    if operation in operations:
                        operations[operation] = False
            spec["deployment"] = True
        return result

    @property
    def capabilities(self) -> dict:
        return self._read_only_capabilities(
            getattr(self._provider, "capabilities", None)
        )

    def connect(self, *args, **kwargs):
        return self._provider.connect(*args, **kwargs)

    def disconnect(self) -> None:
        self._provider.disconnect()

    def capability_catalog(self):
        catalog = deepcopy(self._provider.capability_catalog())
        features = catalog.get("features") if isinstance(catalog, dict) else None
        if isinstance(features, dict):
            catalog["features"] = self._read_only_capabilities(features)
        return catalog

    def __getattr__(self, name: str):
        if name.startswith("_"):
            raise AttributeError(name)
        target = getattr(self._provider, name)
        if not callable(target):
            return target
        if name in self._SAFE_EXACT or name.startswith(self._SAFE_PREFIXES):
            return target

        def blocked(*args, **kwargs):
            raise DeploymentWriteBlocked()

        return blocked

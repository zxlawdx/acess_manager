from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


VALID_SESSION_MODES = frozenset({"supported", "partial", "deployment"})


@dataclass
class DeviceSession:
    """Provider-neutral description of the active device session.

    ``service`` is an internal compatibility binding used by the current
    runtime while the workspace refactor is migrated incrementally. It is
    deliberately excluded from :meth:`public` and is not part of the API
    contract consumed by the frontend.
    """

    vendor: str
    model: str | None = None
    provider: str | None = None
    capabilities: dict[str, dict[str, Any]] = field(default_factory=dict)
    firmware: str | None = None
    hardware: str | None = None
    protocol_family: str | None = None
    device_id: str | None = None
    host: str | None = None
    attendant: str | None = None
    mode: str = "partial"

    # Transitional/legacy metadata retained while existing routes are migrated.
    profile: str | None = None
    model_verified: bool = False
    session_revision: str | None = None
    service: Any = field(default=None, repr=False, compare=False)

    def __post_init__(self) -> None:
        vendor = str(self.vendor or "unknown").strip().casefold()
        self.vendor = vendor or "unknown"
        if self.mode not in VALID_SESSION_MODES:
            raise ValueError(f"invalid device session mode: {self.mode}")

    @classmethod
    def from_connection(
        cls,
        *,
        vendor: str,
        provider: str,
        service: Any,
        result: dict[str, Any],
    ) -> "DeviceSession":
        """Build a session contract from a provider connection result.

        The small vendor-specific profile mapping lives in this factory on
        purpose. Outside the session factory and ``ProviderRouter``, callers
        should not branch on vendor to decide which provider implementation to
        use.
        """

        normalized_vendor = str(vendor or "unknown").strip().casefold() or "unknown"
        if normalized_vendor == "huawei":
            profile = result.get("profile")
        elif normalized_vendor == "zte":
            profile = result.get("adapter") or result.get("profile")
        else:
            profile = result.get("profile")

        model_verified = bool(result.get("model_verified"))
        mode = result.get("mode")
        if mode not in VALID_SESSION_MODES:
            if normalized_vendor == "unknown":
                mode = "deployment"
            elif model_verified:
                mode = "supported"
            else:
                mode = "partial"

        return cls(
            vendor=normalized_vendor,
            model=result.get("model"),
            provider=provider,
            capabilities={
                key: dict(value)
                for key, value in (result.get("capabilities") or {}).items()
            },
            firmware=result.get("firmware"),
            hardware=result.get("hardware"),
            protocol_family=result.get("protocol_family"),
            device_id=result.get("device_id"),
            host=result.get("host"),
            attendant=result.get("attendant"),
            mode=mode,
            profile=profile,
            model_verified=model_verified,
            session_revision=result.get("session_revision"),
            service=service,
        )

    def public(self) -> dict[str, Any]:
        """Return only the provider-neutral/public session contract."""

        return {
            "vendor": self.vendor,
            "model": self.model,
            "firmware": self.firmware,
            "hardware": self.hardware,
            "protocol_family": self.protocol_family,
            "provider": self.provider,
            "capabilities": {
                key: dict(value)
                for key, value in self.capabilities.items()
            },
            "device_id": self.device_id,
            "host": self.host,
            "attendant": self.attendant,
            "mode": self.mode,
            # Compatibility metadata kept visible during the migration cycle.
            "profile": self.profile,
            "model_verified": self.model_verified,
            "session_revision": self.session_revision,
        }

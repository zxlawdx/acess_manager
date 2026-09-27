"""ThinkLua transport recognition and non-blocking firmware compatibility telemetry.

Recognized F670L/F6600P sessions permit normal operator-initiated writes by
default, regardless of the firmware review catalog. An unsupported protocol,
failed authentication, stale device identity or an actual transport/firmware
error is still handled by the driver's session guards.

Known firmware versions and optional operator approvals are *informational*:
neither this catalog nor its absence is a write-permission gate. Captured
F6201B writes retain their separate exact-firmware/protocol guard.
"""
from __future__ import annotations

import json
import logging
import os
import re
from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)

KNOWN_CANDIDATES: Mapping[str, frozenset[str]] = {
    "F670L": frozenset({"V9.0.11P1N9", "V9.0.11P1N40"}),
    "F6600P": frozenset({"V9.0.10P6N34"}),
}
_MODEL_PATTERN = re.compile(r"(?<![A-Z0-9])(F670L|F6600P)(?![A-Z0-9])")


def canonical_model(value: str | None) -> str | None:
    match = _MODEL_PATTERN.search(str(value or "").strip().upper())
    return match.group(1) if match else None


def canonical_firmware(value: str | None) -> str:
    return str(value or "").strip().upper()


@dataclass(frozen=True, slots=True)
class FirmwarePolicy:
    """Non-blocking firmware notes; protocol recognition drives write support."""

    approved: Mapping[str, frozenset[str]] = field(default_factory=dict)

    @classmethod
    def from_approved(cls, values: Mapping[str, Any]) -> FirmwarePolicy:
        """Record operator-reviewed versions as telemetry, not permissions."""
        approved: dict[str, frozenset[str]] = {}
        for model, revisions in values.items():
            canonical = canonical_model(model)
            if canonical is None or str(model).strip().upper() != canonical:
                raise ValueError("Unknown firmware telemetry model")
            if not isinstance(revisions, (list, tuple, set, frozenset)):
                raise ValueError("Firmware telemetry requires a sequence")
            values_clean = frozenset(
                canonical_firmware(version)
                for version in revisions
                if isinstance(version, str) and canonical_firmware(version)
            )
            if len(values_clean) != len(revisions):
                raise ValueError("Firmware telemetry contains invalid values")
            approved[canonical] = values_clean
        return cls(approved=approved)

    @classmethod
    def from_environment(cls) -> FirmwarePolicy:
        raw = os.environ.get("ZTE_APPROVED_FIRMWARE_JSON")
        if not raw:
            return cls()
        try:
            parsed = json.loads(raw)
            if not isinstance(parsed, dict):
                raise ValueError("Firmware telemetry must be a JSON object")
            return cls.from_approved(parsed)
        except (ValueError, TypeError) as exc:
            logger.warning(
                "firmware_telemetry_manifest_rejected error_type=%s",
                type(exc).__name__,
            )
            return cls()

    def recognition_status(
        self, model: str | None, firmware: str | None,
    ) -> str:
        """Telemetry only: reviewed, known_candidate, unreviewed or unavailable."""
        code = canonical_model(model)
        version = canonical_firmware(firmware)
        if not code or not version:
            return "unavailable"
        if version in self.approved.get(code, frozenset()):
            return "reviewed"
        if version in KNOWN_CANDIDATES.get(code, frozenset()):
            return "known_candidate"
        return "unreviewed"

    def permits(
        self, manufacturer: str | None, model: str | None, firmware: str | None,
    ) -> bool:
        """Recognized ThinkLua transport only; firmware revision is NOT a gate.

        The vendor/model response must come from the authenticated ONT;
        the caller must separately verify session liveness and unchanged
        device identity before sending writes. firmware is accepted here
        to preserve the existing call signature.
        """
        del firmware
        if canonical_model(model) is None:
            return False
        vendor = str(manufacturer or "").strip().upper()
        return not vendor or "ZTE" in vendor or "ZXHN" in vendor

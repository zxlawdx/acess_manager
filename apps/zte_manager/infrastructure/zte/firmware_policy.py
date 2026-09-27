"""Fail-closed, exact-version approvals for the *generic* ThinkLua driver.

These versions occur in the repository's test fixtures / F670L compatibility
notes: they are KNOWN CANDIDATES, not claims of completed physical homologation.
Enable a candidate only after local real-device verification by explicitly
setting ZTE_APPROVED_FIRMWARE_JSON, e.g.
{"F670L": ["V9.0.11P1N9"]}. Unknown variants cannot be enabled with this flag.

F6201B V9.3.10P7N7 retains its separately captured, firmware-gated workflow;
it is NEVER a generic ThinkLua write target.
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
    # No fuzzy matching, prefix matching or implicit "latest" support.
    return str(value or "").strip().upper()


@dataclass(frozen=True, slots=True)
class FirmwarePolicy:
    """Operator-approved subset of the explicitly known candidate versions."""

    approved: Mapping[str, frozenset[str]] = field(default_factory=dict)

    @classmethod
    def from_approved(cls, values: Mapping[str, Any]) -> FirmwarePolicy:
        approved: dict[str, frozenset[str]] = {}
        for model, revisions in values.items():
            canonical = canonical_model(model)
            if canonical is None or str(model).upper().strip() != canonical:
                raise ValueError("Unknown firmware-approval model")
            if not isinstance(revisions, (list, tuple, set, frozenset)):
                raise ValueError("Firmware approvals must be a sequence")
            entries = frozenset(canonical_firmware(version) for version in revisions)
            if not entries.issubset(KNOWN_CANDIDATES[canonical]):
                raise ValueError("Firmware approval not in reviewed candidate catalog")
            approved[canonical] = entries
        return cls(approved=approved)

    @classmethod
    def from_environment(cls) -> FirmwarePolicy:
        raw = os.environ.get("ZTE_APPROVED_FIRMWARE_JSON")
        if not raw:
            return cls()
        try:
            parsed = json.loads(raw)
            if not isinstance(parsed, dict):
                raise ValueError("Approval manifest must be a JSON object")
            return cls.from_approved(parsed)
        except (ValueError, TypeError) as exc:
            logger.warning(
                "firmware_approval_manifest_rejected error_type=%s",
                type(exc).__name__,
            )
            return cls()  # Never silently revert to permissive policy.

    def permits(
        self, manufacturer: str | None, model: str | None, firmware: str | None,
    ) -> bool:
        code = canonical_model(model)
        version = canonical_firmware(firmware)
        if not code or not version:
            return False
        if manufacturer and "ZTE" not in manufacturer.strip().upper():
            return False
        return (
            version in KNOWN_CANDIDATES.get(code, frozenset())
            and version in self.approved.get(code, frozenset())
        )

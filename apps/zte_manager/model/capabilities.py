from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class EvidenceLevel(str, Enum):
    RESEARCH_ONLY = "RESEARCH_ONLY"
    FIXTURE_VALIDATED = "FIXTURE_VALIDATED"
    TESTED_AUTOMATICALLY = "TESTED_AUTOMATICALLY"
    PHYSICALLY_VALIDATED = "PHYSICALLY_VALIDATED"
    UNSUPPORTED = "UNSUPPORTED"
    FAILED = "FAILED"
    UNKNOWN = "UNKNOWN"


class CapabilityOperation(str, Enum):
    READ = "READ"
    WRITE = "WRITE"
    CREATE = "CREATE"
    UPDATE = "UPDATE"
    DELETE = "DELETE"
    REBOOT = "REBOOT"


EVIDENCE_BADGES: dict[EvidenceLevel, str] = {
    EvidenceLevel.RESEARCH_ONLY: "DETECTADO",
    EvidenceLevel.FIXTURE_VALIDATED: "EM TESTE",
    EvidenceLevel.TESTED_AUTOMATICALLY: "CONFIRMADO",
    EvidenceLevel.PHYSICALLY_VALIDATED: "CONFIRMADO (físico)",
    EvidenceLevel.UNSUPPORTED: "NÃO SUPORTADO",
    EvidenceLevel.FAILED: "FALHOU",
    EvidenceLevel.UNKNOWN: "DESCONHECIDO",
}


@dataclass(frozen=True)
class CapabilityEvidence:
    """Evidence is tracked per operation, never inferred from an endpoint alone."""

    feature: str
    operations: dict[CapabilityOperation, EvidenceLevel] = field(default_factory=dict)
    details: dict[str, Any] = field(default_factory=dict)

    def level_for(self, operation: CapabilityOperation | str) -> EvidenceLevel:
        operation = CapabilityOperation(operation)
        return self.operations.get(operation, EvidenceLevel.UNKNOWN)

    def as_dict(self) -> dict[str, Any]:
        return {
            "feature": self.feature,
            "operations": {
                operation.value: level.value
                for operation, level in self.operations.items()
            },
            "details": dict(self.details),
        }


def evidence_badge(level: EvidenceLevel | str) -> str:
    return EVIDENCE_BADGES[EvidenceLevel(level)]

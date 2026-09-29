"""Hardware-independent execution/audit boundary.

HTTP 200 or an action returning without exception means *at most* accepted.
Only a caller-provided verifier of a successful post-read proves 'verified'.
Public return values and existing API endpoints remain unchanged in ZTEService.
"""
from __future__ import annotations

import logging
import re
from collections.abc import Callable
from dataclasses import dataclass
from enum import Enum
from typing import Any, Protocol

from apps.zte_manager.application.operations.redaction import redact_sensitive

logger = logging.getLogger(__name__)


class ChangeOutcome(str, Enum):
    ATTEMPTED = "attempted"
    ACCEPTED = "accepted"
    VERIFIED = "verified"
    UNCERTAIN = "uncertain"
    FAILED = "failed"


class ChangeHistory(Protocol):
    def save_change(
        self, session_id: int | None, *, operation: str, target: str | None,
        before: Any, after: Any, success: bool, message: str | None = None,
        outcome: str | None = None,
    ) -> int: ...


Verifier = Callable[[Any, Any, Any], bool]


@dataclass(frozen=True, slots=True)
class AuditResult:
    value: Any
    outcome: ChangeOutcome


def _safe_code(value: str) -> str:
    return re.sub(r"[^a-zA-Z0-9_.-]", "_", value)[:64]


def _capture(reader: Callable[[], Any]) -> tuple[bool, Any]:
    try:
        value = reader()
        if value is None or (
            isinstance(value, dict) and value.get("_error") is not None
        ):
            return False, None
        return True, value
    except Exception as exc:
        # Never log exception messages: firmware errors can include credentials.
        logger.warning("change_read_failed error_type=%s", type(exc).__name__)
        return False, None


def _rejected(value: Any) -> bool:
    if value is False:
        return True
    return isinstance(value, dict) and value.get("success") is False


class AuditedOperation:
    """Use under ZTEService's existing RLock to preserve ThinkLua view context."""

    def __init__(self, history: ChangeHistory) -> None:
        self._history = history

    def _record(
        self, *, session_id: int | None, operation: str, target: str | None,
        before: Any, after: Any, outcome: ChangeOutcome,
        message: str | None = None,
    ) -> None:
        try:
            self._history.save_change(
                session_id, operation=operation, target=target,
                before=redact_sensitive(before),
                after=redact_sensitive(after),
                success=outcome is ChangeOutcome.VERIFIED,
                outcome=outcome.value,
                message=message,
            )
        except Exception as exc:
            # Auditing storage must not turn an accepted hardware operation
            # into a failed POST or shadow the original action exception.
            logger.error(
                "change_audit_storage_failed operation=%s error_type=%s",
                _safe_code(operation), type(exc).__name__,
            )

    def execute(
        self, *, session_id: int | None, operation: str, target: str | None,
        before_reader: Callable[[], Any], action: Callable[[], Any],
        after_reader: Callable[[], Any],
        verify: Verifier | None = None,
    ) -> AuditResult:
        before_ok, before = _capture(before_reader)
        try:
            value = action()
        except Exception as exc:
            self._record(
                session_id=session_id, operation=operation, target=target,
                before=before if before_ok else None, after=None,
                outcome=ChangeOutcome.FAILED,
                message="action_failed:" + _safe_code(type(exc).__name__),
            )
            logger.warning(
                "change_action_failed operation=%s error_type=%s",
                _safe_code(operation), type(exc).__name__,
            )
            raise

        if _rejected(value):
            outcome = ChangeOutcome.FAILED
            self._record(
                session_id=session_id, operation=operation, target=target,
                before=before if before_ok else None, after=None,
                outcome=outcome, message="action_rejected",
            )
            return AuditResult(value=value, outcome=outcome)

        after_ok, after = _capture(after_reader)
        if not after_ok:
            outcome = ChangeOutcome.UNCERTAIN
        elif isinstance(value, dict) and value.get("uncertain") is True:
            outcome = ChangeOutcome.UNCERTAIN
        elif verify is None:
            outcome = ChangeOutcome.ACCEPTED
        elif not before_ok:
            outcome = ChangeOutcome.UNCERTAIN
        else:
            try:
                confirmed = verify(before, value, after)
                # Require the literal True, not a truthy dict/string.
                outcome = (
                    ChangeOutcome.VERIFIED
                    if confirmed is True else ChangeOutcome.UNCERTAIN
                )
            except Exception as exc:
                outcome = ChangeOutcome.UNCERTAIN
                logger.warning(
                    "change_verification_failed operation=%s error_type=%s",
                    _safe_code(operation), type(exc).__name__,
                )

        # Preserve the actual stages of the saved default profile for the
        # attendance report. Store *only fixed stage names and booleans*, not
        # POST payloads, credentials or raw firmware response text.
        history_after = after if after_ok else None
        if operation == "profile_apply" and isinstance(value, dict):
            public_steps = []
            permitted = {
                "Wi-Fi 2.4GHz": "Wi-Fi 2,4 GHz",
                "Wi-Fi 5GHz": "Wi-Fi 5 GHz",
                "DNS": "Servidores DNS",
            }
            for step in value.get("steps", []):
                if not isinstance(step, dict) or step.get("name") not in permitted:
                    continue
                public_steps.append({
                    "name": permitted[step["name"]],
                    "accepted": step.get("success") is True,
                })
            if public_steps:
                history_after = (
                    {**history_after, "_profile_steps": public_steps}
                    if isinstance(history_after, dict)
                    else {"_profile_steps": public_steps}
                )
        self._record(
            session_id=session_id, operation=operation, target=target,
            before=before if before_ok else None,
            after=history_after,
            outcome=outcome,
            message=None if outcome is ChangeOutcome.VERIFIED else "outcome:" + outcome.value,
        )
        return AuditResult(value=value, outcome=outcome)

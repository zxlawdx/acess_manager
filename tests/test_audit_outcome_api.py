"""Regression: the UI must receive the audit outcome, not HTTP success alone.

No physical router is used. The service's audit boundary is exercised with
synthetic responses, and the saved history status is asserted explicitly.
"""
from __future__ import annotations

import unittest
from unittest.mock import Mock, patch

from apps.zte_manager.application.operations.audit_executor import (
    AuditResult, ChangeOutcome
)
from apps.zte_manager.services.zte_service import ZTEService


class AuditOutcomeApiTests(unittest.TestCase):
    def test_run_change_preserves_legacy_response_and_adds_audit_outcome(self):
        service = ZTEService.__new__(ZTEService)
        service._runtime_driver = None
        service._history_session_id = 1
        service._audited_operation = Mock(
            execute=Mock(return_value=AuditResult(
                value={"success": True, "verified": False},
                outcome=ChangeOutcome.ACCEPTED,
            ))
        )
        with patch.object(service, "_is_captured_f6201b", return_value=False):
            result = service._run_change(
                operation="test", target="LAN",
                before_reader=lambda: {},
                action=lambda: {"success": True},
                after_reader=lambda: {},
            )
        self.assertTrue(result["success"])
        self.assertFalse(result["verified"])
        self.assertEqual(result["audit_outcome"], "accepted")

    def test_direct_device_write_does_not_record_accepted_as_verified(self):
        service = ZTEService.__new__(ZTEService)
        service._history_session_id = 1
        with patch(
            "apps.zte_manager.services.zte_service.history_repository.save_change"
        ) as save:
            result = service._audit_device_command(
                "wifi", "SSID", lambda: {"success": True, "verified": False}
            )
        self.assertEqual(result["audit_outcome"], "accepted")
        self.assertEqual(save.call_args.kwargs["outcome"], "accepted")
        self.assertIs(save.call_args.kwargs["success"], False)

    def test_confirmed_direct_write_is_recorded_only_when_verified(self):
        service = ZTEService.__new__(ZTEService)
        service._history_session_id = 1
        with patch(
            "apps.zte_manager.services.zte_service.history_repository.save_change"
        ) as save:
            result = service._audit_device_command(
                "wifi", "SSID", lambda: {"success": True, "verified": True}
            )
        self.assertEqual(result["audit_outcome"], "verified")
        self.assertEqual(save.call_args.kwargs["outcome"], "verified")
        self.assertIs(save.call_args.kwargs["success"], True)

    def test_uncertain_direct_write_must_not_claim_verified(self):
        service = ZTEService.__new__(ZTEService)
        service._history_session_id = 1
        with patch(
            "apps.zte_manager.services.zte_service.history_repository.save_change"
        ) as save:
            result = service._audit_device_command(
                "dns", "DNS", lambda: {
                    "success": True, "verified": False, "partial": True
                }
            )
        self.assertEqual(result["audit_outcome"], "uncertain")
        self.assertEqual(save.call_args.kwargs["outcome"], "uncertain")
        self.assertIs(save.call_args.kwargs["success"], False)


if __name__ == "__main__":
    unittest.main()

"""Complete session-based attendance from cross-page actions (synthetic)."""
import unittest
from unittest.mock import patch

from apps.zte_manager.services.attendance_report_service import (
    AttendanceReportService,
)
from apps.zte_manager.services.zte_service import ZTEService


class CompleteAttendanceTests(unittest.TestCase):
    def test_report_includes_all_chronological_session_events(self):
        report = AttendanceReportService().build(
            diagnostic={
                "mode": "general", "status": "warning",
                "source": "backend_authenticated_ont",
                "model": "F6201B", "firmware": "V9.3.10P7N7",
                "firmware_readings": {"wan": {"available": True}},
                "errors": {"traceroute": "unsupported"},
            },
            timeline={
                "changes": [
                    {"id": 2, "created_at": "2026-09-25T12:00:03+00:00",
                     "success": 1, "operation": "f6201b_ssid_update",
                     "target": "SSID", "before_json": None,
                     "after_json": {"verified": True,
                                    "password": "SENSITIVE_DO_NOT_PRINT"}},
                    {"id": 3, "created_at": "2026-09-25T12:00:06+00:00",
                     "success": 0, "operation": "f6201b_form_update",
                     "target": "WAN", "before_json": None, "after_json": None},
                ],
                "diagnostics": [
                    {"id": 1, "created_at": "2026-09-25T12:00:01+00:00",
                     "payload_json": {"mode": "general", "status": "ok"}},
                    {"id": 2, "created_at": "2026-09-25T12:00:07+00:00",
                     "payload_json": {
                         "source": "backend_authenticated_ont",
                         "firmware_readings": {"wan": {"available": True}},
                         "performed": [
                             {"operation": "ping", "target": "ONT"},
                             {"operation": "speedtest", "target": "PC"},
                         ],
                         "errors": {"traceroute": "not confirmed"},
                     }},
                ],
                "snapshots": [
                    {"id": 1, "captured_at": "2026-09-25T12:00:02+00:00",
                     "reason": "speedtest"},
                    {"id": 2, "captured_at": "2026-09-25T12:00:04+00:00",
                     "reason": "connect", "payload_json": {
                         "password": "SENSITIVE_DO_NOT_PRINT"}},
                    {"id": 3, "captured_at": "2026-09-25T12:00:05+00:00",
                     "reason": "manual"},
                ],
            },
        )
        text = report["text"]
        self.assertIn("ONT F6201B", text)
        self.assertIn("Configuração de SSID", text)
        self.assertIn("tentativa sem confirmação", text)
        self.assertIn("Teste de velocidade realizado", text)
        self.assertIn("Inspeção", text.replace("Diagnóstico", "Inspeção"))
        self.assertIn("ping", text.lower())
        self.assertIn("traceroute", text.lower())
        self.assertNotIn("SENSITIVE_DO_NOT_PRINT", text)
        self.assertLess(text.index("Diagnóstico geral"),
                        text.index("Teste de velocidade realizado"))
        self.assertLess(text.index("Configuração de SSID"),
                        text.index("Configuração avançada"))

    def test_no_diagnostic_reports_only_recorded_actions(self):
        report = AttendanceReportService().build(
            diagnostic={"mode": "general", "sections": {}, "findings": []},
            timeline={"changes": [{
                "created_at": "2026-09-25T12:00:00+00:00",
                "success": 1, "operation": "dhcp_basic", "target": "LAN",
                "before_json": None, "after_json": {"verified": True},
            }], "diagnostics": [], "snapshots": []},
        )
        self.assertIn("Alteração do DHCP", report["text"])
        self.assertIn("Não houve diagnóstico consolidado", report["text"])
        self.assertNotIn("Testes concluídos sem alertas", report["text"])

    def test_report_never_prints_mac_target(self):
        report = AttendanceReportService().build(
            diagnostic={"mode": "general"},
            timeline={"changes": [{
                "created_at": "2026-09-25T12:00:00+00:00",
                "success": 1, "operation": "dhcp_reservation",
                "target": "AA:BB:CC:11:22:33",
            }]},
        )
        self.assertNotIn("AA:BB:CC:11:22:33", report["text"])
        self.assertIn("[MAC oculto]", report["text"])


class CurrentSessionBoundaryTests(unittest.TestCase):
    def setUp(self):
        self.service = ZTEService()
        self.service._history_session_id = 17

    def test_report_without_diagnostic_uses_current_timeline(self):
        timeline = {
            "session": {"id": 17}, "changes": [{
                "created_at": "2026-09-25T12:00:00+00:00",
                "success": 1, "operation": "f6201b_dns_update",
                "target": "DNS",
            }], "diagnostics": [], "snapshots": []
        }
        with patch(
            "apps.zte_manager.services.zte_service.history_repository"
            ".session_timeline", return_value=timeline
        ) as fetch_timeline, patch(
            "apps.zte_manager.services.zte_service.history_repository"
            ".diagnostic", return_value=None
        ) as last:
            report = self.service.generate_attendance()
        fetch_timeline.assert_called_once_with(17)
        last.assert_called_once_with(None, session_id=17)
        self.assertIn("Configuração de DNS", report["text"])
        self.assertEqual(report["session_id"], 17)

    def test_foreign_diagnostic_cannot_expose_another_session(self):
        with patch(
            "apps.zte_manager.services.zte_service.history_repository"
            ".session_timeline", return_value={"changes": []}
        ), patch(
            "apps.zte_manager.services.zte_service.history_repository"
            ".diagnostic", return_value={
                "history_id": 999, "session_id": 999, "mode": "general"
            }
        ):
            with self.assertRaisesRegex(ValueError, "sessão atual"):
                self.service.generate_attendance(diagnostic_id=999)

    def test_direct_f6201b_action_records_success_and_uncertain_result(self):
        with patch(
            "apps.zte_manager.services.zte_service.history_repository"
            ".save_change"
        ) as store:
            ok = self.service._audit_device_command(
                "f6201b_ssid_update", "SSID",
                lambda: {"success": True, "verified": True,
                         "changed_fields": ["ESSID", "KeyPassphrase"],
                         "steps": []},
            )
            uncertain = self.service._audit_device_command(
                "f6201b_form_update", "WAN",
                lambda: {"success": False, "uncertain": True},
            )
        self.assertTrue(ok["verified"])
        self.assertTrue(uncertain["uncertain"])
        self.assertEqual(store.call_count, 2)
        self.assertEqual(store.call_args_list[0].kwargs["after"]["fields"],
                         ["ESSID"])
        self.assertFalse(store.call_args_list[1].kwargs["success"])


if __name__ == "__main__":
    unittest.main()

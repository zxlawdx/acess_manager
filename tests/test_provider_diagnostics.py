"""Hardware-free regression cases for ISP diagnostics, radio write proof and OS history."""
from __future__ import annotations

import unittest

from apps.zte_manager.application.operations.audit_executor import AuditedOperation
from apps.zte_manager.application.operations.verifiers import verify_channel_choice
from apps.zte_manager.services.attendance_report_service import AttendanceReportService
from apps.zte_manager.services.support_diagnostic_service import ChannelAnalyzer


class ChannelEvidenceTests(unittest.TestCase):
    def test_uses_nested_zte_channel_table_not_guessed_defaults(self):
        result = ChannelAnalyzer().analyze(
            band="2.4GHz",
            radio={"banda": "2.4GHz", "canal": "6", "canal_automatico": "0"},
            neighbors=[{"channel": 6, "signal": -42}],
            available_channels=[
                {"banda": "2.4GHz", "canais": [1, 6, 11]},
                {"banda": "5GHz", "canais": [36, 40, 44]},
            ],
            scan_confirmed=True,
        )
        self.assertEqual(sorted(result["scores"]), [1, 6, 11])
        self.assertFalse(result["auto_channel"])
        self.assertTrue(result["candidate_channels_confirmed"])
        self.assertNotEqual(result["best_channel"], 6)
        self.assertEqual(result["recommendation"]["action"]["type"], "wifi_channel")

    def test_no_channel_table_means_no_automatic_write(self):
        result = ChannelAnalyzer().analyze(
            band="5GHz",
            radio={"canal": "36", "canal_automatico": False},
            neighbors=[{"channel": 36, "signal": -40}],
            available_channels=[],
        )
        self.assertEqual(result["scores"], {})
        self.assertFalse(result["candidate_channels_confirmed"])
        self.assertEqual(result["recommendation"], {})

    def test_unconfirmed_scan_is_not_a_write_signal(self):
        result = ChannelAnalyzer().analyze(
            band="2.4GHz",
            radio={"canal": "6", "canal_automatico": False},
            neighbors=[{"channel": 6, "signal": -40}],
            available_channels=[{"canais": [1, 6, 11]}],
            scan_confirmed=False,
        )
        self.assertIsNone(result["best_channel"])
        self.assertFalse(result["neighbor_scan_confirmed"])
        self.assertEqual(result["recommendation"], {})

    def test_channel_write_needs_fresh_specific_readback(self):
        request = {"auto_channel": False, "channel": 11}
        response = {"success": True}
        actual = [{"banda": "2.4GHz", "canal_automatico": False, "canal": "11"}]
        self.assertTrue(verify_channel_choice("2.4GHz", request, None, response, actual))
        self.assertFalse(verify_channel_choice(
            "2.4GHz", request, None, response,
            [{"banda": "2.4GHz", "canal_automatico": False, "canal": "6"}],
        ))
        self.assertFalse(verify_channel_choice("2.4GHz", request, None, response, []))
        self.assertFalse(verify_channel_choice("2.4GHz", request, None, {"success": False}, actual))
        self.assertTrue(verify_channel_choice(
            "2.4GHz", {"auto_channel": True}, None, response,
            [{"banda": "2.4GHz", "canal_automatico": "1", "canal": 11}],
        ))


class SafeProfileHistory:
    def __init__(self):
        self.events = []

    def save_change(self, session_id, **kwargs):
        self.events.append(kwargs)


class ProfileReportTests(unittest.TestCase):
    def test_generic_profile_steps_and_readback_differences_enter_attendance(self):
        history = SafeProfileHistory()
        before = {"wifi": {
            "2.4GHz": {"auto_channel": False, "channel": 6},
            "5GHz": {"auto_channel": False, "channel": 44},
        }, "dns": {"ipv4_1": "192.0.2.1"}}
        after = {"wifi": {
            "2.4GHz": {"auto_channel": False, "channel": 11},
            "5GHz": {"auto_channel": True, "channel": None},
        }, "dns": {"ipv4_1": "192.0.2.2"}}
        result = AuditedOperation(history).execute(
            session_id=7, operation="profile_apply", target="technician",
            before_reader=lambda: before,
            action=lambda: {"success": True, "steps": [
                {"name": "Wi-Fi 2.4GHz", "success": True, "detail": "password=SECRET"},
                {"name": "Wi-Fi 5GHz", "success": True},
                {"name": "DNS", "success": True},
                {"name": "unexpected_password=SECRET", "success": True},
            ]},
            after_reader=lambda: after,
        )
        self.assertEqual(result.outcome.value, "accepted")
        event = history.events[0]
        self.assertFalse(event["success"])
        self.assertEqual(len(event["after"]["_profile_steps"]), 3)
        self.assertNotIn("SECRET", str(event))
        report = AttendanceReportService().build(
            diagnostic={"mode": "general"},
            timeline={"changes": [{
                **event, "operation": "profile_apply", "target": "technician",
                "before_json": event["before"], "after_json": event["after"],
                "created_at": "2026-09-29T10:00:00Z",
            }], "diagnostics": [], "snapshots": []},
        )["text"]
        self.assertIn("Aplicação da configuração padrão", report)
        self.assertIn("Wi-Fi 2,4 GHz: canal", report)
        self.assertIn("Wi-Fi 5 GHz: modo do canal", report)
        self.assertIn("Servidores DNS: parâmetros diferentes", report)
        self.assertIn("comando aceito", report)
        self.assertIn("ainda não verificada", report)
        self.assertNotIn("technician", report)
        self.assertNotIn("SECRET", report)

    def test_without_success_does_not_invent_applied_changes(self):
        report = AttendanceReportService().build(
            diagnostic={"mode": "general"},
            timeline={"changes": [{
                "operation": "profile_apply", "outcome": "failed",
                "success": False, "target": "person",
                "before_json": None, "after_json": {"_profile_steps": [
                    {"name": "Wi-Fi 2,4 GHz", "accepted": False},
                ]},
            }], "diagnostics": [], "snapshots": []},
        )["text"]
        self.assertIn("Wi-Fi 2,4 GHz (falhou)", report)
        self.assertNotIn("diferenças observadas", report)


if __name__ == "__main__":
    unittest.main()

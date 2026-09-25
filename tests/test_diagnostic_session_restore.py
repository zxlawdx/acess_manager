"""Reprodução do logout aparente após diagnóstico no desktop."""

import unittest
from pathlib import Path
from unittest.mock import patch

from apps.zte_manager import api
from apps.zte_manager.services.zte_service import zte_service


ROOT = Path(__file__).resolve().parents[1]


class DiagnosticSessionRestoreTests(unittest.TestCase):
    def test_connection_status_restores_frontend_without_credentials(self):
        client = type("Client", (), {"writes_enabled": False})()
        with patch.object(zte_service, "_zte", client), patch.object(
            zte_service, "current_host", "192.0.2.1"
        ), patch.object(zte_service, "current_attendant", "tecnico"), patch.object(
            zte_service, "_device_info",
            {"modelo": "H288A", "firmware": "test"}
        ):
            state = api.connection_status()

        self.assertTrue(state["connected"])
        self.assertFalse(state["writes_enabled"])
        self.assertEqual(state["model"], "H288A")
        self.assertEqual(state["host"], "192.0.2.1")
        for term in ("password", "token", "session_token"):
            self.assertNotIn(term, state)

    def test_diagnostic_forms_never_submit_as_browser_navigation(self):
        html = (
            ROOT / "apps" / "zte_manager" / "templates" / "index.html"
        ).read_text(encoding="utf-8")
        self.assertIn(
            '<form id="supportDiagnosticForm" class="form-stack" onsubmit="return false;">',
            html,
        )
        self.assertIn(
            '<form id="automaticDiagnosticForm" class="operations-form" onsubmit="return false;">',
            html,
        )

    def test_webview_recovers_existing_session_without_new_login(self):
        js = (
            ROOT / "apps" / "zte_manager" / "static" / "js" / "app.js"
        ).read_text(encoding="utf-8")
        self.assertIn('apiRequest("/connection/status")', js)
        self.assertIn("void restoreDesktopSession();", js)
        self.assertIn("setConnectionStatus(true);", js)


if __name__ == "__main__":
    unittest.main()

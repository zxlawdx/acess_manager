"""Regressões independentes de equipamento para o executável Windows."""

import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from apps.zte_manager.model.zte_configuration import zte_backup
from apps.zte_manager.services.desktop_clipboard import copy_text


ROOT = Path(__file__).resolve().parents[1]


class FakeResponse:
    def __init__(self, content, content_type):
        self.content = content
        self.headers = {
            "Content-Type": content_type,
        }

    def raise_for_status(self):
        return None


class FakeZTE:
    base_url = "http://localhost"
    session_token = "fake-token"

    def __init__(self, response):
        self.response = response
        self.session = SimpleNamespace(
            post=lambda *args, **kwargs: response
        )

    def get_view(self, *args, **kwargs):
        return "" 

    def _validar_resposta(self, text):
        return None


class WindowsCompatibilityTests(unittest.TestCase):
    def test_backup_rejects_login_html_even_with_http_200(self):
        fake = FakeZTE(
            FakeResponse(
                b"<html><title>Bem-vindo a F670L</title>Login</html>",
                "text/html",
            )
        )

        with patch.object(
            zte_backup,
            "post_menu",
            return_value="<ajax_response_xml_root/>",
        ), patch.object(
            zte_backup,
            "data_dir",
            side_effect=AssertionError("HTML nao pode ser salvo"),
        ):
            with self.assertRaisesRegex(RuntimeError, "HTML"):
                zte_backup.export_user_configuration(fake)

    def test_clipboard_requires_windows(self):
        if sys.platform == "win32":
            self.skipTest("teste de plataforma usa runner Linux")

        with self.assertRaisesRegex(RuntimeError, "Windows"):
            copy_text("atendimento")

    def test_clipboard_frontend_uses_native_endpoint(self):
        js = (
            ROOT / "apps" / "zte_manager" / "static"
            / "js" / "support_diagnostics.js"
        ).read_text(encoding="utf-8")

        self.assertIn('"/desktop/clipboard"', js)
        self.assertIn('if (/Windows/i.test(navigator.userAgent))', js)

    def test_windows_layout_scopes_workspace(self):
        css = (
            ROOT / "apps" / "zte_manager" / "static"
            / "css" / "telecom_console.css"
        ).read_text(encoding="utf-8")

        self.assertIn("width: calc(100% - var(--sidebar-width))", css)
        self.assertIn("flex-wrap: wrap", css)


if __name__ == "__main__":
    unittest.main()

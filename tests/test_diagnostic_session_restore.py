"""Reprodução do logout aparente após diagnóstico no desktop."""

from pathlib import Path

from apps.zte_manager import api
from apps.zte_manager.services.zte_service import zte_service


ROOT = Path(__file__).resolve().parents[1]


def test_connection_status_can_restore_frontend_without_credentials(monkeypatch):
    monkeypatch.setattr(zte_service, "_zte", type(
        "Client", (), {"writes_enabled": False}
    )())
    monkeypatch.setattr(zte_service, "current_host", "192.0.2.1")
    monkeypatch.setattr(zte_service, "current_attendant", "tecnico")
    monkeypatch.setattr(
        zte_service,
        "_device_info",
        {"modelo": "H288A", "firmware": "test"},
    )
    state = api.connection_status()
    assert state["connected"] is True
    assert state["writes_enabled"] is False
    assert state["model"] == "H288A"
    assert state["host"] == "192.0.2.1"
    assert not any(
        term in state for term in ("password", "token", "session_token")
    )


def test_diagnostic_forms_never_submit_as_browser_navigation():
    html = (
        ROOT / "apps" / "zte_manager" / "templates" / "index.html"
    ).read_text(encoding="utf-8")
    assert '<form id="supportDiagnosticForm" class="form-stack" onsubmit="return false;">' in html
    assert '<form id="automaticDiagnosticForm" class="operations-form" onsubmit="return false;">' in html


def test_webview_recovers_existing_session_without_new_login():
    js = (
        ROOT / "apps" / "zte_manager" / "static" / "js" / "app.js"
    ).read_text(encoding="utf-8")
    assert 'apiRequest("/connection/status")' in js
    assert "void restoreDesktopSession();" in js
    assert 'setConnectionStatus(true);' in js

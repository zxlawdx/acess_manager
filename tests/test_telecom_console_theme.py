from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TEMPLATE = (
    ROOT
    / "apps"
    / "zte_manager"
    / "templates"
    / "index.html"
)
THEME = (
    ROOT
    / "apps"
    / "zte_manager"
    / "static"
    / "css"
    / "telecom_console.css"
)
APP_JS = (
    ROOT
    / "apps"
    / "zte_manager"
    / "static"
    / "js"
    / "app.js"
)


def test_theme_is_loaded_after_existing_stylesheets():
    html = TEMPLATE.read_text(
        encoding="utf-8"
    )

    management = html.index(
        "management.css"
    )

    telecom = html.index(
        "telecom_console.css"
    )

    assert telecom > management
    assert "cdn.tailwindcss.com" not in html


def test_telecom_shell_contract_is_present():
    html = TEMPLATE.read_text(
        encoding="utf-8"
    )

    for marker in (
        'class="console-ribbon"',
        'id="consoleSessionDot"',
        'id="consoleSessionState"',
        'id="consoleHostText"',
        'class="nav-caption"',
        'data-jump="supportDiagnostic"',
        'data-jump="management"',
    ):
        assert marker in html

    assert (
        'd="M10 13H30L17 27H30"'
        in html
    )


def test_theme_uses_reference_console_palette_and_fonts():
    css = THEME.read_text(
        encoding="utf-8"
    ).lower()

    for marker in (
        "--bg: #0a0a0c",
        "--surface: #18191e",
        "--primary: #00e599",
        "--secondary: #00f0ff",
        "--warning: #f59e0b",
        "--danger: #ef4444",
        '"inter"',
        '"jetbrains mono"',
    ):
        assert marker in css

    assert ":has(" not in css


def test_connection_state_updates_console_chrome():
    js = APP_JS.read_text(
        encoding="utf-8"
    )

    for marker in (
        '"consoleSessionDot"',
        '"consoleSessionState"',
        '"consoleHostText"',
        '"SESSION ACTIVE"',
        '"SESSION OFFLINE"',
        '"ont-connected"',
    ):
        assert marker in js

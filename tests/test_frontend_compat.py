from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
APP_JS = ROOT / "apps" / "zte_manager" / "static" / "js" / "app.js"
STYLE_CSS = ROOT / "apps" / "zte_manager" / "static" / "css" / "style.css"
INDEX_HTML = ROOT / "apps" / "zte_manager" / "templates" / "index.html"
BUILD_REQUIREMENTS = ROOT / "requirements-build.txt"


class FrontendCompatibilityTests(unittest.TestCase):
    def test_app_js_avoids_replace_all(self):
        source = APP_JS.read_text(encoding="utf-8")

        self.assertNotIn(
            ".replaceAll(",
            source,
            "O frontend deve continuar compatível com WebViews sem replaceAll().",
        )

    def test_css_avoids_has_selector(self):
        source = STYLE_CSS.read_text(encoding="utf-8")

        self.assertNotIn(
            ":has(",
            source,
            "Nao dependa de :has() para layout essencial dentro do WebView.",
        )

    def test_text_fonts_do_not_depend_on_google_fonts(self):
        source = INDEX_HTML.read_text(encoding="utf-8")

        self.assertNotIn(
            "family=Inter",
            source,
        )
        self.assertNotIn(
            "JetBrains+Mono",
            source,
        )

    def test_zoom_shortcuts_are_registered(self):
        source = APP_JS.read_text(encoding="utf-8")

        self.assertIn(
            'UI_ZOOM_KEY = "zteAutomatic.uiZoom"',
            source,
        )
        self.assertIn(
            'event.key',
            source,
        )
        self.assertIn(
            'key === "0"',
            source,
        )

    def test_windows_build_uses_pyqt6(self):
        source = BUILD_REQUIREMENTS.read_text(encoding="utf-8")

        self.assertIn(
            "PyQt6",
            source,
        )
        self.assertIn(
            "PyQt6-WebEngine",
            source,
        )
        self.assertNotIn(
            "\nPyQt5",
            source,
        )


if __name__ == "__main__":
    unittest.main()

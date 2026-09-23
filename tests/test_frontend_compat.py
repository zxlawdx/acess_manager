from pathlib import Path
import unittest


class FrontendCompatibilityTests(unittest.TestCase):
    def test_app_js_avoids_replace_all(self):
        source = Path(
            "apps/zte_manager/static/js/app.js"
        ).read_text(encoding="utf-8")

        self.assertNotIn(
            ".replaceAll(",
            source,
            "QtWebEngine de algumas builds nao suporta String.prototype.replaceAll().",
        )


if __name__ == "__main__":
    unittest.main()

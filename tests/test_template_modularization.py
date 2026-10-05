import unittest
from pathlib import Path

from tools import build_frontend_template as builder


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "apps" / "zte_manager" / "templates" / "source"
TARGET = ROOT / "apps" / "zte_manager" / "templates" / "index.html"

ADVANCED_PARTS = (
    "pages/advanced/workbench_discovery.html",
    "pages/advanced/network.html",
    "pages/advanced/huawei_security.html",
    "pages/advanced/inspector_close.html",
)
MANAGEMENT_PARTS = (
    "pages/management/fleet.html",
    "pages/management/remote_monitor.html",
    "pages/management/network_mesh.html",
    "pages/management/lifecycle_provisioning.html",
)


class TemplateModularizationTests(unittest.TestCase):
    def test_generated_template_is_byte_stable(self):
        self.assertEqual(
            builder.build_template(),
            TARGET.read_text(encoding="utf-8"),
            "modular source must reproduce the committed Vela template exactly",
        )

    def test_advanced_and_management_god_files_are_removed(self):
        self.assertFalse((SOURCE / "pages/advanced.html").exists())
        self.assertFalse((SOURCE / "pages/management.html").exists())

    def test_builder_owns_explicit_nested_composition_order(self):
        parts = tuple(builder.PARTS)
        self.assertNotIn("pages/advanced.html", parts)
        self.assertNotIn("pages/management.html", parts)

        advanced_positions = [parts.index(name) for name in ADVANCED_PARTS]
        management_positions = [parts.index(name) for name in MANAGEMENT_PARTS]
        self.assertEqual(advanced_positions, list(range(min(advanced_positions), max(advanced_positions) + 1)))
        self.assertEqual(management_positions, list(range(min(management_positions), max(management_positions) + 1)))

    def test_page_modules_are_real_and_reviewable(self):
        for relative in ADVANCED_PARTS + MANAGEMENT_PARTS:
            with self.subTest(relative=relative):
                path = SOURCE / relative
                self.assertTrue(path.is_file())
                text = path.read_text(encoding="utf-8")
                self.assertGreater(len(text.strip()), 200)
                self.assertLess(len(text.splitlines()), 240)


if __name__ == "__main__":
    unittest.main()

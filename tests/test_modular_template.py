"""HTML source modules must reconstitute the exact legacy Vela DOM contract."""
import importlib.util
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "tools" / "build_frontend_template.py"


class ModularTemplateTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        spec = importlib.util.spec_from_file_location("am_frontend_builder", SCRIPT)
        cls.builder = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cls.builder)

    def test_generated_template_is_in_sync(self):
        expected = self.builder.build_template()
        actual = self.builder.TARGET.read_text(encoding="utf-8")
        self.assertEqual(actual, expected)

    def test_source_is_split_into_twelve_real_pages_and_chrome(self):
        filenames = [p for p in self.builder.PARTS if p.startswith("pages/")]
        self.assertEqual(len(filenames), 12)
        for name in filenames:
            content = (self.builder.SOURCE / name).read_text(encoding="utf-8")
            self.assertIn('<section id="page-', content)
        self.assertIn("appearanceSelect", self.builder.build_template())


if __name__ == "__main__":
    unittest.main()

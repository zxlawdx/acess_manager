from __future__ import annotations

import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CSS_ROOT = ROOT / "apps" / "zte_manager" / "static" / "css"
SHELL = ROOT / "apps" / "zte_manager" / "templates" / "source" / "shell_start.html"
INDEX = ROOT / "apps" / "zte_manager" / "templates" / "index.html"
TOKENS = CSS_ROOT / "foundation" / "tangerine_tokens.css"

EXPECTED_STYLESHEET_ORDER = [
    "style.css",
    "advanced.css",
    "support_diagnostics.css",
    "management.css",
    "telecom_console.css",
    "adaptive_firmware.css",
    "f6201b_editor.css",
    "neutral_console.css",
    "brmodelo_workbench.css",
    "f6201b_workbench.css",
    "light_mode_refine.css",
    "dhcp_module.css",
    "tangerine.css",
    "tangerine_forms.css",
    "tangerine_cards.css",
    "tangerine_workflows.css",
    "components/topology.css",
    "components/firmware_inspector.css",
    "components/shell_layout.css",
    "components/provider_diagnostics.css",
]

EXPECTED_WORKFLOW_IMPORTS = [
    "./foundation/tangerine_tokens.css",
    "./pages/support_workbench.css",
    "./pages/diagnostics_workbench.css",
    "./pages/profile_workbench.css",
    "./pages/workbench_responsive.css",
    "./components/operator_results.css",
]

STYLE_REF = re.compile(r"static\(['\"]zte_manager/css/([^'\"]+)['\"]\)")
CSS_IMPORT = re.compile(r"@import\s+url\(['\"]([^'\"]+)['\"]\)\s*;")
CANONICAL_DEFINITION = re.compile(
    r"(--am-(?:"
    r"color-[a-z0-9-]+|"
    r"space-[a-z0-9-]+|"
    r"radius-[a-z0-9-]+|"
    r"focus-[a-z0-9-]+|"
    r"transition-[a-z0-9-]+|"
    r"z-[a-z0-9-]+|"
    r"font-(?:sans|mono)|"
    r"shadow-[a-z0-9-]+"
    r"))\s*:",
    re.I,
)
INLINE_STYLE = re.compile(r"\sstyle\s*=\s*['\"]", re.I)

# Measured ceilings. Cleanup slices must lower them rather than growing debt.
IMPORTANT_BASELINE = 1537
INLINE_STYLE_BASELINE = 2


def stylesheet_refs(source: str) -> list[str]:
    return STYLE_REF.findall(source)


def css_files() -> list[Path]:
    return sorted(CSS_ROOT.rglob("*.css"))


class CssArchitectureTests(unittest.TestCase):
    def test_shell_stylesheet_order_is_explicit_unique_and_existing(self):
        refs = stylesheet_refs(SHELL.read_text(encoding="utf-8"))
        self.assertEqual(refs, EXPECTED_STYLESHEET_ORDER)
        self.assertEqual(len(refs), len(set(refs)), "stylesheet references must be unique")
        for relative in refs:
            with self.subTest(relative=relative):
                self.assertTrue((CSS_ROOT / relative).is_file(), f"missing stylesheet: {relative}")

    def test_generated_index_keeps_the_same_stylesheet_sequence(self):
        refs = stylesheet_refs(INDEX.read_text(encoding="utf-8"))
        self.assertEqual(refs, EXPECTED_STYLESHEET_ORDER)

    def test_workflow_entrypoint_preserves_layer_order_and_real_assets(self):
        workflow = (CSS_ROOT / "tangerine_workflows.css").read_text(encoding="utf-8")
        imports = CSS_IMPORT.findall(workflow)
        self.assertEqual(imports, EXPECTED_WORKFLOW_IMPORTS)
        for relative in imports:
            target = (CSS_ROOT / relative).resolve()
            with self.subTest(relative=relative):
                self.assertTrue(target.is_file(), f"missing workflow import: {relative}")

        without_comments = re.sub(r"/\*.*?\*/", "", workflow, flags=re.S)
        without_imports = CSS_IMPORT.sub("", without_comments).strip()
        self.assertEqual(without_imports, "", "workflow entrypoint must not regain page/component rules")

    def test_canonical_token_definitions_have_one_source_of_truth(self):
        definitions: dict[str, set[str]] = {}
        for path in css_files():
            source = path.read_text(encoding="utf-8")
            for name in CANONICAL_DEFINITION.findall(source):
                definitions.setdefault(name, set()).add(path.relative_to(CSS_ROOT).as_posix())

        self.assertGreaterEqual(len(definitions), 25, "expected the canonical token vocabulary")
        for name, owners in sorted(definitions.items()):
            with self.subTest(token=name):
                self.assertEqual(
                    owners,
                    {"foundation/tangerine_tokens.css"},
                    f"canonical token {name} is defined outside the foundation",
                )

    def test_component_compatibility_entrypoints_point_to_real_component_files(self):
        forms = (CSS_ROOT / "tangerine_forms.css").read_text(encoding="utf-8")
        cards = (CSS_ROOT / "tangerine_cards.css").read_text(encoding="utf-8")
        self.assertIn('@import url("./components/structured_forms.css");', forms)
        self.assertIn('@import url("./components/configuration_cards.css");', cards)
        self.assertTrue((CSS_ROOT / "components/structured_forms.css").is_file())
        self.assertTrue((CSS_ROOT / "components/configuration_cards.css").is_file())

    def test_css_and_inline_style_debt_does_not_increase(self):
        important_by_file = {}
        for path in css_files():
            count = path.read_text(encoding="utf-8").count("!important")
            if count:
                important_by_file[path.relative_to(CSS_ROOT).as_posix()] = count

        inline_by_file = {}
        source_root = ROOT / "apps" / "zte_manager" / "templates" / "source"
        for path in sorted(source_root.rglob("*.html")):
            count = len(INLINE_STYLE.findall(path.read_text(encoding="utf-8")))
            if count:
                inline_by_file[path.relative_to(source_root).as_posix()] = count

        important_total = sum(important_by_file.values())
        inline_total = sum(inline_by_file.values())
        print("CSS !important inventory:", important_by_file)
        print("CSS !important total:", important_total)
        print("Template inline-style inventory:", inline_by_file)
        print("Template inline-style total:", inline_total)

        self.assertLessEqual(important_total, IMPORTANT_BASELINE)
        self.assertLessEqual(inline_total, INLINE_STYLE_BASELINE)


if __name__ == "__main__":
    unittest.main()

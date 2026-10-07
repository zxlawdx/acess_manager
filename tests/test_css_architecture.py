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

EXPECTED_LIGHT_IMPORTS = [
    "./foundation/tangerine_tokens.css",
    "./themes/light_base_compat.css",
    "./themes/light_feature_compat.css",
    "./themes/light_console_compat.css",
    "./components/native_controls_light.css",
]

EXPECTED_TANGERINE_IMPORTS = [
    "./foundation/tangerine_tokens.css",
    "./themes/tangerine_base_compat.css",
    "./pages/dashboard_tangerine.css",
    "./themes/tangerine_terminal_compat.css",
    "./layout/editorial_workspace.css",
    "./pages/advanced_tangerine.css",
    "./components/history_timeline.css",
    "./pages/connection_inventory.css",
    "./pages/clients_tangerine.css",
    "./pages/device_tangerine.css",
    "./pages/tr069_tangerine.css",
    "./pages/diagnostics_tangerine.css",
]

EXPECTED_WORKFLOW_IMPORTS = [
    "./foundation/tangerine_tokens.css",
    "./pages/support_workbench.css",
    "./pages/diagnostics_workbench.css",
    "./pages/profile_workbench.css",
    "./pages/workbench_responsive.css",
    "./components/operator_results.css",
]

TANGERINE_OWNER_LANDMARKS = {
    "themes/tangerine_base_compat.css": ".menu-item.active",
    "pages/dashboard_tangerine.css": ".am-dashboard-hero",
    "themes/tangerine_terminal_compat.css": "#pingOutput.terminal-output",
    "layout/editorial_workspace.css": ".am-session-bar",
    "pages/advanced_tangerine.css": ".am-workbench-tab",
    "components/history_timeline.css": ".am-history-timeline",
    "pages/connection_inventory.css": ".am-inventory-panel",
    "pages/clients_tangerine.css": ".am-client-workbench",
    "pages/device_tangerine.css": ".am-device-summary",
    "pages/tr069_tangerine.css": ".am-tr069-workspace",
    "pages/diagnostics_tangerine.css": ".am-diagnostic-tabbed",
}

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

# The Tangerine split moves rules without deleting specificity. Exact count is
# a characterization guard for this slice; later cleanup PRs may deliberately
# lower it together with a new tested baseline.
IMPORTANT_EXPECTED = 1537
INLINE_STYLE_BASELINE = 2


def stylesheet_refs(source: str) -> list[str]:
    return STYLE_REF.findall(source)


def css_files() -> list[Path]:
    return sorted(CSS_ROOT.rglob("*.css"))


def assert_import_entrypoint(test_case: unittest.TestCase, relative: str, expected: list[str]) -> None:
    source = (CSS_ROOT / relative).read_text(encoding="utf-8")
    imports = CSS_IMPORT.findall(source)
    test_case.assertEqual(imports, expected)
    for imported in imports:
        target = (CSS_ROOT / imported).resolve()
        with test_case.subTest(entrypoint=relative, imported=imported):
            test_case.assertTrue(target.is_file(), f"missing import from {relative}: {imported}")

    without_comments = re.sub(r"/\*.*?\*/", "", source, flags=re.S)
    without_imports = CSS_IMPORT.sub("", without_comments).strip()
    test_case.assertEqual(without_imports, "", f"{relative} must remain an import-only entrypoint")


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

    def test_light_compatibility_entrypoint_preserves_layer_order(self):
        assert_import_entrypoint(self, "light_mode_refine.css", EXPECTED_LIGHT_IMPORTS)
        source = (CSS_ROOT / "light_mode_refine.css").read_text(encoding="utf-8")
        self.assertNotRegex(source, r"--ui-[a-z0-9-]+\s*:")

    def test_tangerine_entrypoint_preserves_original_feature_order(self):
        assert_import_entrypoint(self, "tangerine.css", EXPECTED_TANGERINE_IMPORTS)

    def test_tangerine_real_owners_keep_characterization_landmarks(self):
        for relative, landmark in TANGERINE_OWNER_LANDMARKS.items():
            with self.subTest(relative=relative):
                source = (CSS_ROOT / relative).read_text(encoding="utf-8")
                self.assertIn(landmark, source)
                self.assertGreater(len(source.strip()), 180)

    def test_workflow_entrypoint_preserves_layer_order_and_real_assets(self):
        assert_import_entrypoint(self, "tangerine_workflows.css", EXPECTED_WORKFLOW_IMPORTS)

    def test_canonical_token_definitions_have_one_source_of_truth(self):
        definitions: dict[str, set[str]] = {}
        for path in css_files():
            source = path.read_text(encoding="utf-8")
            for name in CANONICAL_DEFINITION.findall(source):
                definitions.setdefault(name, set()).add(path.relative_to(CSS_ROOT).as_posix())

        self.assertGreaterEqual(len(definitions), 30, "expected the canonical token vocabulary")
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

    def test_css_specificity_count_is_preserved_by_tangerine_split(self):
        important_by_file = {}
        for path in css_files():
            count = path.read_text(encoding="utf-8").count("!important")
            if count:
                important_by_file[path.relative_to(CSS_ROOT).as_posix()] = count

        important_total = sum(important_by_file.values())
        print("CSS !important inventory:", important_by_file)
        print("CSS !important total:", important_total)
        self.assertEqual(important_total, IMPORTANT_EXPECTED)

    def test_template_inline_style_debt_does_not_increase(self):
        inline_by_file = {}
        source_root = ROOT / "apps" / "zte_manager" / "templates" / "source"
        for path in sorted(source_root.rglob("*.html")):
            count = len(INLINE_STYLE.findall(path.read_text(encoding="utf-8")))
            if count:
                inline_by_file[path.relative_to(source_root).as_posix()] = count

        inline_total = sum(inline_by_file.values())
        print("Template inline-style inventory:", inline_by_file)
        print("Template inline-style total:", inline_total)
        self.assertLessEqual(inline_total, INLINE_STYLE_BASELINE)


if __name__ == "__main__":
    unittest.main()

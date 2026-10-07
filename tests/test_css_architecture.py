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

# Compact characterization contract for the selectors moved out of the old
# Tangerine monolith. These are deliberately domain landmarks rather than a
# giant selector snapshot: each selector must remain in exactly one real owner.
TANGERINE_OWNER_SELECTORS = {
    "themes/tangerine_base_compat.css": [
        "html[data-theme] .brand-mark {",
        "html[data-theme] #themeToggle {display:none!important;}",
    ],
    "pages/dashboard_tangerine.css": [
        "html[data-theme] .am-dashboard-hero {",
        "html[data-theme] .am-activity-list {",
    ],
    "themes/tangerine_terminal_compat.css": [
        'html[data-theme="light"] .firmware-json,',
        "html[data-theme] #pingOutput.terminal-output,",
    ],
    "layout/editorial_workspace.css": [
        "html[data-theme] .am-session-bar{",
        "html[data-theme] .am-connect-story{",
        "html[data-theme] .management-tabs{",
    ],
    "pages/advanced_tangerine.css": [
        "html[data-theme] #page-advanced .advanced-actions {",
        "html[data-theme] .am-toolpanel[hidden] {display:none!important;}",
        "html[data-theme] #firmwareShapeOutput {",
    ],
    "components/history_timeline.css": [
        "html[data-theme] .am-history-timeline {",
        "html[data-theme] .am-history-backup {",
    ],
    "pages/connection_inventory.css": [
        "html[data-theme] .login-layout:has(.am-inventory-panel) {",
        "html[data-theme] .am-inventory-entry {",
    ],
    "pages/clients_tangerine.css": [
        "html[data-theme] #page-clients .am-section-intro {",
        "html[data-theme] .am-client-workbench {",
    ],
    "pages/device_tangerine.css": [
        "html[data-theme] .am-device-summary {",
        "html[data-theme] .am-device-maintenance {",
    ],
    "pages/tr069_tangerine.css": [
        "html[data-theme] .am-tr069-workspace {",
        "html[data-theme] .management-pane[hidden]{display:none!important;}",
    ],
    "pages/diagnostics_tangerine.css": [
        "html[data-theme] .am-diagnostic-workspace.am-diagnostic-tabbed {",
        "html[data-theme] .am-diagnostic-tabbed .diagnostic-card pre.terminal-output {",
    ],
}

TANGERINE_COMPAT_LAYERS = [
    "themes/tangerine_base_compat.css",
    "themes/tangerine_terminal_compat.css",
]

STYLE_REF = re.compile(r"static\(['\"]zte_manager/css/([^'\"]+)['\"]\)")
CSS_IMPORT = re.compile(r"@import\s+url\(['\"]([^'\"]+)['\"]\)\s*;")
CUSTOM_PROPERTY_DEFINITION = re.compile(r"--[a-z0-9-]+\s*:", re.I)
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

# PR #82's green CI measured 1536 declarations on main. The Tangerine split
# relocates all 545 declarations previously owned by tangerine.css without
# changing that global total. Later cleanup PRs may deliberately lower it only
# together with evidence and a new tested baseline.
IMPORTANT_EXPECTED = 1536
INLINE_STYLE_BASELINE = 2
TANGERINE_ENTRYPOINT_MAX_LINES = 24


def stylesheet_refs(source: str) -> list[str]:
    return STYLE_REF.findall(source)


def css_files() -> list[Path]:
    return sorted(CSS_ROOT.rglob("*.css"))


def normalized_import_path(relative: str) -> str:
    return relative.removeprefix("./")


def assert_import_entrypoint(test_case: unittest.TestCase, relative: str, expected: list[str]) -> None:
    source = (CSS_ROOT / relative).read_text(encoding="utf-8")
    imports = CSS_IMPORT.findall(source)
    test_case.assertEqual(imports, expected)
    test_case.assertEqual(len(imports), len(set(imports)), f"duplicate imports in {relative}")
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

    def test_tangerine_entrypoint_cannot_regrow_into_a_god_stylesheet(self):
        source = (CSS_ROOT / "tangerine.css").read_text(encoding="utf-8")
        self.assertLessEqual(len(source.splitlines()), TANGERINE_ENTRYPOINT_MAX_LINES)
        self.assertNotRegex(source, r"\{\s*[^*]", "tangerine.css must coordinate layers, not own CSS rules")

    def test_tangerine_real_owners_keep_exclusive_characterization_selectors(self):
        sources = {
            normalized_import_path(imported): (CSS_ROOT / imported).read_text(encoding="utf-8")
            for imported in EXPECTED_TANGERINE_IMPORTS
            if imported != "./foundation/tangerine_tokens.css"
        }
        self.assertEqual(set(TANGERINE_OWNER_SELECTORS), set(sources))

        for owner, selectors in TANGERINE_OWNER_SELECTORS.items():
            for selector in selectors:
                with self.subTest(owner=owner, selector=selector):
                    self.assertIn(selector, sources[owner], f"critical selector moved/lost from {owner}")
                    duplicates = [
                        other
                        for other, source in sources.items()
                        if other != owner and selector in source
                    ]
                    self.assertEqual(duplicates, [], f"critical selector duplicated outside {owner}")

    def test_tangerine_real_owners_do_not_hide_more_import_layers(self):
        for imported in EXPECTED_TANGERINE_IMPORTS:
            if imported == "./foundation/tangerine_tokens.css":
                continue
            relative = normalized_import_path(imported)
            source = (CSS_ROOT / relative).read_text(encoding="utf-8")
            with self.subTest(relative=relative):
                self.assertEqual(CSS_IMPORT.findall(source), [], f"nested imports can hide cascade cycles in {relative}")

    def test_tangerine_compat_layers_are_not_token_sources(self):
        for relative in TANGERINE_COMPAT_LAYERS:
            source = (CSS_ROOT / relative).read_text(encoding="utf-8")
            with self.subTest(relative=relative):
                self.assertIsNone(
                    CUSTOM_PROPERTY_DEFINITION.search(source),
                    f"compatibility layer {relative} must consume foundation tokens, not define them",
                )

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

"""Contratos básicos de cliques, recuperação e zoom da SPA QtWebEngine."""

import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TEMPLATE = ROOT / "apps/zte_manager/templates/index.html"
STATIC = ROOT / "apps/zte_manager/static"


def js(name):
    return (STATIC / "js" / name).read_text(encoding="utf-8")


class UIActionRegressions(unittest.TestCase):
    def test_important_buttons_have_real_handlers(self):
        html = TEMPLATE.read_text(encoding="utf-8")
        source = "\n".join(
            js(name) for name in (
                "app.js", "advanced.js", "management.js",
                "support_diagnostics.js",
            )
        )
        buttons = (
            "probeCapabilitiesButton", "multimodelProbeButton",
            "multimodelDiagnosticButton", "multimodelMeshButton",
            "captureSnapshotButton", "backupConfigurationButton",
            "dashboardFullDiagnosticButton", "supportCopyAttendance",
            "managementMeshRead", "managementBackupCreate",
            "zoomOutButton", "zoomInButton",
        )
        for button in buttons:
            with self.subTest(button=button):
                self.assertIn('id="' + button + '"', html)
                self.assertIn('"' + button + '"', source)

    def test_zoom_reflows_the_grid_shell_without_clipping_the_viewport(self):
        source = js("app.js")
        tangerine = (
            STATIC / "css" / "tangerine.css"
        ).read_text(encoding="utf-8")
        # QtWebEngine must never magnify <body> and clip the sidebar/topbar.
        self.assertIn('document.documentElement.style.zoom = "";', source)
        self.assertIn('document.body.style.zoom = "";', source)
        self.assertIn('document.body.style.width = "";', source)
        self.assertIn('shell.style.zoom = String(uiZoom);', source)
        self.assertNotIn(
            "document.body.style.zoom = String(uiZoom);", source
        )
        self.assertIn(
            "grid-template-columns:var(--am-current-sidebar) minmax(0,1fr)",
            tangerine,
        )
        self.assertIn(
            "width:calc(100% / var(--am-zoom,1))", tangerine
        )
        self.assertIn('"zoomInButton"', source)
        self.assertIn('"zoomOutButton"', source)

    def test_network_feedback_and_page_hooks_are_visible(self):
        html = TEMPLATE.read_text(encoding="utf-8")
        source = js("app.js")
        advanced = js("advanced.js")
        management = js("management.js")
        self.assertIn('id="requestStatusIndicator"', html)
        self.assertIn("pendingApiRequests++", source)
        self.assertIn("zte:page-open", source)
        self.assertIn("zte:page-open", advanced)
        self.assertIn("zte:page-open", management)
        self.assertIn("window.startQuickProbe", advanced)
        self.assertIn("window.runQuickSupportDiagnostic", js("support_diagnostics.js"))

    def test_management_clipboard_avoids_webview_copy_in_windows(self):
        source = js("management.js")
        region = source.split(
            "async function managementCopyText(", 1
        )[1].split("function managementRelevantNetworkResult()", 1)[0]
        native = js("desktop_clipboard.js")
        self.assertIn("window.desktopClipboard.copy(value, textarea, apiRequest)", region)
        self.assertIn('"/desktop/clipboard"', native)
        self.assertIn('"/desktop/capabilities"', native)
        self.assertNotIn("navigator.userAgent", region)
        self.assertNotIn("execCommand", region)


if __name__ == "__main__":
    unittest.main()

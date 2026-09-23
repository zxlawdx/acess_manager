import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
API = (
    ROOT
    / "apps"
    / "zte_manager"
    / "api.py"
).read_text(encoding="utf-8")
ADVANCED_JS = (
    ROOT
    / "apps"
    / "zte_manager"
    / "static"
    / "js"
    / "advanced.js"
).read_text(encoding="utf-8")
INDEX = (
    ROOT
    / "apps"
    / "zte_manager"
    / "templates"
    / "index.html"
).read_text(encoding="utf-8")


class OperationsContractTests(unittest.TestCase):
    def test_advanced_ui_routes_exist_in_api(self):
        endpoints = (
            "/wifi/schedule",
            "/wifi/schedule/update",
            "/wifi/band-steering/configure",
            "/device/capabilities",
            "/device/capabilities/probe",
            "/features/read",
            "/diagnostics/automatic",
            "/network/dhcp",
            "/network/dhcp/update",
            "/network/dhcp/reservation/save",
            "/network/dhcp/reservation/delete",
            "/network/port-forwarding",
            "/network/port-forwarding/save",
            "/network/port-forwarding/delete",
            "/network/dmz",
            "/network/dmz/update",
            "/system/backup",
            "/history",
            "/history/snapshot",
        )

        for endpoint in endpoints:
            self.assertIn(
                endpoint,
                ADVANCED_JS,
                msg=f"UI não usa a rota esperada: {endpoint}",
            )
            self.assertIn(
                endpoint,
                API,
                msg=f"Rota usada pela UI não registrada: {endpoint}",
            )

    def test_advanced_bundle_is_loaded(self):
        self.assertIn(
            "zte_manager/js/advanced.js",
            INDEX,
        )
        self.assertIn(
            'data-page="advanced"',
            INDEX,
        )

    def test_destructive_routes_require_confirmation_fields(self):
        service = (
            ROOT
            / "apps"
            / "zte_manager"
            / "services"
            / "zte_service.py"
        ).read_text(encoding="utf-8")

        schemas = (
            ROOT
            / "apps"
            / "zte_manager"
            / "schemas.py"
        ).read_text(encoding="utf-8")

        self.assertIn(
            "Confirme explicitamente a alteração da DMZ.",
            service,
        )
        self.assertIn(
            "confirm: bool = False",
            schemas,
        )


if __name__ == "__main__":
    unittest.main()

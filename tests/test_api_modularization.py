from __future__ import annotations

import importlib
import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
API_ROOT = ROOT / "apps" / "zte_manager" / "presentation" / "api"
COMPOSITION_ROOT = ROOT / "apps" / "zte_manager" / "api.py"


class ApiModularizationTests(unittest.TestCase):
    def test_composition_root_has_no_route_implementations(self):
        source = COMPOSITION_ROOT.read_text(encoding="utf-8")
        self.assertNotRegex(source, r"@api\.(?:get|post|put|delete|patch)\(")
        self.assertLess(len(source.splitlines()), 80)
        self.assertIn("presentation.api.system", source)
        self.assertIn("presentation.api.management_artifacts", source)

    def test_http_controllers_do_not_read_private_zte_service_state(self):
        violations: list[str] = []
        pattern = re.compile(r"zte_service\s*\.\s*_[A-Za-z0-9_]+")
        for path in sorted(API_ROOT.glob("*.py")):
            source = path.read_text(encoding="utf-8")
            for match in pattern.finditer(source):
                violations.append(f"{path.name}: {match.group(0)}")
        self.assertEqual(violations, [])

    def test_common_provider_dispatch_is_device_service_first(self):
        source = (API_ROOT / "common.py").read_text(encoding="utf-8")
        self.assertIn("return device_service", source)
        self.assertNotIn("if device_service.vendor == \"huawei\":\n        return device_service\n    return zte_service", source)

    def test_legacy_import_surface_reexports_key_handlers(self):
        module = importlib.import_module("apps.zte_manager.api")
        expected = {
            "health",
            "connect",
            "disconnect",
            "connection_status",
            "device_status",
            "wan_status",
            "wifi_networks",
            "get_radios",
            "set_radio",
            "dns_status",
            "ping",
            "automatic_diagnostic",
            "capability_catalog",
            "discovery_bootstrap",
            "f6201b_workbench_catalog",
            "current_configuration",
            "profiles",
            "management_inventory",
            "management_mesh_status",
            "management_backups",
            "management_acs_status",
        }
        missing = sorted(name for name in expected if not hasattr(module, name))
        self.assertEqual(missing, [])

    def test_route_ownership_is_spread_across_domain_modules(self):
        route_counts = {}
        for path in sorted(API_ROOT.glob("*.py")):
            if path.name in {"__init__.py", "common.py"}:
                continue
            source = path.read_text(encoding="utf-8")
            route_counts[path.name] = len(re.findall(
                r"@api\.(?:get|post|put|delete|patch)\(", source
            ))
        self.assertGreaterEqual(len([count for count in route_counts.values() if count]), 10)
        self.assertLess(max(route_counts.values(), default=0), 40)


if __name__ == "__main__":
    unittest.main()

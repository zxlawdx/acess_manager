from __future__ import annotations

import unittest
from pathlib import Path
from types import SimpleNamespace

from apps.zte_manager.model.session import DeviceSession
from apps.zte_manager.services.device_service import DeviceService


ROOT = Path(__file__).resolve().parents[1]
API_ROOT = ROOT / "apps" / "zte_manager" / "presentation" / "api"
SERVICES_ROOT = ROOT / "apps" / "zte_manager" / "services"
INFRA_ROOT = ROOT / "apps" / "zte_manager" / "infrastructure"
MODEL_ROOT = ROOT / "apps" / "zte_manager" / "model"

# Direct ZTE singleton calls from controllers are no longer allowed. Explicit
# F6201B routes remain vendor-specific but must resolve through the active ZTE
# workspace rather than the global singleton.
CURRENT_DIRECT_ZTE_CONTROLLER_EXCEPTIONS: set[str] = set()


class SpyZTEProvider:
    def __init__(self) -> None:
        self.connected = False
        self.calls: list[str] = []
        self._zte = SimpleNamespace(writes_enabled=True)
        self._selected_model = "F6201B"
        self._model_verified = True
        self._adapter = SimpleNamespace(name="zte-f6201b-thinklua")
        self._session_revision = "zte-rev"
        self.current_host = "192.168.1.1"
        self.current_attendant = "qa"

    def _mark(self, name, result):
        self.calls.append(name)
        return result

    def connect(self, **kwargs):
        self.connected = True
        return {
            "success": True,
            "model": "F6201B",
            "adapter": "zte-f6201b-thinklua",
            "model_verified": True,
            "host": kwargs["ip"],
            "attendant": kwargs.get("attendant"),
        }

    def disconnect(self):
        self.connected = False

    def multimodel_catalog(self):
        return self._mark("multimodel_catalog", {"models": [{"model": "F6201B"}]})

    def multimodel_diagnostic(self, model=None, section=None):
        return self._mark("multimodel_diagnostic", {"model": model, "section": section})

    def multimodel_mesh(self, model=None):
        return self._mark("multimodel_mesh", {"model": model, "available": True})

    def multimodel_probe(self, model=None, count=4, start=0):
        return self._mark(
            "multimodel_probe",
            {"model": model, "count": count, "start": start},
        )

    def read_capability(self, feature):
        return self._mark("read_capability", {"feature": feature})


class SpyHuaweiProvider:
    connected = True
    writes_enabled = True
    capabilities = {
        "wifi_basic": {"read": True, "write": True, "verified": True},
        "dhcp": {"read": True, "write": False, "verified": True},
    }

    def __init__(self) -> None:
        self.calls: list[str] = []

    def disconnect(self):
        self.connected = False

    def capability_catalog(self):
        self.calls.append("capability_catalog")
        return {
            "features": {
                "wifi_basic": {
                    "label": "Wi-Fi",
                    "operations": {
                        "read": True,
                        "write": True,
                        "verified": True,
                    },
                    "evidence_states": ["FULLY_INTEGRATED"],
                }
            }
        }

    def read_capability(self, feature, *, refresh=False):
        self.calls.append("read_capability")
        return {"feature": feature, "refresh": refresh}

    def apply_profile(self, attendant=None):
        self.calls.append("apply_profile")
        return {"success": True, "provider": "huawei", "attendant": attendant}


class VendorIsolationRuntimeTests(unittest.TestCase):
    def make_huawei_manager(self):
        zte = SpyZTEProvider()
        manager = DeviceService(zte_provider=zte)
        huawei = SpyHuaweiProvider()
        manager._session = DeviceSession(
            vendor="huawei",
            model="EG8041X6-10",
            profile="huawei_eg8041x6_10",
            provider="SpyHuaweiProvider",
            service=huawei,
            capabilities=huawei.capabilities,
            model_verified=True,
            host="192.168.18.1",
            attendant="qa",
            mode="supported",
        )
        return manager, huawei, zte

    def test_huawei_generic_discovery_and_capabilities_never_touch_zte(self):
        manager, huawei, zte = self.make_huawei_manager()

        bootstrap = manager.discovery_bootstrap()
        catalog = manager.multimodel_catalog()
        diagnostic = manager.multimodel_diagnostic("ignored", "wifi")
        mesh = manager.multimodel_mesh("ignored")
        probe = manager.multimodel_probe("ignored", 4, 0)
        feature = manager.read_capability("wifi_basic", refresh=True)

        self.assertEqual(bootstrap["vendor"], "huawei")
        self.assertEqual(catalog["models"][0]["family"], "huawei_webui")
        self.assertEqual(diagnostic["family"], "huawei_webui")
        self.assertFalse(mesh["available"])
        self.assertEqual(probe["family"], "huawei_webui")
        self.assertTrue(feature["refresh"])
        self.assertEqual(zte.calls, [])
        self.assertIn("capability_catalog", huawei.calls)

    def test_huawei_profile_apply_stays_on_active_huawei_provider(self):
        manager, huawei, zte = self.make_huawei_manager()
        result = manager.apply_profile("qa")

        self.assertTrue(result["success"])
        self.assertEqual(result["provider"], "huawei")
        self.assertEqual(huawei.calls, ["apply_profile"])
        self.assertEqual(zte.calls, [])

    def test_zte_discovery_path_never_constructs_huawei_provider(self):
        zte = SpyZTEProvider()

        def forbidden_huawei_factory():
            raise AssertionError("Huawei provider must not be constructed for ZTE")

        class NoHuaweiFingerprint:
            @classmethod
            def looks_like_huawei(cls, host, *, https=False, timeout=2.5):
                return False

        manager = DeviceService(
            zte_provider=zte,
            huawei_factory=forbidden_huawei_factory,
            huawei_client_type=NoHuaweiFingerprint,
        )
        manager.connect("192.168.1.1", "admin", "fixture", model_hint="F6201B")

        bootstrap = manager.discovery_bootstrap()
        manager.multimodel_diagnostic("F6201B", "wifi")
        manager.multimodel_mesh("F6201B")
        manager.multimodel_probe("F6201B", 2, 0)
        manager.read_capability("wifi_basic", refresh=True)

        self.assertEqual(bootstrap["vendor"], "zte")
        self.assertEqual(
            zte.calls,
            [
                "multimodel_catalog",
                "multimodel_diagnostic",
                "multimodel_mesh",
                "multimodel_probe",
                "read_capability",
            ],
        )


class VendorIsolationSourceTests(unittest.TestCase):
    def test_huawei_runtime_files_do_not_import_zte_protocol_runtime(self):
        paths = list(SERVICES_ROOT.glob("huawei_*.py"))
        paths.extend((INFRA_ROOT / "huawei").rglob("*.py"))
        forbidden = (
            "apps.zte_manager.services.zte_service",
            "apps.zte_manager.services.f6201b_",
            "apps.zte_manager.model.zte",
            "/f6201b",
        )
        violations = []
        for path in sorted(set(paths)):
            source = path.read_text(encoding="utf-8")
            for token in forbidden:
                if token in source:
                    violations.append(f"{path.relative_to(ROOT)} -> {token}")
        self.assertEqual(violations, [])

    def test_zte_runtime_files_do_not_import_huawei_protocol_runtime(self):
        paths = [SERVICES_ROOT / "zte_service.py", MODEL_ROOT / "zte.py"]
        paths.extend(SERVICES_ROOT.glob("f6201b_*.py"))
        paths.extend((MODEL_ROOT / "zte_configuration").rglob("*.py"))
        forbidden = (
            "apps.zte_manager.infrastructure.huawei",
            "apps.zte_manager.services.huawei_",
            "HuaweiService",
            "/html/bbsp/",
            "/html/amp/",
        )
        violations = []
        for path in sorted(set(paths)):
            if not path.exists():
                continue
            source = path.read_text(encoding="utf-8")
            for token in forbidden:
                if token in source:
                    violations.append(f"{path.relative_to(ROOT)} -> {token}")
        self.assertEqual(violations, [])

    def test_generic_capability_controller_has_no_vendor_dispatch(self):
        source = (API_ROOT / "capabilities.py").read_text(encoding="utf-8")
        self.assertNotIn("zte_service.", source)
        self.assertNotIn('status.get("vendor") == "huawei"', source)
        self.assertNotIn('device_service.vendor == "huawei"', source)

    def test_generic_read_facade_has_no_vendor_dispatch(self):
        source = (API_ROOT / "common.py").read_text(encoding="utf-8")
        self.assertNotIn('device_service.vendor == "huawei"', source)
        self.assertNotIn("services.zte_service", source)
        self.assertIn("ProviderRouter.invoke", source)

    def test_profile_controller_is_provider_neutral(self):
        source = (API_ROOT / "profiles.py").read_text(encoding="utf-8")
        self.assertNotIn("zte_service", source)
        self.assertNotIn("f6201b", source.casefold())
        self.assertIn("device_service.apply_profile", source)
        self.assertIn("device_service.apply_named_preset", source)

    def test_f6201b_controller_does_not_call_global_zte_singleton(self):
        source = (API_ROOT / "f6201b.py").read_text(encoding="utf-8")
        self.assertNotIn("zte_service.", source)
        self.assertIn("_call_f6201b", source)

    def test_direct_zte_controller_exception_list_cannot_grow_silently(self):
        actual = set()
        for path in API_ROOT.glob("*.py"):
            if "zte_service." in path.read_text(encoding="utf-8"):
                actual.add(path.name)
        self.assertEqual(actual, CURRENT_DIRECT_ZTE_CONTROLLER_EXCEPTIONS)


if __name__ == "__main__":
    unittest.main()

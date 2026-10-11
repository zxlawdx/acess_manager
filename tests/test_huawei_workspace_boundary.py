from __future__ import annotations

import unittest
from pathlib import Path
from types import SimpleNamespace

from apps.zte_manager.services.device_service import DeviceService
from apps.zte_manager.vendors.huawei import HuaweiWorkspace


ROOT = Path(__file__).resolve().parents[1]


class FakeZTE:
    def __init__(self) -> None:
        self.connected = False
        self.calls = []
        self._zte = SimpleNamespace(writes_enabled=True)

    def connect(self, **kwargs):
        self.calls.append("connect")
        self.connected = True
        return {"model": "F6201B", "adapter": "zte", "model_verified": True}

    def disconnect(self):
        self.calls.append("disconnect")
        self.connected = False


class FakeHuaweiRuntime:
    writes_enabled = True

    def __init__(self) -> None:
        self.connected = False
        self.calls = []
        self.capabilities = {"wifi_basic": {"read": True, "write": True}}

    def connect(self, **kwargs):
        self.calls.append(("connect", dict(kwargs)))
        self.connected = True
        return {
            "success": True,
            "vendor": "huawei",
            "model": "EG8041X7-10",
            "profile": "huawei_eg8041x7_10",
            "model_verified": True,
            "host": kwargs["ip"],
            "attendant": kwargs.get("attendant"),
            "capabilities": self.capabilities,
            "protocol_family": "AMP_BBSP",
        }

    def disconnect(self):
        self.calls.append(("disconnect", {}))
        self.connected = False

    def device_status(self):
        self.calls.append(("device_status", {}))
        return {"fabricante": "Huawei", "modelo": "EG8041X7-10"}


class HuaweiWorkspaceBoundaryTests(unittest.TestCase):
    def test_workspace_delegates_without_reimplementing_protocol(self):
        provider = FakeHuaweiRuntime()
        workspace = HuaweiWorkspace(provider)

        result = workspace.connect(
            ip="192.168.18.1",
            username="admin",
            password="fixture",
        )
        status = workspace.device_status()

        self.assertTrue(result["success"])
        self.assertEqual(status["fabricante"], "Huawei")
        self.assertIs(workspace.provider, provider)
        self.assertTrue(workspace.connected)
        self.assertTrue(workspace.writes_enabled)

    def test_device_service_uses_workspace_but_keeps_raw_service_compatibility(self):
        zte = FakeZTE()
        created = []

        def factory():
            provider = FakeHuaweiRuntime()
            created.append(provider)
            return provider

        manager = DeviceService(zte_provider=zte, huawei_factory=factory)
        result = manager.connect(
            "192.168.18.1",
            "admin",
            "fixture",
            model_hint="EG8041X7-10",
            attendant="qa",
        )

        self.assertEqual(result["vendor"], "huawei")
        self.assertEqual(len(created), 1)
        self.assertIs(manager.session.service, created[0])
        self.assertIsInstance(manager.session.workspace, HuaweiWorkspace)
        self.assertIs(manager.active_service, manager.session.workspace)
        self.assertEqual(manager.device_status()["fabricante"], "Huawei")
        self.assertEqual(zte.calls, [])

    def test_huawei_workspace_source_has_no_zte_runtime_dependency(self):
        source = (
            ROOT / "apps" / "zte_manager" / "vendors" / "huawei" / "workspace.py"
        ).read_text(encoding="utf-8")
        self.assertNotIn("zte_service", source)
        self.assertNotIn("f6201b", source.casefold())
        self.assertNotIn("apps.zte_manager.model.zte", source)


if __name__ == "__main__":
    unittest.main()

from __future__ import annotations

import unittest
from types import SimpleNamespace

from apps.zte_manager.services.device_service import DeviceService
from apps.zte_manager.vendors.deployment import (
    DeploymentWorkspace,
    DeploymentWriteBlocked,
)
from apps.zte_manager.vendors.huawei import HuaweiWorkspace


class AlwaysHuawei:
    @classmethod
    def looks_like_huawei(cls, host, *, https=False, timeout=2.5):
        return True


class NeverHuawei:
    @classmethod
    def looks_like_huawei(cls, host, *, https=False, timeout=2.5):
        return False


class FakeHuaweiUnknown:
    connected = False
    writes_enabled = True

    def __init__(self, model="HUAWEI-MYSTERY-9000"):
        self.model = model
        self.capabilities = {"wifi": {"read": True, "write": True}}

    def connect(self, **kwargs):
        self.connected = True
        return {
            "success": True,
            "model": self.model,
            "profile": "huawei_unknown",
            "model_verified": False,
            "host": kwargs["ip"],
            "capabilities": self.capabilities,
        }

    def disconnect(self):
        self.connected = False

    def device_status(self):
        return {"model": self.model}

    def apply_profile(self, attendant=None):
        raise AssertionError("deployment must block mutation before provider call")


class FakeZTEUnknown:
    connected = False

    def __init__(self):
        self._zte = SimpleNamespace(writes_enabled=True)

    def connect(self, **kwargs):
        self.connected = True
        return {
            "success": True,
            "model": "ZXHN MYSTERY 9000",
            "adapter": "zte-thinklua",
            "model_verified": False,
            "host": kwargs["ip"],
        }

    def disconnect(self):
        self.connected = False

    def device_status(self):
        return {"model": "ZXHN MYSTERY 9000"}


class DeploymentWorkspaceTests(unittest.TestCase):
    def test_unknown_huawei_enters_read_only_deployment_mode(self):
        runtime = FakeHuaweiUnknown()
        manager = DeviceService(
            zte_provider=FakeZTEUnknown(),
            huawei_factory=lambda: runtime,
            huawei_client_type=AlwaysHuawei,
        )
        result = manager.connect("192.168.18.1", "admin", "fixture")

        self.assertEqual(result["provider"], "DeploymentWorkspace")
        self.assertEqual(manager.status()["mode"], "deployment")
        self.assertFalse(manager.status()["writes_enabled"])
        self.assertIsInstance(manager.session.workspace, DeploymentWorkspace)
        self.assertEqual(manager.device_status()["model"], runtime.model)
        with self.assertRaises(DeploymentWriteBlocked):
            manager.apply_profile("qa")

    def test_unknown_zte_enters_read_only_deployment_mode(self):
        runtime = FakeZTEUnknown()
        manager = DeviceService(
            zte_provider=runtime,
            huawei_factory=lambda: (_ for _ in ()).throw(
                AssertionError("Huawei must not be constructed")
            ),
            huawei_client_type=NeverHuawei,
        )
        result = manager.connect(
            "192.168.1.1", "admin", "fixture", model_hint="ZXHN MYSTERY 9000"
        )

        self.assertEqual(result["provider"], "DeploymentWorkspace")
        self.assertEqual(manager.status()["mode"], "deployment")
        self.assertFalse(manager.status()["writes_enabled"])
        self.assertEqual(manager.device_status()["model"], "ZXHN MYSTERY 9000")

    def test_recognized_partial_huawei_does_not_get_downgraded_to_deployment(self):
        runtime = FakeHuaweiUnknown(model="HG8010H")
        manager = DeviceService(
            zte_provider=FakeZTEUnknown(),
            huawei_factory=lambda: runtime,
            huawei_client_type=AlwaysHuawei,
        )
        manager.connect(
            "192.168.18.1", "admin", "fixture", model_hint="HG8010H"
        )

        self.assertEqual(manager.status()["mode"], "partial")
        self.assertIsInstance(manager.session.workspace, HuaweiWorkspace)
        self.assertNotIsInstance(manager.session.workspace, DeploymentWorkspace)


if __name__ == "__main__":
    unittest.main()

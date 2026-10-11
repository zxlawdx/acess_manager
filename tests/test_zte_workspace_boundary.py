from __future__ import annotations

import unittest
from pathlib import Path
from types import SimpleNamespace

from apps.zte_manager.services.device_service import DeviceService
from apps.zte_manager.vendors.zte import ZTEWorkspace


ROOT = Path(__file__).resolve().parents[1]


class FakeZTERuntime:
    def __init__(self) -> None:
        self.connected = False
        self.calls = []
        self._zte = SimpleNamespace(writes_enabled=True)
        self._selected_model = "F6201B"
        self._model_verified = True
        self._adapter = SimpleNamespace(name="zte-f6201b-thinklua")
        self._session_revision = "zte-rev"
        self.current_host = None
        self.current_attendant = None

    def connect(self, **kwargs):
        self.calls.append(("connect", dict(kwargs)))
        self.connected = True
        self.current_host = kwargs["ip"]
        self.current_attendant = kwargs.get("attendant")
        return {
            "success": True,
            "model": "F6201B",
            "adapter": "zte-f6201b-thinklua",
            "model_verified": True,
            "host": self.current_host,
            "attendant": self.current_attendant,
        }

    def disconnect(self):
        self.calls.append(("disconnect", {}))
        self.connected = False

    def wan_status(self):
        self.calls.append(("wan_status", {}))
        return {"status": "ok"}


class NeverHuawei:
    @classmethod
    def looks_like_huawei(cls, host, *, https=False, timeout=2.5):
        return False


class ZTEWorkspaceBoundaryTests(unittest.TestCase):
    def test_workspace_delegates_without_reimplementing_thinklua(self):
        provider = FakeZTERuntime()
        workspace = ZTEWorkspace(provider)
        result = workspace.connect(
            ip="192.168.1.1",
            username="admin",
            password="fixture",
        )

        self.assertTrue(result["success"])
        self.assertTrue(workspace.connected)
        self.assertTrue(workspace.writes_enabled)
        self.assertIs(workspace.provider, provider)
        self.assertEqual(workspace.wan_status(), {"status": "ok"})

    def test_device_service_uses_zte_workspace_and_keeps_raw_service(self):
        zte = FakeZTERuntime()

        def forbidden_huawei_factory():
            raise AssertionError("Huawei runtime must not be constructed")

        manager = DeviceService(
            zte_provider=zte,
            huawei_factory=forbidden_huawei_factory,
            huawei_client_type=NeverHuawei,
        )
        result = manager.connect(
            "192.168.1.1",
            "admin",
            "fixture",
            model_hint="F6201B",
            attendant="qa",
        )

        self.assertEqual(result["model"], "F6201B")
        self.assertIs(manager.session.service, zte)
        self.assertIsInstance(manager.session.workspace, ZTEWorkspace)
        self.assertIs(manager.active_service, manager.session.workspace)
        self.assertEqual(manager.wan_status(), {"status": "ok"})

    def test_zte_workspace_source_has_no_huawei_runtime_dependency(self):
        source = (
            ROOT / "apps" / "zte_manager" / "vendors" / "zte" / "workspace.py"
        ).read_text(encoding="utf-8")
        self.assertNotIn("Huawei", source)
        self.assertNotIn("infrastructure.huawei", source)
        self.assertNotIn("/html/bbsp", source)
        self.assertNotIn("/html/amp", source)


if __name__ == "__main__":
    unittest.main()

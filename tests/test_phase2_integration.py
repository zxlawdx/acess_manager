"""Phase-2 integration regression tests; synthetic transport and no real hardware."""
from __future__ import annotations

import importlib
import sqlite3
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

from apps.zte_manager.application.inventory.device_registrar import DeviceRegistrar
from apps.zte_manager.infrastructure.zte.adapters.thinklua_device import (
    DeviceWriteNotApproved,
)
from apps.zte_manager.infrastructure.zte.firmware_policy import FirmwarePolicy

service_module = importlib.import_module("apps.zte_manager.services.zte_service")


class FakeManagementRepository:
    def __init__(self, failure: Exception | None = None) -> None:
        self.records: list[dict] = []
        self.failure = failure

    def upsert_device(self, data: dict) -> dict:
        if self.failure is not None:
            raise self.failure
        self.records.append(data)
        return data


class FakeZTE:
    constructed: list["FakeZTE"] = []
    model = "ZXHN F670L"
    firmware = "V9.0.11P1N9"

    def __init__(self, ip: str, username: str, password: str, https: bool = False):
        self.__class__.constructed.append(self)
        self.base_url = ("https" if https else "http") + "://" + ip
        self.username = username
        self.password = password
        self.login_calls = 0
        self.device_calls = 0
        self.dhcp_calls = 0
        self.wifi_calls = 0
        self.posts = 0
        self.writes_enabled = False
        self.identity = {
            "fabricante": "ZTE", "modelo": self.__class__.model,
            "firmware": self.__class__.firmware, "serial": "SERIAL-IN-FIXTURE",
            "password": "never-store-this-secret",
            "irrelevant_large_dump": {"payload": "private"},
        }
        self.dhcp = {"basic": {"ServerEnable": "1"}, "lan_dns": {}}
        self.networks = [{"id": "AP1", "ssid": "old", "ativo": True}]
        self.session = SimpleNamespace(close=Mock(), post=self.post)

    def post(self, *args, **kwargs):
        self.posts += 1
        return None

    def login(self):
        self.login_calls += 1
        return True

    def device_status(self):
        self.device_calls += 1
        return dict(self.identity)

    def dhcp_status(self):
        self.dhcp_calls += 1
        return {
            "basic": dict(self.dhcp["basic"]),
            "lan_dns": dict(self.dhcp["lan_dns"]),
        }

    def set_dhcp_basic(self, values):
        self.dhcp["basic"]["ServerEnable"] = "1" if values.get("enabled") else "0"
        return {"success": True, "verified": True}

    def wifi_networks(self, reveal_password=False):
        self.wifi_calls += 1
        return [dict(item) for item in self.networks]

    def set_ssid_config(self, ssid_id, values):
        for net in self.networks:
            if net["id"] == ssid_id:
                net["ssid"] = values["ssid"]
        return {"success": True, "verified": True}


class DeviceRegistrarTests(unittest.TestCase):
    def test_register_uses_only_allowlisted_scalar_fields(self):
        repository = FakeManagementRepository()
        registrar = DeviceRegistrar(repository)
        self.assertTrue(registrar.register(
            host="192.0.2.10",
            device_info={
                "modelo": "F670L", "firmware": "V9.0.11P1N9",
                "serial": "SERIAL-FIXTURE", "mac": "AA:BB:CC:DD:EE:FF",
                "password": "DONOTSTORE", "token": "PRIVATE",
                "raw_xml": "<secret>not-for-inventory</secret>",
            },
            adapter_name="zte-f670l-thinklua", attendant="technician",
        ))
        entry = repository.records[0]
        self.assertEqual(entry["key"], "SERIAL-FIXTURE")
        self.assertEqual(entry["firmware"], "V9.0.11P1N9")
        self.assertEqual(entry["metadata"], {
            "adapter": "zte-f670l-thinklua", "attendant": "technician",
        })
        self.assertNotIn("DONOTSTORE", str(entry))
        self.assertNotIn("PRIVATE", str(entry))
        self.assertNotIn("raw_xml", str(entry))

    def test_sqlite_schema_error_returns_false_without_exposing_secrets(self):
        repository = FakeManagementRepository(
            sqlite3.OperationalError("password=SECRETPAYLOAD invalid schema"),
        )
        with self.assertLogs(
            "apps.zte_manager.application.inventory.device_registrar", "WARNING"
        ) as capture:
            result = DeviceRegistrar(repository).register(
                host="192.0.2.1",
                device_info={"modelo": "F670L", "password": "SECRET"},
                adapter_name="zte-f670l-thinklua",
            )
        self.assertFalse(result)
        logs = str(capture.output)
        self.assertIn("OperationalError", logs)
        self.assertNotIn("SECRETPAYLOAD", logs)
        self.assertNotIn("192.0.2.1", logs)
        self.assertNotIn("SECRET", logs.replace("SECRETPAYLOAD", ""))

    def test_invalid_identity_skips_storage(self):
        repository = FakeManagementRepository()
        with self.assertLogs(
            "apps.zte_manager.application.inventory.device_registrar", "WARNING"
        ):
            ok = DeviceRegistrar(repository).register(
                host=None, device_info={"password": "only secret"},
                adapter_name=None,
            )
        self.assertFalse(ok)
        self.assertEqual(repository.records, [])


class FirmwarePolicyTests(unittest.TestCase):
    def test_exact_known_firmware_and_explicit_approval_required(self):
        empty = FirmwarePolicy()
        self.assertFalse(empty.permits("ZTE", "F670L", "V9.0.11P1N9"))
        policy = FirmwarePolicy.from_approved({"F670L": ["V9.0.11P1N9"]})
        self.assertTrue(policy.permits(
            "ZTE", "ZXHN F670L", "V9.0.11P1N9"
        ))
        self.assertFalse(policy.permits("ZTE", "F670L", "V9.0.11P1N40"))
        self.assertFalse(policy.permits("ZTE", "F670L", "V9.0.11P1N9-HOTFIX"))
        self.assertFalse(policy.permits("Huawei", "F670L", "V9.0.11P1N9"))
        self.assertFalse(policy.permits("ZTE", "F6201B", "V9.3.10P7N7"))

    def test_invalid_environment_manifest_fails_closed(self):
        with patch.dict("os.environ", {
            "ZTE_APPROVED_FIRMWARE_JSON": '{"F670L": ["UNTESTED"]}'
        }):
            with self.assertLogs(
                "apps.zte_manager.infrastructure.zte.firmware_policy", "WARNING"
            ) as logs:
                policy = FirmwarePolicy.from_environment()
        self.assertEqual(policy.approved, {})
        self.assertNotIn("UNTESTED", str(logs.output))

    def test_cannot_approve_unknown_variant(self):
        with self.assertRaises(ValueError):
            FirmwarePolicy.from_approved({"F670L": ["V12.UNKNOWN"]})


class RealServiceIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.repo = FakeManagementRepository()
        self.registrar = DeviceRegistrar(self.repo)
        self.policy = FirmwarePolicy.from_approved({"F670L": ["V9.0.11P1N9"]})
        FakeZTE.constructed = []
        FakeZTE.model = "ZXHN F670L"
        FakeZTE.firmware = "V9.0.11P1N9"
        self.patchers = [
            patch.object(service_module, "ZTE", FakeZTE),
            patch.object(service_module.history_repository, "start_session", return_value=42),
            patch.object(service_module.history_repository, "save_snapshot"),
            patch.object(service_module.history_repository, "save_change"),
            patch.object(service_module.history_repository, "end_session"),
        ]
        for item in self.patchers:
            item.start()
            self.addCleanup(item.stop)
        self.service = service_module.ZTEService(
            registrar=self.registrar, firmware_policy=self.policy,
        )

    def connect(self):
        return self.service.connect(
            "192.0.2.1", "technician", "fixture-only-password",
            attendant="tester",
        )

    def test_login_binds_same_transport_without_second_login(self):
        response = self.connect()
        self.assertTrue(response["success"])
        self.assertTrue(response["writes_enabled"])
        self.assertTrue(response["model_verified"])
        self.assertTrue(response["adapter"].startswith("zte-f670l"))
        self.assertTrue(response["session_revision"])
        self.assertIs(self.service._runtime_driver._client, self.service._zte)
        self.assertEqual(len(FakeZTE.constructed), 1)
        self.assertEqual(self.service._zte.login_calls, 1)
        self.assertEqual(len(self.repo.records), 1)
        self.assertNotIn("never-store-this-secret", str(self.repo.records[0]))

    def test_ssid_dhcp_and_status_execute_through_bound_driver(self):
        self.connect()
        driver = self.service._runtime_driver
        self.assertIsNotNone(driver)
        with patch.object(driver, "get_wifi_config", wraps=driver.get_wifi_config) as read_wifi, \
             patch.object(driver, "set_wifi_config", wraps=driver.set_wifi_config) as write_wifi, \
             patch.object(driver, "get_lan_config", wraps=driver.get_lan_config) as read_lan, \
             patch.object(driver, "set_lan_config", wraps=driver.set_lan_config) as write_lan, \
             patch.object(driver, "read_device_status", wraps=driver.read_device_status) as read_info:
            self.assertEqual(self.service.device_status()["modelo"], "ZXHN F670L")
            self.assertEqual(self.service.wifi_networks()[0]["ssid"], "old")
            self.assertEqual(self.service.dhcp_status()["basic"]["ServerEnable"], "1")
            self.assertTrue(self.service.set_ssid_config(
                "AP1", {"ssid": "new"}
            )["verified"])
            self.assertTrue(self.service.set_dhcp_basic(
                {"enabled": False}
            )["verified"])
            read_wifi.assert_called()
            write_wifi.assert_called_once()
            read_lan.assert_called()
            write_lan.assert_called_once()
            read_info.assert_called()
        self.assertEqual(self.service.wifi_networks()[0]["ssid"], "new")

    def test_reuse_preserves_single_login_revision_and_driver(self):
        first = self.connect()
        driver = self.service._runtime_driver
        second = self.connect()
        self.assertTrue(second["reused_session"])
        self.assertEqual(second["session_revision"], first["session_revision"])
        self.assertIs(self.service._runtime_driver, driver)
        self.assertEqual(self.service._zte.login_calls, 1)
        self.assertEqual(len(self.repo.records), 1)

    def test_changed_firmware_rejects_reuse_and_write_without_post(self):
        self.connect()
        self.service._zte.identity["firmware"] = "V9.0.11P1N9-UPGRADE"
        with self.assertRaisesRegex(ValueError, "firmware mudou"):
            self.connect()
        with self.assertRaises(DeviceWriteNotApproved):
            self.service.set_dhcp_basic({"enabled": False})
        self.assertEqual(self.service._zte.posts, 0)

    def test_failure_in_both_sqlite_paths_does_not_break_authenticated_login(self):
        failing_registrar = DeviceRegistrar(FakeManagementRepository(
            sqlite3.OperationalError("secret=DO_NOT_LOG"),
        ))
        self.service._registrar = failing_registrar
        with patch.object(
            service_module.history_repository, "start_session",
            side_effect=sqlite3.OperationalError("token=DO_NOT_LOG"),
        ):
            with self.assertLogs(level="WARNING") as capture:
                result = self.connect()
        self.assertTrue(result["success"])
        self.assertTrue(result["writes_enabled"])
        self.assertIsNone(self.service._history_session_id)
        self.assertNotIn("DO_NOT_LOG", str(capture.output))

    def test_failed_snapshot_preserves_history_session_and_login(self):
        with patch.object(
            service_module.history_repository, "save_snapshot",
            side_effect=sqlite3.OperationalError("password=NOT_FOR_LOG"),
        ):
            with self.assertLogs(
                "apps.zte_manager.services.zte_service", "WARNING"
            ) as logs:
                response = self.connect()
        self.assertTrue(response["success"])
        self.assertEqual(self.service._history_session_id, 42)
        self.assertNotIn("NOT_FOR_LOG", str(logs.output))

    def test_unapproved_firmware_installs_read_only_driver_without_legacy_bypass(self):
        self.service._firmware_policy = FirmwarePolicy()
        self.service._driver_factory = lambda: (
            service_module.ThinkLuaDeviceAdapter(
                firmware_policy=self.service._firmware_policy,
            )
        )
        response = self.connect()
        self.assertFalse(response["writes_enabled"])
        self.assertIsNotNone(self.service._runtime_driver)
        with self.assertRaises(PermissionError):
            self.service._zte.session.post("http://example.invalid")
        with self.assertRaises(DeviceWriteNotApproved):
            self.service.set_ssid_config("AP1", {"ssid": "cant-write"})
        self.assertEqual(self.service._zte.posts, 0)

    def test_f6201b_remains_on_captured_legacy_path(self):
        FakeZTE.model = "ZXHN F6201B"
        FakeZTE.firmware = "V9.3.10P7N7"
        result = self.connect()
        self.assertFalse(result["writes_enabled"])
        self.assertIsNone(self.service._runtime_driver)
        self.assertIsNotNone(self.service._readonly_original_post)
        self.assertEqual(self.service._zte.login_calls, 1)


class DesktopCapabilitiesContractTests(unittest.TestCase):
    def test_host_python_is_authoritative_not_browser_user_agent(self):
        from apps.zte_manager.services.desktop_capabilities import (
            get_desktop_capabilities,
        )
        self.assertEqual(get_desktop_capabilities("win32"), {
            "platform": "win32",
            "native_clipboard": True,
            "web_clipboard_allowed": False,
            "webview_transport": "http",
        })
        self.assertEqual(get_desktop_capabilities("linux"), {
            "platform": "linux",
            "native_clipboard": False,
            "web_clipboard_allowed": True,
            "webview_transport": "http",
        })

    def test_real_get_endpoint_preserves_capability_contract(self):
        from apps.zte_manager import api as api_module
        with patch.object(
            api_module, "get_desktop_capabilities",
            return_value={
                "platform": "win32", "native_clipboard": True,
                "web_clipboard_allowed": False, "webview_transport": "http",
            }
        ) as host:
            data = api_module.desktop_capabilities(
                {"headers": {"User-Agent": "Fake Linux browser"}}
            )
        host.assert_called_once_with()
        self.assertEqual(data["platform"], "win32")
        self.assertFalse(data["web_clipboard_allowed"])

    def test_new_script_is_registered_before_support_diagnostics(self):
        from pathlib import Path
        template = (
            Path(__file__).resolve().parents[1]
            / "apps" / "zte_manager" / "templates" / "index.html"
        ).read_text(encoding="utf-8")
        self.assertLess(
            template.index("zte_manager/js/desktop_clipboard.js"),
            template.index("zte_manager/js/support_diagnostics.js"),
        )



if __name__ == "__main__":
    unittest.main()

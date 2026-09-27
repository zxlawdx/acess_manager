"""Hardware-independent contract tests: fake HTTP transport, no ONT writes."""
from __future__ import annotations

import unittest
from types import SimpleNamespace

from apps.zte_manager.application.contracts.device import (
    Credentials, DeviceAdapter, SessionContext,
)
from apps.zte_manager.infrastructure.zte.adapters import (
    ThinkLuaDeviceAdapter,
)
from apps.zte_manager.infrastructure.zte.adapters.thinklua_device import (
    DeviceWriteNotApproved,
)
from apps.zte_manager.infrastructure.zte.firmware_policy import FirmwarePolicy


class FakeZTE:
    def __init__(self, **kwargs):
        self.init = kwargs
        self.closed = False
        self.session = SimpleNamespace(close=self.close)
        self.identity = {
            "fabricante": "ZTE", "modelo": "F670L",
            "firmware": "V9.0.11P1N9", "serial": "LAB1",
        }
        self.dhcp = {
            "basic": {"ServerEnable": "1", "MinAddress": "192.168.1.20"},
            "lan_dns": {},
        }
        self.networks = [
            {"id": "AP1", "ssid": "original", "ativo": True, "password": "******"}
        ]
        self.commands = []

    def login(self):
        return True

    def close(self):
        self.closed = True

    def device_status(self):
        return dict(self.identity)

    def dhcp_status(self):
        return {
            "basic": dict(self.dhcp["basic"]),
            "lan_dns": dict(self.dhcp["lan_dns"]),
        }

    def set_dhcp_basic(self, values):
        self.commands.append("dhcp")
        if "enabled" in values:
            self.dhcp["basic"]["ServerEnable"] = "1" if values["enabled"] else "0"
        return {"success": True, "verified": True}

    def wifi_networks(self, reveal_password=False):
        if reveal_password:
            raise AssertionError("Read-only verifier must never reveal PSK")
        return [dict(item) for item in self.networks]

    def set_ssid_config(self, ssid_id, config):
        self.commands.append("wifi")
        for entry in self.networks:
            if entry["id"] == ssid_id:
                entry["ssid"] = config["ssid"]
        return {"success": True, "verified": True}


class DeviceRuntimeContractTests(unittest.TestCase):
    def setUp(self):
        self.clients = []

        def build(**kwargs):
            client = FakeZTE(**kwargs)
            self.clients.append(client)
            return client

        self.adapter = ThinkLuaDeviceAdapter(
            build,
            firmware_policy=FirmwarePolicy.from_approved(
                {"F670L": ["V9.0.11P1N9"]}
            ),
        )
        self.credentials = Credentials("192.0.2.1", "admin", "never-include-password")

    def test_is_runtime_protocol_with_real_methods(self):
        self.assertIsInstance(self.adapter, DeviceAdapter)
        self.assertNotIn("never-include-password", repr(self.credentials))
        session = self.adapter.authenticate(self.credentials)
        self.assertIsInstance(session, SessionContext)
        self.assertNotIn("192.0.2.1", repr(session))
        self.assertTrue(session.writable)
        self.assertEqual(self.adapter.read_info().model, "F670L")

    def test_dhcp_and_wifi_write_and_prove_their_specific_fields(self):
        self.adapter.authenticate(self.credentials)
        self.adapter.set_lan_config({"enabled": False})
        self.assertTrue(
            self.adapter.verify_change(
                "lan.dhcp", {"basic": {"ServerEnable": "0"}}
            )
        )
        self.assertFalse(
            self.adapter.verify_change(
                "lan.dhcp", {"basic": {"ServerEnable": "1"}}
            )
        )
        self.adapter.set_wifi_config(
            {"ssid_id": "AP1", "changes": {"ssid": "tested"}}
        )
        self.assertTrue(
            self.adapter.verify_change(
                "wifi.ssid", {"id": "AP1", "ssid": "tested"}
            )
        )
        self.assertFalse(
            self.adapter.verify_change("wifi.ssid", {"id": "AP1"})
        )
        self.assertFalse(
            self.adapter.verify_change(
                "wifi.ssid", {"id": "AP1", "password": "unknown"}
            )
        )
        self.assertFalse(self.adapter.verify_change("unknown", {"x": "y"}))
        self.assertEqual(self.clients[0].commands, ["dhcp", "wifi"])

    def test_known_model_writes_by_default_without_firmware_approval(self):
        adapter = ThinkLuaDeviceAdapter(
            lambda **kwargs: FakeZTE(**kwargs),
            firmware_policy=FirmwarePolicy(),
        )
        session = adapter.authenticate(self.credentials)
        self.assertTrue(session.writable)
        result = adapter.set_lan_config({"enabled": False})
        self.assertTrue(result["success"])

    def test_unlisted_firmware_version_is_not_a_write_permission_gate(self):
        def new_version(**kwargs):
            client = FakeZTE(**kwargs)
            client.identity["firmware"] = "OPERATOR-FIRMWARE-NO-CATALOG"
            return client

        adapter = ThinkLuaDeviceAdapter(
            new_version, firmware_policy=FirmwarePolicy(),
        )
        session = adapter.authenticate(self.credentials)
        self.assertTrue(session.writable)
        self.assertTrue(adapter.set_lan_config({"enabled": False})["success"])

    def test_unknown_model_is_read_only_not_implicitly_approved_by_probe(self):
        def unknown(**kwargs):
            client = FakeZTE(**kwargs)
            client.identity["modelo"] = "FUTURE-BRAND"
            return client

        adapter = ThinkLuaDeviceAdapter(unknown)
        session = adapter.authenticate(self.credentials)
        self.assertFalse(session.writable)
        self.assertEqual(
            adapter.get_lan_config()["basic"]["ServerEnable"], "1"
        )
        with self.assertRaises(DeviceWriteNotApproved):
            adapter.set_lan_config({"enabled": False})

    def test_changed_device_identity_blocks_write(self):
        self.adapter.authenticate(self.credentials)
        self.clients[0].identity["serial"] = "DIFFERENT-LAB"
        with self.assertRaises(DeviceWriteNotApproved):
            self.adapter.set_lan_config({"enabled": False})
        self.assertFalse(
            self.adapter.verify_change(
                "lan.dhcp", {"basic": {"ServerEnable": "1"}}
            )
        )

    def test_close_is_local_and_idempotent(self):
        self.adapter.authenticate(self.credentials)
        self.adapter.close()
        self.adapter.close()
        self.assertTrue(self.clients[0].closed)
        with self.assertRaises(RuntimeError):
            self.adapter.get_wifi_config()


if __name__ == "__main__":
    unittest.main()

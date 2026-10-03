from __future__ import annotations

import unittest

from apps.zte_manager.model.device_adapters.huawei import (
    HuaweiEG8041X7Profile,
)
from apps.zte_manager.services.huawei_service import HuaweiService


class FakeClient:
    def close(self):
        return None


class CountingCaptured:
    def __init__(self):
        self.calls = []
        self.radio = {
            "id": "radio-24",
            "banda": "2.4GHz",
            "canal": "1",
            "canal_automatico": False,
            "pais": "BR",
            "potencia": "100%",
            "beacon_interval": 100,
            "rts_cts": 2346,
            "dtim": 1,
        }

    def _read(self, name, value):
        self.calls.append(name)
        return value

    def device_status(self):
        return self._read("device", {
            "fabricante": "Huawei",
            "modelo": "EG8041X7-10",
            "uptime": "86400",
        })

    def optical_status(self):
        return self._read("optical", {"rx": "-20.1", "tx": "2.1"})

    def wan_status(self):
        return self._read("wan", [{
            "id": "wan1",
            "nome": "1_TR069_INTERNET_R_VID_2000",
            "services": "TR069_INTERNET",
            "status": "Connected",
        }])

    def pppoe_status(self, reveal_password=False):
        return self._read("pppoe", [{
            "id": "wan1",
            "username": "subscriber",
            "password": "secret" if reveal_password else "",
            "password_hidden": not reveal_password,
        }])

    def lan_ports(self):
        return self._read("lan_ports", [{"porta": "LAN1", "status": "Up"}])

    def wifi_networks(self, reveal_password=False):
        return self._read("wifi_networks", [{
            "id": "InternetGatewayDevice.LANDevice.1.WLANConfiguration.1",
            "banda": "2.4GHz",
            "ssid": "LAB24",
            "ativo": True,
            "broadcast": True,
            "max_clientes": 64,
            "password": "",
            "password_hidden": True,
        }])

    def wifi_radios(self):
        return self._read("wifi_radios", [dict(self.radio)])

    def dns_status(self):
        return self._read("dns", {
            "domain_name": "lab",
            "ipv4_1": "1.1.1.1",
            "hosts": [],
            "_search_rows": [],
        })

    def lan_clients(self):
        return self._read("lan_clients", [{
            "mac": "00:11:22:33:44:55",
            "ip": "192.168.18.10",
        }])

    def wifi_clients(self):
        return self._read("wifi_clients", [{
            "mac": "00:AA:BB:CC:DD:EE",
            "ip": "192.168.18.20",
        }])

    def tr069_management_status(self):
        return self._read("tr069", {
            "available": True,
            "server": {
                "URL": "http://acs.example/",
                "DefaultWan": "wan1",
            },
        })

    def firewall_level_status(self):
        return self._read("firewall_level", {
            "available": True,
            "firewall": {"Enable": "1", "AdvancedLevel": "1"},
        })

    def dos_status(self):
        return self._read("dos", {"SynFloodEn": "1"})

    def alg_status(self):
        return self._read("alg", {"FtpEnable": "1"})

    def igmp_status(self):
        return self._read("igmp", {"IGMPEnable": "1"})

    def ipv6_firewall_status(self):
        return self._read(
            "ipv6_firewall",
            {"X_HW_IPv6FWDFireWallEnable": "1"},
        )

    def internet_control_status(self):
        return self._read("internet_control", {"Enable": "1"})

    def dhcp_status(self):
        return self._read("dhcp", {
            "basic": {"DHCPServerEnable": "1"},
            "reservations": [],
            "leases": [],
        })

    def set_wifi_radio(self, band, config):
        self.calls.append("wifi_radio_write")
        self.last_radio_config = dict(config)
        self.calls.append("wifi_radio_readback")
        self.radio = {
            **self.radio,
            "banda": band,
            "canal": str(config.get("channel") or self.radio["canal"]),
            "canal_automatico": bool(config.get("auto_channel", False)),
        }
        return {
            "success": True,
            "verified": True,
            "uncertain": False,
            "readback": dict(self.radio),
        }


class CountingIPv4Filter:
    def __init__(self):
        self.calls = []
        self.rule = {
            "domain": "InternetGatewayDevice.X_HW_Security.IpFilterIn.1",
            "name": "LAB",
            "protocol": "TCP",
            "direction": "Bidirectional",
            "lan_start_ip": "192.168.18.10",
            "lan_end_ip": "192.168.18.10",
            "wan_start_ip": "203.0.113.10",
            "wan_end_ip": "203.0.113.10",
            "lan_tcp_port": "41001",
            "lan_udp_port": "",
            "wan_tcp_port": "42002",
            "wan_udp_port": "",
        }

    def list_ipv4_filters(self):
        self.calls.append("ipv4_filter_read")
        return {"available": True, "rules": [dict(self.rule)]}

    def update_ipv4_filter(self, instance_or_domain, rule):
        self.calls.append("ipv4_filter_write")
        self.calls.append("ipv4_filter_readback")
        self.rule = {**rule.as_dict(), "domain": self.rule["domain"]}
        return {
            "success": True,
            "verified": True,
            "uncertain": False,
            "rule": dict(self.rule),
        }


class HuaweiSessionSnapshotTests(unittest.TestCase):
    def make_service(self):
        service = HuaweiService()
        service._client = FakeClient()
        service._profile = HuaweiEG8041X7Profile()
        service._captured = CountingCaptured()
        service._ipv4_filter = CountingIPv4Filter()
        service._capabilities = {
            "ipv4_filter": service._profile.ipv4_filter.as_dict(),
            **{
                key: dict(value)
                for key, value in service._profile.captured_features.items()
            },
        }
        service.current_host = "192.168.18.1"
        service.current_attendant = "tester"
        service.model = "EG8041X7-10"
        service.model_verified = True
        service.session_revision = "session-a"
        service._clear_session_snapshot()
        return service

    @staticmethod
    def warm(service):
        service.device_status()
        service.optical_status()
        service.wan_status()
        service.pppoe_status()
        service.lan_ports()
        service.wifi_networks()
        service.wifi_radios()
        service.dns_status()
        service.lan_clients()
        service.wifi_clients()
        service.dhcp_status()
        service.tr069_management_status()
        service.firewall_management_status()
        service.dos_status()
        service.alg_status()
        service.igmp_status()
        service.ipv6_firewall_status()
        service.internet_control_status()
        service.list_ipv4_filters()

    def test_navigation_reads_zero_router_calls_after_initial_snapshot(self):
        service = self.make_service()
        self.warm(service)
        service._captured.calls.clear()
        service._ipv4_filter.calls.clear()

        # Dashboard -> Wi-Fi -> Clients -> WAN -> Device -> Profiles ->
        # TR-069 -> Advanced -> Wi-Fi again. These are the provider reads
        # the old page-open handlers used to repeat.
        service.device_status()
        service.optical_status()
        service.wifi_networks()
        service.wifi_radios()
        service.lan_clients()
        service.wifi_clients()
        service.wan_status()
        service.pppoe_status()
        service.lan_ports()
        service.tr069_management_status()
        service.list_ipv4_filters()
        service.firewall_management_status()
        service.dos_status()
        service.alg_status()
        service.igmp_status()
        service.ipv6_firewall_status()
        service.internet_control_status()
        for _ in range(10):
            service.wifi_networks()
            service.wifi_radios()

        self.assertEqual(service._captured.calls, [])
        self.assertEqual(service._ipv4_filter.calls, [])

    def test_profile_noop_does_not_submit_or_fake_history_change(self):
        service = self.make_service()
        service._captured.calls.clear()

        result = service._apply_profile_payload(
            {
                "wifi": {
                    "2.4GHz": {
                        "auto_channel": False,
                        "channel": 1,
                        "country": "BR",
                        "tx_power": "100%",
                        "bandwidth_code": "",
                    }
                }
            },
            operation="huawei_profile_apply",
            target="tester",
        )

        self.assertTrue(result["success"])
        self.assertEqual(result["steps"], [])
        self.assertIn("Wi-Fi 2.4GHz", result["unchanged"])
        self.assertNotIn("wifi_radio_write", service._captured.calls)

    def test_profile_change_preserves_unknown_bandwidth_when_raw_code_empty(self):
        service = self.make_service()
        service._captured.calls.clear()

        result = service._apply_profile_payload(
            {
                "wifi": {
                    "2.4GHz": {
                        "auto_channel": False,
                        "channel": 6,
                        "bandwidth_code": "",
                    }
                }
            },
            operation="huawei_profile_apply",
            target="tester",
        )

        self.assertTrue(result["verified"])
        self.assertEqual(
            service._captured.last_radio_config["channel"],
            6,
        )
        self.assertNotIn(
            "bandwidth_code",
            service._captured.last_radio_config,
        )

    def test_explicit_clients_refresh_touches_only_clients(self):
        service = self.make_service()
        self.warm(service)
        service._captured.calls.clear()

        service.lan_clients(refresh=True)
        service.wifi_clients(refresh=True)

        self.assertEqual(
            service._captured.calls,
            ["lan_clients", "wifi_clients"],
        )

    def test_radio_mutation_updates_only_radio_snapshot(self):
        service = self.make_service()
        self.warm(service)
        before = service.session_snapshot()["state"]
        service._captured.calls.clear()

        result = service.set_wifi_radio(
            "2.4GHz",
            {"auto_channel": False, "channel": 6},
        )

        self.assertTrue(result["verified"])
        self.assertEqual(
            service._captured.calls,
            ["wifi_radio_write", "wifi_radio_readback"],
        )
        self.assertEqual(service.wifi_radios()[0]["canal"], "6")
        after = service.session_snapshot()["state"]
        self.assertEqual(after["dns"], before["dns"])
        self.assertEqual(after["wan"], before["wan"])
        self.assertEqual(after["dhcp"], before["dhcp"])

    def test_ipv4_mutation_preserves_unrelated_capabilities_and_snapshot(self):
        service = self.make_service()
        self.warm(service)
        before_state = service.session_snapshot()["state"]
        before_caps = service.capabilities
        service._ipv4_filter.calls.clear()

        result = service.update_ipv4_filter(
            "InternetGatewayDevice.X_HW_Security.IpFilterIn.1",
            {
                "name": "LAB2",
                "protocol": "TCP",
                "direction": "Bidirectional",
                "lan_start_ip": "192.168.18.10",
                "lan_end_ip": "192.168.18.10",
                "wan_start_ip": "203.0.113.10",
                "wan_end_ip": "203.0.113.10",
                "lan_tcp_port": "41011",
                "wan_tcp_port": "42012",
            },
        )

        self.assertTrue(result["verified"])
        self.assertEqual(
            service._ipv4_filter.calls,
            ["ipv4_filter_write", "ipv4_filter_readback"],
        )
        after_state = service.session_snapshot()["state"]
        self.assertEqual(after_state["dns"], before_state["dns"])
        self.assertEqual(after_state["dhcp"], before_state["dhcp"])
        self.assertEqual(after_state["wifi_networks"], before_state["wifi_networks"])
        self.assertEqual(service.capabilities, before_caps)

    def test_session_revision_change_discards_old_snapshot(self):
        service = self.make_service()
        self.warm(service)
        self.assertTrue(service.session_snapshot()["loaded_resources"])

        service.current_host = "192.168.100.1"
        service.session_revision = "session-b"

        snapshot = service.session_snapshot()
        self.assertEqual(snapshot["loaded_resources"], [])
        self.assertEqual(snapshot["state"], {})

    def test_snapshot_never_keeps_session_secrets(self):
        service = self.make_service()
        service._snapshot_store("probe", {
            "password": "ont-secret",
            "CookieHttp": "cookie-secret",
            "X_HW_Token": "token-secret",
            "password_hidden": True,
            "ssid": "LAB24",
        })
        probe = service.session_snapshot()["state"]["probe"]
        self.assertNotIn("password", probe)
        self.assertNotIn("CookieHttp", probe)
        self.assertNotIn("X_HW_Token", probe)
        self.assertTrue(probe["password_hidden"])
        self.assertEqual(probe["ssid"], "LAB24")


if __name__ == "__main__":
    unittest.main()

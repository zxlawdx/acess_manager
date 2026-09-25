"""Independent DHCP feature discovery and captured server mapping tests."""
import unittest
from unittest.mock import Mock
from apps.zte_manager.services import f6201b_dhcp as dhcp


class FakeONT:
    def __init__(self):
        self.views = []
        self.calls = []
        self.fail_tag = None

    def get_view(self, name, **kwargs):
        self.views.append(name)
        return ""

    def get_menu(self, tag):
        self.calls.append(tag)
        if tag == self.fail_tag:
            raise RuntimeError("field not exposed")
        return tag

    def _validar_resposta(self, raw):
        assert raw

    def _parse_instances(self, raw):
        return {
            dhcp.BASIC: {"OBJ_Br0AndDhcpsHosCfg_ID": [{
                "_InstID": "DEV.DHCP.1", "ServerEnable": "1",
                "IPAddr": "192.0.2.1", "SubMask": "255.255.255.0",
                "MinAddress": "192.0.2.100",
                "MaxAddress": "192.0.2.200",
                "IPRouters": "192.0.2.1",
            }]},
            dhcp.LEASE: {"OBJ_DHCPHOSTINFO_ID": [{
                "HostName": "test", "IPAddr": "192.0.2.3"
            }]},
            dhcp.IPV6: {"OBJ_DHCP6S_ID": [{
                "_InstID": "DEV.DHCP6.1", "Enable": "0"
            }]},
        }.get(raw, {})


class DhcpTests(unittest.TestCase):
    def setUp(self):
        self.ont = FakeONT()

    def test_independent_ipv4_leases_and_ipv6_discovery(self):
        result = dhcp.status(self.ont)
        self.assertEqual(result["basic"]["_InstID"], "DEV.DHCP.1")
        self.assertEqual(result["leases"][0]["HostName"], "test")
        self.assertTrue(result["capabilities"]["server_write"])
        self.assertTrue(result["capabilities"]["ipv6_read"])
        self.assertFalse(result["capabilities"]["reservation_write"])

    def test_optional_lease_get_cannot_hide_ipv4_server(self):
        self.ont.fail_tag = dhcp.LEASE
        result = dhcp.status(self.ont)
        self.assertEqual(result["basic"]["IPAddr"], "192.0.2.1")
        self.assertFalse(result["capabilities"]["lease_read"])
        self.assertTrue(result["warnings"])

    def test_dhcp_change_delegates_all_fields_to_exact_captured_tag(self):
        bridge = Mock()
        bridge.apply_changes.return_value = {
            "success": True, "verified": True
        }
        config = {
            "enabled": False, "min_address": "192.0.2.101",
            "max_address": "192.0.2.199", "gateway": "192.0.2.1",
            "dns1": "1.1.1.1", "dns2": "9.9.9.9",
            "lease_time": 3600
        }
        result = dhcp.change(
            bridge, self.ont, config=config,
            host="192.0.2.10", revision="rev",
            attendant="tech", original_post=lambda: None
        )
        self.assertTrue(result["verified"])
        kw = bridge.apply_changes.call_args.kwargs
        self.assertEqual(kw["tag"], dhcp.BASIC)
        self.assertEqual(kw["instance_id"], "DEV.DHCP.1")
        self.assertEqual(kw["changes"]["ServerEnable"], "0")
        self.assertEqual(kw["changes"]["IPRouters"], "192.0.2.1")
        self.assertEqual(kw["changes"]["LeaseTime"], "3600")

    def test_unsupported_dhcp_field_rejected_before_post(self):
        bridge = Mock()
        with self.assertRaisesRegex(ValueError, "não expôs"):
            dhcp.change(bridge, self.ont, config={"unknown": "yes"},
                        host="device", revision="rev",
                        attendant="tech", original_post=None)
        bridge.apply_changes.assert_not_called()


if __name__ == "__main__":
    unittest.main()

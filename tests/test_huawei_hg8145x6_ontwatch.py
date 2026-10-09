from __future__ import annotations

import unittest

from apps.zte_manager.services.huawei_captured_features import (
    DEVICE_INFO_PAGE,
    WAN_CACHE_PAGE,
    WLAN_LIST_PAGE,
)
from apps.zte_manager.services.huawei_hg8145x6_runtime import (
    HG8145X6_ASSOCIATED_DEVICES_PAGE,
    HG8145X6_WLAN_INFO_PAGE,
    HuaweiHG8145X6CapturedFeatureService,
)
from apps.zte_manager.services.huawei_unified_provider import HuaweiUnifiedProvider


def _new(name: str, args: list[object]) -> str:
    encoded = ",".join(repr(str(value)) for value in args)
    return f"new {name}({encoded});"


class FakeHG8145Client:
    def __init__(self):
        wan = [""] * 44
        wan[0] = "InternetGatewayDevice.WANDevice.1.WANConnectionDevice.1.WANPPPConnection.1"
        wan[4] = "AA:BB:CC:DD:EE:01"
        wan[5] = "Connected"
        wan[6] = "ERROR_NONE"
        wan[8] = "INTERNET_R_VID_100"
        wan[12] = "Connected"
        wan[13] = "Route"
        wan[14] = "100.64.1.20"
        wan[15] = "100.64.1.1"
        wan[16] = "1"
        wan[18] = "1.1.1.1,8.8.8.8"
        wan[19] = "cliente@isp"
        wan[21] = "AlwaysOn"
        wan[23] = "100"
        wan[37] = "1492"
        wan[38] = "bras-pvh-01"
        wan[40] = "9876"
        wan[43] = "42"

        ssid_2g = [
            "InternetGatewayDevice.LANDevice.1.WLANConfiguration.1",
            "1", "LAW_2G", "", "", "2.4GHz",
        ]
        ssid_5g = [
            "InternetGatewayDevice.LANDevice.1.WLANConfiguration.5",
            "1", "LAW_5G", "", "", "5GHz",
        ]
        assoc = [
            "InternetGatewayDevice.LANDevice.1.WLANConfiguration.5",
            "AA:BB:CC:DD:EE:FF",
            "120", "866", "721", "-57", "-92", "35", "80",
            "11ax", "", "", "", "192.168.18.33", "phone-law", "2x2",
        ]
        packet = [
            "InternetGatewayDevice.LANDevice.1.WLANConfiguration.5",
            "100000", "1000", "250000", "2000",
        ]
        self.pages = {
            WAN_CACHE_PAGE: _new("WanPPP", wan),
            WLAN_LIST_PAGE: _new("stWlanInfo", ssid_2g) + _new("stWlanInfo", ssid_5g),
            HG8145X6_WLAN_INFO_PAGE: _new("stPacketInfo", packet),
            HG8145X6_ASSOCIATED_DEVICES_PAGE: _new("stAssociatedDevice", assoc),
            DEVICE_INFO_PAGE: "\n".join((
                "var dev_uptime = '54321';",
                "var cpuUsed = '17';",
                "var memUsed = '46';",
            )),
        }

    def get_page(self, path):
        if path not in self.pages:
            raise RuntimeError(f"unexpected path: {path}")
        return self.pages[path]


class HuaweiHG8145X6OntWatchTests(unittest.TestCase):
    def make_service(self):
        return HuaweiHG8145X6CapturedFeatureService(
            FakeHG8145Client(),
            model="HG8145X6-10",
            sleep=lambda _delay: None,
        )

    def test_source_signature_matches_ontwatch_contract(self):
        signature = self.make_service().source_signature()
        self.assertTrue(signature["compatible"])
        self.assertTrue(signature["endpoints"]["wan"]["readable"])
        self.assertTrue(signature["endpoints"]["clients"]["marker"])

    def test_wan_exposes_pppoe_bras_session_and_dns(self):
        rows = self.make_service().wan_status()
        self.assertEqual(len(rows), 1)
        wan = rows[0]
        self.assertEqual(wan["ip"], "100.64.1.20")
        self.assertEqual(wan["gateway"], "100.64.1.1")
        self.assertEqual(wan["dns"], ["1.1.1.1", "8.8.8.8"])
        self.assertEqual(wan["username"], "cliente@isp")
        self.assertEqual(wan["bras"], "bras-pvh-01")
        self.assertEqual(wan["session_id"], "42")
        self.assertEqual(wan["vlan"], 100)
        self.assertEqual(wan["mtu"], 1492)
        self.assertEqual(wan["uptime"], 9876)

    def test_wifi_clients_keep_signal_rates_mode_and_ssid(self):
        rows = self.make_service().wifi_clients()
        self.assertEqual(len(rows), 1)
        client = rows[0]
        self.assertEqual(client["hostname"], "phone-law")
        self.assertEqual(client["ip"], "192.168.18.33")
        self.assertEqual(client["ssid"], "LAW_5G")
        self.assertEqual(client["band"], "5GHz")
        self.assertEqual(client["rssi"], -57)
        self.assertEqual(client["snr"], 35)
        self.assertEqual(client["rx_rate"], 866)
        self.assertEqual(client["tx_rate"], 721)
        self.assertEqual(client["mode"], "11ax")
        self.assertEqual(client["antenna"], "2x2")

    def test_wifi_traffic_exposes_cumulative_per_ssid_counters(self):
        rows = self.make_service().wifi_traffic()
        self.assertEqual(len(rows), 1)
        traffic = rows[0]
        self.assertEqual(traffic["ssid"], "LAW_5G")
        self.assertEqual(traffic["tx_bytes"], 100000)
        self.assertEqual(traffic["rx_bytes"], 250000)
        self.assertEqual(traffic["counter_type"], "cumulative")
        self.assertEqual(traffic["scope"], "wlan_lan_side")

    def test_device_resources_parse_ontwatch_js_variables(self):
        status = self.make_service().device_status()
        self.assertEqual(status["uptime"], 54321)
        self.assertEqual(status["cpu_percent"], "17")
        self.assertEqual(status["memoria_percent"], "46")

    def test_unified_provider_recognizes_hg8145x6_aliases(self):
        for model in ("HG8145X6", "HG8145X6-10", "Huawei HG8145X6-10"):
            with self.subTest(model=model):
                self.assertTrue(HuaweiUnifiedProvider._is_hg8145x6_model(model))
        self.assertFalse(HuaweiUnifiedProvider._is_hg8145x6_model("EG8041X7-10"))


if __name__ == "__main__":
    unittest.main()

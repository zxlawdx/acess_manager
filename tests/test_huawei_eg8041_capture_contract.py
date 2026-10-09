from __future__ import annotations

import unittest

from apps.zte_manager.infrastructure.huawei import HuaweiMutationTransport
from apps.zte_manager.services.huawei_captured_features import (
    LAN_USER_DEV_PAGE,
    WLAN_LIST_PAGE,
)
from apps.zte_manager.services.huawei_eg8041x7_runtime import (
    HuaweiEG8041X7CapturedFeatureService,
)


TOKEN = "c" * 64
WLAN_SOURCE = r"""
function WlanStation(mac, signal, ssid, iface, rx, tx) {
    this.MACAddress = mac;
    this.SignalStrength = signal;
    this.SSID = ssid;
    this.Interface = iface;
    this.RxRate = rx;
    this.TxRate = tx;
}
var station = new WlanStation(
    'AA:BB:CC:DD:EE:FF', '-57', 'LAW_5G', 'wlan0', '866', '721'
);
"""
LAN_SOURCE = r"""
function LanDevice(mac, ip, host, iface) {
    this.MACAddress = mac;
    this.IPAddress = ip;
    this.HostName = host;
    this.Interface = iface;
}
var client = new LanDevice(
    'AA:BB:CC:DD:EE:FF', '192.168.18.33', 'phone-law', 'Ethernet'
);
"""


class RecordingClient:
    def __init__(self):
        self.events = []

    @staticmethod
    def extract_token(_page):
        return TOKEN

    def get_page(self, path):
        self.events.append(("get", path, None))
        if path == WLAN_LIST_PAGE:
            return WLAN_SOURCE
        if path == LAN_USER_DEV_PAGE:
            return ""
        return f'<input id="hwonttoken" value="{TOKEN}">'

    def post_read(self, path, payload=None, *, referer="/index.asp"):
        self.events.append(("post_read", path, dict(payload or {}), referer))
        if path == LAN_USER_DEV_PAGE:
            return LAN_SOURCE
        if path.startswith("/html/amp/common/getSsidProcFlag.asp"):
            return "0"
        return ""

    def post_form(self, path, payload, *, referer):
        self.events.append(("post_form", path, dict(payload), referer))
        return HuaweiMutationTransport(
            http_status=200,
            body="<html><body>accepted</body></html>",
            content_type="text/html; charset=UTF-8",
        )


class PasswordRowsService(HuaweiEG8041X7CapturedFeatureService):
    def _wifi_basic_record(self, band):
        instance = "5" if "5" in str(band) else "1"
        base = (
            "InternetGatewayDevice.LANDevice.1."
            f"WLANConfiguration.{instance}"
        )
        return (
            {"Domain": base, "SSID": "LAW"},
            [{
                "Domain": f"{base}.PreSharedKey.1",
                "PreSharedKey": "senha-real-123",
            }],
        )


class MaskedPasswordRowsService(HuaweiEG8041X7CapturedFeatureService):
    def _wifi_basic_record(self, band):
        instance = "5" if "5" in str(band) else "1"
        base = (
            "InternetGatewayDevice.LANDevice.1."
            f"WLANConfiguration.{instance}"
        )
        return (
            {"Domain": base, "SSID": "LAW"},
            [{
                "Domain": f"{base}.PreSharedKey.1",
                "PreSharedKey": "********",
            }],
        )


class HuaweiEG8041CaptureContractTests(unittest.TestCase):
    def make_service(self):
        client = RecordingClient()
        service = HuaweiEG8041X7CapturedFeatureService(
            client,
            model="EG8041X7-10",
            sleep=lambda _delay: None,
            readback_tries=1,
        )
        return service, client

    def test_wifi_clients_use_only_captured_wlan_list_and_lan_inventory(self):
        service, client = self.make_service()

        clients = service.wifi_clients()

        self.assertEqual(len(clients), 1)
        row = clients[0]
        self.assertEqual(row["mac"], "AA:BB:CC:DD:EE:FF")
        self.assertEqual(row["ip"], "192.168.18.33")
        self.assertEqual(row["hostname"], "phone-law")
        self.assertEqual(row["rssi"], "-57")
        self.assertEqual(row["interface"], "wlan0")
        self.assertEqual(row["connection_type"], "wifi")

        touched = [event[1] for event in client.events]
        self.assertIn(WLAN_LIST_PAGE, touched)
        self.assertIn(LAN_USER_DEV_PAGE, touched)
        self.assertFalse(any("/html/amp/wlaninfo/" in path for path in touched))
        self.assertFalse(any("getassociateddeviceinfo" in path for path in touched))
        self.assertFalse(any("getassociatedstaboost" in path for path in touched))

    def test_wlanbasic_mutation_polls_ssid_proc_flag_before_single_post(self):
        service, client = self.make_service()
        path = (
            "/html/amp/wlanbasic/set.cgi"
            "?y=InternetGatewayDevice.LANDevice.1.WLANConfiguration.5"
            "&RequestFile=html/amp/wlanbasic/WlanBasic.asp"
        )

        result = service._post_verified(
            path=path,
            request_file="/html/amp/wlanbasic/WlanBasic.asp?5G",
            payload={"y.SSID": "LAW_5G"},
            verifier=lambda: {"ssid": "LAW_5G"},
        )

        self.assertTrue(result["success"])
        proc_events = [
            event for event in client.events
            if event[0] == "post_read"
            and event[1].startswith("/html/amp/common/getSsidProcFlag.asp")
        ]
        self.assertEqual(len(proc_events), 1)
        self.assertEqual(proc_events[0][2], {"wlanid": "5"})

        mutation_events = [event for event in client.events if event[0] == "post_form"]
        self.assertEqual(len(mutation_events), 1)
        self.assertEqual(mutation_events[0][2]["x.X_HW_Token"], TOKEN)
        self.assertLess(
            client.events.index(proc_events[0]),
            client.events.index(mutation_events[0]),
        )

    def test_real_psk_is_readable_but_mask_placeholder_is_not(self):
        real = PasswordRowsService(RecordingClient(), model="EG8041X7-10")
        masked = MaskedPasswordRowsService(RecordingClient(), model="EG8041X7-10")

        self.assertEqual(real._wifi_password_from_records("5GHz"), "senha-real-123")
        self.assertEqual(masked._wifi_password_from_records("5GHz"), "")
        self.assertEqual(masked._valid_wifi_psk("********"), "")


if __name__ == "__main__":
    unittest.main()

from __future__ import annotations

import unittest

from apps.zte_manager.services.client_telemetry_service import (
    ClientTelemetryService,
    normalize_client,
)


class FakeRuntime:
    connected = True

    def wifi_clients(self, *, refresh=False):
        return [{
            "MAC": "00:11:22:33:44:55",
            "HostName": "phone",
            "IP": "192.168.1.20",
            "SSID": "Casa-5G",
            "RSSI": "-51",
            "BytesReceived": "1000",
            "BytesSent": "2000",
            "status": "online",
        }]

    def lan_clients(self):
        return [{
            "mac_address": "00:11:22:33:44:66",
            "hostname": "desktop",
            "ip_address": "192.168.1.21",
            "port": "LAN1",
            "rx_bytes": 0,
            "tx_bytes": 0,
            "online": True,
        }]


class FakeDeviceService:
    def __init__(self):
        self.active_service = FakeRuntime()

    def status(self):
        return {
            "vendor": "zte",
            "model": "F6201B",
            "mode": "supported",
            "host": "192.168.1.1",
            "device_id": "fixture",
            "session_revision": "rev-1",
        }


class ClientTelemetryServiceTests(unittest.TestCase):
    def test_normalizer_preserves_unknown_as_none(self):
        client = normalize_client(
            {"mac": "00:11:22:33:44:55", "rx_bytes": 0},
            connection_type="wifi",
        )
        self.assertEqual(client.rx_bytes, 0)
        self.assertIsNone(client.tx_bytes)
        self.assertIsNone(client.rx_rate_bps)
        self.assertIsNone(client.snr)

    def test_collect_normalizes_wifi_and_lan_without_vendor_branch(self):
        result = ClientTelemetryService().collect(FakeDeviceService(), refresh=True)
        self.assertEqual(result["vendor"], "zte")
        self.assertEqual(len(result["clients"]), 2)
        wifi, lan = result["clients"]
        self.assertEqual(wifi["connection_type"], "wifi")
        self.assertEqual(wifi["rssi"], -51)
        self.assertIsNone(wifi["rx_rate_bps"])
        self.assertEqual(lan["connection_type"], "lan")
        self.assertEqual(lan["rx_bytes"], 0)
        self.assertIsNone(lan["rx_rate_bps"])

    def test_session_change_resets_rate_baseline(self):
        service = ClientTelemetryService()
        device = FakeDeviceService()
        first = service.collect(device)
        self.assertIsNone(first["clients"][0]["rx_rate_bps"])

        device.status = lambda: {
            "vendor": "zte", "model": "F6201B", "mode": "supported",
            "host": "192.168.1.2", "device_id": "fixture-2",
            "session_revision": "rev-2",
        }
        second = service.collect(device)
        self.assertIsNone(second["clients"][0]["rx_rate_bps"])


if __name__ == "__main__":
    unittest.main()

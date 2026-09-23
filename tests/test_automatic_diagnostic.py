import unittest

from apps.zte_manager.services.automatic_diagnostic_service import (
    AutomaticDiagnosticService,
    DiagnosticThresholds,
)


class FakeZTE:
    def device_status(self):
        return {
            "modelo": "F670L",
        }

    def optical_status(self):
        return {
            "registration_status": "O5",
            "rx_power_dbm": -20.0,
        }

    def wan_status(self):
        return [
            {
                "status": "Connected",
            }
        ]

    def pppoe_status(self, reveal_password=False):
        return {
            "username": "cliente",
            "password": "••••••••",
        }

    def lan_ports(self):
        return [
            {
                "port": "LAN1",
                "status": "Up",
                "speed": "100 Mbps",
            }
        ]

    def wifi_clients(self):
        return [
            {
                "hostname": "TV",
                "mac": "AA:BB:CC:DD:EE:FF",
                "ssid": "Casa",
                "rssi": "-82",
            }
        ]

    def lan_clients(self):
        return []

    def ping(self, config):
        return {
            "medio_ms": "20",
            "falha": "0",
        }

    def traceroute(self, config):
        return {
            "resultado": "ok",
        }


class AutomaticDiagnosticTests(unittest.TestCase):
    def test_finds_lan_and_wifi_warnings(self):
        result = AutomaticDiagnosticService(
            FakeZTE()
        ).run(
            thresholds=DiagnosticThresholds(
                expected_lan_mbps=1000,
            )
        )

        codes = {
            item["code"]: item["severity"]
            for item in result["findings"]
        }

        self.assertEqual(
            codes["pon_registration"],
            "ok",
        )
        self.assertEqual(
            codes["optical_rx"],
            "ok",
        )
        self.assertEqual(
            codes["lan_negotiation"],
            "warning",
        )
        self.assertEqual(
            codes["wifi_signal"],
            "critical",
        )
        self.assertEqual(
            result["status"],
            "critical",
        )


if __name__ == "__main__":
    unittest.main()

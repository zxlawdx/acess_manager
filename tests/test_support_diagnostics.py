import unittest

from apps.zte_manager.services.attendance_report_service import (
    AttendanceReportService,
)
from apps.zte_manager.services.speed_test_service import (
    HttpWorkstationSpeedTestStrategy,
)
from apps.zte_manager.services.support_diagnostic_service import (
    ChannelAnalyzer,
    ClientPathRule,
    DnsHealthRule,
    SupportDiagnosticOptions,
)


class SupportDiagnosticRuleTests(unittest.TestCase):
    def test_channel_analyzer_prefers_clean_non_overlapping_channel(self):
        result = ChannelAnalyzer().analyze(
            band="2.4GHz",
            radio={
                "banda": "2.4GHz",
                "canal": "6",
                "canal_automatico": False,
            },
            neighbors=[
                {
                    "channel": 6,
                    "signal": -40,
                    "noise": -82,
                },
                {
                    "channel": 6,
                    "signal": -55,
                    "noise": -88,
                },
            ],
            available_channels=[
                {
                    "canais": [
                        1,
                        6,
                        11,
                    ]
                }
            ],
        )

        self.assertNotEqual(
            result["best_channel"],
            6,
        )
        self.assertEqual(
            result["recommendation"]["action"]["type"],
            "wifi_channel",
        )

    def test_dns_zero_static_is_not_failure_when_lookup_works(self):
        context = {
            "sections": {
                "dns_health": {
                    "static_effective": [],
                    "wan_effective": [
                        "100.64.0.10",
                    ],
                    "lookup": {
                        "success": True,
                        "addresses": "104.16.132.229",
                    },
                    "lookup_error": None,
                }
            }
        }

        findings = DnsHealthRule().evaluate(
            context
        )

        self.assertEqual(
            findings[0]["severity"],
            "ok",
        )
        self.assertIn(
            "0.0.0.0",
            findings[0]["message"],
        )

    def test_dns_backend_unavailable_is_inconclusive_not_critical(self):
        context = {
            "sections": {
                "dns_health": {
                    "static_effective": [],
                    "wan_effective": [],
                    "lookup": None,
                    "lookup_error": "menu unavailable",
                }
            }
        }

        findings = DnsHealthRule().evaluate(
            context
        )

        self.assertEqual(
            findings[0]["severity"],
            "info",
        )

    def test_low_speed_client_on_24g_and_low_phy_is_flagged(self):
        rule = ClientPathRule(
            SupportDiagnosticOptions(
                mode="low_speed",
                affected_mac="AA:BB:CC:DD:EE:FF",
            )
        )

        context = {
            "sections": {
                "wifi_clients": [
                    {
                        "hostname": "Notebook",
                        "mac": "AA:BB:CC:DD:EE:FF",
                        "ap": "DEV.WIFI.AP1",
                        "rssi": "-61",
                        "rx_rate": "72000",
                        "tx_rate": "65000",
                    }
                ],
                "lan_clients": [],
                "lan_ports": [],
            }
        }

        findings = rule.evaluate(
            context
        )

        codes = {
            item["code"]
            for item in findings
        }

        self.assertIn(
            "client_on_24ghz",
            codes,
        )
        self.assertIn(
            "wifi_phy_rate",
            codes,
        )


class SpeedTestServerTests(unittest.TestCase):
    def test_custom_base_url_is_normalized(self):
        strategy = HttpWorkstationSpeedTestStrategy(
            base_url="https://speedtest.example.net/"
        )

        self.assertEqual(
            strategy.base_url,
            "https://speedtest.example.net",
        )


class AttendanceReportTests(unittest.TestCase):
    def test_report_uses_diagnostic_and_audit_changes(self):
        diagnostic = {
            "mode": "low_speed",
            "status": "warning",
            "findings": [
                {
                    "severity": "warning",
                    "message": "LAN 1 negociando 100 Mbps.",
                }
            ],
            "sections": {
                "device": {
                    "modelo": "F670L",
                    "firmware": "V1",
                },
                "speedtest": {
                    "source": "ont_native",
                    "download_mbps": 95,
                    "upload_mbps": 90,
                },
            },
        }

        timeline = {
            "changes": [
                {
                    "success": 1,
                    "operation": "wifi_auto_optimization",
                    "target": "2.4GHz",
                    "before_json": {
                        "channel": 6,
                        "password": "secret",
                    },
                    "after_json": {
                        "channel": 1,
                        "password": "another-secret",
                    },
                }
            ]
        }

        report = AttendanceReportService().build(
            diagnostic=diagnostic,
            timeline=timeline,
        )

        self.assertIn(
            "Cliente relata baixa velocidade",
            report["text"],
        )
        self.assertIn(
            "LAN 1 negociando 100 Mbps",
            report["text"],
        )
        self.assertIn(
            "channel: 6",
            report["text"],
        )
        self.assertNotIn(
            "secret",
            report["text"],
        )


if __name__ == "__main__":
    unittest.main()

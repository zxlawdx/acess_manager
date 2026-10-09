from __future__ import annotations

import unittest

from apps.zte_manager.services.huawei_captured_features import (
    DEVICE_INFO_PAGE,
    OPTICAL_PAGE,
    WAN_CACHE_PAGE,
    WLAN_LIST_PAGE,
)
from apps.zte_manager.services.huawei_hg8145x6_runtime import (
    HG8145X6_ASSOCIATED_DEVICES_PAGE,
    HG8145X6_OPTICAL_CANDIDATE_PAGES,
    HG8145X6_WLAN_INFO_PAGE,
    HuaweiHG8145X6CapturedFeatureService,
)
from apps.zte_manager.services.huawei_unified_provider import HuaweiUnifiedProvider


def _new(name: str, args: list[object]) -> str:
    return f"new {name}({','.join(repr(str(value)) for value in args)});"


class SignatureClient:
    def __init__(self, *, optical_path: str | None = None) -> None:
        wan = [""] * 44
        wan[0] = "InternetGatewayDevice.WANDevice.1.WANConnectionDevice.1.WANPPPConnection.1"
        wan[14] = "100.64.1.20"
        wan[18] = "1.1.1.1,8.8.8.8"
        wan[23] = "100"
        wan[37] = "1492"
        ssid = [
            "InternetGatewayDevice.LANDevice.1.WLANConfiguration.5",
            "1", "LAB_5G", "", "", "5GHz",
        ]
        assoc = [
            "InternetGatewayDevice.LANDevice.1.WLANConfiguration.5",
            "AA:BB:CC:DD:EE:FF", "120", "866", "721", "-64",
            "-92", "28", "70", "11ax", "", "", "",
            "192.0.2.40", "fixture-client", "2x2",
        ]
        packet = [
            "InternetGatewayDevice.LANDevice.1.WLANConfiguration.5",
            "100", "1", "200", "2",
        ]
        self.pages = {
            WAN_CACHE_PAGE: _new("WanPPP", wan),
            WLAN_LIST_PAGE: _new("stWlanInfo", ssid),
            HG8145X6_ASSOCIATED_DEVICES_PAGE: _new("stAssociatedDevice", assoc),
            HG8145X6_WLAN_INFO_PAGE: _new("stPacketInfo", packet),
            DEVICE_INFO_PAGE: "\n".join((
                "var dev_uptime='12345';",
                "var cpuUsed='11';",
                "var memUsed='42';",
            )),
        }
        if optical_path:
            self.pages[optical_path] = "\n".join((
                "var RxPower='-20.75';",
                "var TxPower='2.10';",
                "var Temperature='41.2';",
                "var RegisterStatus='O5';",
            ))

    def get_page(self, path: str) -> str:
        if path == OPTICAL_PAGE and path not in self.pages:
            raise RuntimeError("opticinfo unavailable")
        if path not in self.pages:
            raise RuntimeError(f"unsupported fixture path {path}")
        return self.pages[path]


class HuaweiHG8145X6Phase1Tests(unittest.TestCase):
    def test_model_hint_cannot_override_incompatible_runtime_signature(self):
        self.assertFalse(
            HuaweiUnifiedProvider._signature_selects_hg8145x6(
                {"compatible": False, "strong_fingerprint": True},
                model_hint_matches=True,
            )
        )

    def test_unknown_model_requires_strong_runtime_fingerprint(self):
        self.assertFalse(
            HuaweiUnifiedProvider._signature_selects_hg8145x6(
                {"compatible": True, "strong_fingerprint": False},
                model_hint_matches=False,
            )
        )
        self.assertTrue(
            HuaweiUnifiedProvider._signature_selects_hg8145x6(
                {"compatible": True, "strong_fingerprint": True},
                model_hint_matches=False,
            )
        )

    def test_complete_read_contract_is_a_strong_fingerprint(self):
        service = HuaweiHG8145X6CapturedFeatureService(
            SignatureClient(),
            model="UNKNOWN-HUAWEI",
            sleep=lambda _delay: None,
        )
        signature = service.source_signature()
        self.assertTrue(signature["compatible"])
        self.assertTrue(signature["strong_fingerprint"])
        self.assertGreaterEqual(signature["marker_hits"], 5)

    def test_optics_falls_back_to_read_only_candidate_endpoint(self):
        fallback = HG8145X6_OPTICAL_CANDIDATE_PAGES[-1]
        service = HuaweiHG8145X6CapturedFeatureService(
            SignatureClient(optical_path=fallback),
            model="HG8145X6-10",
            sleep=lambda _delay: None,
        )
        optical = service.optical_status()
        self.assertEqual(optical["source"], fallback)
        self.assertEqual(optical["rx_power_dbm"], "-20.75")
        self.assertEqual(optical["tx_power_dbm"], "2.10")
        self.assertEqual(optical["registration_status"], "O5")
        self.assertEqual(optical["evidence"], "runtime_read_only_probe")

    def test_optics_unavailable_is_explicit_not_fabricated(self):
        service = HuaweiHG8145X6CapturedFeatureService(
            SignatureClient(),
            model="HG8145X6-10",
            sleep=lambda _delay: None,
        )
        with self.assertRaisesRegex(RuntimeError, "óptico|Óptica"):
            service.optical_status()


if __name__ == "__main__":
    unittest.main()

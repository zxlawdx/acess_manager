from __future__ import annotations

import unittest
from pathlib import Path
from unittest.mock import patch

from apps.zte_manager.services.device_service import DeviceService, DeviceSession
from apps.zte_manager.services.huawei_eg8041_family_provider import (
    HuaweiEG8041FamilyProvider,
)


FIXTURES = Path("tests/fixtures/huawei/eg8041x6_10_local")


class FakeZte:
    connected = False

    def connect(self, **kwargs):
        return {"success": True, "model": "F670L", "adapter": "generic"}

    def disconnect(self):
        self.connected = False


class FakeHuaweiProfileProvider:
    connected = True
    capabilities = {"wifi_radio": {"read": True, "update": True}}

    def apply_profile(self, attendant=None):
        return {"provider": "huawei", "attendant": attendant, "success": True}


class TerminalDiagnosticClient:
    def __init__(self, frame: str) -> None:
        self.frame = frame
        self.calls = []

    def post_read(self, path, payload=None, *, referer="/index.asp"):
        self.calls.append((path, dict(payload or {}), referer))
        return self.frame


class HuaweiEg8041FamilyProviderTests(unittest.TestCase):
    def test_generic_feature_api_reads_family_channel_discovery(self):
        service = HuaweiEG8041FamilyProvider()
        service._family_compatible = True
        service.model = "EG8041X6-10"
        service._capabilities = {
            "wifi_channel_discovery": {
                "read": True,
                "write": False,
                "state": "READ_SUPPORTED",
            }
        }
        with patch.object(
            service,
            "wifi_channels",
            side_effect=lambda band, country="BR": [{
                "band": band,
                "country": country,
                "canais": [1, 6, 11] if "2.4" in band else [36, 40],
            }],
        ):
            response = service.read_capability("wifi_channel_discovery")

        self.assertTrue(response["available"])
        self.assertFalse(response["writable"])
        self.assertEqual(
            response["objects"]["items"]["2.4ghz"][0]["canais"],
            [1, 6, 11],
        )

    def test_diagnostics_capability_describes_generic_route_without_running_test(self):
        service = HuaweiEG8041FamilyProvider()
        service._family_compatible = True
        service.model = "EG8041X6-10"
        service._capabilities = {
            "diagnostics.ping": {
                "read": True,
                "write": True,
                "state": "WRITE_SUPPORTED",
                "physical_validation": True,
            }
        }
        response = service.read_capability("diagnostics.ping")
        contract = response["objects"]["items"]
        self.assertEqual(contract["start_route"], "/diagnostics/ping")
        self.assertTrue(contract["native"])

    def test_x6_concatenated_traceroute_frame_decodes_complete_and_hops(self):
        source = (FIXTURES / "diagnostic_traceroute_concat.txt").read_text(
            encoding="utf-8"
        )
        output, state = HuaweiEG8041FamilyProvider._decode_diagnostic_result(
            source
        )

        self.assertEqual(state, "Complete")
        self.assertIn("traceroute to 8.8.8.8", output)
        self.assertIn("dns.google (8.8.8.8)", output)
        self.assertNotIn(r"\x20", output)

        hops = HuaweiEG8041FamilyProvider._parse_traceroute_hops(output)
        self.assertEqual([item["numero"] for item in hops], [1, 10])
        self.assertEqual(hops[-1]["ip"], "8.8.8.8")
        self.assertEqual(hops[-1]["latencias_ms"], [31.856])

    def test_x6_terminal_concatenated_frame_stops_polling_immediately(self):
        frame = (FIXTURES / "diagnostic_traceroute_concat.txt").read_text(
            encoding="utf-8"
        )
        service = HuaweiEG8041FamilyProvider()
        client = TerminalDiagnosticClient(frame)
        service._client = client

        output, state, complete = service._poll_huawei_diagnostic(
            service._TRACE_RESULT_PATH,
            deadline_seconds=20,
            client=client,
        )

        self.assertTrue(complete)
        self.assertEqual(state, "Complete")
        self.assertIn("8.8.8.8", output)
        self.assertEqual(len(client.calls), 1)

    def test_x6_concatenated_ping_frame_preserves_valid_negative_result_data(self):
        source = (
            '"PING\\x208\\x2e8\\x2e8\\x2e8\\n" + '
            '"4 packets transmitted, 0 packets received, 100% packet loss\\n" + '
            '"\\x5b\\x40\\x23\\x40\\x5dComplete_Err";'
        )
        output, state = HuaweiEG8041FamilyProvider._decode_diagnostic_result(source)
        stats = HuaweiEG8041FamilyProvider._parse_ping_output(
            output,
            requested_count=4,
        )

        self.assertEqual(state, "Complete_Err")
        self.assertEqual(stats["sucesso"], 0)
        self.assertEqual(stats["falha"], 4)
        self.assertEqual(stats["perda_percentual"], 100)

    def test_diagnostic_decoder_never_executes_non_string_expression(self):
        source = '"safe" + dangerous_call()'
        output, state = HuaweiEG8041FamilyProvider._decode_diagnostic_result(source)
        self.assertEqual(output, source)
        self.assertEqual(state, "")

    def test_configuration_profile_api_remains_device_service_driven(self):
        source = Path(
            "apps/zte_manager/presentation/api/profiles.py"
        ).read_text(encoding="utf-8")
        self.assertIn("device_service.apply_profile", source)
        self.assertNotIn("f6201b_profile", source.casefold())

    def test_active_huawei_profile_apply_does_not_fall_through_to_zte(self):
        manager = DeviceService(zte_provider=FakeZte())
        provider = FakeHuaweiProfileProvider()
        manager._session = DeviceSession(
            vendor="huawei",
            model="EG8041X6-10",
            profile="huawei_unknown",
            provider="FakeHuaweiProfileProvider",
            service=provider,
        )

        result = manager.apply_profile("operator")
        self.assertEqual(result["provider"], "huawei")
        self.assertTrue(result["success"])


if __name__ == "__main__":
    unittest.main()

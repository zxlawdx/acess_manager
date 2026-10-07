from __future__ import annotations

import unittest
from pathlib import Path

from apps.zte_manager.infrastructure.huawei.cli import (
    HuaweiCliOptions,
    _validate_read_command,
)
from apps.zte_manager.infrastructure.huawei.protocol import (
    HuaweiAuthFlow,
    auth_flow_from_login_page,
    extract_huawei_challenge,
)
from apps.zte_manager.model.device_adapters.huawei_registry import (
    HuaweiSupportLevel,
    is_recognized_huawei_model,
    resolve_huawei_model_knowledge,
)
from apps.zte_manager.services.device_service import DeviceService
from apps.zte_manager.services.huawei_cli_telemetry import (
    DISPLAY_ONU_INFO,
    DISPLAY_OPTIC,
    DISPLAY_PON_STATISTICS,
    DISPLAY_SYSINFO,
    HuaweiCliTelemetryReader,
    parse_wap_optical,
    parse_wap_pon_statistics,
    parse_wap_pon_status,
    parse_wap_resources,
)
from apps.zte_manager.services.huawei_telemetry import (
    OPTICAL_AMP_PAGE,
    OPTICAL_STATUS_PAGE,
    parse_huawei_optical_response,
)
from apps.zte_manager.services.huawei_telemetry_runtime import (
    HuaweiTelemetryRuntimeService,
)


FIXTURES = Path(__file__).parent / "fixtures" / "huawei" / "hg8010h_reference"


def fixture(name: str) -> str:
    return (FIXTURES / name).read_text(encoding="utf-8")


class FakePageClient:
    def __init__(self, pages: dict[str, str]):
        self.pages = pages
        self.base_url = "http://192.0.2.10"

    def get_page(self, path: str) -> str:
        if path not in self.pages:
            raise RuntimeError("fixture endpoint unavailable")
        return self.pages[path]


class FakeCli:
    name = "telnet"

    def __init__(self):
        self.commands: list[str] = []
        self.outputs = {
            DISPLAY_OPTIC: fixture("wap_display_optic.txt"),
            DISPLAY_SYSINFO: fixture("wap_display_sysinfo.txt"),
            DISPLAY_PON_STATISTICS: fixture("wap_display_pon_statistics.txt"),
            DISPLAY_ONU_INFO: fixture("wap_display_onu_info.txt"),
        }

    def run(self, command: str) -> str:
        self.commands.append(command)
        return self.outputs[command]

    def close(self) -> None:
        return None


class FakeHuaweiService:
    vendor = "huawei"
    connected = True

    def __init__(self):
        self.capabilities = {"optical_telemetry": {"read": True}}
        self.received = None

    def connect(self, **kwargs):
        self.received = kwargs
        return {
            "success": True,
            "model": "HG8010H",
            "profile": "huawei_unknown",
            "capabilities": self.capabilities,
            "model_verified": False,
            "host": kwargs["ip"],
            "attendant": kwargs.get("attendant"),
            "session_revision": "fixture",
        }

    def disconnect(self):
        self.connected = False


class FakeZteService:
    connected = False

    def connect(self, **kwargs):  # pragma: no cover - must never be called
        raise AssertionError("recognized Huawei model was routed to ZTE")


class HuaweiHg8010TelemetryTests(unittest.TestCase):
    def test_registry_recognizes_hg8010h_without_claiming_physical_validation(self):
        profile = resolve_huawei_model_knowledge("EchoLife HG8010H")
        self.assertIsNotNone(profile)
        self.assertEqual(profile.canonical_model, "HG8010H")
        self.assertEqual(profile.support_level, HuaweiSupportLevel.READ_PARTIAL)
        self.assertFalse(profile.physical_validation)
        self.assertTrue(is_recognized_huawei_model("Huawei HG8010H"))
        self.assertTrue(is_recognized_huawei_model("EG8010H"))

    def test_legacy_cookie_hash_login_is_distinct_from_normal_randcount(self):
        source = fixture("login_legacy_rand_cookie.html")
        self.assertEqual(
            auth_flow_from_login_page(source),
            HuaweiAuthFlow.RAND_COOKIE_HASH,
        )
        self.assertEqual(
            auth_flow_from_login_page('<script src="/asp/GetRandCount.asp"></script>'),
            HuaweiAuthFlow.RAND_COUNT,
        )

    def test_randcount_can_extract_only_characterized_trailing_32_hex_token(self):
        suffix = "0123456789abcdef0123456789abcdef"
        self.assertEqual(
            extract_huawei_challenge("prefix-response:" + suffix),
            suffix,
        )
        opaque = "not-hex-but-valid-token-value-abcdefghijklmnopqrstuvwxyz"
        self.assertEqual(extract_huawei_challenge(opaque), opaque)

    def test_legacy_status_optical_signature_is_normalized_with_explicit_units(self):
        result = parse_huawei_optical_response(
            fixture("optic_status_legacy.asp"),
            endpoint=OPTICAL_STATUS_PAGE,
        )
        self.assertEqual(result.signature, "stOpticInfo/6")
        self.assertAlmostEqual(result.tx_power_dbm, 2.34)
        self.assertAlmostEqual(result.rx_power_dbm, -17.26)
        self.assertAlmostEqual(result.voltage_mv, 3322.0)
        self.assertAlmostEqual(result.temperature_c, 36.0)
        self.assertAlmostEqual(result.bias_ma, 13.0)

    def test_extended_amp_optical_signature_is_normalized(self):
        result = parse_huawei_optical_response(
            fixture("optic_amp_extended.asp"),
            endpoint=OPTICAL_AMP_PAGE,
        )
        self.assertEqual(result.signature, "stOpticInfo/16")
        self.assertEqual(result.link_status, "up")
        self.assertAlmostEqual(result.rx_power_dbm, -19.07)
        self.assertAlmostEqual(result.tx_power_dbm, 2.16)
        self.assertIsNone(result.rf_rx_power_dbm)

    def test_uncharacterized_optical_constructor_shape_is_rejected(self):
        source = '<script>var x = new stOpticInfo("a","b","c","d","e","f","g");</script>'
        with self.assertRaises(RuntimeError):
            parse_huawei_optical_response(source, endpoint=OPTICAL_AMP_PAGE)

    def test_wap_optical_and_resource_outputs_normalize(self):
        optical = parse_wap_optical(
            fixture("wap_display_optic.txt"),
            transport="telnet",
        )
        resources = parse_wap_resources(
            fixture("wap_display_sysinfo.txt"),
            transport="telnet",
        )
        self.assertAlmostEqual(optical.rx_power_dbm, -19.07)
        self.assertAlmostEqual(optical.voltage_mv, 3317.0)
        self.assertEqual(resources.cpu_used_percent, 4.0)
        self.assertEqual(resources.memory_used_percent, 70.0)

    def test_wap_pon_status_and_statistics_are_separate_domain_models(self):
        status = parse_wap_pon_status(
            fixture("wap_display_onu_info.txt"),
            transport="telnet",
        )
        stats = parse_wap_pon_statistics(
            fixture("wap_display_pon_statistics.txt"),
            transport="telnet",
        )
        self.assertEqual(status.o_state, "O5")
        self.assertTrue(status.online)
        self.assertEqual(stats.rx_unicast_packets, 15450712)
        self.assertEqual(stats.tx_omci, 20499)
        self.assertEqual(stats.rx_multicast_gem, 488687744)
        self.assertEqual(stats.rx_omci_overflow, 0)

    def test_cli_reader_never_issues_counter_clear_or_mutation(self):
        transport = FakeCli()
        reader = HuaweiCliTelemetryReader(transport)
        reader.optical()
        reader.resources()
        reader.pon_statistics()
        reader.pon_status()
        self.assertEqual(
            transport.commands,
            [
                DISPLAY_OPTIC,
                DISPLAY_SYSINFO,
                DISPLAY_PON_STATISTICS,
                DISPLAY_ONU_INFO,
            ],
        )
        self.assertFalse(any("clear" in command for command in transport.commands))
        with self.assertRaises(ValueError):
            _validate_read_command("clear pon statistics")
        with self.assertRaises(ValueError):
            _validate_read_command("set foo bar")

    def test_cli_options_are_disabled_by_default_and_never_expose_password(self):
        options = HuaweiCliOptions.from_mapping({
            "enabled": True,
            "transport": "telnet",
            "username": "operator",
            "password": "secret-fixture",
        })
        public = options.public()
        self.assertTrue(public["credentials_supplied"])
        self.assertNotIn("username", public)
        self.assertNotIn("password", public)
        self.assertNotIn("secret-fixture", repr(options))

    def test_runtime_promotes_web_optical_only_after_signature_parser_succeeds(self):
        runtime = HuaweiTelemetryRuntimeService()
        runtime._client = FakePageClient({
            OPTICAL_AMP_PAGE: fixture("optic_amp_extended.asp"),
        })
        runtime.current_host = "fixture"
        runtime.model = "HG8010H"
        runtime._capabilities = {}
        data = runtime.optical_telemetry(refresh=True)
        self.assertAlmostEqual(data["rx_power_dbm"], -19.07)
        capability = runtime._capabilities["optical_telemetry"]
        self.assertTrue(capability["read"])
        self.assertFalse(capability["write"])
        self.assertFalse(capability["verified"])

    def test_runtime_promotes_cli_stats_only_after_explicit_cli_reader_exists(self):
        runtime = HuaweiTelemetryRuntimeService()
        runtime._client = FakePageClient({})
        runtime.current_host = "fixture"
        runtime.model = "HG8010H"
        runtime._capabilities = {}
        runtime._cli_transport = FakeCli()
        runtime._cli_reader = HuaweiCliTelemetryReader(runtime._cli_transport)
        stats = runtime.pon_statistics(refresh=True)
        resources = runtime.resource_telemetry(refresh=True)
        self.assertEqual(stats["bip_errors"], 0)
        self.assertEqual(resources["memory_used_percent"], 70.0)
        self.assertTrue(runtime._capabilities["pon_statistics"]["read"])
        self.assertTrue(runtime._capabilities["resource_telemetry"]["read"])

    def test_recognized_huawei_hint_routes_to_huawei_without_becoming_verified(self):
        service = FakeHuaweiService()
        dispatcher = DeviceService(
            zte_provider=FakeZteService(),
            huawei_factory=lambda: service,
        )
        result = dispatcher.connect(
            "192.0.2.10",
            "web-user",
            "web-password-fixture",
            model_hint="HG8010H",
            huawei_cli={"enabled": False},
        )
        self.assertEqual(result["model"], "HG8010H")
        self.assertFalse(result["model_verified"])
        self.assertEqual(service.received["model_hint"], "HG8010H")
        self.assertEqual(service.received["huawei_cli"], {"enabled": False})


if __name__ == "__main__":
    unittest.main()

from __future__ import annotations

import unittest
from pathlib import Path
from unittest.mock import patch

from apps.zte_manager.infrastructure.huawei.negotiating_client import (
    HuaweiNegotiatingWebClient,
    parse_huawei_https_bootstrap,
)
from apps.zte_manager.infrastructure.huawei.wifi import (
    HuaweiWifiMapper,
    HuaweiWifiMappingError,
    eg8041_family_wifi_capabilities,
)
from apps.zte_manager.model.device_adapters.huawei import resolve_huawei_profile
from apps.zte_manager.model.device_adapters.huawei_registry import (
    HuaweiSupportLevel,
    resolve_huawei_model_knowledge,
)
from apps.zte_manager.model.wifi import WifiConfiguration, WifiRadioConfiguration
from apps.zte_manager.services.device_service import DeviceService
from apps.zte_manager.services.huawei_captured_features import (
    parse_huawei_js_records,
)
from apps.zte_manager.services.huawei_eg8041_family_runtime import (
    HuaweiEG8041FamilyCapturedFeatureService,
    HuaweiEG8041FamilyRuntimeService,
)
from apps.zte_manager.services.huawei_telemetry_runtime import (
    HuaweiTelemetryRuntimeService,
)


FIXTURES = Path("tests/fixtures/huawei/eg8041x6_10_local")


def fixture(name: str) -> str:
    return (FIXTURES / name).read_text(encoding="utf-8")


class FakeResponse:
    def __init__(self, text: str, status_code: int = 200):
        self.text = text
        self.status_code = status_code
        self.url = "http://fixture/"


class FakeSession:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []
        self.verify = True

    def get(self, url, **kwargs):
        self.calls.append((url, kwargs))
        if not self.responses:
            raise AssertionError("unexpected GET")
        return self.responses.pop(0)

    def close(self):
        return None


class FamilySignatureClient:
    def __init__(self):
        self.pages = {
            "/html/ssmp/deviceinfo/deviceinfo.asp": fixture("device_brebg2.asp"),
            "/wifi/2g": fixture("wifi_2g.asp"),
            "/wifi/5g": fixture("wifi_5g.asp"),
        }

    def get_page(self, path):
        return self.pages.get(path, "")


class FamilySignatureCaptured:
    def __init__(self, client):
        self.client = client

    def _wifi_pages(self, band):
        if "5" in str(band):
            return "5GHz", "5", "/basic/5g", "/wifi/5g"
        return "2.4GHz", "1", "/basic/2g", "/wifi/2g"

    def _records(self, *pages):
        html = "\n".join(self.client.get_page(page) for page in pages)
        return html, parse_huawei_js_records(html)


class HuaweiEg8041FamilyRuntimeTests(unittest.TestCase):
    def test_https_bootstrap_requires_sslport_and_https_redirect(self):
        self.assertEqual(
            parse_huawei_https_bootstrap(fixture("http_bootstrap.html")),
            80,
        )
        self.assertIsNone(
            parse_huawei_https_bootstrap(
                '<script>window.location="https://example.invalid"</script>'
            )
        )
        self.assertIsNone(
            parse_huawei_https_bootstrap(
                '<script>var SSLPort="99999";window.location="https://x"</script>'
            )
        )

    def test_http_port_80_bootstrap_negotiates_https_same_port(self):
        client = HuaweiNegotiatingWebClient(
            "100.64.161.200:80",
            "operator",
            "fixture-password",
        )
        client.session.close()
        fake = FakeSession([FakeResponse(fixture("http_bootstrap.html"))])
        client.session = fake

        client._negotiate_endpoint()

        descriptor = client.transport_descriptor()
        self.assertEqual(descriptor["scheme"], "https")
        self.assertEqual(descriptor["port"], 80)
        self.assertTrue(descriptor["https_bootstrap"])
        self.assertTrue(descriptor["negotiated"])
        self.assertEqual(client.base_url, "https://100.64.161.200:80")
        self.assertEqual(fake.calls[0][0], "http://100.64.161.200:80/")

    def test_explicit_https_port_is_preserved_without_assuming_443(self):
        client = HuaweiNegotiatingWebClient(
            "https://192.0.2.10:80",
            "operator",
            "fixture-password",
        )
        descriptor = client.transport_descriptor()
        self.assertEqual(descriptor["scheme"], "https")
        self.assertEqual(descriptor["port"], 80)
        self.assertTrue(descriptor["explicit_port"])
        self.assertFalse(descriptor["negotiated"])

    def test_rfc6598_shared_space_is_probeable_but_outside_address_is_not(self):
        for value in (
            "100.64.0.1",
            "100.64.161.200:80",
            "100.127.255.254",
            "http://100.64.161.200:80/",
        ):
            with self.subTest(value=value):
                self.assertTrue(DeviceService._should_probe_vendor(value))
        self.assertFalse(DeviceService._should_probe_vendor("100.128.0.1"))

    def test_x6_registry_is_evidence_not_x7_operational_profile(self):
        knowledge = resolve_huawei_model_knowledge("Huawei EG8041X6-10")
        self.assertIsNotNone(knowledge)
        self.assertEqual(knowledge.canonical_model, "EG8041X6-10")
        self.assertEqual(knowledge.support_level, HuaweiSupportLevel.READ_SUPPORTED)
        self.assertTrue(knowledge.physical_validation)
        self.assertIn("BREBG2", knowledge.known_cfg_modes)
        self.assertIsNone(resolve_huawei_profile("EG8041X6-10", unknown=False))

    def test_runtime_requires_protocol_and_exact_object_signature(self):
        service = HuaweiEG8041FamilyRuntimeService()
        service.model = "EG8041X6-10"
        service._protocol = {
            "family": "amp_bbsp",
            "auth_flow": "rand_count",
            "evidence": ["endpoint:/asp/GetRandCount.asp"],
        }
        service._client = FamilySignatureClient()
        service._captured = FamilySignatureCaptured(service._client)

        service._characterize_family()

        self.assertTrue(service.family_descriptor["compatible"])
        self.assertEqual(service.family_descriptor["cfg_mode"], "BREBG2")
        self.assertIsInstance(
            service._captured,
            HuaweiEG8041FamilyCapturedFeatureService,
        )
        evidence = service.family_descriptor["evidence"]
        self.assertTrue(any("WLANConfiguration.1" in item for item in evidence))
        self.assertTrue(any("WiFi.Radio.2" in item for item in evidence))

    def test_same_model_without_family_signature_is_not_promoted(self):
        service = HuaweiEG8041FamilyRuntimeService()
        service.model = "EG8041X6-10"
        service._protocol = {
            "family": "amp_bbsp",
            "auth_flow": "rand_count",
            "evidence": [],
        }
        client = FamilySignatureClient()
        client.pages["/wifi/5g"] = "<html>no object graph</html>"
        service._client = client
        service._captured = FamilySignatureCaptured(client)

        service._characterize_family()
        self.assertFalse(service.family_descriptor["compatible"])

    def test_dynamic_channel_list_replaces_static_supported_values(self):
        capabilities = eg8041_family_wifi_capabilities(
            channels_2g=("1", "6", "11"),
            channels_5g=("36", "40", "149"),
        ).as_dict()
        self.assertEqual(
            capabilities["2.4ghz"]["channel"]["supported"],
            ["auto", "1", "6", "11"],
        )
        self.assertEqual(
            capabilities["5ghz"]["channel"]["supported"],
            ["auto", "36", "40", "149"],
        )

    def test_wifi_mapper_keeps_known_widths_and_fails_closed(self):
        two = HuaweiWifiMapper.to_legacy_radio(
            "2.4ghz",
            WifiRadioConfiguration(channel_width="auto_20_40"),
        )
        five = HuaweiWifiMapper.to_legacy_radio(
            "5ghz",
            WifiRadioConfiguration(channel_width="auto_20_40_80_160"),
        )
        self.assertEqual(two["bandwidth_code"], "0")
        self.assertEqual(five["bandwidth_code"], "4")
        with self.assertRaises(HuaweiWifiMappingError):
            HuaweiWifiMapper.to_legacy_radio(
                "5ghz",
                WifiRadioConfiguration(channel_width="80"),
            )

    def test_wifi_mapper_validates_observed_advanced_ranges(self):
        with self.assertRaises(HuaweiWifiMappingError):
            HuaweiWifiMapper.to_legacy_radio(
                "2.4ghz",
                WifiRadioConfiguration(dtim_period=0),
            )
        with self.assertRaises(HuaweiWifiMappingError):
            HuaweiWifiMapper.to_legacy_radio(
                "5ghz",
                WifiRadioConfiguration(beacon_period=1001),
            )
        with self.assertRaises(HuaweiWifiMappingError):
            HuaweiWifiMapper.to_legacy_radio(
                "2.4ghz",
                WifiRadioConfiguration(fragmentation_threshold=255),
            )

    def test_descriptor_keeps_current_default_supported_separate(self):
        service = HuaweiEG8041FamilyRuntimeService()
        service._family_compatible = True
        service.model = "EG8041X6-10"
        service._discovered_channels = {
            "2.4ghz": ("auto", "1", "6", "11"),
            "5ghz": ("auto", "36", "40"),
        }
        current = WifiConfiguration(
            radio_2g=WifiRadioConfiguration(channel="6", mode="b_g_n_ax"),
            radio_5g=WifiRadioConfiguration(channel="36", mode="a_n_ac_ax"),
        )
        with patch.object(service, "normalized_wifi_configuration", return_value=current):
            descriptor = service.wifi_configuration_descriptor()
        self.assertEqual(descriptor["current"]["2.4ghz"]["channel"], "6")
        self.assertEqual(descriptor["defaults"]["2.4ghz"]["channel"], "auto")
        self.assertEqual(
            descriptor["capabilities"]["2.4ghz"]["channel"]["supported"],
            ["auto", "1", "6", "11"],
        )

    def test_ping_adds_normalized_contract_and_dns_resolution(self):
        service = HuaweiEG8041FamilyRuntimeService()
        service._client = type(
            "Client",
            (),
            {
                "post_read": lambda _self, path, payload, referer: "203.0.113.8[@#@]Complete"
            },
        )()
        legacy = {
            "host": "example.net",
            "interface": "wan.object.1",
            "diagnostics_state": "Complete",
            "success": True,
            "sucesso": 4,
            "falha": 0,
            "perda_percentual": 0,
            "minimo_ms": 32.350,
            "medio_ms": 32.682,
            "maximo_ms": 33.076,
        }
        with patch.object(HuaweiTelemetryRuntimeService, "ping", return_value=legacy):
            result = service.ping({"host": "example.net"})
        self.assertEqual(result["target"], "example.net")
        self.assertEqual(result["resolved_ip"], "203.0.113.8")
        self.assertEqual(result["packets_sent"], 4)
        self.assertEqual(result["packets_received"], 4)
        self.assertEqual(result["avg_ms"], 32.682)
        self.assertEqual(result["sucesso"], 4)

    def test_traceroute_adds_normalized_hops_without_breaking_legacy_keys(self):
        service = HuaweiEG8041FamilyRuntimeService()
        legacy = {
            "host": "example.net",
            "interface": "wan.object.1",
            "diagnostics_state": "Complete",
            "success": True,
            "hops": [{
                "numero": 1,
                "ip": "192.0.2.1",
                "latencias_ms": [1.1, 1.2, 1.3],
                "timeout": False,
                "linha": "gateway.local 192.0.2.1 1.1 ms 1.2 ms 1.3 ms",
            }],
        }
        with patch.object(HuaweiTelemetryRuntimeService, "traceroute", return_value=legacy):
            result = service.traceroute({"host": "example.net"})
        hop = result["hops"][0]
        self.assertEqual(hop["numero"], 1)
        self.assertEqual(hop["index"], 1)
        self.assertEqual(hop["address"], "192.0.2.1")
        self.assertEqual(hop["hostname"], "gateway.local")
        self.assertEqual(hop["rtt_samples_ms"], [1.1, 1.2, 1.3])

    def test_profile_preflight_blocks_silent_partial_apply(self):
        service = HuaweiEG8041FamilyRuntimeService()
        service._family_compatible = True
        service.model = "EG8041X6-10"
        service._capabilities = {
            "wifi_radio": {"read": True, "update": True},
            "dns": {"read": True, "update": False},
        }
        with patch.object(
            service,
            "_profile_changed_requirements",
            return_value={"wifi_radio", "dns"},
        ):
            result = service._apply_profile_payload(
                {"wifi": {}, "dns": {}},
                operation="test",
                target="fixture",
            )
        self.assertFalse(result["success"])
        self.assertTrue(result["preflight"])
        self.assertEqual(result["supported"], ["wifi_radio"])
        self.assertEqual(result["unsupported"], ["dns"])
        self.assertEqual(result["steps"], [])


if __name__ == "__main__":
    unittest.main()

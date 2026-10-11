from __future__ import annotations

import unittest
from pathlib import Path

from apps.zte_manager.infrastructure.huawei.protocol import HuaweiAuthFlow
from apps.zte_manager.services.huawei_eg8145v5_family_runtime import (
    COMMON_CLIENT_ENDPOINT,
    EG8145V5_PROFILE,
    HN8010TS_PROFILE,
    HuaweiEG8145V5FamilyRuntime,
)
from apps.zte_manager.services.huawei_unified_provider import HuaweiUnifiedProvider


FIXTURES = Path("tests/fixtures/huawei/phase2")


def fixture(name: str) -> str:
    return (FIXTURES / name).read_text(encoding="utf-8")


class Phase2Client:
    def __init__(self, model: str) -> None:
        self.auth_flow = HuaweiAuthFlow.RAND_COUNT
        self.model = model
        prefix = "hn8010ts" if model == "HN8010TS" else "eg8145v5"
        self.pages = {
            "/html/ssmp/deviceinfo/deviceinfo.asp": fixture(f"{prefix}_deviceinfo.asp"),
        }
        self.posts = {
            COMMON_CLIENT_ENDPOINT.path: fixture(f"{prefix}_clients.asp"),
        }
        if model == "HN8010TS":
            self.pages["/html/amp/opticinfo/opticinfo.asp"] = fixture(
                "hn8010ts_opticinfo.asp"
            )
        self.calls: list[tuple[str, str]] = []

    def get_page(self, path: str) -> str:
        self.calls.append(("GET", path))
        if path not in self.pages:
            raise RuntimeError(f"fixture GET unavailable: {path}")
        return self.pages[path]

    def post_read(self, path: str, payload=None, *, referer="/index.asp") -> str:
        self.calls.append(("POST", path))
        if path not in self.posts:
            raise RuntimeError(f"fixture POST unavailable: {path}")
        return self.posts[path]


class HuaweiPhase2Tests(unittest.TestCase):
    def test_eg8145v5_uses_shared_randcount_session_and_model_schema(self):
        client = Phase2Client("EG8145V5")
        runtime = HuaweiEG8145V5FamilyRuntime(client, EG8145V5_PROFILE)

        signature = runtime.source_signature()
        self.assertTrue(signature["compatible"])
        self.assertTrue(signature["strong_fingerprint"])
        self.assertEqual(signature["model"], "EG8145V5")
        self.assertIn("auth:rand_count", signature["evidence"])
        self.assertIn(
            ("POST", "/html/bbsp/common/GetLanUserDevInfo.asp"),
            client.calls,
        )

        device = runtime.device_status()
        self.assertEqual(device["modelo"], "EG8145V5")
        self.assertEqual(device["detected_model"], "EG8145V5")
        self.assertEqual(device["cpu_percent"], 17.0)
        self.assertEqual(device["memoria_percent"], 43.0)
        self.assertEqual(device["uptime"], 172801)

        clients = runtime.clients()
        self.assertEqual(len(clients), 2)
        by_type = {row["connection_type"]: row for row in clients}
        self.assertIn("lan", by_type)
        self.assertIn("wifi", by_type)
        self.assertIsNone(by_type["wifi"]["rssi"])
        self.assertIsNone(by_type["wifi"]["rx_rate"])

    def test_eg8145v5_does_not_inherit_hn8010ts_optical_endpoint(self):
        runtime = HuaweiEG8145V5FamilyRuntime(
            Phase2Client("EG8145V5"),
            EG8145V5_PROFILE,
        )
        with self.assertRaisesRegex(RuntimeError, "Óptica"):
            runtime.optical_telemetry()

    def test_hn8010ts_requires_and_parses_model_specific_optics(self):
        client = Phase2Client("HN8010TS")
        runtime = HuaweiEG8145V5FamilyRuntime(client, HN8010TS_PROFILE)

        signature = runtime.source_signature()
        self.assertTrue(signature["compatible"])
        self.assertIn(
            "optical:/html/amp/opticinfo/opticinfo.asp",
            signature["evidence"],
        )
        optical = runtime.optical_telemetry()
        self.assertEqual(optical["tx_power_dbm"], 2.31)
        self.assertEqual(optical["rx_power_dbm"], -19.84)
        self.assertEqual(optical["signature"], "stOpticInfo/16")

    def test_hn8010ts_without_optical_shape_is_not_selected(self):
        client = Phase2Client("HN8010TS")
        client.pages["/html/amp/opticinfo/opticinfo.asp"] = "<html>no optic data</html>"
        runtime = HuaweiEG8145V5FamilyRuntime(client, HN8010TS_PROFILE)
        signature = runtime.source_signature()
        self.assertFalse(signature["compatible"])
        self.assertFalse(signature["strong_fingerprint"])

    def test_model_name_alone_cannot_select_wrong_phase2_profile(self):
        client = Phase2Client("HN8010TS")
        runtime = HuaweiEG8145V5FamilyRuntime(client, EG8145V5_PROFILE)
        signature = runtime.source_signature()
        self.assertFalse(signature["compatible"])
        self.assertIn("device-model:mismatch", signature["evidence"])
        self.assertFalse(any(method == "POST" for method, _path in client.calls))

    def test_profile_hint_cannot_replace_missing_model_evidence(self):
        client = Phase2Client("EG8145V5")
        path = "/html/ssmp/deviceinfo/deviceinfo.asp"
        client.pages[path] = client.pages[path].replace(
            ",'EG8145V5','HWTC'",
            ",'','HWTC'",
        )
        runtime = HuaweiEG8145V5FamilyRuntime(client, EG8145V5_PROFILE)
        signature = runtime.source_signature()
        self.assertFalse(signature["compatible"])
        self.assertIn("device-model:missing", signature["evidence"])
        self.assertFalse(any(method == "POST" for method, _path in client.calls))

    def test_non_randcount_session_is_rejected_before_phase2_probe(self):
        provider = HuaweiUnifiedProvider()
        client = Phase2Client("EG8145V5")
        client.auth_flow = HuaweiAuthFlow.RAND_STRING_SESSION_TOKEN
        provider._client = client
        provider.model = "EG8145V5"
        self.assertIsNone(provider._probe_phase2_candidate())
        self.assertEqual(client.calls, [])

    def test_provider_promotes_only_phase2_read_capabilities(self):
        provider = HuaweiUnifiedProvider()
        client = Phase2Client("EG8145V5")
        provider._client = client
        provider.model = "EG8145V5"
        provider._device_info = {"fabricante": "Huawei", "modelo": "EG8145V5"}

        candidate = provider._probe_phase2_candidate()
        self.assertIsNotNone(candidate)
        runtime, profile, signature = candidate
        provider._configure_phase2_runtime(runtime, profile, signature)

        capabilities = provider.capabilities
        for key in ("device_info", "clients", "resource_telemetry"):
            self.assertTrue(capabilities[key]["read"])
            self.assertFalse(capabilities[key].get("write", False))
            self.assertFalse(capabilities[key].get("update", False))
            self.assertFalse(capabilities[key].get("physical_validation", False))
        self.assertNotIn("wifi", capabilities)
        self.assertFalse(provider.writes_enabled)
        with self.assertRaisesRegex(RuntimeError, "somente leitura"):
            provider.set_wifi_radio("5GHz", {"channel": 36})

    def test_hn_provider_promotes_optics_without_promoting_writes(self):
        provider = HuaweiUnifiedProvider()
        client = Phase2Client("HN8010TS")
        provider._client = client
        provider.model = "HN8010TS"
        provider._device_info = {"fabricante": "Huawei", "modelo": "HN8010TS"}

        candidate = provider._probe_phase2_candidate()
        self.assertIsNotNone(candidate)
        runtime, profile, signature = candidate
        provider._configure_phase2_runtime(runtime, profile, signature)

        capabilities = provider.capabilities
        self.assertTrue(capabilities["optical"]["read"])
        self.assertTrue(capabilities["optical_telemetry"]["read"])
        self.assertFalse(capabilities["optical"]["physical_validation"])
        self.assertFalse(provider.writes_enabled)
        optical = provider.optical_status(refresh=True)
        self.assertEqual(optical["rx_power_dbm"], -19.84)


if __name__ == "__main__":
    unittest.main()

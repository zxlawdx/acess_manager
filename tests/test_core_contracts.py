from __future__ import annotations

import unittest

from apps.zte_manager.model.capabilities import (
    CapabilityEvidence,
    CapabilityOperation,
    EvidenceLevel,
    evidence_badge,
)
from apps.zte_manager.model.session import DeviceSession
from apps.zte_manager.model.telemetry import ClientTelemetry
from apps.zte_manager.services.provider_router import ProviderRouter


class FakeZTE:
    def __init__(self):
        self.connected = False
        self.calls = []
        self._zte = type("Backend", (), {"writes_enabled": True})()

    def connect(self, **kwargs):
        self.calls.append(dict(kwargs))
        self.connected = True
        return {
            "model": kwargs.get("model_hint") or "F6201B",
            "adapter": "zte-f6201b",
            "model_verified": True,
            "host": kwargs["ip"],
            "attendant": kwargs.get("attendant"),
        }

    def disconnect(self):
        self.connected = False


class FakeHuawei:
    def __init__(self):
        self.connected = False
        self.calls = []
        self.writes_enabled = True
        self.capabilities = {"wifi": {"read": True, "write": True}}

    def connect(self, **kwargs):
        self.calls.append(dict(kwargs))
        self.connected = True
        return {
            "model": kwargs.get("model_hint") or "HX",
            "profile": "huawei-test",
            "model_verified": True,
            "host": kwargs["ip"],
            "attendant": kwargs.get("attendant"),
            "capabilities": self.capabilities,
            "protocol_family": "AMP_BBSP",
            "firmware": "fixture-fw",
            "hardware": "fixture-hw",
        }

    def disconnect(self):
        self.connected = False


class CoreContractTests(unittest.TestCase):
    def test_session_public_contract_contains_multivendor_fields_not_runtime_service(self):
        runtime = object()
        session = DeviceSession.from_connection(
            vendor="Huawei",
            provider="FakeHuawei",
            service=runtime,
            result={
                "model": "EG8041X6-10",
                "profile": "huawei-eg8041",
                "model_verified": True,
                "firmware": "V1R1",
                "hardware": "REV-A",
                "protocol_family": "AMP_BBSP",
                "device_id": "ont-1",
                "host": "192.168.18.1",
                "attendant": "law",
                "capabilities": {"wifi": {"read": True}},
            },
        )

        data = session.public()
        self.assertEqual(session.service, runtime)
        self.assertEqual(data["vendor"], "huawei")
        self.assertEqual(data["mode"], "supported")
        self.assertEqual(data["protocol_family"], "AMP_BBSP")
        self.assertEqual(data["device_id"], "ont-1")
        self.assertNotIn("service", data)

    def test_unverified_known_vendor_session_is_partial_and_unknown_vendor_deploys(self):
        partial = DeviceSession.from_connection(
            vendor="zte",
            provider="FakeZTE",
            service=object(),
            result={"model": "F9999", "model_verified": False},
        )
        deployment = DeviceSession.from_connection(
            vendor="unknown",
            provider="DeploymentProvider",
            service=object(),
            result={"model": "unknown", "model_verified": False},
        )
        self.assertEqual(partial.mode, "partial")
        self.assertEqual(deployment.mode, "deployment")

    def test_evidence_scale_and_badges_are_single_canonical_vocabulary(self):
        evidence = CapabilityEvidence(
            feature="wifi",
            operations={
                CapabilityOperation.READ: EvidenceLevel.PHYSICALLY_VALIDATED,
                CapabilityOperation.WRITE: EvidenceLevel.FIXTURE_VALIDATED,
            },
        )
        self.assertEqual(
            evidence.level_for(CapabilityOperation.READ),
            EvidenceLevel.PHYSICALLY_VALIDATED,
        )
        self.assertEqual(
            evidence.level_for(CapabilityOperation.DELETE),
            EvidenceLevel.UNKNOWN,
        )
        self.assertEqual(evidence_badge("RESEARCH_ONLY"), "DETECTADO")
        self.assertEqual(evidence_badge("UNSUPPORTED"), "NÃO SUPORTADO")

    def test_client_telemetry_does_not_invent_zero_for_unknown_values(self):
        telemetry = ClientTelemetry(mac="00:11:22:33:44:55", online=True)
        data = telemetry.as_dict()
        self.assertIsNone(data["rx_bytes"])
        self.assertIsNone(data["tx_bytes"])
        self.assertIsNone(data["rx_rate_bps"])
        self.assertIsNone(data["tx_rate_bps"])
        self.assertIsNone(data["snr"])


class ProviderRouterTests(unittest.TestCase):
    def make_router(self, zte=None, huawei_factory=FakeHuawei, probe=None):
        return ProviderRouter(
            zte_provider=zte or FakeZTE(),
            huawei_factory=huawei_factory,
            huawei_model_predicates=(lambda model: model == "HX",),
            vendor_probe=probe or (lambda host, https=False: False),
        )

    def test_manual_huawei_model_selects_only_huawei_provider(self):
        zte = FakeZTE()
        created = []

        def factory():
            provider = FakeHuawei()
            created.append(provider)
            return provider

        router = self.make_router(zte=zte, huawei_factory=factory)
        connection = router.connect(
            ip="192.168.18.1",
            username="admin",
            password="fixture",
            model_hint="HX",
            huawei_cli={"enabled": True},
        )

        self.assertEqual(connection.vendor, "huawei")
        self.assertEqual(zte.calls, [])
        self.assertEqual(len(created), 1)
        self.assertEqual(created[0].calls[0]["huawei_cli"], {"enabled": True})

    def test_zte_selection_never_receives_huawei_only_cli_options(self):
        zte = FakeZTE()
        router = self.make_router(zte=zte)
        connection = router.connect(
            ip="192.168.1.1",
            username="admin",
            password="fixture",
            model_hint="F6201B",
            huawei_cli={"enabled": True},
        )

        self.assertEqual(connection.vendor, "zte")
        self.assertEqual(len(zte.calls), 1)
        self.assertNotIn("huawei_cli", zte.calls[0])

    def test_rfc6598_management_space_is_probed_but_public_neighbor_is_not(self):
        self.assertTrue(ProviderRouter._should_probe_vendor("100.64.0.1"))
        self.assertTrue(ProviderRouter._should_probe_vendor("100.127.255.254"))
        self.assertFalse(ProviderRouter._should_probe_vendor("100.128.0.1"))

    def test_invoke_filters_refresh_for_provider_without_refresh_parameter(self):
        class LegacyProvider:
            def read_capability(self, feature):
                return {"feature": feature}

        result = ProviderRouter.invoke(
            LegacyProvider(),
            "read_capability",
            "wifi",
            refresh=True,
        )
        self.assertEqual(result, {"feature": "wifi"})


if __name__ == "__main__":
    unittest.main()

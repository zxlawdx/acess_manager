from __future__ import annotations

import base64
import unittest
from pathlib import Path
from unittest.mock import patch

import requests

from apps.zte_manager.infrastructure.huawei.auth import (
    HuaweiCredentialSubmissionBudget,
    RandCountAuth,
)
from apps.zte_manager.infrastructure.huawei.errors import (
    HuaweiAuthFamilyAmbiguousError,
    HuaweiCredentialBudgetExceededError,
    HuaweiSameConnectionRequiredError,
)
from apps.zte_manager.infrastructure.huawei.family_client import HuaweiFamilyAwareWebClient
from apps.zte_manager.infrastructure.huawei.js_parser import HuaweiJsConstructorParser
from apps.zte_manager.infrastructure.huawei.negotiating_client import (
    HuaweiNegotiatingWebClient,
    _endpoint_from_input,
    parse_huawei_https_bootstrap,
)
from apps.zte_manager.infrastructure.huawei.protocol import (
    HuaweiProtocolFamily,
    clean_huawei_token,
    plausible_huawei_token,
    protocol_family_from_observations,
)
from apps.zte_manager.infrastructure.huawei.transport import (
    HuaweiTransportPolicy,
    RequestsSessionTransport,
)


FIXTURES = Path("tests/fixtures/huawei/phase0_research")


def fixture(name: str) -> str:
    return (FIXTURES / name).read_text(encoding="utf-8")


class FakeResponse:
    def __init__(self, text: str, status_code: int = 200) -> None:
        self.text = text
        self.status_code = status_code


class HuaweiPhase0ArchitectureTests(unittest.TestCase):
    def test_transport_policy_models_https_port_80_as_first_class(self):
        policy = HuaweiTransportPolicy(
            preferred_scheme="https", port=80, verify_tls=False,
            allow_self_signed=True, request_timeout=7.5,
        )
        self.assertEqual(policy.preferred_scheme, "https")
        self.assertEqual(policy.port, 80)
        self.assertFalse(policy.verify_tls)
        self.assertTrue(policy.allow_self_signed)
        self.assertEqual(policy.credential_submission_budget, 1)

    def test_transport_policy_rejects_credential_budget_above_one(self):
        with self.assertRaises(ValueError):
            HuaweiTransportPolicy(credential_submission_budget=2)

    def test_does_not_force_https_443(self):
        endpoint = _endpoint_from_input("https://192.0.2.10:80")
        self.assertEqual(endpoint.scheme, "https")
        self.assertEqual(endpoint.port, 80)
        self.assertEqual(endpoint.base_url, "https://192.0.2.10:80")

    def test_ipv4_host_port_rendering(self):
        endpoint = _endpoint_from_input("192.0.2.10:80")
        self.assertEqual(endpoint.host, "192.0.2.10")
        self.assertEqual(endpoint.port, 80)
        self.assertEqual(endpoint.base_url, "http://192.0.2.10:80")

    def test_js_sslport_parser_detects_https80_fixture(self):
        self.assertEqual(
            parse_huawei_https_bootstrap(fixture("http_bootstrap_https80.html")),
            80,
        )

    def test_requests_transport_refuses_fake_same_tcp_guarantee(self):
        policy = HuaweiTransportPolicy(challenge_login_connection_affinity=True)
        session = requests.Session()
        try:
            with self.assertRaises(HuaweiSameConnectionRequiredError):
                RequestsSessionTransport(session, policy)
        finally:
            session.close()

    def test_credential_budget_allows_exactly_one_submission(self):
        budget = HuaweiCredentialSubmissionBudget()
        budget.claim()
        self.assertEqual(budget.used, 1)
        self.assertEqual(budget.remaining, 0)
        with self.assertRaises(HuaweiCredentialBudgetExceededError):
            budget.claim()

    def test_randcount_hex64_and_bom_are_accepted(self):
        plain = fixture("randcount_hex64.txt")
        bom = fixture("randcount_bom.txt")
        self.assertTrue(bom.startswith("\ufeff"))
        self.assertEqual(len(clean_huawei_token(plain)), 64)
        self.assertEqual(len(clean_huawei_token(bom)), 64)
        self.assertTrue(plausible_huawei_token(plain))
        self.assertTrue(plausible_huawei_token(bom))
        self.assertEqual(
            RandCountAuth.normalize_challenge(bom),
            clean_huawei_token(plain),
        )

    def test_randcount_invalid_html_is_rejected(self):
        with self.assertRaises(ValueError):
            RandCountAuth.normalize_challenge(
                "<html><form action='login.cgi'></form></html>"
            )

    def test_randcount_payload_is_pure_base64_and_preserves_challenge(self):
        payload = RandCountAuth.build_payload(
            username="fixture-user",
            password="fixture-password",
            challenge="A" * 64,
        )
        self.assertEqual(payload["UserName"], "fixture-user")
        self.assertEqual(
            payload["PassWord"],
            base64.b64encode(b"fixture-password").decode("ascii"),
        )
        self.assertEqual(payload["Language"], "english")
        self.assertEqual(payload["x.X_HW_Token"], "A" * 64)

    def test_ambiguous_read_only_fingerprint_never_claims_credential_budget(self):
        client = HuaweiFamilyAwareWebClient(
            "192.0.2.10", "fixture-user", "fixture-password"
        )
        with patch.object(
            client, "_fetch_rand_count", return_value=FakeResponse("A" * 64)
        ), patch.object(
            client, "_fetch_rand_string", return_value=FakeResponse("B" * 64)
        ):
            with self.assertRaises(HuaweiAuthFamilyAmbiguousError) as raised:
                client._select_auth_flow("")
        self.assertEqual(raised.exception.code, "auth_family_ambiguous")
        self.assertEqual(client._credential_budget.used, 0)
        client.close()

    def test_negotiating_client_preserves_explicit_auth_ambiguity(self):
        client = HuaweiNegotiatingWebClient(
            "https://192.0.2.10:80",
            "fixture-user",
            "fixture-password",
        )
        try:
            with patch.object(
                HuaweiFamilyAwareWebClient,
                "login",
                side_effect=HuaweiAuthFamilyAmbiguousError(),
            ):
                with self.assertRaises(HuaweiAuthFamilyAmbiguousError) as raised:
                    client.login()
            self.assertEqual(raised.exception.code, "auth_family_ambiguous")
        finally:
            client.close()

    def test_api_boundary_exposes_auth_ambiguity_without_secret_text(self):
        from apps.zte_manager.presentation.api.common import _safe_call

        result = _safe_call(
            lambda: (_ for _ in ()).throw(HuaweiAuthFamilyAmbiguousError())
        )
        self.assertEqual(result["code"], "auth_family_ambiguous")
        self.assertEqual(result["type"], "unconfirmed")
        self.assertFalse(result["retryable"])
        self.assertIn("Nenhuma credencial foi submetida", result["error"])
        self.assertNotIn("fixture", result["error"].casefold())

    def test_js_constructor_parser_handles_hex_nested_and_variable_fields(self):
        source = r'''
        function stAssociatedDevice(a,b,c){this.Domain=a;this.MAC=b;this.Name=c;}
        var row = new stAssociatedDevice(
          'InternetGatewayDevice.LANDevice.1.WLANConfiguration.5',
          'AA:BB:CC:DD:EE:FF','RE\x5fTEST',helper(1, 2),'tail');
        '''
        parser = HuaweiJsConstructorParser({
            ("amp_bbsp", "stAssociatedDevice"): (
                "domain", "mac", "hostname", "nested", "tail"
            )
        })
        rows = parser.parse(source, protocol_family="amp_bbsp")
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["Name"], "RE_TEST")
        self.assertEqual(rows[0]["hostname"], "RE_TEST")
        self.assertEqual(rows[0]["nested"], "helper(1, 2)")
        self.assertEqual(rows[0]["tail"], "tail")
        self.assertEqual(len(rows[0]["_raw_args"]), 5)

    def test_api_sestoken_xml_json_fixtures_are_detection_evidence_only(self):
        for name in ("sestokeninfo.xml", "sestokeninfo.json"):
            with self.subTest(name=name):
                family, evidence = protocol_family_from_observations(
                    [], sources=(fixture(name),)
                )
                self.assertEqual(family, HuaweiProtocolFamily.API_SESTOKEN)
                self.assertEqual(evidence, ("api-sestoken-marker",))

    def test_api_sestoken_is_protocol_family_not_model_guess(self):
        family, evidence = protocol_family_from_observations([
            "/api/webserver/SesTokenInfo", "/api/system/deviceinfo",
        ])
        self.assertEqual(family, HuaweiProtocolFamily.API_SESTOKEN)
        self.assertIn("/api/webserver/SesTokenInfo", evidence)


if __name__ == "__main__":
    unittest.main()

from __future__ import annotations

import base64
import unittest
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
from apps.zte_manager.infrastructure.huawei.family_client import (
    HuaweiFamilyAwareWebClient,
)
from apps.zte_manager.infrastructure.huawei.js_parser import (
    HuaweiJsConstructorParser,
)
from apps.zte_manager.infrastructure.huawei.protocol import (
    HuaweiProtocolFamily,
    protocol_family_from_observations,
)
from apps.zte_manager.infrastructure.huawei.transport import (
    HuaweiTransportPolicy,
    RequestsSessionTransport,
)


class FakeResponse:
    def __init__(self, text: str, status_code: int = 200) -> None:
        self.text = text
        self.status_code = status_code


class HuaweiPhase0ArchitectureTests(unittest.TestCase):
    def test_transport_policy_models_https_port_80_as_first_class(self):
        policy = HuaweiTransportPolicy(
            preferred_scheme="https",
            port=80,
            verify_tls=False,
            allow_self_signed=True,
            request_timeout=7.5,
        )
        self.assertEqual(policy.preferred_scheme, "https")
        self.assertEqual(policy.port, 80)
        self.assertFalse(policy.verify_tls)
        self.assertTrue(policy.allow_self_signed)
        self.assertEqual(policy.credential_submission_budget, 1)

    def test_transport_policy_rejects_credential_budget_above_one(self):
        with self.assertRaises(ValueError):
            HuaweiTransportPolicy(credential_submission_budget=2)

    def test_requests_transport_refuses_fake_same_tcp_guarantee(self):
        policy = HuaweiTransportPolicy(
            challenge_login_connection_affinity=True,
        )
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
            "192.0.2.10",
            "fixture-user",
            "fixture-password",
        )
        with patch.object(
            client,
            "_fetch_rand_count",
            return_value=FakeResponse("A" * 64),
        ), patch.object(
            client,
            "_fetch_rand_string",
            return_value=FakeResponse("B" * 64),
        ):
            with self.assertRaises(HuaweiAuthFamilyAmbiguousError):
                client._select_auth_flow("")
        self.assertEqual(client._credential_budget.used, 0)
        client.close()

    def test_js_constructor_parser_handles_hex_nested_and_variable_fields(self):
        source = r'''
        function stAssociatedDevice(a,b,c){this.Domain=a;this.MAC=b;this.Name=c;}
        var row = new stAssociatedDevice(
          'InternetGatewayDevice.LANDevice.1.WLANConfiguration.5',
          'AA:BB:CC:DD:EE:FF',
          'RE\x5fTEST',
          helper(1, 2),
          'tail'
        );
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

    def test_api_sestoken_is_protocol_family_not_model_guess(self):
        family, evidence = protocol_family_from_observations([
            "/api/webserver/SesTokenInfo",
            "/api/system/deviceinfo",
        ])
        self.assertEqual(family, HuaweiProtocolFamily.API_SESTOKEN)
        self.assertIn("/api/webserver/SesTokenInfo", evidence)


if __name__ == "__main__":
    unittest.main()

from __future__ import annotations

import unittest

from apps.zte_manager.infrastructure.huawei.negotiating_client import (
    HuaweiTransportError,
    HuaweiTransportFailure,
)
from apps.zte_manager.services.error_policy import classify


class HuaweiTransportErrorPolicyTests(unittest.TestCase):
    def _failure(self, code: HuaweiTransportFailure):
        failure = classify(
            HuaweiTransportError(
                code,
                "fixture internal message must never become public",
                phase="fixture",
                original_exception="FixtureError",
                scheme="https",
                port=80,
                auth_flow="rand_count",
            )
        )
        self.assertIsNotNone(failure)
        return failure

    def test_network_error_has_distinct_safe_contract(self):
        failure = self._failure(HuaweiTransportFailure.NETWORK_ERROR)
        self.assertEqual(failure.code, "NETWORK_ERROR")
        self.assertEqual(failure.message, "Não foi possível alcançar a ONT.")
        self.assertTrue(failure.retryable)

    def test_tls_error_has_distinct_safe_contract(self):
        failure = self._failure(HuaweiTransportFailure.TLS_ERROR)
        self.assertEqual(failure.code, "TLS_ERROR")
        self.assertEqual(failure.message, "Não foi possível estabelecer TLS com a ONT.")
        self.assertTrue(failure.retryable)

    def test_auth_rejected_has_distinct_safe_contract(self):
        failure = self._failure(HuaweiTransportFailure.AUTH_REJECTED)
        self.assertEqual(failure.code, "AUTH_REJECTED")
        self.assertEqual(failure.message, "A ONT rejeitou a autenticação.")
        self.assertTrue(failure.retryable)

    def test_auth_protocol_mismatch_has_distinct_safe_contract(self):
        failure = self._failure(HuaweiTransportFailure.AUTH_PROTOCOL_MISMATCH)
        self.assertEqual(failure.code, "AUTH_PROTOCOL_MISMATCH")
        self.assertEqual(
            failure.message,
            "O fluxo de autenticação desta Huawei não foi reconhecido.",
        )
        self.assertFalse(failure.retryable)


if __name__ == "__main__":
    unittest.main()

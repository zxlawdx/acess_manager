"""Cross-boundary Vela integration: invoke real decorated API handlers with
simulated device service failures, not just a mocked frontend toast."""
from __future__ import annotations
import unittest
from unittest.mock import patch
from requests.exceptions import HTTPError

from apps.zte_manager import api as routes
from apps.zte_manager.services.error_policy import (
    AuthenticationFailure, SessionExpired, MissingFirmwareCapability,
    CapabilityUnconfirmed, NotAuthorized, PartialOperation,
    UnexpectedDeviceResponse,
)


class ApiBoundaryIntegration(unittest.TestCase):
    LOGIN = {"json": {
        "ip": "192.0.2.9", "username": "admin", "password": "DO_NOT_DISCLOSE",
        "attendant": "test",
    }}

    def test_real_connect_handler_success_and_classified_auth_failure(self):
        with patch.object(routes.zte_service, "connect", return_value={
            "success": True, "model": "F6600P", "model_verified": True
        }):
            result = routes.connect(self.LOGIN)
            self.assertTrue(result["success"])
            self.assertEqual(result["model"], "F6600P")
        with patch.object(routes.zte_service, "connect",
                          side_effect=AuthenticationFailure("token:DO_NOT_DISCLOSE")):
            result = routes.connect(self.LOGIN)
            self.assertEqual(result["code"], "AUTH_FAILED")
            self.assertEqual(result["type"], "authentication")
            self.assertNotIn("DO_NOT_DISCLOSE", str(result))

    def test_missing_request_fields_are_not_echoed(self):
        result = routes.connect({"json": {
            "ip": "192.0.2.9", "password": "DO_NOT_DISCLOSE",
        }})
        self.assertEqual(result["code"], "INVALID_INPUT")
        self.assertNotIn("DO_NOT_DISCLOSE", str(result))

    def test_live_status_route_is_preserved_and_does_not_read_password(self):
        with patch.object(routes.zte_service, "device_status",
                          return_value={"modelo": "F680", "firmware": "1.0"}):
            self.assertEqual(routes.device_status(), {
                "modelo": "F680", "firmware": "1.0"
            })

    def test_device_read_timeout_classifies_without_exposing_http(self):
        with patch.object(routes.zte_service, "wan_status", side_effect=TimeoutError(
            "GET /api/wan?password=DO_NOT_DISCLOSE"
        )):
            result = routes.wan_status()
            self.assertEqual(result["code"], "TIMEOUT")
            self.assertTrue(result["retryable"])
            self.assertNotIn("password", str(result).lower())

    def test_expired_session_is_distinct_from_permission(self):
        with patch.object(routes.zte_service, "wifi_networks",
                          side_effect=SessionExpired()):
            self.assertEqual(routes.wifi_networks()["code"], "SESSION_EXPIRED")
        with patch.object(routes.zte_service, "wifi_networks",
                          side_effect=PermissionError("secret auth token")):
            result = routes.wifi_networks()
            self.assertEqual(result["code"], "OPERATION_FORBIDDEN")
            self.assertNotEqual(result["type"], "unsupported")

    def test_unverified_capability_is_not_unsupported(self):
        for exc, expected in (
            (CapabilityUnconfirmed(), "CAPABILITY_UNCONFIRMED"),
            (UnexpectedDeviceResponse(), "INVALID_DEVICE_RESPONSE"),
        ):
            with self.subTest(exc=type(exc).__name__):
                result = routes._safe_call(lambda: (_ for _ in ()).throw(exc))
                self.assertEqual(result["code"], expected)
                self.assertNotEqual(result["type"], "unsupported")
        confirmed = routes._safe_call(
            lambda: (_ for _ in ()).throw(MissingFirmwareCapability())
        )
        self.assertEqual(confirmed["type"], "unsupported")
        self.assertEqual(confirmed["code"], "FEATURE_ABSENT")

    def test_http_404_is_not_evidence_of_unsupported_firmware(self):
        response = type("Response", (), {"status_code": 404})()
        error = HTTPError("GET /hidden?token=DO_NOT_DISCLOSE")
        error.response = response
        result = routes._safe_call(lambda: (_ for _ in ()).throw(error))
        self.assertEqual(result["code"], "ROUTE_UNCONFIRMED")
        self.assertEqual(result["type"], "unconfirmed")
        self.assertNotIn("DO_NOT_DISCLOSE", str(result))

    def test_partial_result_requires_reconciliation_not_retry_blindly(self):
        result = routes._safe_call(lambda: (_ for _ in ()).throw(
            PartialOperation("POST /secret token", completed=2, total=4)
        ))
        self.assertEqual(result["code"], "OPERATION_PARTIAL")
        self.assertEqual(result["completed"], 2)
        self.assertEqual(result["total"], 4)
        self.assertNotIn("secret", str(result).lower())


if __name__ == "__main__":
    unittest.main()

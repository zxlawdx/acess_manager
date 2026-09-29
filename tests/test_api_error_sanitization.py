"""Phase 3 API envelope: retain client contract without leaking host/device data."""
from __future__ import annotations

import re
import unittest
from unittest.mock import patch

from apps.zte_manager import api as api_module


class SanitizedApiErrorsTests(unittest.TestCase):
    def test_unexpected_error_has_stable_envelope_and_private_correlation(self):
        secret = "SECRET_OLT_ACCESS_PASSWORD_999"
        def failing_action():
            raise Exception("firmware=" + secret + " /home/technician/router.dump")

        with self.assertLogs(
            "apps.zte_manager.api", "ERROR"
        ) as logged:
            result = api_module._safe_call(failing_action)

        self.assertEqual(result["type"], "internal")
        self.assertEqual(set(result), {"error", "type", "code", "retryable", "error_id"})
        self.assertRegex(result["error_id"], r"^[0-9a-f]{32}$")
        self.assertIn(result["error_id"], result["error"])
        self.assertNotIn(secret, str(result))
        self.assertNotIn(secret, "\n".join(logged.output))
        self.assertNotIn("/home/technician/", "\n".join(logged.output))
        self.assertIn("error_type=Exception", logged.output[0])
        self.assertIn("action=failing_action", logged.output[0])
        self.assertIn("frames=", logged.output[0])

    def test_unhandled_type_error_does_not_leak_device_payload(self):
        class FakeFirmwareError(TypeError):
            pass
        def mutation():
            raise FakeFirmwareError("<xml>ONT PASSWORD:PRIVATE_TOKEN</xml>")
        with self.assertLogs("apps.zte_manager.api","ERROR") as logged:
            result = api_module._safe_call(mutation)
        self.assertNotIn("PRIVATE_TOKEN", str(result) + str(logged.output))
        self.assertEqual(result["type"], "internal")

    def test_existing_domain_error_keys_and_success_return_are_preserved(self):
        self.assertEqual(
            api_module._safe_call(lambda: {"success":True, "value":42}),
            {"success":True, "value":42},
        )
        validation = api_module._safe_call(
            lambda: (_ for _ in ()).throw(ValueError("Identificação inválida"))
        )
        self.assertEqual(validation, {
            "error":"Identificação inválida", "type":"validation",
            "code":"INVALID_INPUT", "retryable":False,
        })
        state = api_module._safe_call(
            lambda: (_ for _ in ()).throw(RuntimeError("Sessão expirada"))
        )
        self.assertEqual(state, {
            "error":"A sessão expirou. Reconecte-se ao equipamento.",
            "type":"session", "code":"SESSION_EXPIRED", "retryable":True,
        })


if __name__ == "__main__":
    unittest.main()

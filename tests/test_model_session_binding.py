"""Regression: a new ONT behind the same address must not reuse the old adapter."""
import unittest

from apps.zte_manager.services.zte_service import ZTEService
from apps.zte_manager.model.device_adapters import select_adapter


class FakeRouter:
    def __init__(self, identity):
        self.identity = identity
        self.base_url = "http://192.0.2.9"
        self.username = "admin"
        self.password = "not-a-real-password"
        self.writes_enabled = False

    def device_status(self):
        return dict(self.identity)


class RouterSwitchTests(unittest.TestCase):
    def service(self, model="F6201B"):
        service = ZTEService()
        service._zte = FakeRouter({"modelo": model,
                                   "firmware": "synthetic"})
        service._device_info = {"modelo": "F6201B"}
        service._selected_model = "F6201B"
        service._model_verified = True
        service._adapter = select_adapter("F6201B")
        service.current_host = "192.0.2.9"
        service.current_attendant = "tester"
        return service

    @staticmethod
    def reconnect(service, hint=None):
        return service.connect(
            "192.0.2.9", "admin", "not-a-real-password",
            model_hint=hint,
        )

    def test_switch_behind_same_ip_never_keeps_experimental_adapter(self):
        service = self.service("F6600P")
        with self.assertRaisesRegex(ValueError, "mudou"):
            self.reconnect(service)
        self.assertEqual(service._selected_model, "F6201B")

    def test_wrong_manual_hint_rejected_even_for_same_http_session(self):
        service = self.service("F6600P")
        with self.assertRaisesRegex(ValueError, "diverge"):
            self.reconnect(service, hint="F6201B")

    def test_confirmed_reuse_keeps_revision_and_validated_model(self):
        service = self.service("F6201B")
        revision = service._session_revision
        response = self.reconnect(service)
        self.assertTrue(response["reused_session"])
        self.assertTrue(response["model_verified"])
        self.assertEqual(response["session_revision"], revision)
        self.assertEqual(response["model"], "F6201B")

    def test_manual_change_without_real_detection_requires_reconnect(self):
        service = self.service("ZTE")
        with self.assertRaisesRegex(ValueError, "Desconecte"):
            self.reconnect(service, hint="F6600P")


if __name__ == "__main__":
    unittest.main()

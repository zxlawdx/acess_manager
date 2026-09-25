"""Regressões de uma tela Avançado que conecta mas não exibe dados."""

import unittest
from unittest.mock import patch

from apps.zte_manager import api
from apps.zte_manager.services import model_diagnostic_service as models
from apps.zte_manager.services.zte_service import zte_service


class BootstrapRecoveryTests(unittest.TestCase):
    def test_bootstrap_does_not_call_ont_or_take_session_lock(self):
        """Mesmo com o contexto do roteador ocupado, a UI deve abrir."""
        sentinel = object()
        with patch.object(zte_service, "_zte", sentinel), patch.object(
            zte_service, "_selected_model", "F6600P"
        ), patch.object(
            zte_service, "_device_info", {"modelo": "F6600P",
                                         "firmware": "V9.0.10P6N6"}
        ), patch.object(
            zte_service, "multimodel_catalog",
            return_value={"models": [{"model": "F6600P"}]}
        ) as catalog:
            result = api.discovery_bootstrap()
        self.assertTrue(result["connected"])
        self.assertEqual(result["model"], "F6600P")
        self.assertEqual(result["firmware"], "V9.0.10P6N6")
        self.assertEqual(result["catalog"]["models"][0]["model"], "F6600P")
        self.assertFalse(result["writes_enabled"])
        catalog.assert_called_once()

    def test_unsupported_section_is_rejected_without_any_ont_call(self):
        with self.assertRaises(ValueError):
            models.diagnostic(object(), "F6600P", section="erase_settings")

    def test_empty_wan_is_not_counted_as_a_successful_read(self):
        result = models._result("wan", lambda: [])
        self.assertFalse(result["available"])
        self.assertEqual(result["reason"], "no_data_from_firmware")

    def test_zero_connected_clients_is_legitimate(self):
        result = models._result("wifi_clients", lambda: {"connected": 0})
        self.assertTrue(result["available"])


if __name__ == "__main__":
    unittest.main()

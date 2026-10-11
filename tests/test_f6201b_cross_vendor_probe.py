from __future__ import annotations

import unittest
from unittest.mock import patch

from apps.zte_manager.presentation.api import f6201b as f6201b_api


class F6201BCrossVendorProbeTests(unittest.TestCase):
    def test_huawei_profile_page_probe_is_negative_without_touching_active_provider(self):
        status = {
            "connected": True,
            "vendor": "huawei",
            "model": "EG8041X6-10",
            "writes_enabled": True,
        }
        with patch.object(
            f6201b_api.device_service,
            "status",
            return_value=status,
        ), patch.object(f6201b_api, "_call_f6201b") as provider_call:
            result = f6201b_api.f6201b_write_status()

        provider_call.assert_not_called()
        self.assertFalse(result["supported_firmware"])
        self.assertFalse(result["writes_enabled"])
        self.assertTrue(result["connected"])
        self.assertEqual(result["vendor"], "huawei")
        self.assertEqual(result["model"], "EG8041X6-10")
        self.assertEqual(result["reason"], "active_session_is_not_f6201b")
        self.assertNotIn("error", result)

    def test_actual_f6201b_session_uses_active_workspace(self):
        status = {
            "connected": True,
            "vendor": "zte",
            "model": "F6201B",
        }
        expected = {
            "supported_firmware": True,
            "writes_enabled": True,
        }
        with patch.object(
            f6201b_api.device_service,
            "status",
            return_value=status,
        ), patch.object(
            f6201b_api,
            "_call_f6201b",
            return_value=expected,
        ) as provider_call:
            result = f6201b_api.f6201b_write_status()

        provider_call.assert_called_once_with("f6201b_write_status")
        self.assertEqual(result, expected)

    def test_disconnected_probe_is_also_side_effect_free(self):
        with patch.object(
            f6201b_api.device_service,
            "status",
            return_value={
                "connected": False,
                "vendor": None,
                "model": None,
            },
        ), patch.object(f6201b_api, "_call_f6201b") as provider_call:
            result = f6201b_api.f6201b_write_status()

        provider_call.assert_not_called()
        self.assertFalse(result["supported_firmware"])
        self.assertFalse(result["connected"])


if __name__ == "__main__":
    unittest.main()

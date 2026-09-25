"""API/service boundary for the one-action F6201B saved profile command."""
import unittest
from unittest.mock import patch

from apps.zte_manager.services.zte_service import ZTEService
from apps.zte_manager.services.f6201b_writes import EXACT_FIRMWARE


class SavedProfileServiceTests(unittest.TestCase):
    def setUp(self):
        self.service = ZTEService()
        self.service.current_attendant = "tech-synthetic"
        self.service.current_host = "192.0.2.52"
        self.service._session_revision = "session-synthetic"

    def test_other_saved_presets_are_not_an_employee_permission_boundary(self):
        fake = object()
        expected = {"success": True, "noop": False}
        with patch.object(self.service, "_f6201b_write_firmware",
                          return_value=EXACT_FIRMWARE), patch.object(
            self.service, "get_client", return_value=fake
        ), patch(
            "apps.zte_manager.services.zte_service.profile_service.get_profile",
            return_value={"wifi": {}, "dns": {}}
        ) as storage, patch.object(
            self.service._f6201b_profile, "apply_saved",
            return_value=expected
        ) as command:
            report = self.service.f6201b_profile_apply_saved("other-tech")
        self.assertEqual(report, expected)
        storage.assert_called_once_with("other-tech")
        self.assertIs(command.call_args.args[0], fake)

    def test_executes_one_internal_command_from_persisted_profile(self):
        preset = {"wifi": {"2.4GHz": {"auto_channel": True}},
                  "dns": {"ipv4_1": "192.0.2.11"}}
        expected = {"success": True, "verified": True, "noop": False}
        fake_ont = object()
        self.service._readonly_original_post = lambda: None
        with patch.object(self.service, "_f6201b_write_firmware",
                          return_value=EXACT_FIRMWARE), patch.object(
            self.service, "get_client", return_value=fake_ont
        ), patch(
            "apps.zte_manager.services.zte_service.profile_service.get_profile",
            return_value=preset
        ) as storage, patch.object(
            self.service._f6201b_profile, "apply_saved",
            return_value=expected
        ) as command:
            report = self.service.f6201b_profile_apply_saved("tech-synthetic")
        self.assertEqual(report, expected)
        storage.assert_called_once_with("tech-synthetic")
        kwargs = command.call_args.kwargs
        self.assertIs(command.call_args.args[0], fake_ont)
        self.assertEqual(kwargs["profile"], preset)
        self.assertEqual(kwargs["revision"], "session-synthetic")
        self.assertEqual(kwargs["host"], "192.0.2.52")


if __name__ == "__main__":
    unittest.main()

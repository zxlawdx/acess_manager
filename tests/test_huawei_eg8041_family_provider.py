from __future__ import annotations

import unittest
from pathlib import Path
from unittest.mock import patch

from apps.zte_manager.services.device_service import DeviceService, DeviceSession
from apps.zte_manager.services.huawei_eg8041_family_provider import (
    HuaweiEG8041FamilyProvider,
)


class FakeZte:
    connected = False

    def connect(self, **kwargs):
        return {"success": True, "model": "F670L", "adapter": "generic"}

    def disconnect(self):
        self.connected = False


class FakeHuaweiProfileProvider:
    connected = True
    capabilities = {"wifi_radio": {"read": True, "update": True}}

    def apply_profile(self, attendant=None):
        return {"provider": "huawei", "attendant": attendant, "success": True}


class HuaweiEg8041FamilyProviderTests(unittest.TestCase):
    def test_generic_feature_api_reads_family_channel_discovery(self):
        service = HuaweiEG8041FamilyProvider()
        service._family_compatible = True
        service.model = "EG8041X6-10"
        service._capabilities = {
            "wifi_channel_discovery": {
                "read": True,
                "write": False,
                "state": "READ_SUPPORTED",
            }
        }
        with patch.object(
            service,
            "wifi_channels",
            side_effect=lambda band, country="BR": [{
                "band": band,
                "country": country,
                "canais": [1, 6, 11] if "2.4" in band else [36, 40],
            }],
        ):
            response = service.read_capability("wifi_channel_discovery")

        self.assertTrue(response["available"])
        self.assertFalse(response["writable"])
        self.assertEqual(
            response["objects"]["items"]["2.4ghz"][0]["canais"],
            [1, 6, 11],
        )

    def test_diagnostics_capability_describes_generic_route_without_running_test(self):
        service = HuaweiEG8041FamilyProvider()
        service._family_compatible = True
        service.model = "EG8041X6-10"
        service._capabilities = {
            "diagnostics.ping": {
                "read": True,
                "write": True,
                "state": "WRITE_SUPPORTED",
                "physical_validation": True,
            }
        }
        response = service.read_capability("diagnostics.ping")
        contract = response["objects"]["items"]
        self.assertEqual(contract["start_route"], "/diagnostics/ping")
        self.assertTrue(contract["native"])

    def test_configuration_profile_api_remains_device_service_driven(self):
        source = Path(
            "apps/zte_manager/presentation/api/profiles.py"
        ).read_text(encoding="utf-8")
        self.assertIn("device_service.apply_profile", source)
        self.assertNotIn("f6201b_profile", source.casefold())

    def test_active_huawei_profile_apply_does_not_fall_through_to_zte(self):
        manager = DeviceService(zte_provider=FakeZte())
        provider = FakeHuaweiProfileProvider()
        manager._session = DeviceSession(
            vendor="huawei",
            model="EG8041X6-10",
            profile="huawei_unknown",
            provider="FakeHuaweiProfileProvider",
            service=provider,
        )

        result = manager.apply_profile("operator")
        self.assertEqual(result["provider"], "huawei")
        self.assertTrue(result["success"])


if __name__ == "__main__":
    unittest.main()

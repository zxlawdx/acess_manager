from __future__ import annotations

import unittest

from apps.zte_manager.infrastructure.huawei.negotiating_client import (
    HuaweiNegotiatingWebClient,
)
from apps.zte_manager.services.device_service import DeviceService
from apps.zte_manager.services.huawei_eg8041_family_provider import (
    HuaweiEG8041FamilyProvider,
)
from apps.zte_manager.services.huawei_unified_provider import (
    HuaweiUnifiedProvider,
)


class HuaweiProductionTransportTests(unittest.TestCase):
    def test_device_service_production_path_uses_negotiating_transport(self):
        service = DeviceService()
        self.assertIs(service._huawei_client_type, HuaweiNegotiatingWebClient)
        self.assertIs(service._huawei_factory, HuaweiUnifiedProvider)
        self.assertTrue(issubclass(HuaweiUnifiedProvider, HuaweiEG8041FamilyProvider))

    def test_family_provider_uses_same_embedded_tls_transport(self):
        provider = HuaweiUnifiedProvider()
        self.assertIs(provider._client_factory, HuaweiNegotiatingWebClient)
        client = provider._client_factory(
            "192.0.2.10:80",
            "operator",
            "fixture-password",
            https=True,
        )
        try:
            self.assertEqual(client.base_url, "https://192.0.2.10:80")
            self.assertFalse(client.session.verify)
        finally:
            client.close()


if __name__ == "__main__":
    unittest.main()

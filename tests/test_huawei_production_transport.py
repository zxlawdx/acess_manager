from __future__ import annotations

import unittest

from apps.zte_manager.infrastructure.huawei.affinity_client import (
    HuaweiAffinityNegotiatingWebClient,
)
from apps.zte_manager.infrastructure.huawei.negotiating_client import (
    HuaweiNegotiatingWebClient,
)
from apps.zte_manager.services.device_service import DeviceService
from apps.zte_manager.services.huawei_affinity_provider import (
    HuaweiAffinityUnifiedProvider,
)
from apps.zte_manager.services.huawei_eg8041_family_provider import (
    HuaweiEG8041FamilyProvider,
)
from apps.zte_manager.services.huawei_unified_provider import (
    HuaweiUnifiedProvider,
)


class HuaweiProductionTransportTests(unittest.TestCase):
    def test_device_service_production_path_uses_affinity_aware_negotiating_transport(self):
        service = DeviceService()
        self.assertIs(
            service._huawei_client_type,
            HuaweiAffinityNegotiatingWebClient,
        )
        self.assertIs(service._huawei_factory, HuaweiAffinityUnifiedProvider)
        self.assertTrue(
            issubclass(HuaweiAffinityNegotiatingWebClient, HuaweiNegotiatingWebClient)
        )
        self.assertTrue(
            issubclass(HuaweiAffinityUnifiedProvider, HuaweiUnifiedProvider)
        )
        self.assertTrue(issubclass(HuaweiUnifiedProvider, HuaweiEG8041FamilyProvider))

    def test_affinity_provider_keeps_embedded_tls_transport_and_defaults_affinity_off(self):
        provider = HuaweiAffinityUnifiedProvider()
        self.assertIs(provider._client_factory, HuaweiAffinityNegotiatingWebClient)
        client = provider._client_factory(
            "192.0.2.10:80",
            "operator",
            "fixture-password",
            https=True,
        )
        try:
            self.assertEqual(client.base_url, "https://192.0.2.10:80")
            self.assertFalse(client.session.verify)
            descriptor = client.transport_descriptor()
            self.assertFalse(descriptor["challenge_login_connection_affinity"])
            self.assertIsNone(descriptor["endpoint_profile"])
        finally:
            client.close()


if __name__ == "__main__":
    unittest.main()

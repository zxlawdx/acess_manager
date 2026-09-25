"""Geração de estrutura para investigar firmwares sem expor valores."""

import unittest
from unittest.mock import Mock

from apps.zte_manager.services.capability_service import CapabilityService


class FakeAdapter:
    name = "zte-f670l-thinklua"
    features = {"dhcp_leases": object()}


class CapabilityShapeTests(unittest.TestCase):
    def test_shape_contains_only_field_names_and_counts(self):
        service = CapabilityService(
            Mock(),
            FakeAdapter(),
        )

        service.gateway.read = Mock(
            return_value={
                "feature": "dhcp_leases",
                "available": True,
                "endpoint": {
                    "view": "lanMgrIpv4",
                    "tag": "test.lua",
                },
                "objects": {
                    "OBJ_DHCPHOSTINFO_ID": [
                        {
                            "HostName": "cliente-pessoal",
                            "MACAddress": "AA:BB:CC:DD:EE:FF",
                            "IPAddress": "192.168.1.40",
                        },
                    ],
                    "__meta__": {
                        "SerialNumber": "sensivel",
                    },
                },
            }
        )

        result = service.shape("dhcp_leases")
        self.assertEqual(
            result["objects"]["OBJ_DHCPHOSTINFO_ID"]["count"],
            1,
        )
        self.assertEqual(
            result["objects"]["OBJ_DHCPHOSTINFO_ID"]["fields"],
            ["HostName", "IPAddress", "MACAddress"],
        )

        rendered = str(result)
        self.assertNotIn("cliente-pessoal", rendered)
        self.assertNotIn("AA:BB:CC:DD:EE:FF", rendered)
        self.assertNotIn("sensivel", rendered)


if __name__ == "__main__":
    unittest.main()

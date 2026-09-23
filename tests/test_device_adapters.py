import unittest

from apps.zte_manager.model.device_adapters import (
    F6600PAdapter,
    F670LAdapter,
    ThinkLuaAdapter,
    select_adapter,
)


class DeviceAdapterTests(unittest.TestCase):
    def test_selects_f670l_adapter(self):
        adapter = select_adapter(
            "ZXHN F670L",
            "V9.0.11P1N40",
        )

        self.assertIsInstance(
            adapter,
            F670LAdapter,
        )
        self.assertIn(
            "dhcp_basic",
            adapter.features,
        )
        self.assertIn(
            "tr069",
            adapter.features,
        )

    def test_selects_f6600p_adapter(self):
        adapter = select_adapter(
            "F6600P",
            "V9.0.10P6N34",
        )

        self.assertIsInstance(
            adapter,
            F6600PAdapter,
        )

    def test_unknown_model_uses_thinklua_fallback(self):
        adapter = select_adapter(
            "ZXHN TEST",
            "1.0",
        )

        self.assertIsInstance(
            adapter,
            ThinkLuaAdapter,
        )
        self.assertEqual(
            adapter.feature(
                "port_forwarding"
            ).dangerous,
            True,
        )


if __name__ == "__main__":
    unittest.main()

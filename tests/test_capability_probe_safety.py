"""Probe failures are inconclusive and must not expose ThinkLua internals."""
import unittest
from types import SimpleNamespace
from apps.zte_manager.services.capability_service import ThinkLuaCapabilityGateway, _mask_secrets


class Adapter:
    features = {"wifi_status": object()}
    def feature(self, key):
        if key != "wifi_status":
            raise KeyError(key)
        endpoint = SimpleNamespace(
            view="secretView", tag="POST-secret.lua",
            query={"password": "VERY_SECRET"}, object_keys=(),
        )
        return SimpleNamespace(
            label="Wi-Fi", endpoints=(endpoint,), writable=False,
            dangerous=False, notes="",
        )


class Device:
    def get_view(self, *args, **kwargs):
        raise RuntimeError("POST /secret?password=VERY_SECRET")


class ProbeSafetyTests(unittest.TestCase):
    def test_inspection_masks_nested_acs_urls_and_wifi_keys(self):
        original = {
            "OBJ_MANAGESERVER_ID": [
                {"URL": "https://admin:PRIVATE@example.org/acs",
                 "ConnectionRequestURL": "http://router.local/?token=SECRET",
                 "UserName": "admin", "Password": "PRIVATE_PSK",
                 "PeriodicInformEnable": "1",
                 "PeriodicInformInterval": "3600"},
            ],
            "OBJ_WLAN_ID": [{"PSK": "WIFI_PASSWORD",
                             "SSID": "Rede local"}],
            "logStr": "password=SECRET",
        }
        sanitized = _mask_secrets(original)
        self.assertNotIn("PRIVATE", str(sanitized))
        self.assertNotIn("SECRET", str(sanitized))
        self.assertNotIn("admin", str(sanitized))
        self.assertNotIn("WIFI_PASSWORD", str(sanitized))
        self.assertEqual(sanitized["OBJ_WLAN_ID"][0]["SSID"], "Rede local")
        self.assertEqual(
            sanitized["OBJ_MANAGESERVER_ID"][0]["PeriodicInformInterval"],
            "3600",
        )


    def test_failed_probe_is_inconclusive_without_protocol_details(self):
        gateway=ThinkLuaCapabilityGateway(Device(),Adapter())
        result=gateway.probe("wifi_status")
        self.assertFalse(result["available"])
        self.assertEqual(result["status"], "inconclusive")
        self.assertEqual(result["reason"], "probe_inconclusive")
        self.assertTrue(result["probeable"])

        message=result["error"].lower()
        for secret in ("post","secretview","very_secret","http","query",".lua"):
            self.assertNotIn(secret,message)
        self.assertIn("não foi possível confirmar",message)


if __name__=="__main__":
    unittest.main()

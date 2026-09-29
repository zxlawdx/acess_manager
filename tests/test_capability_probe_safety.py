"""Probe failures are inconclusive and must not expose ThinkLua internals."""
import unittest
from types import SimpleNamespace
from apps.zte_manager.services.capability_service import ThinkLuaCapabilityGateway


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
    def test_failed_probe_is_inconclusive_without_protocol_details(self):
        gateway=ThinkLuaCapabilityGateway(Device(),Adapter())
        result=gateway.probe("wifi_status")
        self.assertFalse(result["available"])
        message=result["error"].lower()
        for secret in ("post","secretview","very_secret","http","query",".lua"):
            self.assertNotIn(secret,message)
        self.assertIn("não foi possível confirmar",message)


if __name__=="__main__":
    unittest.main()

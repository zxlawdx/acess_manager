from __future__ import annotations

import unittest
from unittest.mock import patch

from apps.zte_manager.infrastructure.huawei.detector import HuaweiDetector
from apps.zte_manager.infrastructure.huawei.family_client import (
    HuaweiFamilyAwareWebClient,
)
from apps.zte_manager.infrastructure.huawei.protocol import (
    HuaweiAuthFlow,
    HuaweiProtocolFamily,
    auth_flow_from_login_page,
    protocol_family_from_observations,
)
from apps.zte_manager.services.huawei_pon import HuaweiPonStateReader
from apps.zte_manager.services.huawei_wifi_domain_runtime import (
    HuaweiWifiDomainRuntimeService,
)


class FakeResponse:
    def __init__(self, status_code=200, text="", url="http://192.168.18.1/"):
        self.status_code = status_code
        self.text = text
        self.url = url
        self.headers = {}
        self.history = []
        self.request = None


class FakeCookies:
    def clear(self):
        return None


class ScriptedSession:
    def __init__(self, *, flow: str, login_ok: bool = True):
        self.flow = flow
        self.login_ok = login_ok
        self.cookies = FakeCookies()
        self.closed = False
        self.login_submissions = 0
        self.calls = []

    def close(self):
        self.closed = True

    def get(self, url, **kwargs):
        self.calls.append(("GET", url))
        if url.endswith("/"):
            marker = (
                "getRandString.asp"
                if self.flow == "rand_string"
                else "GetRandCount.asp"
            )
            return FakeResponse(200, f'<script src="{marker}"></script>', url)
        if url.endswith("getRandString.asp"):
            return FakeResponse(200, "\ufeff" + "a" * 32, url)
        if url.endswith("GetRandToken.asp"):
            return FakeResponse(200, "\ufeff" + "b" * 32, url)
        if url.endswith("GetRandCount.asp"):
            return FakeResponse(200, "c" * 32, url)
        if url.endswith("deviceinfo.asp"):
            return FakeResponse(
                200,
                'var ProductName="EG8145V5"; var SoftwareVersion="V500R019C00";',
                url,
            )
        return FakeResponse(404, "", url)

    def post(self, url, data=None, **kwargs):
        self.calls.append(("POST", url))
        if url.endswith("GetRandCount.asp"):
            return FakeResponse(200, "c" * 32, url)
        if url.endswith("login.cgi"):
            self.login_submissions += 1
            if self.login_ok:
                return FakeResponse(200, "", "http://192.168.18.1/index.asp")
            return FakeResponse(
                200,
                '<form action="login.cgi"><input name="UserName"></form>',
                "http://192.168.18.1/login.cgi",
            )
        if url.endswith("getMenuArray.asp"):
            if self.login_ok:
                return FakeResponse(200, "bbsp home page", url)
            return FakeResponse(403, "Forbidden", url)
        return FakeResponse(404, "", url)


class PageClient:
    def __init__(self, source: str):
        self.source = source

    def get_page(self, path: str) -> str:
        return self.source


class DetectorClient:
    def protocol_descriptor(self):
        return {
            "family": "amp_bbsp",
            "auth_flow": "rand_string_session_token",
            "evidence": ["/html/ssmp/common/getRandString.asp"],
        }

    def get_page(self, path: str):
        if path.endswith("deviceinfo.asp"):
            return (
                'var ProductName = "EG8021V5";'
                'var SoftwareVersion = "V500R020C10";'
            )
        raise RuntimeError("not mapped in fixture")


PON_FIXTURE = """
<script>
var PonMode = "GPON";
var CfgModeWord = "Route";
var state = new OntStateInfo("ignored", "12", "O5", "extra");
</script>
"""


class HuaweiMultirepoFoundationTests(unittest.TestCase):
    def test_auth_flow_is_selected_from_explicit_login_page_evidence(self):
        self.assertEqual(
            auth_flow_from_login_page("/asp/GetRandCount.asp"),
            HuaweiAuthFlow.RAND_COUNT,
        )
        self.assertEqual(
            auth_flow_from_login_page("/html/ssmp/common/getRandString.asp"),
            HuaweiAuthFlow.RAND_STRING_SESSION_TOKEN,
        )

    def test_protocol_family_depends_on_observed_endpoints_not_model(self):
        family, _ = protocol_family_from_observations(
            ["/html/ssmp/deviceinfo/deviceinfo.asp", "/html/bbsp/common/ontstate.asp"]
        )
        self.assertEqual(family, HuaweiProtocolFamily.AMP_BBSP)
        family, _ = protocol_family_from_observations(["/asp/GetConfig.asp?para=X"])
        self.assertEqual(family, HuaweiProtocolFamily.ASP_CONFIG)

    def test_detector_keeps_unknown_model_unverified_but_preserves_identity(self):
        detection = HuaweiDetector.detect_authenticated(DetectorClient())
        self.assertEqual(detection.model, "EG8021V5")
        self.assertEqual(detection.firmware, "V500R020C10")
        self.assertEqual(detection.confidence, "medium")
        self.assertFalse(detection.verified)
        self.assertEqual(detection.protocol_family, HuaweiProtocolFamily.AMP_BBSP)
        self.assertEqual(
            detection.auth_flow,
            HuaweiAuthFlow.RAND_STRING_SESSION_TOKEN,
        )

    def test_rand_string_login_strips_bom_and_uses_post_login_session_token(self):
        session = ScriptedSession(flow="rand_string")
        with patch.object(
            HuaweiFamilyAwareWebClient,
            "_new_session",
            staticmethod(lambda: session),
        ):
            client = HuaweiFamilyAwareWebClient(
                "192.168.18.1",
                "user",
                "not-a-real-password",
            )
            self.assertTrue(client.login(retries=4))
        self.assertEqual(session.login_submissions, 1)
        self.assertEqual(
            client.auth_flow,
            HuaweiAuthFlow.RAND_STRING_SESSION_TOKEN,
        )
        self.assertEqual(client.protocol_family, HuaweiProtocolFamily.AMP_BBSP)
        descriptor = client.protocol_descriptor()
        self.assertNotIn("token", " ".join(descriptor.keys()).casefold())
        self.assertNotIn("a" * 32, str(descriptor))
        self.assertNotIn("b" * 32, str(descriptor))

    def test_failed_login_never_blind_retries_credentials(self):
        session = ScriptedSession(flow="rand_count", login_ok=False)
        with patch.object(
            HuaweiFamilyAwareWebClient,
            "_new_session",
            staticmethod(lambda: session),
        ):
            client = HuaweiFamilyAwareWebClient(
                "192.168.18.1",
                "user",
                "not-a-real-password",
            )
            with self.assertRaises(RuntimeError):
                client.login(retries=9)
        self.assertEqual(session.login_submissions, 1)

    def test_pon_reader_uses_existing_constructor_parser_and_normalizes_state(self):
        result = HuaweiPonStateReader(PageClient(PON_FIXTURE)).read()
        self.assertEqual(result["pon_mode"], "GPON")
        self.assertEqual(result["registration_status"], "O5")
        self.assertEqual(result["onu_id"], "12")
        self.assertEqual(result["configuration_mode"], "Route")
        self.assertTrue(result["online"])

    def test_unrecognized_pon_response_is_not_claimed_as_supported(self):
        with self.assertRaises(RuntimeError):
            HuaweiPonStateReader(PageClient("<html>unknown</html>")).read()

    def test_runtime_promotes_pon_read_only_after_successful_probe(self):
        runtime = HuaweiWifiDomainRuntimeService()
        runtime._client = PageClient(PON_FIXTURE)
        runtime.current_host = "fixture"
        runtime.model = "EG8021V5"
        runtime._capabilities = {}
        runtime._probe_pon_state()
        capability = runtime._capabilities["pon"]
        self.assertTrue(capability["read"])
        self.assertFalse(capability["write"])
        self.assertFalse(capability["verified"])
        self.assertEqual(capability["state"], "READ_SUPPORTED")
        response = runtime.read_capability("pon")
        self.assertEqual(response["objects"]["items"]["registration_status"], "O5")

    def test_runtime_keeps_pon_unknown_when_probe_cannot_parse_response(self):
        runtime = HuaweiWifiDomainRuntimeService()
        runtime._client = PageClient("<html>unknown</html>")
        runtime.current_host = "fixture"
        runtime.model = "EG8041X7-10"
        runtime._capabilities = {}
        runtime._probe_pon_state()
        capability = runtime._capabilities["pon"]
        self.assertFalse(capability["read"])
        self.assertEqual(capability["state"], "UNKNOWN")


if __name__ == "__main__":
    unittest.main()

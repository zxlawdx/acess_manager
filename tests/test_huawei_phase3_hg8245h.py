from __future__ import annotations

import base64
import hashlib
import unittest
from pathlib import Path
from unittest.mock import patch
from urllib.parse import urlsplit

from apps.zte_manager.infrastructure.huawei.auth import (
    ApiSesTokenAuth,
    HuaweiCredentialSubmissionBudget,
)
from apps.zte_manager.infrastructure.huawei.errors import (
    HuaweiAuthFamilyAmbiguousError,
)
from apps.zte_manager.infrastructure.huawei.family_client import (
    API_DEVICE_INFO_PATH,
    API_LOGIN_PATH,
    API_SES_TOKEN_PATH,
    HuaweiFamilyAwareWebClient,
)
from apps.zte_manager.infrastructure.huawei.protocol import (
    HuaweiAuthFlow,
    HuaweiProtocolFamily,
)
from apps.zte_manager.services.huawei_hg8245h_runtime import (
    HuaweiHG8245HApiRuntime,
)
from apps.zte_manager.services.huawei_unified_provider import HuaweiUnifiedProvider


FIXTURES = Path("tests/fixtures/huawei/phase3")


def fixture(name: str) -> str:
    return (FIXTURES / name).read_text(encoding="utf-8")


class FakeCookies:
    def clear(self) -> None:
        return None


class FakeResponse:
    def __init__(
        self,
        text: str = "",
        *,
        status_code: int = 200,
        headers: dict | None = None,
        url: str = "http://192.0.2.10/",
    ) -> None:
        self.text = text
        self.status_code = status_code
        self.headers = dict(headers or {})
        self.url = url
        self.history = []
        self.request = None


class ScriptedSession:
    def __init__(self, mode: str = "api", *, ambiguous_script: bool = False) -> None:
        self.mode = mode
        self.ambiguous_script = ambiguous_script
        self.headers: dict[str, str] = {}
        self.cookies = FakeCookies()
        self.verify = False
        self.calls: list[tuple[str, str, dict]] = []
        self.credential_posts: list[tuple[str, dict]] = []

    @staticmethod
    def _path(url: str) -> str:
        parsed = urlsplit(url)
        return parsed.path or "/"

    def close(self) -> None:
        return None

    def get(self, url: str, **kwargs):
        path = self._path(url)
        self.calls.append(("GET", path, dict(kwargs)))
        if path == "/":
            if self.mode == "legacy":
                return FakeResponse(
                    "<html><script>var p='/asp/GetRandCount.asp';</script></html>",
                    url=url,
                )
            return FakeResponse(fixture("login_sha256.html"), url=url)
        if path == API_SES_TOKEN_PATH:
            body = (
                fixture("api_unavailable.html")
                if self.mode == "legacy"
                else fixture("sestokeninfo.xml")
            )
            return FakeResponse(body, url=url)
        if path == "/js/safelogin.js":
            body = (
                "function login(password){ return password; }"
                if self.ambiguous_script
                else fixture("safelogin.js")
            )
            return FakeResponse(body, url=url)
        if path == API_DEVICE_INFO_PATH:
            return FakeResponse(fixture("deviceinfo.xml"), url=url)
        if path == "/html/ssmp/deviceinfo/deviceinfo.asp":
            return FakeResponse("<html>legacy device page</html>", url=url)
        raise AssertionError(f"unexpected GET {path}")

    def post(self, url: str, data=None, **kwargs):
        path = self._path(url)
        payload = dict(data or {})
        self.calls.append(("POST", path, {**dict(kwargs), "data": payload}))
        if path == API_LOGIN_PATH:
            self.credential_posts.append((path, payload))
            return FakeResponse("", url=url)
        if path == "/asp/GetRandCount.asp":
            return FakeResponse("A" * 64, url=url)
        if path == "/login.cgi":
            self.credential_posts.append((path, payload))
            return FakeResponse("login-ok", url=url)
        if path == "/asp/getMenuArray.asp":
            return FakeResponse("Home Page bbsp", url=url)
        raise AssertionError(f"unexpected POST {path}")


class RuntimeClient:
    def __init__(self, model: str = "HG8245H") -> None:
        self.auth_flow = HuaweiAuthFlow.API_SES_TOKEN
        self.protocol_family = HuaweiProtocolFamily.API_SESTOKEN
        self.model = model
        self.device_source = fixture("deviceinfo.xml").replace("HG8245H", model)
        self.reads: list[str] = []

    def authenticated_identity_source(self):
        return API_DEVICE_INFO_PATH, self.device_source

    def get_api_page(self, path: str):
        self.reads.append(path)
        if path != API_DEVICE_INFO_PATH:
            raise RuntimeError("unsupported API fixture")
        return self.device_source


class HuaweiPhase3HG8245HTests(unittest.TestCase):
    def test_sestoken_parser_accepts_xml_and_json(self):
        for name in ("sestokeninfo.xml", "sestokeninfo.json"):
            with self.subTest(name=name):
                context = ApiSesTokenAuth.parse_session_token_info(fixture(name))
                self.assertTrue(context.session_info)
                self.assertGreaterEqual(len(context.token), 16)

    def test_api_password_encodings_match_reference_formula(self):
        context = ApiSesTokenAuth.parse_session_token_info(fixture("sestokeninfo.xml"))
        password = "fixture-password"
        b64 = base64.b64encode(password.encode()).decode("ascii")
        self.assertEqual(
            ApiSesTokenAuth.encode_password(password, context.token, "base64"),
            b64,
        )
        digest = hashlib.sha256((b64 + context.token).encode()).hexdigest()
        expected = base64.b64encode(digest.encode("ascii")).decode("ascii")
        self.assertEqual(
            ApiSesTokenAuth.encode_password(password, context.token, "token_sha256"),
            expected,
        )

    def test_ambiguous_api_password_mode_does_not_claim_budget(self):
        auth = ApiSesTokenAuth(HuaweiCredentialSubmissionBudget())
        context = ApiSesTokenAuth.parse_session_token_info(fixture("sestokeninfo.xml"))
        with self.assertRaises(ValueError):
            auth.submit(
                lambda _payload: object(),
                username="fixture-user",
                password="fixture-password",
                context=context,
                mode="unknown",
            )
        self.assertEqual(auth.budget.used, 0)

    def test_modern_api_login_submits_credentials_once_and_proves_session(self):
        session = ScriptedSession("api")
        with patch.object(HuaweiFamilyAwareWebClient, "_new_session", return_value=session):
            client = HuaweiFamilyAwareWebClient(
                "192.0.2.10", "fixture-user", "fixture-password"
            )
            try:
                self.assertTrue(client.login())
                self.assertEqual(client.auth_flow, HuaweiAuthFlow.API_SES_TOKEN)
                self.assertEqual(client.protocol_family, HuaweiProtocolFamily.API_SESTOKEN)
                self.assertEqual(client._credential_budget.used, 1)
                self.assertEqual(len(session.credential_posts), 1)
                path, payload = session.credential_posts[0]
                self.assertEqual(path, API_LOGIN_PATH)
                context = ApiSesTokenAuth.parse_session_token_info(fixture("sestokeninfo.xml"))
                expected = ApiSesTokenAuth.encode_password(
                    "fixture-password", context.token, "token_sha256"
                )
                self.assertEqual(payload["password"], expected)
                identity = client.authenticated_identity_source()
                self.assertIsNotNone(identity)
                self.assertEqual(identity[0], API_DEVICE_INFO_PATH)
                self.assertIn("HG8245H", identity[1])
                self.assertIn(
                    ("GET", API_DEVICE_INFO_PATH),
                    [(method, path) for method, path, _kwargs in session.calls],
                )
            finally:
                client.close()

    def test_api_algorithm_ambiguity_fails_before_credentials(self):
        session = ScriptedSession("api", ambiguous_script=True)
        with patch.object(HuaweiFamilyAwareWebClient, "_new_session", return_value=session):
            client = HuaweiFamilyAwareWebClient(
                "192.0.2.10", "fixture-user", "fixture-password"
            )
            try:
                with self.assertRaises(HuaweiAuthFamilyAmbiguousError):
                    client.login()
                self.assertEqual(client._credential_budget.used, 0)
                self.assertEqual(session.credential_posts, [])
            finally:
                client.close()

    def test_invalid_api_fingerprint_falls_back_to_legacy_randcount(self):
        session = ScriptedSession("legacy")
        with patch.object(HuaweiFamilyAwareWebClient, "_new_session", return_value=session):
            client = HuaweiFamilyAwareWebClient(
                "192.0.2.10", "fixture-user", "fixture-password"
            )
            try:
                self.assertTrue(client.login())
                self.assertEqual(client.auth_flow, HuaweiAuthFlow.RAND_COUNT)
                self.assertEqual(client._credential_budget.used, 1)
                self.assertEqual(len(session.credential_posts), 1)
                self.assertEqual(session.credential_posts[0][0], "/login.cgi")
            finally:
                client.close()

    def test_api_runtime_requires_model_from_authenticated_deviceinfo(self):
        runtime = HuaweiHG8245HApiRuntime(RuntimeClient("HG8245H"))
        signature = runtime.source_signature()
        self.assertTrue(signature["compatible"])
        self.assertTrue(signature["strong_fingerprint"])
        self.assertEqual(signature["model"], "HG8245H")

        wrong = HuaweiHG8245HApiRuntime(RuntimeClient("HG8245Q2"))
        wrong_signature = wrong.source_signature()
        self.assertFalse(wrong_signature["compatible"])
        self.assertFalse(wrong_signature["strong_fingerprint"])

    def test_provider_phase3_is_read_only_and_reboot_is_blocked(self):
        provider = HuaweiUnifiedProvider()
        provider._client = RuntimeClient("HG8245H")
        provider.model = "HG8245H"
        provider._device_info = {"fabricante": "Huawei", "modelo": "HG8245H"}

        candidate = provider._probe_phase3_candidate()
        self.assertIsNotNone(candidate)
        runtime, signature = candidate
        provider._configure_phase3_runtime(runtime, signature)

        capabilities = provider.capabilities
        self.assertTrue(capabilities["device_info"]["read"])
        self.assertFalse(capabilities["device_info"].get("write", False))
        self.assertFalse(capabilities["device_info"].get("physical_validation", False))
        self.assertFalse(capabilities["reboot"].get("write", False))
        self.assertFalse(provider.writes_enabled)
        self.assertEqual(provider.device_status(refresh=True)["modelo"], "HG8245H")
        with self.assertRaisesRegex(RuntimeError, "Reboot HG8245H"):
            provider.reboot()
        with self.assertRaisesRegex(RuntimeError, "não foi caracterizado"):
            provider.clients(refresh=True)
        with self.assertRaisesRegex(RuntimeError, "somente leitura"):
            provider.set_wifi_radio("5GHz", {"channel": 36})


if __name__ == "__main__":
    unittest.main()

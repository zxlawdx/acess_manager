from __future__ import annotations

import os
import unittest
from pathlib import Path
from urllib.parse import urlsplit
from unittest.mock import patch

import requests

from apps.zte_manager.infrastructure.huawei.family_client import (
    HuaweiFamilyAwareWebClient,
)
from apps.zte_manager.infrastructure.huawei.negotiating_client import (
    HuaweiNegotiatingWebClient,
    HuaweiTransportError,
    HuaweiTransportFailure,
    _trace_exchange,
)
from apps.zte_manager.infrastructure.huawei.protocol import HuaweiAuthFlow


FIXTURES = Path("tests/fixtures/huawei/eg8041x6_10_local")


def fixture(name: str) -> str:
    return (FIXTURES / name).read_text(encoding="utf-8")


BOOTSTRAP = """<html><script>
var SSLPort='80';
var target='https://' + window.location.hostname + ':' + SSLPort;
window.location = target;
</script></html>"""


class FakeResponse:
    def __init__(self, text: str, status_code: int = 200) -> None:
        self.text = text
        self.status_code = status_code
        self.url = "http://fixture/"
        self.headers = {}
        self.history = []
        self.request = None


class SequencedSession:
    def __init__(self, frames, *, verify: bool = False) -> None:
        self.frames = list(frames)
        self.calls = []
        self.verify = verify
        self.closed = False

    def _next(self, method: str, url: str, kwargs):
        self.calls.append({"method": method, "url": url, "kwargs": kwargs})
        if not self.frames:
            raise AssertionError(f"unexpected Huawei transport {method} {url}")
        expected_method, expected_path, frame = self.frames.pop(0)
        self.assert_call = (expected_method, expected_path)
        parsed = urlsplit(url)
        if method != expected_method or parsed.path != expected_path:
            raise AssertionError(
                f"expected {expected_method} {expected_path}, got {method} {parsed.path}"
            )
        if isinstance(frame, BaseException):
            try:
                frame.request = requests.Request(method, url).prepare()
            except Exception:
                pass
            raise frame
        frame.url = url
        frame.request = requests.Request(method, url).prepare()
        return frame

    def get(self, url, **kwargs):
        return self._next("GET", url, kwargs)

    def post(self, url, **kwargs):
        return self._next("POST", url, kwargs)

    def close(self) -> None:
        self.closed = True


class HuaweiTransportNegotiationTests(unittest.TestCase):
    def _auth_frames(self):
        return [
            ("GET", "/", FakeResponse(fixture("auth_root_login.html"))),
            ("POST", "/asp/GetRandCount.asp", FakeResponse(fixture("auth_rand_count.txt"))),
            ("POST", "/login.cgi", FakeResponse(fixture("auth_login_success.html"))),
            ("POST", "/asp/getMenuArray.asp", FakeResponse(fixture("auth_menu_proof.asp"))),
        ]

    def test_untrusted_embedded_certificate_policy_is_centralized(self):
        client = HuaweiNegotiatingWebClient(
            "https://192.0.2.10:80",
            "operator",
            "fixture-password",
        )
        try:
            descriptor = client.transport_descriptor()
            self.assertEqual(client.base_url, "https://192.0.2.10:80")
            self.assertEqual(descriptor["scheme"], "https")
            self.assertEqual(descriptor["port"], 80)
            self.assertTrue(descriptor["explicit_port"])
            self.assertFalse(descriptor["tls_verify"])
            self.assertFalse(client.session.verify)
        finally:
            client.close()

    def test_bootstrap_tls_failure_is_not_misclassified_as_auth_rejected(self):
        client = HuaweiNegotiatingWebClient(
            "100.64.161.200:80",
            "operator",
            "fixture-password",
        )
        client.session.close()
        client.session = SequencedSession([
            ("GET", "/", FakeResponse(BOOTSTRAP)),
            ("GET", "/", requests.exceptions.SSLError("fixture certificate/TLS failure")),
        ])

        with self.assertRaises(HuaweiTransportError) as raised:
            client._negotiate_endpoint(validate_secure=True)

        self.assertEqual(raised.exception.code, HuaweiTransportFailure.TLS_ERROR)
        self.assertNotEqual(
            raised.exception.code,
            HuaweiTransportFailure.AUTH_REJECTED,
        )
        self.assertEqual(client.base_url, "https://100.64.161.200:80")
        self.assertEqual(client.session.calls[0]["url"], "http://100.64.161.200:80/")
        self.assertEqual(client.session.calls[1]["url"], "https://100.64.161.200:80/")
        self.assertFalse(client.session.calls[1]["kwargs"]["verify"])

    def test_login_preserves_transport_tls_error_before_authentication(self):
        client = HuaweiNegotiatingWebClient(
            "https://192.0.2.20:80",
            "operator",
            "fixture-password",
        )
        tls_error = HuaweiTransportError(
            HuaweiTransportFailure.TLS_ERROR,
            "fixture TLS error",
        )
        with patch.object(client, "_negotiate_endpoint", side_effect=tls_error):
            with self.assertRaises(HuaweiTransportError) as raised:
                client.login()
        self.assertIs(raised.exception, tls_error)
        self.assertEqual(raised.exception.code, HuaweiTransportFailure.TLS_ERROR)

    def test_explicit_https_80_uses_familyaware_randcount_without_http_probe(self):
        initial = SequencedSession([], verify=False)
        authenticated = SequencedSession(self._auth_frames(), verify=False)
        with patch.object(
            HuaweiNegotiatingWebClient,
            "_new_session",
            side_effect=[initial, authenticated],
        ):
            client = HuaweiNegotiatingWebClient(
                "192.0.2.10:80",
                "operator",
                "fixture-password",
                https=True,
            )
            self.assertIs(client.session, initial)
            self.assertFalse(client.session.verify)
            self.assertTrue(client.login())

        self.assertTrue(initial.closed)
        self.assertEqual(initial.calls, [])
        self.assertIs(client.session, authenticated)
        self.assertFalse(client.session.verify)
        self.assertEqual(client.base_url, "https://192.0.2.10:80")
        self.assertEqual(client.endpoint.scheme, "https")
        self.assertEqual(client.endpoint.port, 80)
        self.assertEqual(client.auth_flow, HuaweiAuthFlow.RAND_COUNT)
        self.assertEqual(
            [(item["method"], urlsplit(item["url"]).path) for item in authenticated.calls],
            [
                ("GET", "/"),
                ("POST", "/asp/GetRandCount.asp"),
                ("POST", "/login.cgi"),
                ("POST", "/asp/getMenuArray.asp"),
            ],
        )
        self.assertTrue(all(urlsplit(item["url"]).scheme == "https" for item in authenticated.calls))
        self.assertTrue(all(urlsplit(item["url"]).port == 80 for item in authenticated.calls))

    def test_auto_http_bootstrap_converges_to_same_https_80_auth_pipeline(self):
        bootstrap = SequencedSession([
            ("GET", "/", FakeResponse(fixture("http_bootstrap.html"))),
        ], verify=False)
        authenticated = SequencedSession(self._auth_frames(), verify=False)
        with patch.object(
            HuaweiNegotiatingWebClient,
            "_new_session",
            side_effect=[bootstrap, authenticated],
        ):
            client = HuaweiNegotiatingWebClient(
                "192.0.2.10:80",
                "operator",
                "fixture-password",
                https=False,
            )
            self.assertTrue(client.login())

        self.assertEqual(bootstrap.calls[0]["url"], "http://192.0.2.10:80/")
        self.assertTrue(bootstrap.closed)
        self.assertIs(client.session, authenticated)
        self.assertFalse(client.session.verify)
        self.assertTrue(client.bootstrap_detected)
        self.assertTrue(client.negotiated)
        self.assertEqual(client.base_url, "https://192.0.2.10:80")
        self.assertEqual(client.endpoint.scheme, "https")
        self.assertEqual(client.endpoint.port, 80)
        self.assertEqual(client.auth_flow, HuaweiAuthFlow.RAND_COUNT)
        self.assertTrue(all(urlsplit(item["url"]).scheme == "https" for item in authenticated.calls))
        self.assertTrue(all(urlsplit(item["url"]).port == 80 for item in authenticated.calls))

    def test_real_session_factory_keeps_verify_false_after_familyaware_recreation(self):
        root = FakeResponse(fixture("auth_root_login.html"))
        challenge = FakeResponse(fixture("auth_rand_count.txt"))
        login = FakeResponse(fixture("auth_login_success.html"))
        proof = FakeResponse(fixture("auth_menu_proof.asp"))

        def fake_get(session, url, **kwargs):
            response = root
            response.url = url
            return response

        post_frames = [challenge, login, proof]

        def fake_post(session, url, **kwargs):
            if not post_frames:
                raise AssertionError("unexpected POST")
            response = post_frames.pop(0)
            response.url = url
            return response

        with patch.object(requests.Session, "get", new=fake_get), patch.object(
            requests.Session,
            "post",
            new=fake_post,
        ):
            client = HuaweiNegotiatingWebClient(
                "192.0.2.10:80",
                "operator",
                "fixture-password",
                https=True,
            )
            initial_session = client.session
            self.assertFalse(initial_session.verify)
            self.assertTrue(client.login())

        self.assertIsNot(client.session, initial_session)
        self.assertTrue(initial_session is not client.session)
        self.assertFalse(client.session.verify)
        self.assertEqual(client.base_url, "https://192.0.2.10:80")

    def test_wrapped_connection_error_is_network_error_not_auth_rejected(self):
        prepared = requests.Request(
            "POST",
            "https://192.0.2.10:80/asp/GetRandCount.asp",
        ).prepare()
        original = requests.exceptions.ConnectionError("fixture reset", request=prepared)
        try:
            raise original
        except requests.exceptions.ConnectionError as cause:
            wrapped = RuntimeError("Não foi possível autenticar na ONT Huawei.")
            wrapped.__cause__ = cause

        client = HuaweiNegotiatingWebClient(
            "192.0.2.10:80",
            "operator",
            "fixture-password",
            https=True,
        )
        with patch.object(HuaweiFamilyAwareWebClient, "login", side_effect=wrapped):
            with self.assertRaises(HuaweiTransportError) as raised:
                client.login()

        self.assertEqual(raised.exception.code, HuaweiTransportFailure.NETWORK_ERROR)
        self.assertEqual(raised.exception.phase, "rand_count")
        self.assertEqual(raised.exception.original_exception, "ConnectionError")
        self.assertNotEqual(raised.exception.code, HuaweiTransportFailure.AUTH_REJECTED)

    def test_trace_is_structured_and_never_prints_query_or_response_secret(self):
        response = requests.Response()
        response.status_code = 200
        response._content = b"fixture-secret-token-value-123456789"
        response.url = "https://192.0.2.10:80/login.cgi?token=fixture-secret-query"
        response.request = requests.Request(
            "POST",
            response.url,
            data={"PassWord": "fixture-secret-password", "x.X_HW_Token": "fixture-token"},
        ).prepare()
        response.headers = {"Set-Cookie": "fixture-secret-cookie"}

        with patch.dict(os.environ, {"HUAWEI_HTTP_TRACE": "true"}, clear=False), patch(
            "builtins.print"
        ) as printed:
            _trace_exchange(response)

        output = " ".join(str(arg) for call in printed.call_args_list for arg in call.args)
        self.assertIn("huawei_http_trace", output)
        self.assertIn("method=POST", output)
        self.assertIn("scheme=https", output)
        self.assertIn("port=80", output)
        self.assertIn("path=/login.cgi", output)
        self.assertNotIn("fixture-secret", output)
        self.assertNotIn("token=", output)
        self.assertNotIn("PassWord", output)
        self.assertNotIn("Set-Cookie", output)


if __name__ == "__main__":
    unittest.main()

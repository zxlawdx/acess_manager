from __future__ import annotations

import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs

import requests

from apps.zte_manager.infrastructure.huawei.affinity_client import (
    HuaweiAffinityNegotiatingWebClient,
)
from apps.zte_manager.infrastructure.huawei.protocol import HuaweiAuthFlow
from apps.zte_manager.infrastructure.huawei.transport import (
    AffinityHttpTransport,
    HG8245X6_TTNET2_AFFINITY_PROFILE,
    HuaweiEndpointProfile,
    HuaweiTransportPolicy,
    RequestsSessionTransport,
    endpoint_profile_from_login_source,
)
from apps.zte_manager.infrastructure.huawei.errors import (
    HuaweiSameConnectionRequiredError,
    HuaweiTransportNegotiationError,
)


FIXTURES = Path("tests/fixtures/huawei/phase4")


def fixture(name: str) -> str:
    return (FIXTURES / name).read_text(encoding="utf-8")


class _AffinityFixtureHandler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    challenge_connection: int | None = None
    login_connection: int | None = None
    challenge_count = 0
    login_count = 0
    proof_count = 0
    login_payload: dict[str, list[str]] = {}
    proof_cookie: str | None = None
    login_html = fixture("hg8245x6_ttnet2_login.html")

    @classmethod
    def reset(cls, *, login_html: str | None = None) -> None:
        cls.challenge_connection = None
        cls.login_connection = None
        cls.challenge_count = 0
        cls.login_count = 0
        cls.proof_count = 0
        cls.login_payload = {}
        cls.proof_cookie = None
        cls.login_html = (
            login_html
            if login_html is not None
            else fixture("hg8245x6_ttnet2_login.html")
        )

    def log_message(self, format, *args):  # pragma: no cover - silence fixture server
        return

    def _read_body(self) -> bytes:
        length = int(self.headers.get("Content-Length") or 0)
        return self.rfile.read(length) if length else b""

    def _send(self, status: int, body: bytes, headers: dict[str, str] | None = None):
        self.send_response(status)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Connection", "keep-alive")
        for name, value in (headers or {}).items():
            self.send_header(name, value)
        self.end_headers()
        if body:
            self.wfile.write(body)
            self.wfile.flush()

    def do_GET(self):
        if self.path == "/":
            self._send(200, type(self).login_html.encode("utf-8"))
            return
        if self.path == "/asp/GetRandCount.asp":
            type(self).challenge_connection = id(self.connection)
            type(self).challenge_count += 1
            self._send(200, ("B" * 64).encode("ascii"))
            return
        if self.path == "/html/ssmp/deviceinfo/deviceinfo.asp":
            self._send(
                200,
                b"var ProductName='HG8245X6'; var SoftwareVersion='fixture';",
            )
            return
        self._send(404, b"not found")

    def do_POST(self):
        body = self._read_body()
        if self.path == "/asp/GetRandCount.asp":
            type(self).challenge_connection = id(self.connection)
            type(self).challenge_count += 1
            self._send(200, ("A" * 64).encode("ascii"))
            return

        if self.path == "/login.cgi":
            type(self).login_connection = id(self.connection)
            type(self).login_count += 1
            type(self).login_payload = parse_qs(body.decode("utf-8"))
            self._send(
                200,
                b"login accepted",
                {
                    "Set-Cookie": (
                        "Cookie=sid=fixture-session:Language:english:id=1; "
                        "Path=/; HttpOnly"
                    )
                },
            )
            return

        if self.path == "/asp/getMenuArray.asp":
            type(self).proof_count += 1
            type(self).proof_cookie = self.headers.get("Cookie")
            if type(self).proof_cookie and "sid=fixture-session" in type(self).proof_cookie:
                self._send(200, b"Home Page bbsp ipincoming")
            else:
                self._send(403, b"Forbidden")
            return

        self._send(404, b"not found")


class HuaweiPhase4AffinityTests(unittest.TestCase):
    def setUp(self):
        _AffinityFixtureHandler.reset()
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), _AffinityFixtureHandler)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        host, port = self.server.server_address
        self.base = f"http://{host}:{port}"

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=2)

    def test_reference_profile_requires_all_strict_fingerprint_markers(self):
        source = fixture("hg8245x6_ttnet2_login.html")
        profile = endpoint_profile_from_login_source(source)
        self.assertIs(profile, HG8245X6_TTNET2_AFFINITY_PROFILE)
        self.assertTrue(profile.challenge_login_connection_affinity)

        partial = source.replace("LockLeftTime", "unrelatedMarker")
        self.assertIsNone(endpoint_profile_from_login_source(partial))

    def test_requests_session_still_refuses_to_claim_same_tcp_guarantee(self):
        policy = HuaweiTransportPolicy(challenge_login_connection_affinity=True)
        session = requests.Session()
        try:
            with self.assertRaises(HuaweiSameConnectionRequiredError):
                RequestsSessionTransport(session, policy)
        finally:
            session.close()

    def test_affinity_transport_does_not_claim_single_segment_mutation_support(self):
        policy = HuaweiTransportPolicy(
            challenge_login_connection_affinity=True,
            single_segment_post=True,
        )
        with self.assertRaises(HuaweiTransportNegotiationError):
            AffinityHttpTransport(self.base, policy)

    def test_explicit_endpoint_profile_applies_affinity_without_model_guess(self):
        profile = HuaweiEndpointProfile(
            key="fixture-explicit-affinity",
            challenge_login_connection_affinity=True,
            evidence=("fixture",),
        )
        client = HuaweiAffinityNegotiatingWebClient(
            self.base,
            "operator",
            "fixture-password",
            endpoint_profile=profile,
        )
        try:
            self.assertTrue(client.transport_policy.challenge_login_connection_affinity)
            self.assertEqual(client.endpoint_profile.key, "fixture-explicit-affinity")
        finally:
            client.close()

    def test_login_fingerprint_uses_same_tcp_socket_for_challenge_and_credentials(self):
        client = HuaweiAffinityNegotiatingWebClient(
            self.base,
            "operator",
            "fixture-password",
        )
        try:
            self.assertTrue(client.login())
            descriptor = client.transport_descriptor()
        finally:
            client.close()

        self.assertEqual(client.auth_flow, HuaweiAuthFlow.RAND_COUNT)
        self.assertTrue(descriptor["challenge_login_connection_affinity"])
        self.assertEqual(
            descriptor["endpoint_profile"],
            "hg8245x6_ttnet2_same_tcp",
        )
        self.assertIsNotNone(_AffinityFixtureHandler.challenge_connection)
        self.assertEqual(
            _AffinityFixtureHandler.challenge_connection,
            _AffinityFixtureHandler.login_connection,
            "GetRandCount and login.cgi must arrive over the exact same TCP socket",
        )
        self.assertEqual(_AffinityFixtureHandler.challenge_count, 1)
        self.assertEqual(_AffinityFixtureHandler.login_count, 1)
        self.assertEqual(_AffinityFixtureHandler.proof_count, 1)
        self.assertIn("sid=fixture-session", _AffinityFixtureHandler.proof_cookie or "")
        self.assertEqual(
            _AffinityFixtureHandler.login_payload.get("UserName"),
            ["operator"],
        )
        self.assertEqual(
            _AffinityFixtureHandler.login_payload.get("x.X_HW_Token"),
            ["A" * 64],
        )
        self.assertEqual(client._credential_budget.used, 1)
        self.assertIn(
            "transport:challenge-login-same-tcp",
            client.protocol_evidence,
        )

    def test_ordinary_randcount_page_does_not_enable_affinity(self):
        ordinary_login = """
        <html><form action='/login.cgi'>
        <input name='UserName'><input name='PassWord'>
        <script src='/asp/GetRandCount.asp'></script>
        </form></html>
        """
        _AffinityFixtureHandler.reset(login_html=ordinary_login)
        client = HuaweiAffinityNegotiatingWebClient(
            self.base,
            "operator",
            "fixture-password",
        )
        try:
            root = client.session.get(self.base + "/", timeout=2)
            flow = client._select_auth_flow(root.text)
            self.assertEqual(flow, HuaweiAuthFlow.RAND_COUNT)
            self.assertFalse(
                client.transport_policy.challenge_login_connection_affinity
            )
            self.assertIsNone(client.endpoint_profile)
        finally:
            client.close()


if __name__ == "__main__":
    unittest.main()

from __future__ import annotations

import unittest
from unittest.mock import patch

import requests

from apps.zte_manager.infrastructure.huawei.negotiating_client import (
    HuaweiNegotiatingWebClient,
    HuaweiTransportError,
    HuaweiTransportFailure,
)


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


class SequencedSession:
    def __init__(self, frames) -> None:
        self.frames = list(frames)
        self.calls = []
        self.verify = True

    def get(self, url, **kwargs):
        self.calls.append((url, kwargs))
        if not self.frames:
            raise AssertionError("unexpected Huawei transport GET")
        frame = self.frames.pop(0)
        if isinstance(frame, BaseException):
            raise frame
        return frame

    def close(self) -> None:
        return None


class HuaweiTransportNegotiationTests(unittest.TestCase):
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
            FakeResponse(BOOTSTRAP),
            requests.exceptions.SSLError("fixture certificate/TLS failure"),
        ])

        with self.assertRaises(HuaweiTransportError) as raised:
            client._negotiate_endpoint(validate_secure=True)

        self.assertEqual(raised.exception.code, HuaweiTransportFailure.TLS_ERROR)
        self.assertNotEqual(
            raised.exception.code,
            HuaweiTransportFailure.AUTH_REJECTED,
        )
        self.assertEqual(client.base_url, "https://100.64.161.200:80")
        self.assertEqual(client.session.calls[0][0], "http://100.64.161.200:80/")
        self.assertEqual(client.session.calls[1][0], "https://100.64.161.200:80/")
        self.assertFalse(client.session.calls[1][1]["verify"])

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


if __name__ == "__main__":
    unittest.main()

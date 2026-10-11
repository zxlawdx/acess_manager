from __future__ import annotations

import unittest
from pathlib import Path
from unittest.mock import patch

import requests

from apps.zte_manager.infrastructure.huawei.protocol import HuaweiAuthFlow
from apps.zte_manager.infrastructure.huawei.single_write import SingleWriteHttpTransport
from apps.zte_manager.services.huawei_affinity_provider import HuaweiAffinityUnifiedProvider
from apps.zte_manager.services.huawei_hg8347r_runtime import HuaweiHG8347RRuntime


FIXTURES = Path("tests/fixtures/huawei/phase5")


def fixture(name: str) -> str:
    return (FIXTURES / name).read_text(encoding="utf-8")


class FakeHG8347RClient:
    auth_flow = HuaweiAuthFlow.RAND_COUNT
    base_url = "http://192.0.2.1"
    timeout = 3.0

    def __init__(self) -> None:
        self.session = requests.Session()
        self.post_calls = []

    def get_page(self, path):
        if path == HuaweiHG8347RRuntime.USER_DEVICE_PAGE:
            return fixture("hg8347r_userdev_page.html")
        raise RuntimeError(path)

    def post_read(self, path, payload=None, *, referer="/index.asp"):
        self.post_calls.append((path, dict(payload or {}), referer))
        if path == HuaweiHG8347RRuntime.USER_DEVICE_AJAX:
            return fixture("hg8347r_clients.json")
        raise RuntimeError(path)


class FakeMapped:
    pass


class LabProvider(HuaweiAffinityUnifiedProvider):
    def mapped_write_feature(self, operation, config):
        return {
            "success": True,
            "accepted": True,
            "verified": False,
            "operation": operation,
            "config": dict(config or {}),
        }

    def mapped_write_request(self, path, payload, **kwargs):
        return {
            "success": True,
            "accepted": True,
            "verified": False,
            "path": path,
            "payload_keys": sorted(dict(payload or {})),
        }


class FakeSocket:
    def __init__(self):
        self.sendall_calls = []
        self.recv_calls = 0
        self.closed = False

    def sendall(self, data):
        self.sendall_calls.append(bytes(data))

    def settimeout(self, value):
        self.timeout = value

    def recv(self, size):
        self.recv_calls += 1
        if self.recv_calls == 1:
            return b"HTTP/1.1 200 OK\r\nContent-Length: 0\r\n\r\n"
        return b""

    def close(self):
        self.closed = True


class HuaweiPhase5HG8347RTests(unittest.TestCase):
    def test_clean_room_runtime_extracts_token_and_clients(self):
        client = FakeHG8347RClient()
        runtime = HuaweiHG8347RRuntime(client)
        signature = runtime.source_signature()
        rows = runtime.clients()

        self.assertTrue(signature["compatible"])
        self.assertTrue(signature["strong_fingerprint"])
        self.assertEqual(signature["model"], "HG8347R")
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0]["ip"], "192.0.2.10")
        self.assertEqual(rows[0]["connection_type"], "wifi")
        self.assertEqual(rows[1]["connection_type"], "lan")
        self.assertFalse(rows[1]["online"])
        self.assertNotIn("rssi", rows[0])
        self.assertEqual(len(client.post_calls), 1)
        sent = client.post_calls[0][1]
        self.assertEqual(sent["x.X_HW_Token"], "0123456789abcdef0123456789abcdef")

    def test_phase5_probe_promotes_only_client_reader(self):
        provider = HuaweiAffinityUnifiedProvider()
        provider._client = FakeHG8347RClient()
        provider.current_host = "192.0.2.1"
        provider.model = "Huawei"
        provider._device_info = {"fabricante": "Huawei", "modelo": "Huawei"}
        provider._capabilities = {}

        candidate = provider._probe_phase5_candidate()
        self.assertIsNotNone(candidate)
        runtime, signature = candidate
        provider._configure_phase5_runtime(runtime, signature)

        self.assertEqual(provider.model, "HG8347R")
        self.assertTrue(provider.model_verified)
        self.assertTrue(provider._phase5_active)
        self.assertTrue(provider.capabilities["clients"]["read"])
        self.assertFalse(provider.capabilities["clients"].get("update", False))
        self.assertEqual(len(provider.clients(refresh=True)), 2)
        self.assertNotIn("wifi", provider.capabilities)

    def test_lab_mode_is_explicit_and_exposes_mapped_writes(self):
        provider = LabProvider()
        provider._client = FakeHG8347RClient()
        provider._mapped = FakeMapped()
        provider.model = "HG8347R"

        self.assertFalse(provider.lab_mode)
        with self.assertRaises(RuntimeError):
            provider.lab_write(operation="upnp", payload={"x.Enable": "1"})

        status = provider.set_lab_mode(True)
        self.assertTrue(status["enabled"])
        self.assertTrue(status["writes_enabled"])
        self.assertIn("upnp", status["mapped_operations"])
        self.assertFalse(status["reboot"]["hg8347r_known_endpoint"])

        result = provider.lab_write(operation="upnp", payload={"x.Enable": "1"})
        self.assertTrue(result["success"])
        self.assertTrue(result["experimental"])
        self.assertTrue(result["lab_mode"])

    def test_phase5_never_inherits_typed_eg8041_writers_even_in_lab(self):
        provider = HuaweiAffinityUnifiedProvider()
        provider._client = FakeHG8347RClient()
        provider._phase5_runtime = HuaweiHG8347RRuntime(provider._client)
        provider._lab_mode = True
        with self.assertRaises(RuntimeError):
            provider._specialized_block_write()

    def test_single_write_transport_emits_headers_and_body_in_one_sendall(self):
        fake = FakeSocket()
        session = requests.Session()
        session.cookies.set("Cookie", "sid=fixture:Language:english:id=1")
        transport = SingleWriteHttpTransport("http://192.0.2.1", timeout=2)
        with patch(
            "apps.zte_manager.infrastructure.huawei.single_write.socket.create_connection",
            return_value=fake,
        ):
            result = transport.post(
                "/html/ssmp/reset/set.cgi?x=ResetBoard",
                {"x.X_HW_Token": "fixture-token"},
                referer="http://192.0.2.1/html/ssmp/reset/reset.asp",
                cookie_header=transport.cookie_header(session),
            )

        self.assertTrue(result.sent)
        self.assertEqual(result.http_status, 200)
        self.assertEqual(len(fake.sendall_calls), 1)
        raw = fake.sendall_calls[0]
        self.assertIn(b"POST /html/ssmp/reset/set.cgi?x=ResetBoard HTTP/1.1", raw)
        self.assertIn(b"Content-Length:", raw)
        self.assertIn(b"x.X_HW_Token=fixture-token", raw)
        self.assertIn(b"Cookie: Cookie=sid=fixture", raw)
        self.assertNotIn(b"\r\n\r\n\r\n", raw)


if __name__ == "__main__":
    unittest.main()

from __future__ import annotations

import unittest

from apps.zte_manager.infrastructure.huawei import HuaweiMutationTransport
from apps.zte_manager.model.device_adapters.huawei import HuaweiEG8041X7Profile
from apps.zte_manager.services.huawei_mapped_surface import HuaweiMappedSurfaceService
from apps.zte_manager.services.huawei_service import HuaweiService


TOKEN_PAGE = (
    '<input type="hidden" id="hwonttoken" '
    'value="fresh-token-123456">'
)


class FakeDiagnosticClient:
    def __init__(self):
        self.get_calls = []
        self.post_read_calls = []
        self.post_form_calls = []

    @staticmethod
    def extract_token(source):
        if "fresh-token-123456" not in source:
            raise RuntimeError("token missing")
        return "fresh-token-123456"

    def get_page(self, path):
        self.get_calls.append(path)
        if path == "/html/bbsp/maintenance/diagnosecommon.asp":
            return TOKEN_PAGE
        return ""

    def post_read(self, path, payload=None, *, referer="/index.asp"):
        self.post_read_calls.append((path, dict(payload or {}), referer))
        if path.endswith("/GetPingResult.asp"):
            return repr(
                "PING 8.8.8.8\n"
                "4 packets transmitted, 4 packets received, 0% packet loss\n"
                "round-trip min/avg/max = 10.1/11.2/12.3 ms"
                "[@#@]Complete"
            )
        if path.endswith("/GetRouteResult.asp"):
            return repr(
                "traceroute to 8.8.8.8\n"
                "1  192.168.18.1  1.2 ms  1.1 ms  1.3 ms\n"
                "2  8.8.8.8  10.0 ms  10.2 ms  10.1 ms"
                "[@#@]Complete"
            )
        return ""

    def post_form(self, path, payload, *, referer):
        self.post_form_calls.append((path, dict(payload), referer))
        return HuaweiMutationTransport(http_status=200)


class HuaweiNativeDiagnosticsTests(unittest.TestCase):
    def make_service(self):
        self.client = FakeDiagnosticClient()
        mapped = HuaweiMappedSurfaceService(
            self.client,
            model="EG8041X7-10",
        )
        service = HuaweiService()
        service._client = self.client
        service._mapped = mapped
        service._profile = HuaweiEG8041X7Profile()
        service.model = "EG8041X7-10"
        return service

    def test_ping_uses_huawei_ipping_flow_and_polls_result(self):
        service = self.make_service()

        result = service.ping({
            "host": "8.8.8.8",
            "interface": "wan1.1.ppp1",
            "ip_version": "IPv4",
            "count": 4,
            "data_size": 56,
            "timeout": 10000,
        })

        self.assertTrue(result["verified"])
        self.assertEqual(result["sucesso"], 4)
        self.assertEqual(result["falha"], 0)
        self.assertEqual(result["perda_percentual"], 0)
        self.assertEqual(result["minimo_ms"], 10.1)
        self.assertEqual(result["medio_ms"], 11.2)
        self.assertEqual(result["maximo_ms"], 12.3)

        self.assertEqual(len(self.client.post_form_calls), 1)
        path, payload, referer = self.client.post_form_calls[0]
        self.assertIn("x=InternetGatewayDevice.IPPingDiagnostics", path)
        self.assertIn("RUNSTATE_FLAG=Ping", path)
        self.assertEqual(
            referer,
            "/html/bbsp/maintenance/diagnosecommon.asp",
        )
        self.assertEqual(payload["x.Host"], "8.8.8.8")
        self.assertEqual(payload["x.DiagnosticsState"], "Requested")
        self.assertEqual(payload["x.NumberOfRepetitions"], "4")
        self.assertEqual(payload["x.DataBlockSize"], "56")
        self.assertEqual(payload["x.Timeout"], "10000")
        self.assertEqual(payload["x.Interface"], "wan1.1.ppp1")
        self.assertEqual(payload["RUNSTATE_FLAG.value"], "START")
        self.assertEqual(
            payload["x.X_HW_Token"],
            "fresh-token-123456",
        )
        self.assertTrue(
            any(
                call[0].endswith("/GetPingResult.asp")
                for call in self.client.post_read_calls
            )
        )

    def test_traceroute_uses_huawei_flow_and_parses_hops(self):
        service = self.make_service()

        result = service.traceroute({
            "host": "8.8.8.8",
            "interface": "wan1.1.ppp1",
            "protocol": "AUTO",
            "timeout": 5000,
        })

        self.assertTrue(result["verified"])
        self.assertEqual(len(result["hops"]), 2)
        self.assertEqual(result["hops"][0]["numero"], 1)
        self.assertEqual(result["hops"][0]["ip"], "192.168.18.1")
        self.assertEqual(result["hops"][1]["ip"], "8.8.8.8")

        self.assertEqual(len(self.client.post_form_calls), 1)
        path, payload, referer = self.client.post_form_calls[0]
        self.assertIn(
            "x=InternetGatewayDevice.TraceRouteDiagnostics",
            path,
        )
        self.assertIn("RUNSTATE_FLAG=Traceroute", path)
        self.assertEqual(
            referer,
            "/html/bbsp/maintenance/diagnosecommon.asp",
        )
        self.assertEqual(payload["x.Host"], "8.8.8.8")
        self.assertEqual(payload["x.DataBlockSize"], "38")
        self.assertEqual(payload["x.Interface"], "wan1.1.ppp1")
        self.assertEqual(payload["RUNSTATE_FLAG.value"], "START")
        self.assertTrue(
            any(
                call[0].endswith("/GetRouteResult.asp")
                for call in self.client.post_read_calls
            )
        )


if __name__ == "__main__":
    unittest.main()

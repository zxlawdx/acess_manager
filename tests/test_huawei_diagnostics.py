from __future__ import annotations

import unittest
from unittest.mock import patch

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
        self.ping_result = (
            "PING 8.8.8.8\n"
            "4 packets transmitted, 4 packets received, 0% packet loss\n"
            "round-trip min/avg/max = 10.1/11.2/12.3 ms"
            "[@#@]Complete"
        )
        self.route_result = (
            "traceroute to 8.8.8.8\n"
            "1  192.168.18.1  1.2 ms  1.1 ms  1.3 ms\n"
            "2  8.8.8.8  10.0 ms  10.2 ms  10.1 ms"
            "[@#@]Complete"
        )

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
            return repr(self.ping_result)
        if path.endswith("/GetRouteResult.asp"):
            return repr(self.route_result)
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

    def test_ping_complete_err_is_verified_but_connectivity_failed(self):
        service = self.make_service()
        self.client.ping_result = (
            "PING 8.8.8.8\n"
            "ping: sendto: Network unreachable\n"
            "1 packets transmitted, 0 packets received, 100% packet loss"
            "[@#@]Complete_Err"
        )

        result = service.ping({
            "host": "8.8.8.8",
            "count": 1,
            "timeout": 1000,
        })

        self.assertTrue(result["verified"])
        self.assertFalse(result["success"])
        self.assertFalse(result["uncertain"])
        self.assertEqual(result["diagnostics_state"], "Complete_Err")
        self.assertEqual(result["sucesso"], 0)
        self.assertEqual(result["falha"], 1)
        self.assertEqual(result["perda_percentual"], 100)

    def test_poll_tolerates_timeout_and_empty_frames_until_complete(self):
        service = self.make_service()
        original_post_read = self.client.post_read
        frames = iter([
            TimeoutError("temporary timeout"),
            "",
            repr(self.client.ping_result),
        ])

        def flaky_post_read(path, payload=None, *, referer="/index.asp"):
            if path.endswith("/GetPingResult.asp"):
                value = next(frames)
                if isinstance(value, BaseException):
                    raise value
                self.client.post_read_calls.append(
                    (path, dict(payload or {}), referer)
                )
                return value
            return original_post_read(
                path,
                payload,
                referer=referer,
            )

        self.client.post_read = flaky_post_read

        with patch(
            "apps.zte_manager.services.huawei_service.time.sleep",
            return_value=None,
        ):
            result = service.ping({
                "host": "8.8.8.8",
                "count": 4,
                "timeout": 1000,
            })

        self.assertTrue(result["verified"])
        self.assertTrue(result["success"])
        self.assertEqual(result["sucesso"], 4)

    def test_ping_parser_accepts_sent_received_and_labelled_rtt(self):
        parsed = HuaweiService._parse_ping_output(
            (
                "Packets: Sent = 4, Received = 3, Lost = 1 (25% loss)\n"
                "Minimum = 8ms, Maximum = 12ms, Average = 10ms"
            ),
            requested_count=4,
        )

        self.assertEqual(parsed["sucesso"], 3)
        self.assertEqual(parsed["falha"], 1)
        self.assertEqual(parsed["perda_percentual"], 25)
        self.assertEqual(parsed["minimo_ms"], 8.0)
        self.assertEqual(parsed["medio_ms"], 10.0)
        self.assertEqual(parsed["maximo_ms"], 12.0)

    def test_traceroute_empty_interface_selects_active_internet_ppp_and_forces_auto(self):
        service = self.make_service()
        active_domain = (
            "InternetGatewayDevice.WANDevice.1."
            "WANConnectionDevice.1.WANPPPConnection.1"
        )
        service.wan_status = lambda refresh=False: [{
            "id": active_domain,
            "status": "Connected",
            "nome": "1_TR069_INTERNET_R_VID_2000",
            "services": "TR069_INTERNET",
            "wan_type": "PPPoE",
        }]

        result = service.traceroute({
            "host": "8.8.8.8",
            "interface": "",
            "protocol": "ICMP",
            "timeout": 2000,
        })

        self.assertTrue(result["verified"])
        self.assertEqual(result["interface"], active_domain)
        self.assertEqual(result["protocol"], "AUTO")
        self.assertEqual(result["protocol_code"], "0")
        payload = self.client.post_form_calls[0][1]
        self.assertEqual(payload["x.Interface"], active_domain)
        self.assertEqual(payload["x.X_HW_ProtocolType"], "0")

    def test_traceroute_max_hops_is_terminal_verified_failure(self):
        service = self.make_service()
        self.client.route_result = (
            "None[@#@]Error_MaxHopCountExceeded"
        )

        result = service.traceroute({
            "host": "8.8.8.8",
            "interface": (
                "InternetGatewayDevice.WANDevice.1."
                "WANConnectionDevice.1.WANPPPConnection.1"
            ),
            "protocol": "AUTO",
            "timeout": 2000,
        })

        self.assertTrue(result["verified"])
        self.assertFalse(result["success"])
        self.assertFalse(result["uncertain"])
        self.assertEqual(
            result["diagnostics_state"],
            "Error_MaxHopCountExceeded",
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
        self.assertEqual(payload["x.X_HW_ProtocolType"], "0")
        self.assertEqual(payload["RUNSTATE_FLAG.value"], "START")
        self.assertTrue(
            any(
                call[0].endswith("/GetRouteResult.asp")
                for call in self.client.post_read_calls
            )
        )


if __name__ == "__main__":
    unittest.main()

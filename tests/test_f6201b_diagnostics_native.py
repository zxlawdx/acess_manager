"""Mocked network diagnostics: ensure actual captured POST, readback and no retry."""
import unittest
from urllib.parse import parse_qsl

from apps.zte_manager.services.f6201b_diagnostics import (
    F6201BDiagnostics, PING, TRACE, trace_hops
)
from apps.zte_manager.services.f6201b_evidence import OBSERVED_DIAGNOSTIC_ACTIONS


class FakeResponse:
    status_code = 200
    url = "http://192.0.2.5/"
    text = ("<ajax_response_xml_root><IF_ERRORID>0</IF_ERRORID>"
            "</ajax_response_xml_root>")


class FakeSession:
    def blocked(self, *_args, **_kwargs):
        raise PermissionError("transport locked")

    def __init__(self):
        self.blocked = self.blocked
        self.post = self.blocked


class FakeONT:
    def __init__(self):
        self.session = FakeSession()
        self.writes_enabled = False
        self.base_url = "http://192.0.2.5"
        self.integrity_check = False
        self.public_key_pem = None
        self.session_tmp_token = "fake-diagnostic-token"
        self.posted = []
        self.changed = False
        self.count_reads = 0

    def get_view(self, tag, **_kwargs):
        assert tag == "networkDiag"
        return "<form/>"

    def get_menu(self, tag):
        self.count_reads += 1
        self.tag = tag
        return ("<ajax_response_xml_root><IF_ERRORID>0</IF_ERRORID>" +
                "<" + ("OBJ_DEVPING_ID" if tag == PING else "OBJ_TRACERT_ID") +
                "/></ajax_response_xml_root>")

    def _validar_resposta(self, raw):
        assert "<IF_ERRORID>0</IF_ERRORID>" in raw

    def _parse_instances(self, raw):
        if self.tag == PING:
            value = {"PingAck": "old",
                     "SuccessCount": "2", "FailureCount": "2"}
            if self.changed:
                value.update({"PingAck": "4 packets transmitted",
                              "SuccessCount": "3", "FailureCount": "1",
                              "MinimumResponseTime": "5",
                              "AverageResponseTime": "8",
                              "MaximumResponseTime": "11"})
            return {"OBJ_DEVPING_ID": [value]}
        row = {"Flag": "0", "Result": "1  192.0.2.1  2 ms"}
        if self.changed:
            row["Result"] = "1 192.0.2.1 1 ms\n2 * * *"
        return {"OBJ_TRACERT_ID": [row]}

    def transport(self, url, *, params, data, headers, timeout):
        self.posted.append((params, list(parse_qsl(data))))
        self.changed = True
        return FakeResponse()


class DiagnosticTests(unittest.TestCase):
    def setUp(self):
        self.ont = FakeONT()
        self.diag = F6201BDiagnostics(sleep=lambda _: None, attempts=2)

    def test_ping_native_post_and_packet_loss(self):
        result = self.diag.execute(self.ont, self.ont.transport, PING, {
            "host": "example.com", "count": 4,
            "data_size": 64, "timeout": 5000
        })
        self.assertTrue(result["verified"])
        self.assertEqual(result["perda_percentual"], 25)
        self.assertEqual(len(self.ont.posted), 1)
        self.assertEqual(
            tuple(key for key, _ in self.ont.posted[0][1]),
            OBSERVED_DIAGNOSTIC_ACTIONS[PING]
        )
        self.assertFalse(self.ont.writes_enabled)
        self.assertIs(self.ont.session.post, self.ont.session.blocked)

    def test_diagnostic_schemas_match_full_captured_form_order(self):
        self.assertEqual(OBSERVED_DIAGNOSTIC_ACTIONS[PING], (
            "IF_ACTION", "_InstID", "Host", "Interface",
            "NumofRepeat", "DataBlockSize", "Timeout",
            "Btn_cancel_PingDiagnosis", "Btn_PingDiagnosis",
            "PingAck", "_sessionTOKEN",
        ))
        self.assertEqual(OBSERVED_DIAGNOSTIC_ACTIONS[TRACE], (
            "IF_ACTION", "_InstID", "Control", "Host", "Interface",
            "MaxHopCount", "Timeout", "Protocol",
            "Btn_TraceRouteDiagnosis", "Result", "_sessionTOKEN",
        ))

    def test_traceroute_native_hops(self):
        result = self.diag.execute(self.ont, self.ont.transport, TRACE, {
            "host": "192.0.2.9", "max_hops": 30, "timeout": 5000
        })
        self.assertEqual(len(result["hops"]), 2)
        self.assertTrue(result["hops"][1]["timeout"])
        self.assertEqual(len(self.ont.posted), 1)

    def test_incomplete_firmware_form_never_posts(self):
        self.ont.get_menu = lambda tag: (
            "<ajax_response_xml_root><IF_ERRORID>0</IF_ERRORID>"
            "</ajax_response_xml_root>"
        )
        with self.assertRaises(RuntimeError):
            self.diag.execute(self.ont, self.ont.transport, PING, {
                "host": "192.0.2.2"
            })
        self.assertEqual(self.ont.posted, [])

    def test_unobserved_interface_ipv6_is_not_silently_dropped(self):
        with self.assertRaises(ValueError):
            self.diag.execute(self.ont, self.ont.transport, PING, {
                "host": "2001:db8::1", "ip_version": "IPv6"
            })
        self.assertEqual(self.ont.posted, [])

    def test_trace_parser_keeps_raw_lines(self):
        rows = trace_hops("1 192.0.2.1 2.3 ms\n2 * * *")
        self.assertEqual(rows[0]["ip"], "192.0.2.1")
        self.assertTrue(rows[1]["timeout"])


if __name__ == "__main__":
    unittest.main()

from __future__ import annotations

import unittest
from pathlib import Path

from apps.zte_manager.infrastructure.huawei import (
    HuaweiMutationTransport,
    HuaweiWebClient,
    decode_huawei_js_string,
)
from apps.zte_manager.services.attendance_report_service import (
    AttendanceReportService,
)
from apps.zte_manager.services.huawei_ipv4_filter_service import (
    HuaweiIPv4FilterRule,
    HuaweiIPv4FilterService,
    build_create_payload,
    build_delete_payload,
    build_update_payload,
    parse_st_filter_in,
    resolve_ipv4_filter_domain,
)


FIXTURE = (
    Path(__file__).parent
    / "fixtures"
    / "huawei_ipincoming.html"
)


def fixture_html() -> str:
    return FIXTURE.read_text(
        encoding="utf-8"
    )


def fixture_rule() -> HuaweiIPv4FilterRule:
    return HuaweiIPv4FilterRule(
        domain="",
        name="RE_TEST_01",
        protocol="TCP",
        direction="Bidirectional",
        lan_start_ip="192.168.18.240",
        lan_end_ip="192.168.18.241",
        wan_start_ip="203.0.113.10",
        wan_end_ip="203.0.113.11",
        lan_tcp_port="41001",
        lan_udp_port="",
        wan_tcp_port="42002",
        wan_udp_port="",
    )


class FakeHuaweiClient:
    extract_token = staticmethod(
        HuaweiWebClient.extract_token
    )

    def __init__(
        self,
        pages,
        *,
        transport=None,
    ):
        self.pages = list(pages)
        self.transport = (
            transport
            or HuaweiMutationTransport(
                http_status=200
            )
        )
        self.posts = []

    def get_page(self, path):
        if not self.pages:
            raise AssertionError(
                "Unexpected read-back"
            )
        return self.pages.pop(0)

    def post_form(
        self,
        path,
        payload,
        *,
        referer,
    ):
        self.posts.append({
            "path": path,
            "payload": payload,
            "referer": referer,
        })
        return self.transport


class HuaweiDecoderTests(unittest.TestCase):
    def test_decodes_any_hex_escape(self):
        self.assertEqual(
            decode_huawei_js_string(
                r"RE\x5fTEST\x5f01"
            ),
            "RE_TEST_01",
        )
        self.assertEqual(
            decode_huawei_js_string(
                r"192\x2e168\x2e18\x2e240"
            ),
            "192.168.18.240",
        )
        self.assertEqual(
            decode_huawei_js_string(
                r"A\x2fB\x3aC"
            ),
            "A/B:C",
        )


class HuaweiParserTests(unittest.TestCase):
    def test_parses_st_filter_in_and_decodes_fields(self):
        rules = parse_st_filter_in(
            fixture_html()
        )
        self.assertEqual(
            len(rules),
            1,
        )
        rule = rules[0]
        self.assertEqual(
            rule.domain,
            (
                "InternetGatewayDevice."
                "X_HW_Security.IpFilterIn.1"
            ),
        )
        self.assertEqual(
            rule.name,
            "RE_TEST_01",
        )
        self.assertEqual(
            rule.lan_start_ip,
            "192.168.18.240",
        )
        self.assertEqual(
            rule.wan_end_ip,
            "203.0.113.11",
        )
        self.assertEqual(
            rule.source_interface,
            (
                "InternetGatewayDevice.WANDevice.1."
                "WANConnectionDevice.1"
            ),
        )
        self.assertEqual(
            rule.vlan_id,
            "100",
        )

    def test_resolves_instance_or_full_domain(self):
        expected = (
            "InternetGatewayDevice."
            "X_HW_Security.IpFilterIn.7"
        )
        self.assertEqual(
            resolve_ipv4_filter_domain(7),
            expected,
        )
        self.assertEqual(
            resolve_ipv4_filter_domain(
                expected
            ),
            expected,
        )
        with self.assertRaises(
            ValueError
        ):
            resolve_ipv4_filter_domain(
                "0"
            )


class HuaweiPayloadTests(unittest.TestCase):
    def test_create_payload_matches_lab_fields(self):
        payload = build_create_payload(
            fixture_rule(),
            "token-1",
        )
        self.assertEqual(
            payload,
            {
                "x.Protocol": "TCP",
                "x.Direction": "Bidirectional",
                "x.Name": "RE_TEST_01",
                "x.SourceIPStart": "192.168.18.240",
                "x.SourceIPEnd": "192.168.18.241",
                "x.DestIPStart": "203.0.113.10",
                "x.DestIPEnd": "203.0.113.11",
                "x.LanSideTcpPort": "41001",
                "x.LanSideUdpPort": "",
                "x.WanSideTcpPort": "42002",
                "x.WanSideUdpPort": "",
                "x.X_HW_Token": "token-1",
            },
        )

    def test_update_payload_matches_create_field_contract(self):
        payload = build_update_payload(
            fixture_rule(),
            "token-2",
        )
        self.assertEqual(
            payload["x.Name"],
            "RE_TEST_01",
        )
        self.assertEqual(
            payload["x.LanSideTcpPort"],
            "41001",
        )
        self.assertEqual(
            payload["x.X_HW_Token"],
            "token-2",
        )
        self.assertNotIn(
            "x.Priority",
            payload,
        )
        self.assertNotIn(
            "x.Action",
            payload,
        )

    def test_delete_payload_uses_domain_as_form_key(self):
        payload = build_delete_payload(
            3,
            "token-3",
        )
        self.assertEqual(
            payload,
            {
                (
                    "InternetGatewayDevice."
                    "X_HW_Security.IpFilterIn.3"
                ): "",
                "x.X_HW_Token": "token-3",
            },
        )


class HuaweiReadBackTests(unittest.TestCase):
    def setUp(self):
        self.before = (
            '<input id="hwonttoken" '
            'value="fixture-token-1234567890">'
        )
        self.after = fixture_html()

    def service(
        self,
        client,
        *,
        tries=1,
    ):
        return HuaweiIPv4FilterService(
            client,
            model="EG8041X7-10",
            sleep=lambda _delay: None,
            readback_tries=tries,
        )

    def test_create_timeout_is_success_when_readback_matches(self):
        client = FakeHuaweiClient(
            [self.before, self.after],
            transport=HuaweiMutationTransport(
                http_status=None,
                timed_out=True,
            ),
        )
        result = self.service(
            client
        ).create_ipv4_filter(
            fixture_rule()
        )
        self.assertTrue(
            result["success"]
        )
        self.assertTrue(
            result["verified"]
        )
        self.assertTrue(
            result["transport"]["timed_out"]
        )
        self.assertIn(
            "/add.cgi?x=InternetGatewayDevice."
            "X_HW_Security.IpFilterIn",
            client.posts[0]["path"],
        )

    def test_http_200_is_not_success_without_semantic_readback(self):
        client = FakeHuaweiClient(
            [self.before, self.before],
            transport=HuaweiMutationTransport(
                http_status=200
            ),
        )
        result = self.service(
            client
        ).create_ipv4_filter(
            fixture_rule()
        )
        self.assertFalse(
            result["success"]
        )
        self.assertFalse(
            result["verified"]
        )
        self.assertTrue(
            result["uncertain"]
        )

    def test_update_confirms_same_domain_and_new_values(self):
        current = fixture_html()
        edited = current.replace(
            "RE\\x5fTEST\\x5f01",
            "RE\\x5fEDIT",
        ).replace(
            '"42002"',
            '"42003"',
        )
        rule = fixture_rule()
        updated = HuaweiIPv4FilterRule(
            **{
                **rule.as_dict(),
                "domain": (
                    "InternetGatewayDevice."
                    "X_HW_Security.IpFilterIn.1"
                ),
                "name": "RE_EDIT",
                "wan_tcp_port": "42003",
            }
        )
        client = FakeHuaweiClient(
            [current, edited]
        )
        result = self.service(
            client
        ).update_ipv4_filter(
            1,
            updated,
        )
        self.assertTrue(
            result["verified"]
        )
        self.assertIn(
            "set.cgi?x=InternetGatewayDevice."
            "X_HW_Security.IpFilterIn.1",
            client.posts[0]["path"],
        )

    def test_delete_confirms_rule_absence(self):
        client = FakeHuaweiClient(
            [
                fixture_html(),
                self.before,
            ]
        )
        result = self.service(
            client
        ).delete_ipv4_filter(
            (
                "InternetGatewayDevice."
                "X_HW_Security.IpFilterIn.1"
            )
        )
        self.assertTrue(
            result["verified"]
        )
        self.assertEqual(
            result["previous"]["name"],
            "RE_TEST_01",
        )
        self.assertIn(
            (
                "InternetGatewayDevice."
                "X_HW_Security.IpFilterIn.1"
            ),
            client.posts[0]["payload"],
        )

    def test_unknown_huawei_model_is_read_only(self):
        client = FakeHuaweiClient(
            [fixture_html()]
        )
        service = HuaweiIPv4FilterService(
            client,
            model="UNKNOWN-HUAWEI",
            sleep=lambda _delay: None,
            readback_tries=1,
        )
        state = service.list_ipv4_filters()
        self.assertTrue(
            state["capability"]["read"]
        )
        self.assertFalse(
            state["capability"]["verified"]
        )
        with self.assertRaises(
            PermissionError
        ):
            service.create_ipv4_filter(
                fixture_rule()
            )


class HuaweiAttendanceTests(unittest.TestCase):
    def test_verified_create_appears_in_attendance_report(self):
        rule = fixture_rule().as_dict()
        report = AttendanceReportService().build(
            diagnostic={
                "mode": "general",
                "sections": {},
                "findings": [],
                "status": "info",
            },
            timeline={
                "changes": [{
                    "id": 1,
                    "created_at": "2026-10-01T00:00:00Z",
                    "operation": "huawei_ipv4_filter_create",
                    "target": "RE_TEST_01",
                    "before_json": None,
                    "after_json": rule,
                    "success": True,
                    "outcome": "verified",
                }],
                "diagnostics": [],
                "snapshots": [],
            },
        )
        text = report["text"]
        self.assertIn(
            "IPv4 Filtering - Regra criada: RE_TEST_01",
            text,
        )
        self.assertIn(
            "LAN: 192.168.18.240-192.168.18.241",
            text,
        )
        self.assertIn(
            "Porta WAN: 42002",
            text,
        )
        self.assertIn(
            "alteração verificada por releitura",
            text,
        )


if __name__ == "__main__":
    unittest.main()

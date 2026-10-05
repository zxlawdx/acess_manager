from __future__ import annotations

import unittest
from copy import deepcopy

from apps.zte_manager.infrastructure.huawei import (
    HuaweiMutationTransport,
    HuaweiResponseParser,
)
from apps.zte_manager.services.huawei_eg8041x7_runtime import (
    HuaweiEG8041X7CapturedFeatureService,
    HuaweiEG8041X7RuntimeService,
)


TOKEN = "b" * 64
SEARCH_ROOT = "InternetGatewayDevice.X_HW_DNS.SearList"
HOST_ROOT = "InternetGatewayDevice.X_HW_DNS.HOSTS"


class FakeEGClient:
    def __init__(self, *, mutation_body="<html><body>ok</body></html>"):
        self.mutation_body = mutation_body
        self.posts = []
        self.search_rows = [{
            "Domain": SEARCH_ROOT + ".1",
            "DNSServer": "177.221.56.3",
            "DomainName": "cloudflare.com",
            "Interface": "wan1.1.ppp1",
        }]
        self.hosts = [
            {
                "id": HOST_ROOT + ".2",
                "ip": "8.8.8.8",
                "nome": "google",
            },
            {
                "id": HOST_ROOT + ".3",
                "ip": "1.1.1.1",
                "nome": "cloudflare",
            },
        ]

    @staticmethod
    def extract_token(_page):
        return TOKEN

    def get_page(self, _path):
        return f'<input id="hwonttoken" value="{TOKEN}">'

    def post_form(self, path, payload, *, referer):
        self.posts.append((path, dict(payload), referer))
        safe = {
            key: value
            for key, value in payload.items()
            if key != "x.X_HW_Token"
        }

        if "X_HW_DNS.SearList" in path:
            if "/set.cgi" in path:
                domain = path.split("?x=", 1)[1].split("&", 1)[0]
                row = next(
                    item for item in self.search_rows
                    if item["Domain"] == domain
                )
                row.update({
                    "DNSServer": str(safe["x.DNSServer"]),
                    "DomainName": str(safe["x.DomainName"]),
                    "Interface": str(safe["x.Interface"]),
                })
            elif "/add.cgi" in path:
                index = len(self.search_rows) + 1
                self.search_rows.append({
                    "Domain": f"{SEARCH_ROOT}.{index}",
                    "DNSServer": str(safe["x.DNSServer"]),
                    "DomainName": str(safe["x.DomainName"]),
                    "Interface": str(safe["x.Interface"]),
                })

        if "X_HW_DNS.HOSTS" in path:
            if "/del.cgi" in path:
                domains = set(safe)
                self.hosts = [
                    item for item in self.hosts
                    if item["id"] not in domains
                ]
            elif "/add.cgi" in path:
                index = max(
                    [int(item["id"].rsplit(".", 1)[1]) for item in self.hosts]
                    or [0]
                ) + 1
                self.hosts.append({
                    "id": f"{HOST_ROOT}.{index}",
                    "ip": str(safe["x.IPAddress"]),
                    "nome": str(safe["x.DomainName"]),
                })
            elif "/set.cgi" in path:
                domain = path.split("?x=", 1)[1].split("&", 1)[0]
                row = next(item for item in self.hosts if item["id"] == domain)
                row.update({
                    "ip": str(safe["x.IPAddress"]),
                    "nome": str(safe["x.DomainName"]),
                })

        return HuaweiMutationTransport(
            http_status=200,
            body=self.mutation_body,
            content_type="text/html; charset=UTF-8",
        )


class StatefulCaptured(HuaweiEG8041X7CapturedFeatureService):
    def dns_status(self):
        rows = deepcopy(self.client.search_rows)
        ipv4 = [
            item["DNSServer"]
            for item in rows
            if item.get("DNSServer") and ":" not in item["DNSServer"]
        ]
        ipv6 = [
            item["DNSServer"]
            for item in rows
            if item.get("DNSServer") and ":" in item["DNSServer"]
        ]
        return {
            "domain_name": str(rows[0].get("DomainName") or "") if rows else "",
            "ipv4_1": ipv4[0] if ipv4 else "",
            "ipv4_2": ipv4[1] if len(ipv4) > 1 else "",
            "ipv6_1": ipv6[0] if ipv6 else "",
            "ipv6_2": ipv6[1] if len(ipv6) > 1 else "",
            "hosts": deepcopy(self.client.hosts),
            "_search_rows": rows,
        }


class ProfileCapturedFake:
    def __init__(self, dns_result=None):
        self.calls = []
        self.dns_result = dns_result or {
            "success": True,
            "accepted": True,
            "confirmed_by_response": False,
            "verified": True,
            "verified_by_readback": True,
            "readback_attempts": 1,
            "response_type": "html",
            "readback": None,
        }

    def set_wifi_radio(self, band, config):
        self.calls.append(("wifi", band, deepcopy(config)))
        return {
            "success": True,
            "accepted": True,
            "confirmed_by_response": False,
            "verified": True,
            "verified_by_readback": True,
            "readback_attempts": 1,
            "response_type": "html",
            "readback": None,
        }

    def set_dns(self, config):
        self.calls.append(("dns", deepcopy(config)))
        return deepcopy(self.dns_result)


class HuaweiEG8041X7RuntimeTests(unittest.TestCase):
    @staticmethod
    def make_captured(*, body="<html><body>ok</body></html>", rows=True):
        client = FakeEGClient(mutation_body=body)
        if not rows:
            client.search_rows = []
        service = StatefulCaptured(
            client,
            model="EG8041X7-10",
            sleep=lambda _delay: None,
            readback_tries=2,
        )
        return service, client

    def test_parser_rejects_login_page_even_with_http_200(self):
        parsed = HuaweiResponseParser.parse(
            http_status=200,
            content_type="text/html",
            body=(
                '<html><form action="login.cgi">'
                '<input name="UserName"><input name="Password">'
                '<script src="GetRandCount.asp"></script></form></html>'
            ),
        )
        self.assertFalse(parsed.accepted)
        self.assertEqual(parsed.response_type, "login_page")
        self.assertEqual(parsed.error_code, "session_expired")

    def test_full_html_with_unrelated_result_variable_is_not_false_failure(self):
        parsed = HuaweiResponseParser.parse(
            http_status=200,
            content_type="text/html",
            body=(
                '<html><script>function helper(){var result = 1; '
                'return result;}</script><body>config</body></html>'
            ),
        )
        self.assertTrue(parsed.accepted)
        self.assertFalse(parsed.confirmed)
        self.assertEqual(parsed.response_type, "html")

    def test_post_verified_accepts_empty_html_and_redirect_only_after_readback(self):
        bodies = (
            "",
            "<html><body>configuration</body></html>",
            '<script>window.location.href="/html/bbsp/test.asp";</script>',
        )
        for body in bodies:
            with self.subTest(body=body):
                service, _client = self.make_captured(body=body)
                result = service._post_verified(
                    path="/html/bbsp/test/set.cgi?RequestFile=html/bbsp/test.asp",
                    request_file="/html/bbsp/dnsconfiguration/dnsconfigcommon.asp",
                    payload={"x.Value": "1"},
                    verifier=lambda: {"Value": "1"},
                )
                self.assertTrue(result["accepted"])
                self.assertTrue(result["verified"])
                self.assertTrue(result["verified_by_readback"])
                self.assertGreaterEqual(result["readback_attempts"], 1)

    def test_post_verified_readback_mismatch_is_explicit(self):
        service, _client = self.make_captured()
        result = service._post_verified(
            path="/html/bbsp/test/set.cgi?RequestFile=html/bbsp/test.asp",
            request_file="/html/bbsp/dnsconfiguration/dnsconfigcommon.asp",
            payload={"x.Value": "1"},
            verifier=lambda: None,
        )
        self.assertTrue(result["accepted"])
        self.assertFalse(result["verified"])
        self.assertEqual(result["error_code"], "readback_mismatch")
        self.assertEqual(result["readback_attempts"], 2)

    def test_post_verified_readback_exception_is_explicit(self):
        service, _client = self.make_captured()

        def broken():
            raise ValueError("broken readback parser")

        result = service._post_verified(
            path="/html/bbsp/test/set.cgi?RequestFile=html/bbsp/test.asp",
            request_file="/html/bbsp/dnsconfiguration/dnsconfigcommon.asp",
            payload={"x.Value": "1"},
            verifier=broken,
        )
        self.assertTrue(result["accepted"])
        self.assertFalse(result["verified"])
        self.assertEqual(result["error_code"], "readback_error")
        self.assertIn("broken readback parser", result["error_message"])

    def test_dns_search_existing_entry_uses_set_and_semantic_readback(self):
        service, client = self.make_captured()
        result = service.set_dns({
            "domain_name": "cloudflare.com",
            "ipv4_1": "9.9.9.9",
            "ipv4_2": "",
            "ipv6_1": "",
            "ipv6_2": "",
            "hosts": deepcopy(client.hosts),
        })
        self.assertTrue(result["verified"])
        self.assertTrue(result["semantic_verified"])
        self.assertEqual(len(client.posts), 1)
        path, payload, _referer = client.posts[0]
        self.assertIn("/dnsconfiguration/set.cgi", path)
        self.assertIn("x=InternetGatewayDevice.X_HW_DNS.SearList.1", path)
        self.assertEqual(payload["x.DNSServer"], "9.9.9.9")

    def test_dns_search_create_uses_add_and_semantic_readback(self):
        service, client = self.make_captured(rows=False)
        result = service.set_dns({
            "interface": "wan1.1.ppp1",
            "domain_name": "example.test",
            "ipv4_1": "9.9.9.9",
            "ipv4_2": "",
            "ipv6_1": "",
            "ipv6_2": "",
        })
        self.assertTrue(result["verified"])
        self.assertEqual(len(client.posts), 1)
        path, payload, _referer = client.posts[0]
        self.assertIn("/dnsconfiguration/add.cgi", path)
        self.assertIn("x=InternetGatewayDevice.X_HW_DNS.SearList", path)
        self.assertEqual(payload["x.Interface"], "wan1.1.ppp1")

    def test_dns_search_delete_unmapped_sends_no_invalid_post(self):
        service, client = self.make_captured()
        result = service.set_dns({
            "domain_name": "cloudflare.com",
            "ipv4_1": "",
            "ipv4_2": "",
            "ipv6_1": "",
            "ipv6_2": "",
            "hosts": deepcopy(client.hosts),
        })
        self.assertFalse(result["verified"])
        self.assertEqual(result["error_code"], "unsupported_delete")
        self.assertEqual(client.posts, [])
        self.assertEqual(client.search_rows[0]["DNSServer"], "177.221.56.3")

    def test_dns_host_delete_uses_captured_del_cgi(self):
        service, client = self.make_captured()
        requested_hosts = [deepcopy(client.hosts[0])]
        result = service.set_dns({
            "domain_name": "cloudflare.com",
            "ipv4_1": "177.221.56.3",
            "ipv4_2": "",
            "ipv6_1": "",
            "ipv6_2": "",
            "hosts": requested_hosts,
        })
        self.assertTrue(result["verified"])
        delete_posts = [item for item in client.posts if "/del.cgi" in item[0]]
        self.assertEqual(len(delete_posts), 1)
        path, payload, _referer = delete_posts[0]
        self.assertIn("x=InternetGatewayDevice.X_HW_DNS.HOSTS", path)
        self.assertIn(HOST_ROOT + ".3", payload)

    @staticmethod
    def _physical_profile():
        return {
            "wifi": {
                "2.4GHz": {
                    "auto_channel": True,
                    "channel": None,
                    "standard": "11ax",
                    "country": "BR",
                    "bandwidth": "Auto",
                    "bandwidth_code": "0",
                    "sgi": False,
                    "beacon_interval": 100,
                    "tx_power": "100%",
                },
                "5GHz": {
                    "auto_channel": True,
                    "channel": None,
                    "standard": "11ax",
                    "country": "BR",
                    "bandwidth": "Auto",
                    "bandwidth_code": "4",
                    "sgi": False,
                    "beacon_interval": 100,
                    "tx_power": "100%",
                },
            },
            "dns": {
                "domain_name": "cloudflare.com",
                "ipv4_1": "177.221.56.3",
                "ipv4_2": "",
                "ipv6_1": "",
                "ipv6_2": "",
                "hosts": [
                    {"nome": "cloudflare", "ip": "1.1.1.1"},
                    {"nome": "google", "ip": "8.8.8.8"},
                ],
            },
        }

    def test_profile_wifi_already_correct_only_applies_dns_change(self):
        service = HuaweiEG8041X7RuntimeService()
        service.model = "EG8041X7-10"
        captured = ProfileCapturedFake()
        service._captured = captured
        profile = self._physical_profile()
        current = deepcopy(profile)
        current["dns"]["ipv4_1"] = "9.9.9.9"
        service.current_configuration = lambda: deepcopy(current)
        service._audit_captured = lambda **_kwargs: None

        result = service._apply_profile_payload(
            profile,
            operation="test_profile",
            target="tester",
        )

        self.assertTrue(result["verified"])
        self.assertEqual([item[0] for item in captured.calls], ["dns"])
        self.assertIn("Wi-Fi 2.4GHz", result["unchanged"])
        self.assertIn("Wi-Fi 5GHz", result["unchanged"])

    def test_profile_noop_is_success_without_write_or_audit(self):
        service = HuaweiEG8041X7RuntimeService()
        service.model = "EG8041X7-10"
        captured = ProfileCapturedFake()
        service._captured = captured
        profile = self._physical_profile()
        service.current_configuration = lambda: deepcopy(profile)
        audits = []
        service._audit_captured = lambda **kwargs: audits.append(kwargs)

        result = service._apply_profile_payload(
            profile,
            operation="test_profile",
            target="tester",
        )

        self.assertTrue(result["success"])
        self.assertEqual(result["steps"], [])
        self.assertEqual(captured.calls, [])
        self.assertEqual(audits, [])

    def test_profile_failure_returns_specific_step_and_reason(self):
        service = HuaweiEG8041X7RuntimeService()
        service.model = "EG8041X7-10"
        captured = ProfileCapturedFake(dns_result={
            "success": False,
            "accepted": True,
            "confirmed_by_response": False,
            "verified": False,
            "verified_by_readback": False,
            "readback_attempts": 2,
            "response_type": "html",
            "error_code": "readback_mismatch",
            "error_message": (
                "A alteração foi aceita, mas a releitura não confirmou o estado esperado."
            ),
        })
        service._captured = captured
        profile = self._physical_profile()
        current = deepcopy(profile)
        current["dns"]["ipv4_1"] = "9.9.9.9"
        service.current_configuration = lambda: deepcopy(current)
        service._audit_captured = lambda **_kwargs: None

        result = service._apply_profile_payload(
            profile,
            operation="test_profile",
            target="tester",
        )

        self.assertFalse(result["success"])
        self.assertEqual(result["step"], "dns")
        self.assertEqual(result["error_code"], "readback_mismatch")
        self.assertIn("Falha ao aplicar DNS / hosts", result["error"])
        self.assertIn("releitura", result["reason"])


if __name__ == "__main__":
    unittest.main()

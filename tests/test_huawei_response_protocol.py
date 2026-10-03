from __future__ import annotations

import unittest

from apps.zte_manager.infrastructure.huawei import (
    HuaweiMutationTransport,
    HuaweiResponseParser,
    HuaweiWebClient,
)
from apps.zte_manager.services.huawei_mapped_surface import (
    HuaweiMappedSurfaceService,
)


TOKEN = "f" * 64


class FakeResponse:
    def __init__(self, status_code, text="", url="http://192.168.18.1/"):
        self.status_code = status_code
        self.text = text
        self.url = url


class FakeMappedClient:
    def __init__(self, *, mutation_body="<html><body>ok</body></html>"):
        self.get_calls = []
        self.post_calls = []
        self.mutation_body = mutation_body
        self.state = "0"

    @staticmethod
    def extract_token(source):
        if TOKEN not in source:
            raise RuntimeError("token missing")
        return TOKEN

    def get_page(self, path):
        self.get_calls.append(path)
        return (
            "function stUpnp(Enable){this.Enable=Enable;}"
            f'new stUpnp("{self.state}");'
            f'<input id="hwonttoken" value="{TOKEN}">'
        )

    def post_read(self, path, payload=None, *, referer="/index.asp"):
        return self.get_page(path)

    def post_form(self, path, payload, *, referer):
        self.post_calls.append((path, dict(payload), referer))
        if "x.Enable" in payload:
            self.state = str(payload["x.Enable"])
        return HuaweiMutationTransport(
            http_status=200,
            body=self.mutation_body,
            content_type="text/html; charset=UTF-8",
        )


class HuaweiResponseProtocolTests(unittest.TestCase):
    def test_requestfile_keeps_literal_slashes(self):
        value = HuaweiWebClient._preserve_request_file(
            "/html/bbsp/dmz/set.cgi?"
            "x=InternetGatewayDevice.Test&"
            "RequestFile=html%2Fbbsp%2Fdmz%2Fdmz.asp"
        )
        self.assertIn("RequestFile=html/bbsp/dmz/dmz.asp", value)
        self.assertNotIn("RequestFile=html%2Fbbsp", value)

    def test_403_huawei_error_is_not_automatically_login_loss(self):
        response = FakeResponse(
            403,
            '<script>var ErrCode = "0x1";</script>',
        )
        self.assertFalse(HuaweiWebClient.is_login_response(response))

    def test_normal_html_is_accepted_but_not_confirmed(self):
        parsed = HuaweiResponseParser.parse(
            http_status=200,
            body="<html><body>DMZ</body></html>",
            content_type="text/html; charset=UTF-8",
        )
        self.assertTrue(parsed.ok)
        self.assertTrue(parsed.accepted)
        self.assertFalse(parsed.confirmed)
        self.assertEqual(parsed.response_type, "html")

    def test_huawei_error_page_is_failure_even_with_http_200(self):
        parsed = HuaweiResponseParser.parse(
            http_status=200,
            body='<html><script>var ErrCode = "0x1";</script></html>',
            content_type="text/html",
        )
        self.assertFalse(parsed.ok)
        self.assertFalse(parsed.accepted)
        self.assertEqual(parsed.error_code, "0x1")
        self.assertEqual(parsed.response_type, "error_page")

    def test_http_403_is_failure(self):
        parsed = HuaweiResponseParser.parse(
            http_status=403,
            body="Forbidden",
        )
        self.assertFalse(parsed.ok)
        self.assertFalse(parsed.accepted)
        self.assertEqual(parsed.response_type, "http_error")

    def test_hex_ajax_result_zero_is_semantic_success(self):
        parsed = HuaweiResponseParser.parse(
            http_status=200,
            body=(
                r"\x7b\x20\x22result\x22\x3a\x200\x20\x7d"
            ),
        )
        self.assertTrue(parsed.ok)
        self.assertTrue(parsed.accepted)
        self.assertTrue(parsed.confirmed)
        self.assertEqual(parsed.data, {"result": 0})

    def test_hex_ajax_nonzero_is_semantic_failure(self):
        parsed = HuaweiResponseParser.parse(
            http_status=200,
            body=(
                r"\x7b\x22result\x22\x3a1\x2c"
                r"\x22error\x22\x3a\x220x1\x22\x7d"
            ),
        )
        self.assertFalse(parsed.ok)
        self.assertFalse(parsed.accepted)
        self.assertEqual(parsed.error_code, "0x1")
        self.assertEqual(parsed.data["result"], 1)

    def test_mapped_write_derives_token_page_from_requestfile(self):
        client = FakeMappedClient()
        service = HuaweiMappedSurfaceService(
            client,
            model="EG8041X7-10",
        )
        result = service.write_request(
            "/html/bbsp/upnp/set.cgi?"
            "x=InternetGatewayDevice.X_HW_MainUPnP&"
            "RequestFile=html%2Fbbsp%2Fupnp%2Fupnp.asp",
            {"x.Enable": "0"},
            referer="/html/bbsp/other/set.cgi",
        )
        self.assertTrue(result["accepted"])
        self.assertIn(
            "/html/bbsp/upnp/upnp.asp",
            client.get_calls,
        )
        _path, payload, referer = client.post_calls[0]
        self.assertEqual(referer, "/html/bbsp/upnp/upnp.asp")
        self.assertEqual(payload["x.X_HW_Token"], TOKEN)

    def test_mapped_html_write_requires_readback_for_verification(self):
        client = FakeMappedClient()
        service = HuaweiMappedSurfaceService(client)
        result = service.write_request(
            "/html/bbsp/upnp/set.cgi?"
            "x=InternetGatewayDevice.X_HW_MainUPnP&"
            "RequestFile=html/bbsp/upnp/upnp.asp",
            {"x.Enable": "1"},
            readback_path="/html/bbsp/upnp/upnp.asp",
            readback_expect={"Enable": "1"},
        )
        self.assertTrue(result["accepted"])
        self.assertTrue(result["verified"])
        self.assertTrue(result["success"])

    def test_mapped_html_without_expected_state_is_not_falsely_verified(self):
        client = FakeMappedClient()
        service = HuaweiMappedSurfaceService(client)
        result = service.write_request(
            "/html/bbsp/upnp/set.cgi?"
            "x=InternetGatewayDevice.X_HW_MainUPnP&"
            "RequestFile=html/bbsp/upnp/upnp.asp",
            {"x.Enable": "1"},
            readback_path="/html/bbsp/upnp/upnp.asp",
        )
        self.assertTrue(result["accepted"])
        self.assertFalse(result["verified"])
        self.assertTrue(result["success"])

    def test_ajax_failure_prevents_readback_false_positive(self):
        client = FakeMappedClient(
            mutation_body=(
                r"\x7b\x22result\x22\x3a1\x2c"
                r"\x22error\x22\x3a\x220x1\x22\x7d"
            )
        )
        service = HuaweiMappedSurfaceService(client)
        result = service.write_request(
            "/html/bbsp/dscptopbit/setajax.cgi?"
            "RequestFile=html/bbsp/dscptopbit/dscptopbit.asp",
            {"x.DefaultPbit": "0"},
            readback_path="/html/bbsp/dscptopbit/dscptopbit.asp",
            readback_expect={"DefaultPbit": "0"},
        )
        self.assertFalse(result["accepted"])
        self.assertFalse(result["verified"])
        self.assertFalse(result["success"])
        self.assertEqual(result["error_code"], "0x1")


if __name__ == "__main__":
    unittest.main()

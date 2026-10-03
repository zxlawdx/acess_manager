from __future__ import annotations

import unittest
from types import SimpleNamespace

from apps.zte_manager.infrastructure.huawei import HuaweiMutationTransport
from apps.zte_manager.model.device_adapters.huawei import (
    HuaweiEG8041X7Profile,
    HuaweiUnknownProfile,
)
from apps.zte_manager.services.huawei_mapped_surface import (
    HUAWEI_MAPPED_FEATURES,
    HuaweiMappedSurfaceService,
)
from apps.zte_manager.services.huawei_service import HuaweiService


TOKEN_PAGE = (
    '<input type="hidden" id="hwonttoken" '
    'value="fresh-token-123456">'
)


class FakeClient:
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
        if path in {
            "/html/test/page.asp",
            "/html/ssmp/Sectionspeed/Sectionspeed.asp",
        }:
            return TOKEN_PAGE + (
                "<script>"
                "function stRow(a){this.Name=a;}"
                "var row=new stRow('ok');"
                "</script>"
            )
        return (
            "<script>"
            "function stRow(a){this.Name=a;}"
            "var row=new stRow('ok');"
            "</script>"
        )

    def post_read(self, path, payload=None, *, referer="/index.asp"):
        self.post_read_calls.append((path, dict(payload or {}), referer))
        return (
            "<script>"
            "function stRow(a){this.Name=a;}"
            "var row=new stRow('post-ok');"
            "</script>"
        )

    def post_form(self, path, payload, *, referer):
        self.post_form_calls.append((path, dict(payload), referer))
        return HuaweiMutationTransport(http_status=200)


class HuaweiMappedSurfaceTests(unittest.TestCase):
    def make_service(self):
        self.client = FakeClient()
        return HuaweiMappedSurfaceService(
            self.client,
            model="EG8041X7-10",
        )

    def test_catalog_exposes_mapped_groups_and_raw_read_write(self):
        service = self.make_service()
        catalog = service.catalog()
        keys = {item["key"] for item in catalog["features"]}

        self.assertIn("upnp", keys)
        self.assertIn("routing", keys)
        self.assertIn("speed_test", keys)
        self.assertIn("diagnostics_webui", keys)
        self.assertTrue(catalog["raw_relative_requests"]["read"])
        self.assertTrue(catalog["raw_relative_requests"]["write"])

    def test_read_feature_reads_real_mapped_page(self):
        service = self.make_service()
        result = service.read_feature("upnp")

        self.assertTrue(result["available"])
        self.assertEqual(
            self.client.get_calls,
            ["/html/bbsp/upnp/upnp.asp"],
        )
        self.assertEqual(
            result["pages"][0]["records"][0]["Name"],
            "ok",
        )

    def test_read_request_supports_post_only_read_endpoints(self):
        service = self.make_service()
        result = service.read_request(
            "/getajax.cgi?x=InternetGatewayDevice.Test",
            method="POST",
            payload={"x.State": "Requested"},
            referer="/html/test/page.asp",
        )

        self.assertTrue(result["success"])
        self.assertEqual(len(self.client.post_read_calls), 1)
        self.assertEqual(
            result["data"]["records"][0]["Name"],
            "post-ok",
        )

    def test_tokenized_post_read_gets_fresh_token_without_mutating(self):
        service = self.make_service()
        result = service.read_request(
            "/html/test/read.cgi",
            method="POST",
            payload={"x.State": "Requested"},
            referer="/html/test/page.asp",
            token_page="/html/test/page.asp",
        )

        self.assertTrue(result["success"])
        self.assertEqual(len(self.client.post_form_calls), 0)
        self.assertEqual(len(self.client.post_read_calls), 1)
        _path, payload, _referer = self.client.post_read_calls[0]
        self.assertEqual(
            payload["x.X_HW_Token"],
            "fresh-token-123456",
        )

    def test_mapped_features_include_captured_post_reads(self):
        service = self.make_service()
        catalog = {
            item["key"]: item
            for item in service.catalog()["features"]
        }
        self.assertGreater(catalog["wan_config"]["read_request_count"], 0)
        self.assertGreater(catalog["user_devices"]["read_request_count"], 0)
        self.assertGreater(catalog["diagnostics_webui"]["read_request_count"], 0)
        self.assertGreater(catalog["security_check"]["read_request_count"], 0)

    def test_write_schema_exposes_only_captured_semantic_mutations(self):
        speed = HuaweiMappedSurfaceService.write_schema("speed_test")
        self.assertTrue(speed["available"])
        operations = {item["key"] for item in speed["operations"]}
        self.assertEqual(
            operations,
            {"speed_test", "speed_test_mode"},
        )
        upnp = HuaweiMappedSurfaceService.write_schema("upnp")
        self.assertFalse(upnp["available"])

    def test_request_never_leaves_connected_huawei_host(self):
        service = self.make_service()

        with self.assertRaises(ValueError):
            service.read_request("https://example.test/admin")
        with self.assertRaises(ValueError):
            service.write_request(
                "http://example.test/set.cgi",
                {"x.Enable": "1"},
            )

    def test_write_injects_fresh_token_and_submits_exactly_once(self):
        service = self.make_service()
        result = service.write_request(
            "/html/test/set.cgi?x=InternetGatewayDevice.Test",
            {
                "x.Enable": "1",
                "x.X_HW_Token": "caller-token-must-not-pass",
            },
            referer="/html/test/page.asp",
            token_page="/html/test/page.asp",
            readback_path="/html/test/page.asp",
        )

        self.assertEqual(len(self.client.post_form_calls), 1)
        path, payload, referer = self.client.post_form_calls[0]
        self.assertEqual(
            path,
            "/html/test/set.cgi?x=InternetGatewayDevice.Test",
        )
        self.assertEqual(referer, "/html/test/page.asp")
        self.assertEqual(payload["x.Enable"], "1")
        self.assertEqual(
            payload["x.X_HW_Token"],
            "fresh-token-123456",
        )
        self.assertNotIn(
            "caller-token-must-not-pass",
            payload.values(),
        )
        self.assertTrue(result["verified"])
        self.assertFalse(result["uncertain"])

    def test_speed_test_writer_uses_captured_fields_only(self):
        service = self.make_service()
        result = service.write_feature(
            "speed_test",
            {
                "x.DiagnosticsState": "requested",
                "x.ServerAddr": "192.0.2.10",
                "x.TestMode": "UPLOAD",
                "x.Port": 5201,
                "x.ProtocolType": "TCP",
                "x.MaxTime": 10,
                "x.Parallel": 1,
                "not.captured": "must-not-be-forwarded",
            },
        )

        self.assertTrue(result["verified"])
        self.assertEqual(len(self.client.post_form_calls), 1)
        payload = self.client.post_form_calls[0][1]
        self.assertNotIn("not.captured", payload)
        self.assertEqual(payload["x.ServerAddr"], "192.0.2.10")
        self.assertEqual(payload["x.Port"], "5201")


class HuaweiMappedProviderIntegrationTests(unittest.TestCase):
    def test_known_profile_publishes_mapped_capabilities(self):
        profile = HuaweiEG8041X7Profile()

        for feature in HUAWEI_MAPPED_FEATURES:
            self.assertIn(feature, profile.captured_features)
            self.assertTrue(profile.captured_features[feature]["read"])

    def test_captured_service_is_not_blocked_by_profile_key(self):
        service = HuaweiService()
        marker = SimpleNamespace()
        service._captured = marker
        service._profile = HuaweiUnknownProfile("Huawei mapped")

        self.assertIs(service._require_captured(), marker)


if __name__ == "__main__":
    unittest.main()

"""F6201B operator access: every mapped GET is inspectable on request.

These are synthetic responses: an HTTP 200 alone is not treated as proof
that a real router firmware implements any given menu.
"""
from __future__ import annotations

import unittest

from apps.zte_manager.services import f6201b_capture


class Router:
    base_url = "http://192.0.2.1"
    def __init__(self):
        self.views = []
        self.menus = []
    def get_view(self, name, **kwargs):
        self.views.append(name)
        return "<html>mock session</html>"
    def get_menu(self, tag, **kwargs):
        self.menus.append((tag, kwargs))
        if tag == "topo_lua.lua":
            return '{"master":{"token":"DO_NOT_RETURN"},"password":"HIDDEN","ad":{"one":{"MacAddr":"SECRET_MAC"}}}'
        return """<ajax_response_xml_root>
            <IF_ERRORID>0</IF_ERRORID>
            <OBJ_ACCESSDEV_ID>
                <Instance>
                    <ParaName>IPAddress</ParaName><ParaValue>192.168.100.4</ParaValue>
                    <ParaName>Password</ParaName><ParaValue>SECRET_ROUTER_PASSWORD</ParaValue>
                    <ParaName>LinkUp</ParaName><ParaValue>1</ParaValue>
                </Instance>
            </OBJ_ACCESSDEV_ID>
        </ajax_response_xml_root>"""


class CapturedReadTests(unittest.TestCase):
    def test_catalog_lists_all_observed_get_routes(self):
        data = f6201b_capture.catalog()
        self.assertGreaterEqual(data["total_get_routes"], 90)
        self.assertIn("topo_lua.lua", [r["tag"] for r in data["routes"]])

    def test_rootless_xml_is_structurally_inspected_without_values(self):
        router = Router()
        result = f6201b_capture.inspect(router, "accessdev_homepage_lua.lua")
        self.assertTrue(result["available"])
        self.assertIn("OBJ_ACCESSDEV_ID", result["structure"])
        self.assertEqual(result["structure"]["OBJ_ACCESSDEV_ID"]["fields"], ["LinkUp"])
        self.assertNotIn("192.168.100.4", str(result))
        self.assertNotIn("SECRET_ROUTER_PASSWORD", str(result))
        self.assertEqual(router.views, ["homePage"])

    def test_json_route_shows_structure_only(self):
        router = Router()
        result = f6201b_capture.inspect(router, "topo_lua.lua")
        self.assertTrue(result["available"])
        self.assertEqual(result["structure"]["type"], "dict")
        self.assertNotIn("HIDDEN", str(result))
        self.assertNotIn("SECRET_MAC", str(result))
        self.assertNotIn("password", str(result).lower())

    def test_unmapped_or_error_response_still_fails_without_leak(self):
        router = Router()
        with self.assertRaises(ValueError):
            f6201b_capture.inspect(router, "arbitrary_menu_that_was_not_captured")
        router.get_menu = lambda _tag, **_opts: "<html>SECRET_SESSION_TOKEN</html>"
        report = f6201b_capture.inspect(router, "accessdev_homepage_lua.lua")
        self.assertFalse(report["available"])
        self.assertNotIn("SECRET_SESSION_TOKEN", str(report))


if __name__ == "__main__":
    unittest.main()

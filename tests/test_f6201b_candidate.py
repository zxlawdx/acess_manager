"""Owner-captured F6201B GET route and XML structure regressions."""
import unittest

from apps.zte_manager.services import multimodel_service as multimodel
from apps.zte_manager.services import model_diagnostic_service as diagnostic
from apps.zte_manager.services import f6201b_capture
from apps.zte_manager.model.device_adapters import select_adapter


XML = """
<ajax_response_xml_root>
    <OBJ_DEVINFO_ID>
        <Instance>
            <ParaName>ModelName</ParaName><ParaValue>F6201B</ParaValue>
        </Instance>
    </OBJ_DEVINFO_ID>
</ajax_response_xml_root>
"""


class ReadOnlyDevice:
    def __init__(self):
        self.calls = []

    def get_view(self, view, **kwargs):
        self.calls.append(("GET_VIEW", view))

    def get_menu(self, tag, **kwargs):
        self.calls.append(("GET_MENU", tag))
        return XML

    def post(self, *args, **kwargs):
        raise AssertionError("A probe must never use POST against the ONT")


class F6201BTests(unittest.TestCase):
    def test_experimental_profile_never_enables_writes(self):
        model, family = multimodel.find_family("ZXHN F6201B")
        self.assertEqual((model, family), ("F6201B", "f6201b_candidate"))
        self.assertEqual(multimodel.catalog()["models"][-1]["evidence"],
                         "owner_capture_V9.3.10P7N7")
        self.assertIn("pon_optical",
                      multimodel.catalog()["models"][-1]["candidate_features"])
        self.assertIn("lan_ports",
                      multimodel.catalog()["models"][-1]["candidate_features"])
        self.assertNotIn("lan_clients", multimodel.FAMILY[family])
        adapter = select_adapter("F6201B")
        self.assertNotIn(adapter.name,
                         {"zte-f6600p-thinklua", "zte-f670l-thinklua"})

    def test_probe_confirms_only_matching_xml_shape(self):
        client = ReadOnlyDevice()
        result = multimodel.probe(client, "F6201B",
                                  max_endpoints=1, start=1)
        self.assertTrue(result["read_only"])
        self.assertEqual(result["model"], "F6201B")
        # Optical XML must not be confused with the valid device XML.
        self.assertFalse(result["endpoints"]["pon_optical"]["available"])
        self.assertFalse(result["supported"])
        self.assertTrue(all(call[0].startswith("GET") for call in client.calls))

    def test_captured_routes_and_safe_field_projection(self):
        features = multimodel.FAMILY["f6201b_candidate"]
        self.assertEqual(features["wifi_clients"].tag, "wlan_homepage_lua.lua")
        self.assertEqual(features["lan_ports"].tag, "status_lan_info_lua.lua")
        self.assertEqual(features["pon_optical"].tag, "optical_info_lua.lua")
        self.assertEqual(features["wifi_ssids"].root, "OBJ_WLANAP_ID")
        self.assertNotIn("Username", str(diagnostic.F6201B_FIELDS))
        self.assertNotIn("Password", str(diagnostic.F6201B_FIELDS))

    def test_captured_inventory_is_complete_and_manual(self):
        routes = f6201b_capture.catalog()
        self.assertGreaterEqual(routes["total_get_routes"], 92)
        self.assertTrue(any(item["tag"] == "optical_info_lua.lua"
                            for item in routes["routes"]))
        self.assertFalse(f6201b_capture.ALLOWED["topo_lua.lua"]["inspectable"])
        self.assertTrue(f6201b_capture.ALLOWED[
            "wan_internetstatus_lua.lua"]["inspectable"])

    def test_captured_inspection_is_structural_and_allowlisted(self):
        fake = ReadOnlyDevice()
        with self.assertRaises(ValueError):
            f6201b_capture.inspect(fake, "arbitrary.lua")
        self.assertEqual(fake.calls, [])
        response = f6201b_capture.inspect(fake, "devmgr_statusmgr_lua.lua")
        self.assertTrue(response["available"])
        self.assertEqual(response["structure"]["OBJ_DEVINFO_ID"]["records"], 1)
        self.assertNotIn("F6201B", str(response["structure"]))
        self.assertTrue(all(action.startswith("GET") for action, _ in fake.calls))

    def test_device_diagnostic_can_use_validated_read_only_shape(self):
        client = ReadOnlyDevice()
        result = diagnostic.diagnostic(client, "F6201B", section="device")
        self.assertTrue(result["experimental"])
        self.assertTrue(result["sections"]["device"]["available"])
        self.assertEqual(result["sections"]["device"]["data"]["identity"][0]["model"],
                         "F6201B")
        self.assertTrue(all(call[0].startswith("GET") for call in client.calls))


if __name__ == "__main__":
    unittest.main()

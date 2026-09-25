"""F6201B is a provisional GET-only profile, not an assumed supported firmware."""
import unittest

from apps.zte_manager.services import multimodel_service as multimodel
from apps.zte_manager.services import model_diagnostic_service as diagnostic
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
                         "unverified_candidate")
        self.assertNotIn("pon_optical",
                         multimodel.catalog()["models"][-1]["candidate_features"])
        adapter = select_adapter("F6201B")
        self.assertNotIn(adapter.name,
                         {"zte-f6600p-thinklua", "zte-f670l-thinklua"})

    def test_probe_confirms_only_matching_xml_shape(self):
        client = ReadOnlyDevice()
        result = multimodel.probe(client, "F6201B",
                                  max_endpoints=1, start=0)
        self.assertTrue(result["read_only"])
        self.assertEqual(result["model"], "F6201B")
        # The first endpoint expects WIFI XML, but device XML must not
        # be falsely classified as Wi-Fi support.
        self.assertFalse(result["endpoints"]["wifi_clients"]["available"])
        self.assertFalse(result["supported"])
        self.assertTrue(all(call[0].startswith("GET") for call in client.calls))

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

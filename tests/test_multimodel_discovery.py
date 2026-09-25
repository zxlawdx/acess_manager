"""Perfis ZTE: evidência por endpoint sem assumir suporte de escrita."""

import unittest

from apps.zte_manager.services.multimodel_service import (
    MODEL_FAMILY,
    catalog,
    find_family,
    probe,
)


def xml(object_name="OBJ_ACCESSDEV_ID", name="LinkTime", value="123"):
    return (
        "<ajax_response_xml_root><IF_ERRORSTR>SUCC</IF_ERRORSTR>"
        f"<{object_name}><Instance><ParaName>{name}</ParaName>"
        f"<ParaValue>{value}</ParaValue></Instance></{object_name}>"
        "</ajax_response_xml_root>"
    )


class FakeClient:
    def __init__(self, response):
        self.response = response
        self.calls = []

    def get_view(self, view, **options):
        self.calls.append(("view", view, options))

    def get_menu(self, tag, **options):
        self.calls.append(("menu", tag, options))
        return self.response


class MultiModelDiscoveryTests(unittest.TestCase):
    def test_all_requested_models_are_in_catalog(self):
        names = {
            "F6640", "F6645P", "F680", "F6600P", "F8748",
            "H169A", "H2640", "H288A", "H388X", "H3600P",
            "H3640", "H6645P", "H6745", "E2631", "SR7410",
        }
        self.assertTrue(names.issubset(MODEL_FAMILY))
        self.assertEqual(len(catalog()["models"]), len(MODEL_FAMILY))

    def test_firmware_suffix_and_variant_map_correctly(self):
        self.assertEqual(find_family("ZTE H3640 V10"), ("H3640", "h288a"))
        self.assertEqual(find_family("H6645P V2"), ("H6645P", "h288a"))
        self.assertEqual(find_family("F6600P"), ("F6600P", "f6640"))
        self.assertEqual(find_family("ZTE BE7200 SR7410"), ("SR7410", "vue"))

    def test_h288a_returns_only_field_names(self):
        client = FakeClient(xml(value="private-customer-value"))
        result = probe(client, "H288A", max_endpoints=1)
        self.assertTrue(result["supported"])
        self.assertTrue(result["read_only"])
        shape = result["endpoints"]["wifi_clients"]["structure"]
        self.assertEqual(shape["OBJ_ACCESSDEV_ID"]["records"], 1)
        self.assertIn("LinkTime", shape["OBJ_ACCESSDEV_ID"]["fields"])
        self.assertNotIn("private-customer-value", str(result))
        self.assertEqual(client.calls[0][1], "localNetStatus")
        self.assertEqual(client.calls[1][1], "accessdev_ssiddev_lua.lua")

    def test_vue_uses_read_only_vue_data(self):
        class VueClient:
            base_url = "https://router.local"
            def __init__(self):
                self.calls = []
                self.session = self
            def get(self, url, params, timeout):
                self.calls.append(params)
                return self
            @property
            def text(self):
                return xml("OBJ_CLIENTS_ID")
            def raise_for_status(self):
                return None

        client = VueClient()
        result = probe(client, "SR7410", max_endpoints=1)
        self.assertTrue(result["supported"])
        self.assertEqual(client.calls[0]["_type"], "vueData")
        self.assertEqual(client.calls[1]["_tag"], "vue_client_data")
        self.assertEqual(result["read_only"], True)

    def test_unknown_does_not_guess_endpoints(self):
        client = FakeClient(xml())
        result = probe(client, "unknown device")
        self.assertFalse(result["supported"])
        self.assertEqual(client.calls, [])

    def test_invalid_html_not_accepted_as_endpoint(self):
        client = FakeClient("<html>Bem-vindo. Por favor entre.</html>")
        result = probe(client, "H288A", max_endpoints=1)
        self.assertFalse(result["supported"])
        self.assertFalse(result["endpoints"]["wifi_clients"]["available"])

    def test_missing_expected_object_rejected(self):
        client = FakeClient(xml("OBJ_UNRELATED"))
        result = probe(client, "H288A", max_endpoints=1)
        self.assertFalse(result["supported"])

    def test_sensitive_field_names_not_in_structural_report(self):
        client = FakeClient(
            xml(name="Password", value="private")
        )
        result = probe(client, "H288A", max_endpoints=1)
        fields = result["endpoints"]["wifi_clients"]["structure"][
            "OBJ_ACCESSDEV_ID"
        ]["fields"]
        self.assertEqual(fields, [])


if __name__ == "__main__":
    unittest.main()

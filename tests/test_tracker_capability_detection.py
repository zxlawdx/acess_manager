"""Regressões da descoberta automática e verificações contra HTTP 200 falso.

O endpoint listado por um projeto externo é *candidato*, não certificado.
Nenhum teste realiza requisições ou configura equipamentos reais.
"""
import unittest
from pathlib import Path

from apps.zte_manager.model.device_adapters import select_adapter
from apps.zte_manager.services.capability_service import CapabilityService
from apps.zte_manager.services.multimodel_service import (
    MODEL_FAMILY, FAMILY, catalog, find_family, probe,
)


ROOT = Path(__file__).resolve().parents[1]


class FakeONT:
    def __init__(self, xml):
        self.xml = xml
        self.calls = []
    def get_view(self, view, **kwargs):
        self.calls.append(("view", view))
    def get_menu(self, tag, **kwargs):
        self.calls.append(("menu", tag))
        return self.xml
    @staticmethod
    def _validar_resposta(xml):
        return xml
    @staticmethod
    def _parse_instances(xml):
        return {}


class TrackerCapabilityDetectionTests(unittest.TestCase):
    def test_probe_pagination_keeps_candidate_status(self):
        response = (
            "<ajax_response_xml_root><IF_ERRORSTR>SUCC</IF_ERRORSTR>"
            "<OBJ_ACCESSDEV_ID><Instance /></OBJ_ACCESSDEV_ID>"
            "</ajax_response_xml_root>"
        )
        result = probe(FakeONT(response), "H288A", max_endpoints=2, start=1)
        self.assertEqual(result["next_offset"], 3)
        self.assertEqual(result["total_candidates"], len(FAMILY["h288a"]))
        self.assertNotIn("wifi_clients", result["endpoints"])
        self.assertIn("wifi_clients", {
            item["feature"] for item in result["candidate_features"]
        })

    def test_full_tracker_inventory_including_sr7110(self):
        expected = {
            "F6640", "F6645P", "F680", "F6600P", "F8748",
            "H169A", "H2640", "H288A", "H388X", "H3600P",
            "H3640", "H6645P", "H6745", "E2631", "SR7410",
            "SR7110",
        }
        self.assertEqual(expected, set(MODEL_FAMILY))
        self.assertEqual(catalog()["tracker_models"], len(expected))
        self.assertEqual(find_family("ZTE SR7110"), ("SR7110", "vue"))

    def test_f8748_counter_and_f6600p_optics_do_not_leak_to_aliases(self):
        by_model = {m["model"]: m for m in catalog()["models"]}
        self.assertIn("wan_traffic_counters", by_model["F8748"]["firmware_differences"])
        self.assertIn("pon_optical", by_model["F6600P"]["candidate_features"])
        self.assertNotIn("pon_optical", by_model["F680"]["candidate_features"])
        self.assertIn("wifi_ssids", FAMILY["f6640"])

    def test_probe_reports_confirmed_not_all_family_candidates(self):
        xml = (
            "<ajax_response_xml_root><IF_ERRORSTR>SUCC</IF_ERRORSTR>"
            "<OBJ_WLAN_AD_ID><Instance><ParaName>HostName</ParaName>"
            "<ParaValue>do-not-disclose</ParaValue></Instance>"
            "</OBJ_WLAN_AD_ID></ajax_response_xml_root>"
        )
        result = probe(FakeONT(xml), "F6600P", max_endpoints=1)
        self.assertEqual(result["capabilities"][0]["status"], "detected")
        self.assertGreater(len(result["candidate_features"]), 0)
        self.assertNotIn("do-not-disclose", str(result))

    def test_http_ok_with_login_html_is_not_capability(self):
        fake = FakeONT("<html>Bem-vindo a F6600P. Por favor entre.</html>")
        service = CapabilityService(fake, select_adapter("F6600P"))
        result = service.probe(["dhcp_leases"])
        self.assertFalse(result["features"][0]["available"])

    def test_missing_expected_object_is_not_capability(self):
        fake = FakeONT(
            "<ajax_response_xml_root><IF_ERRORSTR>SUCC</IF_ERRORSTR>"
            "<OBJ_WRONG_ID><Instance /></OBJ_WRONG_ID>"
            "</ajax_response_xml_root>"
        )
        service = CapabilityService(fake, select_adapter("F6600P"))
        result = service.probe(["dhcp_leases"])
        self.assertFalse(result["features"][0]["available"])

    def test_automatic_ui_displays_tracker_and_preserves_full_probe(self):
        js = (ROOT / "apps/zte_manager/static/js/advanced.js").read_text("utf8")
        template = (ROOT / "apps/zte_manager/templates/index.html").read_text("utf8")
        self.assertIn("autoDiscoverTracker()", js)
        self.assertIn("max_endpoints: 2", js)
        self.assertIn("start: offset", js)
        self.assertIn("offset < total", js)
        self.assertIn("renderTrackerDiscovery(result)", js)
        self.assertIn('id="trackerCapabilityGrid"', template)
        self.assertIn('id="capabilityGrid"', template)


if __name__ == "__main__":
    unittest.main()

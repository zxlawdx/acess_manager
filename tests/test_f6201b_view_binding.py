"""Captured F6201B V9.3.10P7N7 menuView→menuData regression.

No live ONT, no captured subscriber values, no requests. The map of
tags/views/params and object names is reconstructed from the original
244-event capture supplied by the owner.
"""
import unittest
import xml.etree.ElementTree as ET

from apps.zte_manager.services import multimodel_service as profiles
from apps.zte_manager.services import model_diagnostic_service as diagnostics


# Expected real associations, not inferred from F6640.
VIEWS = {
    "wifi_ssids": ("wlanBasic", "wlan_wlansssidconf_lua.lua", "OBJ_WLANAP_ID"),
    "wifi_radios": ("wlanBasic", "wlan_wlanbasiconoff_lua.lua", "OBJ_WLANSETTING_ID"),
    "band_steering": ("wifibandsteer", "wlan_BandSteering_lua.lua", "OBJ_WLAN_BANDSTEERING_ID"),
    "wps": ("wps", "wlan_wps_lua.lua", "OBJ_WPS_ID"),
    "wifi_schedule": ("wlanBasic", "wlan_wlanbasiconoff_lua.lua", "OBJ_WLANTIMECFG_ID"),
    "device_info": ("statusMgr", "devmgr_statusmgr_lua.lua", "OBJ_DEVINFO_ID"),
    "pon_optical": ("ponopticalinfo", "optical_info_lua.lua", "OBJ_PON_OPTICALPARA_ID"),
    "lan_ports": ("localNetStatus", "status_lan_info_lua.lua", "OBJ_PON_PORT_BASIC_STATUS_ID"),
    "wifi_clients": ("homePage", "wlan_homepage_lua.lua", "OBJ_ACCESSDEV_ID"),
    "dhcp_leases": ("lanMgrIpv4", "Localnet_LanMgrIpv4_DHCPHostInfo_lua.lua", "OBJ_DHCPHOSTINFO_ID"),
    "dns": ("dns", "dns_localdns_lua.lua", "OBJ_DNS_ID"),
    "wan": ("ethWanStatus", "wan_internetstatus_lua.lua", "ID_WAN_COMFIG"),
}


def xml_response(root_tag, fields=None):
    root = ET.Element("ajax_response_xml_root")
    ET.SubElement(root, "IF_ERRORSTR").text = "SUCC"
    ET.SubElement(root, "IF_ERRORID").text = "0"
    obj = ET.SubElement(root, root_tag)
    instance = ET.SubElement(obj, "Instance")
    for name, value in (fields or {"Enable": "1", "RadioStatus": "1"}).items():
        ET.SubElement(instance, "ParaName").text = name
        ET.SubElement(instance, "ParaValue").text = value
    return ET.tostring(root, encoding="unicode")


class ContextRequiredRouter:
    """Simulates the observed dependency: direct menuData returns no OBJ."""

    def __init__(self):
        self.views = []
        self.calls = []
        self.current_view = None

    def get_view(self, view, **extras):
        self.views.append((view, extras))
        self.calls.append(("VIEW", view, extras))
        self.current_view = view
        return "menu prepared"

    def get_menu(self, tag, **params):
        self.calls.append(("DATA", tag, params))
        found = next(((view, expected_tag, obj) for view, expected_tag, obj
                      in VIEWS.values() if expected_tag == tag and
                      view == self.current_view), None)
        # wlan_wlanbasiconoff serves radio and schedule using same menuData.
        if not found:
            return xml_response("OBJ_UNRELATED")
        view, _, root = found
        # Both objects in the radio/schedule response were observed together.
        if tag == "wlan_wlanbasiconoff_lua.lua":
            text = xml_response("OBJ_WLANSETTING_ID", {
                "Band": "2.4G", "RadioStatus": "1"
            })
            root = ET.fromstring(text)
            timer = ET.SubElement(root, "OBJ_WLANTIMECFG_ID")
            instance = ET.SubElement(timer, "Instance")
            ET.SubElement(instance, "ParaName").text = "TimerEnable"
            ET.SubElement(instance, "ParaValue").text = "0"
            return ET.tostring(root, encoding="unicode")
        if tag == "wlan_homepage_lua.lua" and params.get("InstNum") != "5":
            return xml_response("OBJ_UNRELATED")
        if tag == "wlan_wlansssidconf_lua.lua":
            return xml_response("OBJ_WLANAP_ID", {"Enable": "1", "ESSID": "test"})
        return xml_response(root)


class CapturedViewBindingTests(unittest.TestCase):
    def test_exact_view_for_every_captured_route(self):
        family = profiles.FAMILY["f6201b_candidate"]
        for feature, (view, tag, root) in VIEWS.items():
            with self.subTest(feature=feature):
                endpoint = family[feature]
                self.assertEqual((endpoint.view, endpoint.tag, endpoint.root),
                                 (view, tag, root))

    def test_five_wifi_sections_load_with_context(self):
        zte = ContextRequiredRouter()
        for section in ("wifi_ssids", "wifi_radios", "band_steering",
                        "wps", "wifi_schedule"):
            with self.subTest(section=section):
                result = diagnostics.diagnostic(zte, "F6201B", section=section)
                self.assertIn(section, result["sections"])
                self.assertTrue(result["sections"][section]["available"],
                    result["sections"][section])
        self.assertEqual(len([x for x in zte.calls if x[0] == "VIEW"]), 5)
        self.assertEqual(len([x for x in zte.calls if x[0] == "DATA"]), 5)
        self.assertTrue(all(zte.calls[i][0] == "VIEW" and
                            zte.calls[i+1][0] == "DATA"
                            for i in range(0, len(zte.calls), 2)))

    def test_wan_optical_and_wifi_clients_use_captured_context(self):
        zte = ContextRequiredRouter()
        family = profiles.FAMILY["f6201b_candidate"]
        for feature in ("wan", "pon_optical", "wifi_clients"):
            with self.subTest(feature=feature):
                endpoint = family[feature]
                raw = profiles._fetch(zte, endpoint)
                self.assertIn(endpoint.root, profiles._shape(raw, endpoint.root))
        self.assertEqual(family["wifi_clients"].params, (("InstNum", "5"),))
        self.assertEqual(family["wan"].params, (("TypeUplink", "2"), ("pageType", "1")))

    def test_direct_get_is_not_evidence_of_compatibility(self):
        zte = ContextRequiredRouter()
        endpoint = profiles.FAMILY["f6201b_candidate"]["wifi_ssids"]
        direct = zte.get_menu(endpoint.tag)
        with self.assertRaises(RuntimeError):
            profiles._shape(direct, endpoint.root)
        self.assertIn("OBJ_WLANAP_ID", profiles._shape(
            profiles._fetch(zte, endpoint), endpoint.root))


if __name__ == "__main__":
    unittest.main()

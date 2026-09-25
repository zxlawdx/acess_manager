"""Second F6201B capture regression tests (schema only; NO secrets)."""
import os
import unittest
from unittest.mock import patch

from apps.zte_manager.model.zte_configuration import zte_wifi
from apps.zte_manager.services.f6201b_dns_writes import ExperimentalF6201BDNS
from apps.zte_manager.services.f6201b_writes import OPT_IN_ENV
from apps.zte_manager.services.f6201b_evidence import (
    SSID_APPLY_FIELDS, OBSERVED_APPLY_FIELDS, CAPTURED_GET_VIEWS,
    CAPTURED_GET_ROOTS, CAPTURE_STATISTICS,
)
from apps.zte_manager.services import f6201b_capture

XML_ENCODE = """<ajax_response_xml_root>
 <encode>MasterAuthServerSecret,BackupAuthServerSecret</encode>
 <OBJ_WLANAP_ID/>
 <encode>WEPKey</encode>
 <OBJ_WLANPSK_ID/>
 <encode>KeyPassphrase</encode>
</ajax_response_xml_root>"""

class Session:
    def __init__(self):
        self.post = self.deny
    @staticmethod
    def deny(*args, **kwargs):
        raise PermissionError("Read-only session")

class DNSTestRouter:
    def __init__(self):
        self.session=Session()
        self.session_tmp_token="synthetic token"
        self.public_key_pem="test"
        self.integrity_check=False
        self.writes_enabled=False
        self.state={
            "_InstID":"IGD", "SerIPAddress1":"1.1.1.1",
            "SerIPAddress2":"9.9.9.9", "SerIPv6Address1":"::",
            "SerIPv6Address2":"::",
        }
        self.events=[]
    def get_view(self, name, **kwargs):
        self.events.append(("view",name))
        return "form"
    def get_menu(self, name, **kwargs):
        self.events.append(("get",name))
        return "<ajax_response_xml_root><IF_ERRORID>0</IF_ERRORID></ajax_response_xml_root>"
    def _validar_resposta(self, raw):
        pass
    def _parse_instances(self, raw):
        return {"OBJ_DNS_ID":[dict(self.state)]}

class CaptureCompatibilityTests(unittest.TestCase):
    def test_exact_wifi_apply_field_order_and_secret_marker(self):
        self.assertEqual(SSID_APPLY_FIELDS[:3],
                         ("IF_ACTION","Enable","_InstID"))
        self.assertEqual(SSID_APPLY_FIELDS[-2:],
                         ("encode","_sessionTOKEN"))
        self.assertIn("Btn_apply_WLANSSIDConf",SSID_APPLY_FIELDS)
        self.assertIn("_InstID_GUEST",SSID_APPLY_FIELDS)
        self.assertEqual(len(SSID_APPLY_FIELDS),40)
        self.assertEqual(len(SSID_APPLY_FIELDS),
                         len(set(SSID_APPLY_FIELDS)))
        self.assertEqual(OBSERVED_APPLY_FIELDS[
            "wlan_wlansssidconf_lua.lua"],SSID_APPLY_FIELDS)
        self.assertEqual(CAPTURE_STATISTICS["total_http"],209)
        self.assertEqual(CAPTURE_STATISTICS["successful_apply_events"],28)
        self.assertEqual(len(OBSERVED_APPLY_FIELDS),25)
        self.assertEqual(CAPTURE_STATISTICS["successful_unique_apply_routes"],25)
        self.assertEqual(len(OBSERVED_APPLY_FIELDS["wan_internet_lua.lua"]),66)
        self.assertEqual(len(OBSERVED_APPLY_FIELDS["dns_localdns_lua.lua"]),9)

    def test_all_repeated_encode_blocks_are_detected(self):
        self.assertEqual(zte_wifi._get_encode_fields(XML_ENCODE),
             {"MasterAuthServerSecret", "BackupAuthServerSecret",
              "WEPKey", "KeyPassphrase"})

    def test_new_get_views_are_verified_by_capture(self):
        expected={
            "wan_internet_lua.lua":"ethWanConfig",
            "wan_internetstatus_lua.lua":"ethWanStatus",
            "wlan_wlansssidconf_lua.lua":"wlanBasic",
            "wlan_wlanbasicadconf_lua.lua":"wlanBasic",
            "firewall_dmz_lua.lua":"dmz",
            "upnp_portmap_lua.lua":"upnpportmapss"
        }
        for tag,view in expected.items():
            self.assertEqual(CAPTURED_GET_VIEWS[tag],view)
        self.assertEqual(CAPTURED_GET_ROOTS[
            "wan_internetstatus_lua.lua"],"ID_WAN_COMFIG")
        catalog=f6201b_capture.catalog()
        self.assertTrue(any(x["tag"]=="wan_internetstatus_lua.lua"
                            and x["inspectable"] for x in catalog["routes"]))

    def test_dns_opt_in_preview_only_read(self):
        dns=ExperimentalF6201BDNS()
        zte=DNSTestRouter()
        with patch.dict(os.environ,{OPT_IN_ENV:"1"}):
            proposal=dns.preview(zte,host="192.0.2.17",
                firmware="V9.3.10P7N7",
                changes={"ipv4_2":"8.8.8.8"})
        self.assertEqual(proposal["operation"],"dns_ipv4_ipv6")
        self.assertEqual(proposal["changes"]["SerIPAddress2"]["after"],"8.8.8.8")
        self.assertTrue(all(item[0] in ("view","get") for item in zte.events))
        self.assertFalse(zte.writes_enabled)

    def test_dns_replay_block_and_captured_write_order(self):
        dns=ExperimentalF6201BDNS()
        zte=DNSTestRouter()
        observed=[]
        original=zte.session.post
        def fake_post(zte_,tag,fields):
            self.assertEqual(tag,"dns_localdns_lua.lua")
            self.assertIs(zte.session.post,original)
            self.assertTrue(zte.writes_enabled)
            self.assertEqual(
                tuple(key for key,_ in fields)+("_sessionTOKEN",),
                OBSERVED_APPLY_FIELDS["dns_localdns_lua.lua"])
            observed.append(tag)
            zte.state["SerIPAddress2"]="8.8.8.8"
            return "<ajax_response_xml_root><IF_ERRORID>0</IF_ERRORID></ajax_response_xml_root>"
        with patch.dict(os.environ,{OPT_IN_ENV:"1"}),patch(
                "apps.zte_manager.services.f6201b_dns_writes.post_menu",
                side_effect=fake_post):
            proposal=dns.preview(zte,host="192.0.2.17",
                firmware="V9.3.10P7N7",
                changes={"ipv4_2":"8.8.8.8"})
            result=dns.apply(zte,host="192.0.2.17",
                firmware="V9.3.10P7N7", nonce=proposal["nonce"],
                confirmation="APLICAR DNS F6201B",
                original_post=original)
            self.assertTrue(result["verified"])
            self.assertEqual(observed,["dns_localdns_lua.lua"])
            self.assertIs(zte.session.post,original)
            self.assertFalse(zte.writes_enabled)
            with self.assertRaises(PermissionError):
                dns.apply(zte,host="192.0.2.17",
                    firmware="V9.3.10P7N7",nonce=proposal["nonce"],
                    confirmation="APLICAR DNS F6201B",
                    original_post=original)
            self.assertEqual(len(observed),1)

    def test_dns_invalid_input_cannot_send_post(self):
        dns=ExperimentalF6201BDNS()
        zte=DNSTestRouter()
        with patch.dict(os.environ,{OPT_IN_ENV:"1"}):
            for changes in [{"ipv4_1":"not-an-ip"},
                            {"ipv4_1":"127.0.0.1","password":"NO"},
                            {"ipv6_1":"not-an-ipv6"}]:
                with self.assertRaises(ValueError):
                    dns.preview(zte,host="192.0.2.17",
                        firmware="V9.3.10P7N7",changes=changes)
        self.assertEqual(zte.events,[])

if __name__=="__main__":
    unittest.main()

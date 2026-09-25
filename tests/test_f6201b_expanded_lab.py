"""Expanded F6201B lab options are opt-in and preserve live state."""
import os
import unittest
from unittest.mock import patch

from apps.zte_manager.services.f6201b_profile import (
    ExperimentalF6201BProfile, _domain_name_valid
)
from apps.zte_manager.services.f6201b_writes import (
    ExperimentalF6201BWrites, OPT_IN_ENV, EXACT_FIRMWARE
)
from apps.zte_manager.services.f6201b_dns_writes import ExperimentalF6201BDNS
from tests.test_f6201b_profile import FakeONT, FakeDNS


class FullProfileTests(unittest.TestCase):
    def setUp(self):
        self.engine=ExperimentalF6201BProfile()
        self.zte=FakeONT()
        self.dns=FakeDNS()
        self.domain={"_InstID":"IGD","DomainName":"old.example"}
        self.hosts=[{"id":"IGD.DNS.1","nome":"printer","ip":"192.0.2.10"}]
        self.kw=dict(host="192.0.2.31",revision="rev-1",
                     firmware=EXACT_FIRMWARE,dns_adapter=self.dns)
        self.profile={"wifi":{}, "dns":{
            "ipv4_1":"1.1.1.1","ipv4_2":"9.9.9.9",
            "domain_name":"lab.example",
            "hosts":[{"nome":"printer","ip":"192.0.2.20"},
                     {"nome":"laptop","ip":"192.0.2.30"}],
        }}

    def read_dns(self,zte):
        return dict(self.domain)
    def read_hosts(self,zte):
        return [dict(item) for item in self.hosts]

    def test_domain_input_validation(self):
        for invalid in ["host..example","-bad.example","bad_.example",
                        "bad/example","not á domain"]:
            self.assertFalse(_domain_name_valid(invalid),invalid)
        for valid in ["", "lab.example", "router.local"]:
            self.assertTrue(_domain_name_valid(valid),valid)

    def test_domain_and_hosts_are_diffed_without_writing(self):
        with patch.dict(os.environ,{OPT_IN_ENV:"1"}),patch(
            "apps.zte_manager.services.f6201b_dns_writes._read",
            side_effect=self.read_dns),patch(
            "apps.zte_manager.services.f6201b_profile._read_hosts",
            side_effect=self.read_hosts):
            proposal=self.engine.preview(self.zte,profile=self.profile,
                                         **self.kw)
        self.assertEqual(proposal["domain"],
                         {"before":"old.example","after":"lab.example"})
        self.assertEqual(len(proposal["hosts"]),2)
        self.assertEqual(proposal["hosts"][0]["before"],"192.0.2.10")
        self.assertIsNone(proposal["hosts"][1]["before"])
        self.assertEqual(self.dns.applied,0)
        self.assertFalse(self.zte.writes_enabled)

    def test_domain_and_hosts_use_captured_fields_and_readback(self):
        from apps.zte_manager.services.f6201b_evidence import (
            DNS_DOMAIN_APPLY_FIELDS, OBSERVED_APPLY_FIELDS
        )
        operations=[]
        def fake_post(zte,tag,fields):
            self.assertTrue(zte.writes_enabled)
            self.assertEqual(
                tuple(key for key,_ in fields)+("_sessionTOKEN",),
                DNS_DOMAIN_APPLY_FIELDS if tag=="dns_localdns_lua.lua"
                else OBSERVED_APPLY_FIELDS["dns_hostname_lua.lua"])
            form=dict(fields)
            if tag=="dns_localdns_lua.lua":
                self.domain["DomainName"]=form["DomainName"]
            else:
                name=form["HostName"]
                found=next((row for row in self.hosts
                            if row["nome"]==name),None)
                if found:
                    found["ip"]=form["IPAddress"]
                else:
                    self.hosts.append({"id":"IGD.DNS.2","nome":name,
                                       "ip":form["IPAddress"]})
            operations.append(tag)
            return "<ajax_response_xml_root><IF_ERRORID>0</IF_ERRORID></ajax_response_xml_root>"
        with patch.dict(os.environ,{OPT_IN_ENV:"1"}),patch(
            "apps.zte_manager.services.f6201b_dns_writes._read",
            side_effect=self.read_dns),patch(
            "apps.zte_manager.services.f6201b_profile._read_hosts",
            side_effect=self.read_hosts),patch(
            "apps.zte_manager.services.f6201b_profile.post_menu",
            side_effect=fake_post):
            proposal=self.engine.preview(self.zte,profile=self.profile,
                                         **self.kw)
            result=self.engine.apply(
                self.zte,nonce=proposal["nonce"],
                confirmation="APLICAR PERFIL F6201B",
                original_post=self.zte.session.blocked, **self.kw
            )
            self.assertTrue(result["success"],result)
            self.assertEqual(len(result["steps"]),3)
            with self.assertRaises(PermissionError):
                self.engine.apply(self.zte,nonce=proposal["nonce"],
                    confirmation="APLICAR PERFIL F6201B",
                    original_post=self.zte.session.blocked, **self.kw)
        self.assertEqual(operations,[
            "dns_localdns_lua.lua","dns_hostname_lua.lua","dns_hostname_lua.lua"
        ])
        self.assertFalse(self.zte.writes_enabled)

    def test_ipv6_dns_validates_full_address(self):
        dns=ExperimentalF6201BDNS()
        zte=FakeONT()
        # Preflight validates input BEFORE touching the simulated ONT.
        with patch.dict(os.environ,{OPT_IN_ENV:"1"}):
            with self.assertRaises(ValueError):
                dns.preview(zte,host="192.0.2.1",firmware=EXACT_FIRMWARE,
                    changes={"ipv6_1":"invalid:ipv6:z"})
        self.assertEqual(zte.views,[])

    def test_wifi_password_never_returned_in_diff(self):
        zte=FakeONT()
        writer=ExperimentalF6201BWrites()
        raw='<ajax_response_xml_root><IF_ERRORID>0</IF_ERRORID></ajax_response_xml_root>'
        ap={"_InstID":"DEV.WIFI.AP1","ESSID":"lab","Enable":"1",
            "ESSIDHideEnable":"0","VapIsolationEnable":"0",
            "MaxUserNum":"32", "BeaconType":"11i"}
        def inspect(_):
            return [ap],raw
        zte._parse_instances=lambda xml:{
            "OBJ_WLANPSK_ID":[{"_InstID":"DEV.WIFI.AP1.PSK1",
                                "KeyPassphrase":"encrypted-placeholder"}]
        }
        with patch.dict(os.environ,{OPT_IN_ENV:"1"}),patch.object(
            writer,"_inspect_session",side_effect=inspect),patch.object(
            writer,"_ensure_psk_preservable",return_value=None):
            report=writer.preview(zte,host="192.0.2.1",
                firmware=EXACT_FIRMWARE,ssid_id="DEV.WIFI.AP1",
                config={"password":"synthetic-secret9"})
        self.assertEqual(report["changes"]["password"],
                         {"before":"********","after":"********"})
        self.assertNotIn("synthetic-secret9",str(report))


if __name__=="__main__":
    unittest.main()

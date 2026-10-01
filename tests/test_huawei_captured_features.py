from __future__ import annotations

import unittest

from apps.zte_manager.infrastructure.huawei import HuaweiMutationTransport
from apps.zte_manager.services.huawei_captured_features import (
    DHCP_SERVER_PAGE,
    DNS_HOSTS_PAGE,
    DNS_PAGE,
    DMZ_PAGE,
    HuaweiCapturedFeatureService,
    WLAN_ADV_PAGE,
    WLAN_BASIC_PAGE,
    WAN_CACHE_PAGE,
    WAN_INFO_PAGE,
    parse_huawei_js_records,
)


TOKEN = "a" * 64


def constructor(name: str, params: list[str], values: list[str]) -> str:
    assignments = "\n".join(
        f"this.{item} = {item};"
        for item in params
    )
    encoded = ", ".join(
        '"' + str(value).replace('"', '\\"') + '"'
        for value in values
    )
    return (
        f"function {name}({','.join(params)}){{{assignments}}}\n"
        f"var value = new {name}({encoded});\n"
        f'<input id="hwonttoken" value="{TOKEN}">'
    )


class FakeHuaweiClient:
    def __init__(self):
        self.posts = []
        self.dhcp = {
            "Domain": "InternetGatewayDevice.LANDevice.1.LANHostConfigManagement",
            "DHCPEnable": "0",
            "DHCPServerEnable": "1",
            "X_HW_DHCPL2RelayEnable": "1",
            "X_HW_Option125Enable": "1",
            "X_HW_DNSList": "177.221.56.3,177.221.56.10",
            "MinAddress": "192.168.18.2",
            "MaxAddress": "192.168.18.254",
            "DHCPLeaseTime": "3600",
        }
        self.dns = {
            "Domain": "InternetGatewayDevice.X_HW_DNS.SearList.1",
            "DNSServer": "1.1.1.1",
            "DomainName": "cloudflare.com",
            "Interface": "wan1.1.ppp1",
        }
        self.dmz = {
            "Domain": (
                "InternetGatewayDevice.WANDevice.1.WANConnectionDevice.1."
                "WANPPPConnection.1.X_HW_DMZ"
            ),
            "DMZEnable": "0",
            "DMZHostIPAddress": "192.168.18.4",
        }

    def extract_token(self, html):
        return TOKEN

    def _page(self, record, name):
        params = list(record)
        values = [record[key] for key in params]
        return constructor(name, params, values)

    def get_page(self, path):
        if path.startswith(DHCP_SERVER_PAGE):
            return self._page(self.dhcp, "stDhcp")
        if path == "/html/bbsp/dhcp/dhcp.asp":
            return (
                constructor(
                    "stLan",
                    ["IPInterfaceIPAddress", "IPInterfaceSubnetMask"],
                    ["192.168.18.1", "255.255.255.0"],
                )
            )
        if path == "/html/bbsp/dhcpstatic/dhcpstatic.asp":
            return '<input id="hwonttoken" value="' + TOKEN + '">'
        if path == "/html/bbsp/common/dhcpinfo.asp":
            return '<input id="hwonttoken" value="' + TOKEN + '">'
        if path == DNS_PAGE:
            return self._page(self.dns, "stDns")
        if path == DNS_HOSTS_PAGE:
            return constructor(
                "stHost",
                ["Domain", "IPAddress", "DomainName"],
                [
                    "InternetGatewayDevice.X_HW_DNS.HOSTS.1",
                    "1.1.1.1",
                    "cloudflare.com",
                ],
            )
        if path == DMZ_PAGE:
            return self._page(self.dmz, "stDmz")
        if path.startswith(WLAN_BASIC_PAGE):
            instance = "5" if "5G" in path else "1"
            return constructor(
                "stWlan",
                [
                    "Domain", "Enable", "SSIDAdvertisementEnabled", "SSID",
                    "X_HW_AssociateNum", "BeaconType", "SsidInst",
                ],
                [
                    f"InternetGatewayDevice.LANDevice.1.WLANConfiguration.{instance}",
                    "1", "1", "Lab5" if instance == "5" else "Lab24",
                    "64", "WPA2/WPA3", instance,
                ],
            )
        if path.startswith(WLAN_ADV_PAGE):
            instance = "5" if "5G" in path else "1"
            return constructor(
                "stRadio",
                [
                    "Domain", "Channel", "AutoChannelEnable",
                    "RegulatoryDomain", "TransmitPower", "X_HW_HT20",
                    "X_HW_Standard", "BeaconPeriod",
                ],
                [
                    f"InternetGatewayDevice.LANDevice.1.WLANConfiguration.{instance}",
                    "0", "1", "BR", "100", "4" if instance == "5" else "0",
                    "11ax", "100",
                ],
            )
        if path == WAN_INFO_PAGE:
            return (
                "function WanPPP("
                "domain,Status,Name,IPAddress,Gateway,NATEnable,dnsstr,"
                "Username,Password,VlanId,ServiceList,MaxMRUSize,Uptime"
                "){"
                "this.domain=domain;this.Status=Status;this.Name=Name;"
                "this.IPAddress=IPAddress;this.Gateway=Gateway;"
                "this.NATEnable=NATEnable;this.Username=Username;"
                "this.Password=Password;this.VlanId=VlanId;"
                "this.ServiceList=ServiceList;this.Uptime=Uptime;"
                "}"
            )
        if path == WAN_CACHE_PAGE:
            return (
                "function(){var obj={};"
                "obj.IPWanList=new Array(null);"
                "obj.PPPWanList=new Array("
                'new WanPPP("InternetGatewayDevice.WANDevice.1.'
                'WANConnectionDevice.1.WANPPPConnection.1",'
                '"Connected","1_TR069_INTERNET_R_VID_2000",'
                '"100.64.0.2","100.64.0.1","1",'
                '"1.1.1.1,8.8.8.8","labuser","masked",'
                '"2000","TR069_INTERNET","1492","321"),null);'
                "return obj;}"
            )
        if path in {
            "/html/bbsp/firewalllevel/firewalllevel.asp",
            "/html/bbsp/Dos/Dos.asp",
            "/html/bbsp/ipv6firewall/firewall.asp",
            "/html/bbsp/internetcontrol/internetcontrol.asp",
            "/html/bbsp/alg/alg.asp",
            "/html/bbsp/igmp/igmp.asp",
        }:
            return '<input id="hwonttoken" value="' + TOKEN + '">'
        raise RuntimeError(path)

    def post_form(self, path, payload, *, referer):
        self.posts.append((path, dict(payload), referer))
        if "dhcpservercfg/set.cgi" in path:
            mapping = {
                "z.DHCPServerEnable": "DHCPServerEnable",
                "z.X_HW_DNSList": "X_HW_DNSList",
                "z.MinAddress": "MinAddress",
                "z.MaxAddress": "MaxAddress",
                "z.DHCPLeaseTime": "DHCPLeaseTime",
            }
            for source, target in mapping.items():
                if source in payload:
                    self.dhcp[target] = str(payload[source])
        elif "dnsconfiguration/set.cgi" in path:
            self.dns["DNSServer"] = str(payload["x.DNSServer"])
            self.dns["DomainName"] = str(payload["x.DomainName"])
            self.dns["Interface"] = str(payload["x.Interface"])
        elif "/dmz/set.cgi" in path:
            self.dmz["DMZEnable"] = str(payload["x.DMZEnable"])
            self.dmz["DMZHostIPAddress"] = str(payload["x.DMZHostIPAddress"])
        return HuaweiMutationTransport(http_status=200)


class HuaweiGenericParserTests(unittest.TestCase):
    def test_constructor_parser_maps_properties_and_decodes_hex(self):
        html = (
            "function stItem(domain,Name,IP){"
            "this.Domain=domain;this.Name=Name;this.IPAddress=IP;}"
            'var x = new stItem("InternetGatewayDevice.Test.1",'
            '"RE\\x5fTEST","192\\x2e168\\x2e18\\x2e1");'
        )
        records = parse_huawei_js_records(html)
        self.assertEqual(len(records), 1)
        self.assertEqual(records[0]["Name"], "RE_TEST")
        self.assertEqual(records[0]["IPAddress"], "192.168.18.1")
        self.assertEqual(
            records[0]["Domain"],
            "InternetGatewayDevice.Test.1",
        )


class HuaweiCapturedFeatureTests(unittest.TestCase):
    def make_service(self):
        return HuaweiCapturedFeatureService(
            FakeHuaweiClient(),
            model="EG8041X7-10",
            sleep=lambda _delay: None,
        )

    def test_dhcp_read_and_update_uses_captured_endpoint(self):
        service = self.make_service()
        before = service.dhcp_status()
        self.assertEqual(before["basic"]["MinAddress"], "192.168.18.2")
        self.assertEqual(before["basic"]["DNSServer1"], "177.221.56.3")

        result = service.set_dhcp_basic({
            "enabled": True,
            "min_address": "192.168.18.10",
            "max_address": "192.168.18.200",
            "dns1": "1.1.1.1",
            "dns2": "8.8.8.8",
            "lease_time": 7200,
        })
        self.assertTrue(result["verified"])
        self.assertEqual(len(service.client.posts), 1)
        path, payload, referer = service.client.posts[0]
        self.assertIn("/html/bbsp/dhcpservercfg/set.cgi", path)
        self.assertEqual(referer, DHCP_SERVER_PAGE)
        self.assertEqual(payload["z.MinAddress"], "192.168.18.10")
        self.assertEqual(payload["z.X_HW_DNSList"], "1.1.1.1,8.8.8.8")
        self.assertEqual(payload["x.X_HW_Token"], TOKEN)

    def test_dns_update_preserves_captured_interface(self):
        service = self.make_service()
        result = service.set_dns({
            "ipv4_1": "9.9.9.9",
            "domain_name": "example.test",
        })
        self.assertTrue(result["verified"])
        self.assertEqual(len(service.client.posts), 1)
        path, payload, _referer = service.client.posts[0]
        self.assertIn(
            "x=InternetGatewayDevice.X_HW_DNS.SearList.1",
            path,
        )
        self.assertEqual(payload["x.DNSServer"], "9.9.9.9")
        self.assertEqual(payload["x.Interface"], "wan1.1.ppp1")

    def test_dmz_update_uses_captured_domain_and_readback(self):
        service = self.make_service()
        result = service.set_dmz({
            "enabled": True,
            "internal_client": "192.168.18.50",
        })
        self.assertTrue(result["verified"])
        self.assertEqual(len(service.client.posts), 1)
        path, payload, _referer = service.client.posts[0]
        self.assertIn("WANPPPConnection.1.X_HW_DMZ", path)
        self.assertEqual(payload["x.DMZEnable"], "1")
        self.assertEqual(
            payload["x.DMZHostIPAddress"],
            "192.168.18.50",
        )

    def test_wan_cache_uses_constructor_definition_and_live_values(self):
        service = self.make_service()
        rows = service.wan_status()
        self.assertEqual(len(rows), 1)
        wan = rows[0]
        self.assertEqual(wan["status"], "Connected")
        self.assertEqual(wan["ip"], "100.64.0.2")
        self.assertEqual(wan["gateway"], "100.64.0.1")
        self.assertEqual(wan["dns1"], "1.1.1.1")
        self.assertEqual(wan["dns2"], "8.8.8.8")
        self.assertEqual(wan["vlan"], "2000")
        self.assertEqual(wan["services"], "TR069_INTERNET")

        pppoe = service.pppoe_status(reveal_password=False)
        self.assertEqual(len(pppoe), 1)
        self.assertEqual(pppoe[0]["username"], "labuser")
        self.assertEqual(pppoe[0]["password"], "")
        self.assertTrue(pppoe[0]["password_hidden"])

    def test_wifi_read_maps_both_bands(self):
        service = self.make_service()
        networks = service.wifi_networks()
        self.assertEqual(
            [item["ssid"] for item in networks],
            ["Lab24", "Lab5"],
        )
        radios = service.wifi_radios()
        self.assertEqual(
            [item["banda"] for item in radios],
            ["2.4GHz", "5GHz"],
        )
        self.assertTrue(all(item["canal_automatico"] for item in radios))

    def test_wifi_password_write_is_rejected_without_post(self):
        service = self.make_service()
        with self.assertRaises(ValueError):
            service.set_ssid_config(
                "InternetGatewayDevice.LANDevice.1.WLANConfiguration.1",
                {"password": "not-captured"},
            )
        self.assertEqual(service.client.posts, [])


if __name__ == "__main__":
    unittest.main()

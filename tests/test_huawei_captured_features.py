from __future__ import annotations

import unittest

from apps.zte_manager.infrastructure.huawei import HuaweiMutationTransport
from apps.zte_manager.services.huawei_captured_features import (
    DHCP_SERVER_PAGE,
    DNS_HOSTS_PAGE,
    DNS_PAGE,
    DMZ_PAGE,
    DEVICE_INFO_CUS_PAGE,
    DEVICE_INFO_PAGE,
    DHCP_INFO_PAGE,
    HuaweiCapturedFeatureService,
    LAN_USER_DHCP_PAGE,
    LAN_USER_DEV_PAGE,
    LAN_USER_INFO_PAGE,
    USER_DEVICE_PAGE,
    WLAN_ADV_PAGE,
    WLAN_ASSOC_PAGE,
    WLAN_BASIC_PAGE,
    WLAN_INFO_PAGE,
    WLAN_LIST_PAGE,
    WLAN_STA_BOOST_PAGE,
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
        self.read_posts = []
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
        if path == DEVICE_INFO_PAGE:
            return (
                '<table><tr><td>Software Version</td><td>V5R020</td></tr>'
                '<tr><td>Hardware Version</td><td>10D</td></tr>'
                '<tr><td>Serial Number</td><td>48575443TEST</td></tr></table>'
                'var ProductName="Huawei EG8041X7\\x2d10";'
                'var Manufacturer="Huawei";'
            )
        if path == DEVICE_INFO_CUS_PAGE:
            return ""
        if path in {
            USER_DEVICE_PAGE,
            LAN_USER_INFO_PAGE,
            LAN_USER_DEV_PAGE,
            LAN_USER_DHCP_PAGE,
            WLAN_INFO_PAGE,
            WLAN_LIST_PAGE,
            WLAN_ASSOC_PAGE,
            WLAN_STA_BOOST_PAGE,
        }:
            return ""
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

    def post_read(self, path, payload=None, *, referer="/index.asp"):
        self.read_posts.append((path, dict(payload or {}), referer))
        if path == LAN_USER_DEV_PAGE:
            return (
                "function stLanDev(MACAddress,IPAddress,HostName,Interface){"
                "this.MACAddress=MACAddress;this.IPAddress=IPAddress;"
                "this.HostName=HostName;this.Interface=Interface;}"
                'new stLanDev("02:11:22:33:44:55","192.168.18.20",'
                '"Notebook","LAN1");'
            )
        if path == LAN_USER_DHCP_PAGE:
            return (
                "function stDhcp(MACAddress,IPAddress,HostName){"
                "this.MACAddress=MACAddress;this.IPAddress=IPAddress;"
                "this.HostName=HostName;}"
                'new stDhcp("02:AA:BB:CC:DD:EE","192.168.18.30","Phone");'
            )
        if path == WLAN_ASSOC_PAGE:
            return (
                "function stAssoc(AssociatedDeviceMACAddress,IPAddress,"
                "HostName,SSID,SignalStrength,TxRate,RxRate){"
                "this.AssociatedDeviceMACAddress=AssociatedDeviceMACAddress;"
                "this.IPAddress=IPAddress;this.HostName=HostName;"
                "this.SSID=SSID;this.SignalStrength=SignalStrength;"
                "this.TxRate=TxRate;this.RxRate=RxRate;}"
                'new stAssoc("02:AA:BB:CC:DD:EE","192.168.18.30",'
                '"Phone","Lab5","-51","433","390");'
            )
        if path == WLAN_STA_BOOST_PAGE:
            return ""
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

    def test_device_status_reads_js_and_table_values(self):
        service = self.make_service()
        status = service.device_status()
        self.assertEqual(status["fabricante"], "Huawei")
        self.assertEqual(status["modelo"], "Huawei EG8041X7-10")
        self.assertEqual(status["firmware"], "V5R020")
        self.assertEqual(status["hardware"], "10D")
        self.assertEqual(status["serial"], "48575443TEST")

    def test_client_inventory_uses_captured_post_only_feeds(self):
        service = self.make_service()
        wifi = service.wifi_clients()
        self.assertEqual(len(wifi), 1)
        self.assertEqual(wifi[0]["mac"], "02:AA:BB:CC:DD:EE")
        self.assertEqual(wifi[0]["ssid"], "Lab5")
        self.assertEqual(wifi[0]["rssi"], "-51")

        lan = service.lan_clients()
        self.assertTrue(
            any(
                item["mac"] == "02:11:22:33:44:55"
                for item in lan
            )
        )
        post_paths = [item[0] for item in service.client.read_posts]
        self.assertIn(WLAN_ASSOC_PAGE, post_paths)
        self.assertIn(LAN_USER_DEV_PAGE, post_paths)
        self.assertIn(LAN_USER_DHCP_PAGE, post_paths)

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

    def test_wifi_password_write_uses_captured_pre_shared_key(self):
        service = self.make_service()
        result = service.set_ssid_config(
            "InternetGatewayDevice.LANDevice.1.WLANConfiguration.1",
            {"password": "MappedPassword123"},
        )

        self.assertTrue(result["success"])
        self.assertEqual(len(service.client.posts), 1)
        path, payload, referer = service.client.posts[0]
        self.assertIn("/html/amp/wlanbasic/set.cgi", path)
        self.assertIn(
            "k=InternetGatewayDevice.LANDevice.1."
            "WLANConfiguration.1.PreSharedKey.1",
            path,
        )
        self.assertEqual(payload["k.PreSharedKey"], "MappedPassword123")
        self.assertEqual(payload["x.X_HW_Token"], TOKEN)
        self.assertTrue(referer.startswith(WLAN_BASIC_PAGE))


if __name__ == "__main__":
    unittest.main()

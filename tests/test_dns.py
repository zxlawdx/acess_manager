import unittest

from apps.zte_manager.model.zte_configuration.zte_dns import (
    _parse_hosts,
    _validate_host,
)


class DnsTest(unittest.TestCase):
    def test_parse_hosts_filtra_entradas_dhcp(self):
        xml = """
        <ajax_response_xml_root>
            <IF_ERRORSTR>SUCC</IF_ERRORSTR>
            <ALLDNSHOST>
                <Instance>
                    <ParaName>_InstID</ParaName><ParaValue>1</ParaValue>
                    <ParaName>HostName</ParaName><ParaValue>cliente-dhcp</ParaValue>
                    <ParaName>IPAddress</ParaName><ParaValue>192.168.1.10</ParaValue>
                    <ParaName>LeaseTime</ParaName><ParaValue>3600</ParaValue>
                </Instance>
                <Instance>
                    <ParaName>_InstID</ParaName><ParaValue>2</ParaValue>
                    <ParaName>HostName</ParaName><ParaValue>cloudflare</ParaValue>
                    <ParaName>IPAddress</ParaName><ParaValue>1.1.1.1</ParaValue>
                </Instance>
            </ALLDNSHOST>
        </ajax_response_xml_root>
        """

        hosts = _parse_hosts(
            xml
        )

        self.assertEqual(
            hosts,
            [
                {
                    "id": "2",
                    "nome": "cloudflare",
                    "ip": "1.1.1.1",
                    "lease_time": None,
                }
            ]
        )

    def test_validate_host_aceita_ipv4_e_ipv6(self):
        _validate_host(
            "cloudflare",
            "1.1.1.1"
        )

        _validate_host(
            "dns-v6",
            "2606:4700:4700::1111"
        )

    def test_validate_host_rejeita_ip_invalido(self):
        with self.assertRaises(
            ValueError
        ):
            _validate_host(
                "dns",
                "999.999.999.999"
            )


if __name__ == "__main__":
    unittest.main()


class DnsHostPersistenceTest(unittest.TestCase):
    def test_wait_host_applied_aguarda_segunda_entrada(self):
        from unittest.mock import patch
        from apps.zte_manager.model.zte_configuration import zte_dns

        missing = """
        <ajax_response_xml_root>
            <IF_ERRORSTR>SUCC</IF_ERRORSTR>
            <ALLDNSHOST></ALLDNSHOST>
        </ajax_response_xml_root>
        """
        present = """
        <ajax_response_xml_root>
            <IF_ERRORSTR>SUCC</IF_ERRORSTR>
            <ALLDNSHOST>
                <Instance>
                    <ParaName>_InstID</ParaName><ParaValue>7</ParaValue>
                    <ParaName>HostName</ParaName><ParaValue>google</ParaValue>
                    <ParaName>IPAddress</ParaName><ParaValue>8.8.8.8</ParaValue>
                </Instance>
            </ALLDNSHOST>
        </ajax_response_xml_root>
        """

        class Fake:
            @staticmethod
            def _validar_resposta(xml):
                return xml

        with patch.object(
            zte_dns,
            "dns_hosts_raw",
            side_effect=[missing, present],
        ), patch.object(
            zte_dns.time,
            "sleep",
            return_value=None,
        ):
            result = zte_dns._wait_host_applied(
                Fake(),
                "google",
                "8.8.8.8",
                tentativas=2,
                intervalo=0,
            )

        self.assertEqual(result["nome"], "google")
        self.assertEqual(result["ip"], "8.8.8.8")


class DnsServerPersistenceTest(unittest.TestCase):
    def test_wait_dns_servers_confirma_segundo_dns(self):
        from unittest.mock import patch
        from apps.zte_manager.model.zte_configuration import zte_dns

        incomplete = """
        <ajax_response_xml_root>
            <IF_ERRORSTR>SUCC</IF_ERRORSTR>
            <OBJ_DNS_ID><Instance>
                <ParaName>SerIPAddress1</ParaName><ParaValue>1.1.1.1</ParaValue>
                <ParaName>SerIPAddress2</ParaName><ParaValue></ParaValue>
                <ParaName>SerIPv6Address1</ParaName><ParaValue>::</ParaValue>
                <ParaName>SerIPv6Address2</ParaName><ParaValue>::</ParaValue>
            </Instance></OBJ_DNS_ID>
        </ajax_response_xml_root>
        """

        complete = """
        <ajax_response_xml_root>
            <IF_ERRORSTR>SUCC</IF_ERRORSTR>
            <OBJ_DNS_ID><Instance>
                <ParaName>SerIPAddress1</ParaName><ParaValue>1.1.1.1</ParaValue>
                <ParaName>SerIPAddress2</ParaName><ParaValue>8.8.8.8</ParaValue>
                <ParaName>SerIPv6Address1</ParaName><ParaValue>::</ParaValue>
                <ParaName>SerIPv6Address2</ParaName><ParaValue>::</ParaValue>
            </Instance></OBJ_DNS_ID>
        </ajax_response_xml_root>
        """

        class Fake:
            @staticmethod
            def _validar_resposta(xml):
                return xml

            @staticmethod
            def _parse_instances(xml):
                from apps.zte_manager.model.zte import ZTE
                return ZTE._parse_instances(xml)

        with patch.object(
            zte_dns,
            "dns_status_raw",
            side_effect=[incomplete, complete],
        ), patch.object(
            zte_dns.time,
            "sleep",
            return_value=None,
        ):
            result = zte_dns._wait_dns_servers_applied(
                Fake(),
                {
                    "ipv4_1": "1.1.1.1",
                    "ipv4_2": "8.8.8.8",
                    "ipv6_1": "::",
                    "ipv6_2": "::",
                },
                tentativas=2,
                intervalo=0,
            )

        self.assertTrue(result)

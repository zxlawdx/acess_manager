import unittest
from unittest.mock import patch

from apps.zte_manager.model.zte import ZTE
from apps.zte_manager.model.zte_configuration import zte_wifi


WIFI_XML = """<?xml version="1.0"?>
<ajax_response_xml_root>
    <IF_ERRORSTR>SUCC</IF_ERRORSTR>
    <OBJ_WLANAP_ID>
        <Instance>
            <ParaName>_InstID</ParaName><ParaValue>DEV.WIFI.AP1</ParaValue>
            <ParaName>Enable</ParaName><ParaValue>1</ParaValue>
            <ParaName>Alias</ParaName><ParaValue>SSID1</ParaValue>
            <ParaName>ESSID</ParaName><ParaValue>Casa 2G</ParaValue>
            <ParaName>WLANViewName</ParaName><ParaValue>DEV.WIFI.RD1</ParaValue>
            <ParaName>ESSIDHideEnable</ParaName><ParaValue>0</ParaValue>
            <ParaName>BeaconType</ParaName><ParaValue>11i</ParaValue>
            <ParaName>11iAuthMode</ParaName><ParaValue>PSKAuthentication</ParaValue>
            <ParaName>11iEncryptType</ParaName><ParaValue>AESEncryption</ParaValue>
            <ParaName>VapIsolationEnable</ParaName><ParaValue>0</ParaValue>
            <ParaName>MaxUserNum</ParaName><ParaValue>32</ParaValue>
        </Instance>
    </OBJ_WLANAP_ID>
    <OBJ_WLANPSK_ID>
        <Instance>
            <ParaName>_InstID</ParaName><ParaValue>DEV.WIFI.AP1.PSK1</ParaValue>
            <ParaName>KeyPassphrase</ParaName><ParaValue>senha1234</ParaValue>
        </Instance>
    </OBJ_WLANPSK_ID>
</ajax_response_xml_root>
"""


class FakeZte:
    _parse_instances = staticmethod(
        ZTE._parse_instances
    )
    _validar_resposta = staticmethod(
        ZTE._validar_resposta
    )

    session_tmp_token = "1234567890123456"
    public_key_pem = "fake"

    def get_view(self, tag, **extras):
        return "<html></html>"

    def get_menu(self, tag, **extras):
        return WIFI_XML


class WifiSSIDTest(unittest.TestCase):
    def test_networks_traz_nome_banda_e_estado(self):
        redes = zte_wifi.wifi_networks(
            FakeZte()
        )

        self.assertEqual(
            redes[0]["ssid"],
            "Casa 2G"
        )
        self.assertEqual(
            redes[0]["banda"],
            "2.4GHz"
        )
        self.assertTrue(
            redes[0]["ativo"]
        )
        self.assertEqual(
            redes[0]["seguranca"],
            "WPA2-PSK-AES"
        )

    def test_set_ssid_preserva_payload_e_permite_desativar(self):
        capturado = {}

        def fake_post_menu(zte, tag, campos, **extras):
            capturado["tag"] = tag
            capturado["campos"] = dict(campos)
            return (
                "<ajax_response_xml_root>"
                "<IF_ERRORSTR>SUCC</IF_ERRORSTR>"
                "</ajax_response_xml_root>"
            )

        with patch.object(
            zte_wifi,
            "post_menu",
            fake_post_menu
        ), patch.object(
            zte_wifi,
            "_verify_ssid",
            return_value=True
        ), patch.object(
            zte_wifi.zte_security,
            "rsa_encrypt_text",
            return_value="encoded-key"
        ):
            zte_wifi.set_ssid_config(
                FakeZte(),
                "DEV.WIFI.AP1",
                {
                    "enabled": False,
                    "ssid": "Casa Nova",
                    "password": "novasenha123",
                }
            )

        self.assertEqual(
            capturado["tag"],
            "wlan_wlansssidconf_lua.lua"
        )
        self.assertEqual(
            capturado["campos"]["Enable"],
            "0"
        )
        self.assertEqual(
            capturado["campos"]["ESSID"],
            "Casa Nova"
        )
        self.assertEqual(
            capturado["campos"]["_PSKCONIG"],
            "Y"
        )
        self.assertIn(
            "encode",
            capturado["campos"]
        )


if __name__ == "__main__":
    unittest.main()

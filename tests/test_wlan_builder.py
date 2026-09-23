import unittest
from unittest.mock import patch

from apps.zte_manager.model.zte import ZTE
from apps.zte_manager.model.zte_configuration import zte_wlan_channel_configuration as wlan


WLAN_XML = """<?xml version="1.0"?>
<ajax_response_xml_root>
    <IF_ERRORSTR>SUCC</IF_ERRORSTR>
    <IF_ERRORPARAM>SUCC</IF_ERRORPARAM>
    <IF_ERRORTYPE>SUCC</IF_ERRORTYPE>
    <OBJ_WLANSETTING_ID>
        <Instance>
            <ParaName>_InstID</ParaName><ParaValue>DEV.WIFI.RD1</ParaValue>
            <ParaName>Band</ParaName><ParaValue>2.4GHz</ParaValue>
            <ParaName>Standard</ParaName><ParaValue>b,g,n</ParaValue>
            <ParaName>Channel</ParaName><ParaValue>6</ParaValue>
            <ParaName>AutoChannelEnabled</ParaName><ParaValue>0</ParaValue>
            <ParaName>BandWidth</ParaName><ParaValue>20MHz</ParaValue>
            <ParaName>CountryCode</ParaName><ParaValue>BRI</ParaValue>
            <ParaName>BasicDataRates</ParaName><ParaValue>1,2,5.5,11</ParaValue>
            <ParaName>OpDataRates</ParaName><ParaValue>1,2,5.5,11,6,9,12,18,24,36,48,54</ParaValue>
            <ParaName>11nMode</ParaName><ParaValue>1</ParaValue>
            <ParaName>GreenField</ParaName><ParaValue>0</ParaValue>
            <ParaName>SGIEnabled</ParaName><ParaValue>0</ParaValue>
            <ParaName>BeaconInterval</ParaName><ParaValue>100</ParaValue>
            <ParaName>TxPower</ParaName><ParaValue>100%</ParaValue>
            <ParaName>QosType</ParaName><ParaValue>WMM</ParaValue>
            <ParaName>WorkMode</ParaName><ParaValue>1</ParaValue>
            <ParaName>RtsCts</ParaName><ParaValue>2347</ParaValue>
            <ParaName>DTIM</ParaName><ParaValue>1</ParaValue>
        </Instance>
    </OBJ_WLANSETTING_ID>
    <OBJ_CHANNEL_ID>
        <Instance>
            <ParaName>_InstID</ParaName><ParaValue>16</ParaValue>
            <ParaName>CountryCode</ParaName><ParaValue>BRI</ParaValue>
            <ParaName>Band</ParaName><ParaValue>2.4GHz</ParaValue>
            <ParaName>BandWidth</ParaName><ParaValue>20MHz</ParaValue>
            <ParaName>ChannelList</ParaName><ParaValue>1,2,3,4,5,6,7,8,9,10,11,12,13</ParaValue>
        </Instance>
    </OBJ_CHANNEL_ID>
</ajax_response_xml_root>
"""


class FakeZte:
    _parse_instances = staticmethod(
        ZTE._parse_instances
    )

    _validar_resposta = staticmethod(
        ZTE._validar_resposta
    )

    def get_view(self, tag, **extras):
        self.last_view = (
            tag,
            extras
        )

        return "<html></html>"

    def get_menu(self, tag, **extras):
        self.last_menu = (
            tag,
            extras
        )

        return WLAN_XML


class WlanBuilderTest(unittest.TestCase):
    def test_auto_channel_reproduz_regra_do_js(self):
        zte = FakeZte()
        capturado = {}

        def fake_post_menu(
            zte,
            tag,
            campos,
            **extras
        ):
            capturado["tag"] = tag
            capturado["campos"] = dict(
                campos
            )

            return (
                "<ajax_response_xml_root>"
                "<IF_ERRORSTR>SUCC</IF_ERRORSTR>"
                "</ajax_response_xml_root>"
            )

        with patch.object(
            wlan,
            "post_menu",
            fake_post_menu
        ):
            wlan.set_radio_config(
                zte,
                "2.4GHz",
                {
                    "auto_channel": True,
                    "standard": "b,g,n",
                    "country": "BRI",
                    "bandwidth": "20MHz",
                    "sgi": False,
                    "beacon_interval": 100,
                    "tx_power": "100%",
                }
            )

        campos = capturado[
            "campos"
        ]

        self.assertEqual(
            capturado["tag"],
            "wlan_wlanbasicadconf_lua.lua"
        )

        self.assertEqual(
            campos["AutoChannelEnabled"],
            "1"
        )

        self.assertEqual(
            campos["Channel"],
            "NULL"
        )

        self.assertEqual(
            campos["QosType"],
            "WMM"
        )

        self.assertIn(
            "Btn_apply_WlanBasicAdConf",
            campos
        )

    def test_rejeita_canal_fora_da_tabela_do_firmware(self):
        zte = FakeZte()

        with self.assertRaises(
            ValueError
        ):
            wlan.set_radio_config(
                zte,
                "2.4GHz",
                {
                    "auto_channel": False,
                    "channel": 149,
                    "country": "BRI",
                    "bandwidth": "20MHz",
                }
            )


if __name__ == "__main__":
    unittest.main()

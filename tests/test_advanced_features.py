import unittest
from unittest.mock import patch

from apps.zte_manager.model.zte_configuration import zte_advanced


class FakeZTE:
    def __init__(self, xml):
        self.xml = xml
        self.views = []
        self.menus = []

    def get_view(self, tag, **extras):
        self.views.append((tag, extras))
        return "<html></html>"

    def get_menu(self, tag, **extras):
        self.menus.append((tag, extras))
        return self.xml

    def _validar_resposta(self, xml):
        return xml

    @staticmethod
    def _parse_instances(xml):
        from apps.zte_manager.model.zte import ZTE
        return ZTE._parse_instances(xml)


class AdvancedFeaturesTest(unittest.TestCase):
    def test_radio_power_status(self):
        xml = """
        <ajax_response_xml_root>
            <IF_ERRORSTR>SUCC</IF_ERRORSTR>
            <OBJ_WLANTIMECFG_ID><Instance>
                <ParaName>_InstID</ParaName><ParaValue>IGD</ParaValue>
                <ParaName>TimerEnable</ParaName><ParaValue>0</ParaValue>
            </Instance></OBJ_WLANTIMECFG_ID>
            <OBJ_WLANTIME_ID><Instance>
                <ParaName>TimeStartHour</ParaName><ParaValue>1</ParaValue>
                <ParaName>TimeStartMin</ParaName><ParaValue>2</ParaValue>
                <ParaName>TimeEndHour</ParaName><ParaValue>3</ParaValue>
                <ParaName>TimeEndMin</ParaName><ParaValue>4</ParaValue>
            </Instance></OBJ_WLANTIME_ID>
            <OBJ_WLANSETTING_ID>
                <Instance>
                    <ParaName>_InstID</ParaName><ParaValue>DEV.WIFI.RD1</ParaValue>
                    <ParaName>Band</ParaName><ParaValue>2.4GHz</ParaValue>
                    <ParaName>RadioStatus</ParaName><ParaValue>1</ParaValue>
                </Instance>
                <Instance>
                    <ParaName>_InstID</ParaName><ParaValue>DEV.WIFI.RD2</ParaValue>
                    <ParaName>Band</ParaName><ParaValue>5GHz</ParaValue>
                    <ParaName>RadioStatus</ParaName><ParaValue>0</ParaValue>
                </Instance>
            </OBJ_WLANSETTING_ID>
        </ajax_response_xml_root>
        """

        result = zte_advanced.radio_power_status(FakeZTE(xml))

        self.assertFalse(result["timer_enabled"])
        self.assertTrue(result["radios"][0]["enabled"])
        self.assertFalse(result["radios"][1]["enabled"])

    def test_set_radio_power_preserva_outro_radio(self):
        before = {
            "timer_enabled": False,
            "timer_id": "IGD",
            "schedule": {
                "start_hour": "0",
                "start_minute": "0",
                "end_hour": "0",
                "end_minute": "0",
            },
            "radios": [
                {"id": "DEV.WIFI.RD1", "band": "2.4GHz", "enabled": True},
                {"id": "DEV.WIFI.RD2", "band": "5GHz", "enabled": True},
            ],
        }
        after = {
            **before,
            "radios": [
                {"id": "DEV.WIFI.RD1", "band": "2.4GHz", "enabled": False},
                {"id": "DEV.WIFI.RD2", "band": "5GHz", "enabled": True},
            ],
        }

        fake = FakeZTE("<ajax_response_xml_root><IF_ERRORSTR>SUCC</IF_ERRORSTR></ajax_response_xml_root>")

        with patch.object(
            zte_advanced,
            "radio_power_status",
            side_effect=[before, after],
        ), patch.object(
            zte_advanced,
            "post_menu",
            return_value="<ajax_response_xml_root><IF_ERRORSTR>SUCC</IF_ERRORSTR></ajax_response_xml_root>",
        ) as post:
            result = zte_advanced.set_radio_power(
                fake,
                "2.4GHz",
                False,
            )

        fields = dict(post.call_args.args[2])
        self.assertEqual(fields["RadioStatus_0"], "0")
        self.assertEqual(fields["RadioStatus_1"], "1")
        self.assertTrue(result["success"])

    def test_wps_status_paira_bandas(self):
        xml = """
        <ajax_response_xml_root>
            <IF_ERRORSTR>SUCC</IF_ERRORSTR>
            <OBJ_WPS_ID>
                <Instance>
                    <ParaName>_InstID</ParaName><ParaValue>DEV.WIFI.AP1</ParaValue>
                    <ParaName>Enable</ParaName><ParaValue>0</ParaValue>
                    <ParaName>WPSMode</ParaName><ParaValue>0</ParaValue>
                </Instance>
                <Instance>
                    <ParaName>_InstID</ParaName><ParaValue>DEV.WIFI.AP5</ParaValue>
                    <ParaName>Enable</ParaName><ParaValue>1</ParaValue>
                    <ParaName>WPSMode</ParaName><ParaValue>0</ParaValue>
                </Instance>
            </OBJ_WPS_ID>
            <OBJ_WLANSETTING_ID>
                <Instance>
                    <ParaName>_InstID</ParaName><ParaValue>DEV.WIFI.RD1</ParaValue>
                    <ParaName>Band</ParaName><ParaValue>2.4GHz</ParaValue>
                    <ParaName>RadioStatus</ParaName><ParaValue>1</ParaValue>
                </Instance>
                <Instance>
                    <ParaName>_InstID</ParaName><ParaValue>DEV.WIFI.RD2</ParaValue>
                    <ParaName>Band</ParaName><ParaValue>5GHz</ParaValue>
                    <ParaName>RadioStatus</ParaName><ParaValue>1</ParaValue>
                </Instance>
            </OBJ_WLANSETTING_ID>
        </ajax_response_xml_root>
        """

        result = zte_advanced.wps_status(FakeZTE(xml))

        self.assertEqual(result[0]["band"], "2.4GHz")
        self.assertEqual(result[0]["mode"], "Disabled")
        self.assertEqual(result[1]["band"], "5GHz")
        self.assertEqual(result[1]["mode"], "PBC")

    def test_upnp_status(self):
        xml = """
        <ajax_response_xml_root>
            <IF_ERRORSTR>SUCC</IF_ERRORSTR>
            <OBJ_UPNPCONFIG_ID><Instance>
                <ParaName>_InstID</ParaName><ParaValue>IGD</ParaValue>
                <ParaName>EnableUPnPIGD</ParaName><ParaValue>1</ParaValue>
                <ParaName>WanName</ParaName><ParaValue>DEV.WAN1</ParaValue>
                <ParaName>Wanv6Name</ParaName><ParaValue>DEV.WAN1</ParaValue>
                <ParaName>ADPeriod</ParaName><ParaValue>30</ParaValue>
                <ParaName>TTL</ParaName><ParaValue>4</ParaValue>
            </Instance></OBJ_UPNPCONFIG_ID>
        </ajax_response_xml_root>
        """

        result = zte_advanced.upnp_status(FakeZTE(xml))

        self.assertTrue(result["available"])
        self.assertTrue(result["enabled"])
        self.assertEqual(result["advertisement_period"], 30)
        self.assertEqual(result["ttl"], 4)


if __name__ == "__main__":
    unittest.main()


class BandSteeringTest(unittest.TestCase):
    def test_band_steering_status(self):
        xml = """
        <ajax_response_xml_root>
            <IF_ERRORSTR>SUCC</IF_ERRORSTR>
            <OBJ_BANDSTEER_ENABLE_ID><Instance>
                <ParaName>_InstID</ParaName><ParaValue>IGD</ParaValue>
                <ParaName>EnBandSteer</ParaName><ParaValue>1</ParaValue>
            </Instance></OBJ_BANDSTEER_ENABLE_ID>
            <OBJ_MGTS_BANDSTEER_ID><Instance>
                <ParaName>BsRssiLmt24G</ParaName><ParaValue>-72</ParaValue>
                <ParaName>BsRssiLmt5G</ParaName><ParaValue>-75</ParaValue>
                <ParaName>BsBwUtil24G</ParaName><ParaValue>60</ParaValue>
                <ParaName>BsBwUtil5G</ParaName><ParaValue>70</ParaValue>
            </Instance></OBJ_MGTS_BANDSTEER_ID>
        </ajax_response_xml_root>
        """

        result = zte_advanced.band_steering_status(
            FakeZTE(xml)
        )

        self.assertTrue(result["available"])
        self.assertTrue(result["enabled"])
        self.assertEqual(
            result["parameters"]["rssi_limit_24g"],
            -72
        )

    def test_set_band_steering_usa_set_enables(self):
        fake = FakeZTE(
            "<ajax_response_xml_root><IF_ERRORSTR>SUCC</IF_ERRORSTR></ajax_response_xml_root>"
        )

        before = {
            "available": True,
            "id": "IGD",
            "enabled": False,
            "parameters": {},
        }

        after = {
            **before,
            "enabled": True,
        }

        with patch.object(
            zte_advanced,
            "band_steering_status",
            side_effect=[before, after],
        ), patch.object(
            zte_advanced,
            "post_menu",
            return_value="<ajax_response_xml_root><IF_ERRORSTR>SUCC</IF_ERRORSTR></ajax_response_xml_root>",
        ) as post:
            result = zte_advanced.set_band_steering(
                fake,
                True
            )

        fields = dict(
            post.call_args.args[2]
        )

        self.assertEqual(
            fields["IF_ACTION"],
            "SET_ENABLES"
        )
        self.assertEqual(
            fields["EnBandSteer"],
            "1"
        )
        self.assertTrue(
            result["success"]
        )

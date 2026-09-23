import unittest

from apps.zte_manager.model.zte import ZTE
from apps.zte_manager.model.zte_configuration import zte_device_management


OPTICAL_XML = """<ajax_response_xml_root>
<IF_ERRORSTR>SUCC</IF_ERRORSTR>
<OBJ_PON_OPTICALPARA_ID><Instance>
<ParaName>RxPower</ParaName><ParaValue>-19.4</ParaValue>
<ParaName>TxPower</ParaName><ParaValue>2.8</ParaValue>
<ParaName>Temp</ParaName><ParaValue>44.2</ParaValue>
</Instance></OBJ_PON_OPTICALPARA_ID>
<OBJ_GPONREGSTATUS_ID><Instance>
<ParaName>RegStatus</ParaName><ParaValue>O5</ParaValue>
</Instance></OBJ_GPONREGSTATUS_ID>
</ajax_response_xml_root>"""


class FakeZte:
    _parse_instances = staticmethod(ZTE._parse_instances)
    _validar_resposta = staticmethod(ZTE._validar_resposta)

    def get_view(self, tag, **extras):
        return "<html></html>"

    def get_menu(self, tag, **extras):
        return OPTICAL_XML


class DeviceManagementTest(unittest.TestCase):
    def test_parse_optical(self):
        data = zte_device_management.optical_status(
            FakeZte()
        )

        self.assertEqual(
            data["rx_power_dbm"],
            -19.4
        )
        self.assertEqual(
            data["registration_status"],
            "O5"
        )


if __name__ == "__main__":
    unittest.main()

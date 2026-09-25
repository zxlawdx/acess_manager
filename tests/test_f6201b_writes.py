"""No-router safety regression tests for guarded F6201B write workflow."""
import os
import unittest
from unittest.mock import patch

from apps.zte_manager.services.f6201b_writes import (
    ExperimentalF6201BWrites as Writer, EXACT_FIRMWARE, OPT_IN_ENV,
)


XML = """
<ajax_response_xml_root>
  <IF_ERRORID>0</IF_ERRORID><IF_ERRORSTR>SUCC</IF_ERRORSTR>
  <OBJ_WLANAP_ID><Instance>
    <ParaName>_InstID</ParaName><ParaValue>DEV.WIFI.AP1</ParaValue>
    <ParaName>ESSID</ParaName><ParaValue>LAB_WIFI</ParaValue>
    <ParaName>Enable</ParaName><ParaValue>1</ParaValue>
    <ParaName>ESSIDHideEnable</ParaName><ParaValue>0</ParaValue>
    <ParaName>BeaconType</ParaName><ParaValue>None</ParaValue>
  </Instance></OBJ_WLANAP_ID>
  <OBJ_WLANPSK_ID><Instance><ParaName>_InstID</ParaName>
    <ParaValue>DEV.WIFI.AP1.PSK1</ParaValue>
    <ParaName>KeyPassphrase</ParaName><ParaValue>masked-ciphertext</ParaValue>
  </Instance></OBJ_WLANPSK_ID>
</ajax_response_xml_root>
"""


def denied_post(*args, **kwargs):
    raise PermissionError("Globally blocked")


class Session:
    post = staticmethod(denied_post)


class Router:
    def __init__(self, *, menu_valid=True):
        self.session = Session()
        self.writes_enabled = False
        self.session_tmp_token = "fake temporary token"
        self.public_key_pem = "test key"
        self.integrity_check = True
        self.menu_valid = menu_valid
        self.calls = []

    def get_view(self, tag, **kwargs):
        self.calls.append(("GET_VIEW", tag))
        return ("wlan_wlansssidconf_lua.lua" if self.menu_valid
                else "<html>Different firmware</html>")

    def get_menu(self, tag, **kwargs):
        self.calls.append(("GET_MENU", tag))
        return XML

    @staticmethod
    def _parse_instances(raw):
        return {
            "OBJ_WLANAP_ID": [{
                "_InstID": "DEV.WIFI.AP1", "ESSID": "LAB_WIFI",
                "Enable": "1", "ESSIDHideEnable": "0", "BeaconType": "None",
            }],
            "OBJ_WLANPSK_ID": [{"_InstID": "DEV.WIFI.AP1.PSK1",
                                "KeyPassphrase": "masked-ciphertext"}],
        }


class F6201BWriteTests(unittest.TestCase):
    def setUp(self):
        self.writer = Writer()
        self.zte = Router()

    def preview(self, changes=None):
        return self.writer.preview(
            self.zte, host="192.0.2.1", firmware=EXACT_FIRMWARE,
            ssid_id="DEV.WIFI.AP1", config=changes or {"ssid": "LAB_WIFI_2"},
        )

    def test_internal_env_toggle_does_not_block_authenticated_device(self):
        with patch.dict(os.environ, {OPT_IN_ENV: "0"}):
            proposal = self.preview()
        self.assertEqual(proposal["changes"]["ssid"]["after"], "LAB_WIFI_2")
        self.assertEqual(len(self.zte.calls), 2)
        self.assertFalse(self.zte.writes_enabled)

    def test_preview_is_get_only_and_redacted(self):
        with patch.dict(os.environ, {OPT_IN_ENV: "1"}):
            result = self.preview()
        self.assertEqual(result["changes"]["ssid"]["after"], "LAB_WIFI_2")
        self.assertNotIn("masked-ciphertext", str(result))
        self.assertNotIn("fake temporary token", str(result))
        self.assertEqual([call[0] for call in self.zte.calls],
                         ["GET_VIEW", "GET_MENU"])
        self.assertFalse(self.zte.writes_enabled)

    def test_rejects_apply_without_real_preflight_nonce(self):
        result = self.preview()
        with self.assertRaisesRegex(PermissionError, "Prévia"):
            self.writer.apply(
                self.zte, host="192.0.2.1", firmware=EXACT_FIRMWARE,
                nonce="not-" + result["nonce"], confirmation="",
                original_post=lambda *a: None,
            )
        self.assertFalse(self.zte.writes_enabled)

    def test_apply_uses_legacy_verified_writer_once_then_relocks(self):
        with patch.dict(os.environ, {OPT_IN_ENV: "1"}):
            preview = self.preview({"broadcast": False})
            def fake_legacy(*args, **kwargs):
                self.assertIs(kwargs.get("captured_f6201b"), True)
                self.assertTrue(self.zte.writes_enabled)
                self.assertIs(self.zte.session.post, original_post)
                return {"success": True, "verified": True}
            def original_post(*args):
                pass
            with patch(
                "apps.zte_manager.services.f6201b_writes.zte_wifi.set_ssid_config",
                side_effect=fake_legacy
            ) as writer:
                result = self.writer.apply(
                    self.zte, host="192.0.2.1", firmware=EXACT_FIRMWARE,
                    nonce=preview["nonce"], confirmation="APLICAR F6201B",
                    original_post=original_post,
                )
                self.assertTrue(result["verified"])
                self.assertEqual(writer.call_count, 1)
                self.assertIs(self.zte.session.post, denied_post)
                self.assertFalse(self.zte.writes_enabled)
                with self.assertRaises(PermissionError):
                    self.writer.apply(
                        self.zte, host="192.0.2.1", firmware=EXACT_FIRMWARE,
                        nonce=preview["nonce"], confirmation="APLICAR F6201B",
                        original_post=original_post,
                    )
                self.assertEqual(writer.call_count, 1)

    def test_apply_failure_also_restores_transport(self):
        with patch.dict(os.environ, {OPT_IN_ENV: "1"}):
            preview = self.preview()
            with patch(
                "apps.zte_manager.services.f6201b_writes.zte_wifi.set_ssid_config",
                side_effect=RuntimeError("firmware refused"),
            ):
                with self.assertRaises(RuntimeError):
                    self.writer.apply(
                        self.zte, host="192.0.2.1", firmware=EXACT_FIRMWARE,
                        nonce=preview["nonce"], confirmation="APLICAR F6201B",
                        original_post=lambda *a: None,
                    )
            self.assertIs(self.zte.session.post, denied_post)
            self.assertFalse(self.zte.writes_enabled)

    def test_rejects_wrong_firmware_unknown_field_or_view(self):
        with patch.dict(os.environ, {OPT_IN_ENV: "1"}):
            with self.assertRaises(PermissionError):
                self.writer.preview(self.zte, host="192.0.2.1",
                    firmware="V9.3.10P8N1", ssid_id="DEV.WIFI.AP1",
                    config={"ssid": "NEW"})
            with self.assertRaises(ValueError):
                self.preview({"password": "no!"})
            with self.assertRaises(ValueError):
                self.writer.preview(self.zte, host="192.0.2.1",
                    firmware=EXACT_FIRMWARE, ssid_id="bad/ssid",
                    config={"ssid": "NEW"})
            self.zte.menu_valid = False
            with self.assertRaises(RuntimeError):
                self.preview()

    def test_secure_ssid_without_proven_encryption_refused(self):
        # Não arriscar alterar a PSK inadvertidamente quando o firmware
        # expõe a instância mas não comprova como a cifra foi construída.
        def secure_parser(raw):
            return {
                "OBJ_WLANAP_ID": [{
                    "_InstID": "DEV.WIFI.AP1", "ESSID": "LAB_WIFI",
                    "Enable": "1", "ESSIDHideEnable": "0",
                    "BeaconType": "11i",
                }],
                "OBJ_WLANPSK_ID": [{
                    "_InstID": "DEV.WIFI.AP1.PSK1",
                    "KeyPassphrase": "unknown-cipher",
                }],
            }
        self.zte._parse_instances = secure_parser
        with patch.dict(os.environ, {OPT_IN_ENV: "1"}):
            with self.assertRaisesRegex(RuntimeError, "criptografia"):
                self.preview()
        self.assertFalse(self.zte.writes_enabled)

    def test_list_ssids_never_returns_password(self):
        result = Writer.list_ssids(self.zte)
        self.assertEqual(result[0]["ssid"], "LAB_WIFI")
        self.assertNotIn("masked-ciphertext", str(result))


if __name__ == "__main__":
    unittest.main()

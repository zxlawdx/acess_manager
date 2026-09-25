"""Synthetic RF profile tests; never send a request to actual ONT."""
import os
import unittest
from unittest.mock import patch

from apps.zte_manager.services.f6201b_profile import (
    ExperimentalF6201BProfile, RADIO_SCHEMA,
)
from apps.zte_manager.services.f6201b_writes import (
    EXACT_FIRMWARE, OPT_IN_ENV,
)


class FakeSession:
    @staticmethod
    def blocked(*args, **kwargs):
        raise PermissionError("Read-only")
    def __init__(self):
        self.post = self.blocked


class FakeONT:
    def __init__(self):
        self.session = FakeSession()
        self.writes_enabled = False
        self._values = {
            "BasicDataRates": "1,2,5.5,11",
            "OpDataRates": "1,2,5.5,11,6,9,12,18,24,36,48,54",
            "11nMode": "1", "GreenField": "0", "AutoChannelEnabled": "1",
            "Band": "2.4GHz", "Channel": "NULL",
            "Standard": "b,g,n", "BandWidth": "20MHz",
            "AutoChRange": "0", "MUMIMOEnable": "0", "UPLinkOFDMA": "0",
            "SSIDIsolationEnable": "0", "CountryCode": "BRI",
            "SGIEnabled": "0", "BeaconInterval": "100",
            "TxPower": "50%", "PreambleType": "0",
            "_InstID": "DEV.WIFI.RADIO1",
        }
        self.views = []
    def get_view(self, view, **kw):
        self.views.append(view)
        return "form"
    def get_menu(self, tag, **kw):
        self.views.append(tag)
        return "<ajax_response_xml_root><IF_ERRORID>0</IF_ERRORID></ajax_response_xml_root>"
    def _parse_instances(self, xml):
        return {"OBJ_WLANSETTING_ID": [dict(self._values)]}


class FakeDNS:
    def __init__(self):
        self.cleared = 0
        self.applied = 0
    def clear(self):
        self.cleared += 1
    def read(self, zte):
        return {"ipv4_1": "1.1.1.1", "ipv4_2": "9.9.9.9"}
    def preview(self, *args, **kwargs):
        return {"nonce": "fake-dns", "changes": {
            "SerIPAddress2": {"before": "9.9.9.9", "after": "8.8.8.8"}
        }}
    def apply(self, *args, **kwargs):
        self.applied += 1
        return {"verified": True}


class BatchTests(unittest.TestCase):
    def setUp(self):
        self.zte = FakeONT()
        self.dns = FakeDNS()
        self.engine = ExperimentalF6201BProfile()
        self.kw = dict(host="192.0.2.31", revision="session-a",
                       firmware=EXACT_FIRMWARE, dns_adapter=self.dns)
        self.profile = {"wifi": {
            "2.4GHz": {"tx_power": "75%"}
        }, "dns": {"ipv4_1": "1.1.1.1", "ipv4_2": "8.8.8.8"}}

    def preview(self):
        return self.engine.preview(self.zte, profile=self.profile, **self.kw)

    def apply(self, nonce, confirmation="APLICAR PERFIL F6201B"):
        return self.engine.apply(self.zte, nonce=nonce,
            confirmation=confirmation,
            original_post=self.zte.session.blocked, **self.kw)

    def test_off_by_default(self):
        with patch.dict(os.environ, {OPT_IN_ENV: "0"}):
            with self.assertRaises(PermissionError):
                self.preview()
        self.assertEqual(self.zte.views, [])

    def test_preview_get_only_has_two_independent_stages(self):
        with patch.dict(os.environ, {OPT_IN_ENV: "1"}):
            p = self.preview()
        self.assertEqual(len(p["radios"]), 1)
        self.assertEqual(p["radios"][0]["band"], "2.4GHz")
        self.assertEqual(p["radios"][0]["changes"]["TxPower"]["after"], "75%")
        self.assertIn("SerIPAddress2", p["dns"])
        self.assertFalse(self.zte.writes_enabled)
        self.assertEqual(self.dns.applied, 0)

    def test_apply_captured_order_verification_and_replay(self):
        calls = []
        def fake_post(zte, tag, payload):
            self.assertEqual(tag, "wlan_wlanbasicadconf_lua.lua")
            self.assertEqual(
                tuple(k for k, _ in payload) + ("_sessionTOKEN",),
                RADIO_SCHEMA)
            self.assertTrue(zte.writes_enabled)
            self.assertIs(zte.session.post, zte.session.blocked)
            calls.append(1)
            zte._values["TxPower"] = "75%"
            return "<ajax_response_xml_root><IF_ERRORID>0</IF_ERRORID></ajax_response_xml_root>"
        with patch.dict(os.environ, {OPT_IN_ENV: "1"}), patch(
            "apps.zte_manager.services.f6201b_profile.post_menu",
            side_effect=fake_post
        ):
            p = self.preview()
            report = self.apply(p["nonce"])
            self.assertTrue(report["success"])
            self.assertFalse(report["partial"])
            self.assertEqual(len(report["steps"]), 2)
            self.assertEqual(self.dns.applied, 1)
            self.assertFalse(self.zte.writes_enabled)
            self.assertIs(self.zte.session.post, self.zte.session.blocked)
            with self.assertRaises(PermissionError):
                self.apply(p["nonce"])
        self.assertEqual(calls, [1])

    def test_profile_already_applied_is_noop_without_nonce_or_post(self):
        self.profile = {
            "wifi": {"2.4GHz": {"tx_power": "50%"}},
            "dns": {"ipv4_1": "1.1.1.1", "ipv4_2": "9.9.9.9",
                    "hosts": []},
        }
        with patch.dict(os.environ, {OPT_IN_ENV: "1"}):
            result = self.preview()
        self.assertTrue(result["noop"])
        self.assertNotIn("nonce", result)
        self.assertIsNone(self.engine._pending)
        self.assertEqual(self.dns.applied, 0)

    def test_auto_channel_operating_channel_is_not_fixed_or_stale(self):
        # Real firmware may keep the last selected channel while
        # AutoChannelEnabled=1; this is a runtime value, not a static
        # configuration drift.
        self.zte._values["Channel"] = "6"
        self.profile["wifi"]["2.4GHz"]["auto_channel"] = True
        events = []
        def dynamic_post(zte, tag, payload):
            events.append(tag)
            # Firmware chooses channel 11 instead of returning NULL.
            zte._values["Channel"] = "11"
            zte._values["TxPower"] = "75%"
            return ("<ajax_response_xml_root><IF_ERRORID>0</IF_ERRORID>"
                    "</ajax_response_xml_root>")
        with patch.dict(os.environ, {OPT_IN_ENV: "1"}), patch(
            "apps.zte_manager.services.f6201b_profile.post_menu",
            side_effect=dynamic_post
        ):
            preview = self.preview()
            self.assertIn("Channel", preview["radios"][0]["changes"])
            # A scan can occur after preview and before confirmation.
            self.zte._values["Channel"] = "1"
            report = self.apply(preview["nonce"])
        self.assertTrue(report["success"], report)
        self.assertEqual(events, ["wlan_wlanbasicadconf_lua.lua"])

    def test_bad_confirmation_never_posts(self):
        with patch.dict(os.environ, {OPT_IN_ENV: "1"}):
            p = self.preview()
            with self.assertRaises(PermissionError):
                self.apply(p["nonce"], "sim")
        self.assertFalse(self.zte.writes_enabled)
        self.assertEqual(self.dns.applied, 0)

    def test_no_dns_after_ambiguous_radio_result(self):
        def no_update(*args):
            return "<ajax_response_xml_root><IF_ERRORID>0</IF_ERRORID></ajax_response_xml_root>"
        with patch.dict(os.environ, {OPT_IN_ENV: "1"}), patch(
            "apps.zte_manager.services.f6201b_profile.post_menu",
            side_effect=no_update
        ):
            p = self.preview()
            report = self.apply(p["nonce"])
        self.assertFalse(report["success"])
        self.assertFalse(report["partial"])
        self.assertEqual(report["failed_stage"], "Wi-Fi 2.4GHz")
        self.assertEqual(report["steps"][-1]["name"], "Wi-Fi 2.4GHz")
        self.assertEqual(self.dns.applied, 0)
        self.assertFalse(self.zte.writes_enabled)

    def test_missing_autochrange_uses_homologated_firmware_default(self):
        del self.zte._values["AutoChRange"]
        captured = {}

        def fake_post(zte, tag, payload):
            captured.update(dict(payload))
            zte._values["AutoChRange"] = "0"
            zte._values["TxPower"] = "75%"
            return ("<ajax_response_xml_root><IF_ERRORID>0</IF_ERRORID>"
                    "</ajax_response_xml_root>")

        with patch.dict(os.environ, {OPT_IN_ENV: "1"}), patch(
            "apps.zte_manager.services.f6201b_profile.post_menu",
            side_effect=fake_post
        ):
            proposal = self.preview()
            result = self.apply(proposal["nonce"])

        self.assertTrue(result["success"], result)
        self.assertEqual(captured["AutoChRange"], "0")

    def test_missing_live_form_field_fails_before_any_write(self):
        del self.zte._values["PreambleType"]
        with patch.dict(os.environ, {OPT_IN_ENV: "1"}):
            with self.assertRaisesRegex(RuntimeError, "PreambleType"):
                self.preview()
        self.assertEqual(self.dns.applied, 0)


if __name__ == "__main__":
    unittest.main()

"""Synthetic integration tests for 14 distinct captured F6201B form strategies.

No real ONT, passwords, network traffic, or capture bytes are used.
"""
from contextlib import ExitStack
import os
import unittest
from unittest.mock import patch

from apps.zte_manager.services.f6201b_evidence import OBSERVED_APPLY_FIELDS
from apps.zte_manager.services.f6201b_full_forms import (
    FORM_SPECS, FullCapturedForms, _assemble, _form_fields, _load,
)
from apps.zte_manager.services.f6201b_workbench import (
    CapturedFormWorkbench, catalog,
)


class FakeSession:
    def __init__(self):
        self.post = self.blocked

    def blocked(self, *_args, **_kwargs):
        raise PermissionError("transport locked")


class FakeONT:
    def __init__(self, tag, *, removed=(), more_objects=None, encoded=()):
        self.tag = tag
        self.spec = FORM_SPECS[tag]
        self.session = FakeSession()
        self.original_post = lambda *_args, **_kwargs: "<fake/>"
        self.writes_enabled = False
        self.session_tmp_token = "synthetic-token"
        self.public_key_pem = "not-a-real-key"
        self.views = []
        self.post_count = 0
        self.encoded = encoded
        self.form = {}
        self.current = {"_InstID": "DEV.SYNTHETIC.1"}
        for field in OBSERVED_APPLY_FIELDS[tag]:
            if field in {"IF_ACTION", "_sessionTOKEN"} or field.startswith("Btn_"):
                continue
            if field not in removed:
                self.form[field] = "0"
        for field in self.spec.editable:
            if field not in removed:
                self.current[field] = "0"
        if tag == "wan_internet_lua.lua":
            self.current["UserName"] = "cipher-username"
            self.current["Password"] = "cipher-password"
        if tag == "Localnet_LanMgrIpv4_DHCPBasicCfg_lua.lua":
            self.current["IPAddr"] = "192.0.2.1"
        self.objects = {self.spec.root: [self.current]}
        self.objects.update(more_objects or {})

    def get_view(self, view, **kwargs):
        self.views.append(view)
        return "".join(
            '<input name="' + field + '" value="' + value + '">'
            for field, value in self.form.items()
        )

    def get_menu(self, tag, **kwargs):
        if tag != self.tag:
            raise AssertionError("wrong _tag")
        encode = "<encode>" + ",".join(self.encoded) + "</encode>"
        return ("<ajax_response_xml_root><IF_ERRORID>0</IF_ERRORID>" +
                encode + "</ajax_response_xml_root>")

    def _parse_instances(self, _xml):
        return self.objects


class FullFormTests(unittest.TestCase):
    def setUp(self):
        opt_in = patch.dict(os.environ, {
            "ZTE_F6201B_EXPERIMENTAL_WRITES": "1",
        })
        opt_in.start()
        self.addCleanup(opt_in.stop)
        self.clock = lambda: 100.0
        self.command = FullCapturedForms(clock=self.clock, sleep=lambda _: None)

    def _preview(self, fake, changes):
        return self.command.preview(
            fake, tag=fake.tag, instance_id="DEV.SYNTHETIC.1",
            changes=changes, host="192.0.2.10", revision="syn-r1",
            attendant="synthetic-tech",
        )

    def _apply(self, fake, preview, **kw):
        return self.command.apply(
            fake, nonce=preview["nonce"], confirmation=kw.get(
                "confirmation", "APLICAR ROTA F6201B"
            ), risk_ack=kw.get("risk_ack", True),
            original_post=fake.original_post, host="192.0.2.10",
            revision="syn-r1", attendant=kw.get("attendant", "synthetic-tech"),
        )

    def test_all_remaining_routes_have_individual_strategies(self):
        result = catalog()
        self.assertEqual(len(FORM_SPECS), 14)
        self.assertEqual(result["total_observed_apply_routes"], 25)
        self.assertEqual(
            {r["tag"] for r in result["routes"]},
            set(OBSERVED_APPLY_FIELDS),
        )
        self.assertEqual(sum(r["state"] == "supervised_lab"
                             for r in result["routes"]), 21)
        self.assertEqual(sum(r["state"] == "existing_adapter"
                             for r in result["routes"]), 4)

    def test_each_form_can_prepare_all_captured_fields_from_synthetic_html(self):
        for tag, spec in FORM_SPECS.items():
            with self.subTest(tag=tag):
                fake = FakeONT(tag)
                if tag == "wan_internet_lua.lua":
                    # Nonencrypted WAN credentials in this particular fake.
                    pass
                records = _load(fake, tag)
                self.assertEqual(len(records), 1)
                body = _assemble(tag, records[0].values, {})
                self.assertEqual(
                    [key for key, _ in body],
                    [key for key in OBSERVED_APPLY_FIELDS[tag]
                     if key != "_sessionTOKEN"],
                )
                self.assertEqual(dict(body)["IF_ACTION"], "Apply")
                self.assertEqual(records[0].instance_id, "DEV.SYNTHETIC.1")

    def test_fails_closed_if_conditional_field_missing(self):
        tag = "route_routestaticipv4_lua.lua"
        fake = FakeONT(tag, removed=("Type",))
        record = _load(fake, tag)[0]
        self.assertNotIn("Type", record.values)
        with self.assertRaisesRegex(ValueError, "Type"):
            _assemble(tag, record.values, {})
        with self.assertRaisesRegex(ValueError, "incompleto"):
            self._preview(fake, {"Enable": "1"})
        self.assertIsNone(self.command._pending)
        self.assertEqual(fake.post_count, 0)

    def test_wps_keeps_real_ssid_binding_and_scoped_instance(self):
        fake = FakeONT("wlan_wps_lua.lua", removed=("SSID_InstID",))
        record = _load(fake, fake.tag)[0]
        self.assertEqual(record.values["SSID_InstID"], "DEV.SYNTHETIC.1")
        self.assertEqual(record.values["_InstID"], "-1")

    def test_dhcp_host_is_from_live_ip_not_hardcoded(self):
        fake = FakeONT(
            "Localnet_LanMgrIpv4_DHCPBasicCfg_lua.lua",
            removed=("IF_URL_HOST",)
        )
        record = _load(fake, fake.tag)[0]
        self.assertEqual(record.values["IF_URL_HOST"], "192.0.2.1")

    def test_ra_mtu_is_derived_only_from_captured_alternate_name(self):
        fake = FakeONT("ra_raservice_lua.lua", removed=("S_AdvLinkMTU",))
        fake.current["AdvLinkMTU"] = "1400"
        record = _load(fake, fake.tag)[0]
        self.assertEqual(record.values["S_AdvLinkMTU"], "1400")

    def test_multi_radio_fields_are_preserved_from_radio_objects(self):
        tag = "wlan_wlanbasiconoff_lua.lua"
        fake = FakeONT(tag, removed=(
            "_InstID_0", "_InstID_1", "RadioStatus_0", "RadioStatus_1"
        ), more_objects={"OBJ_WLANSETTING_ID": [
            {"_InstID": "radio24", "RadioStatus": "1"},
            {"_InstID": "radio5", "RadioStatus": "0"},
        ]})
        record = _load(fake, tag)[0]
        for key, val in {
            "_InstID_0": "radio24", "_InstID_1": "radio5",
            "RadioStatus_0": "1", "RadioStatus_1": "0",
        }.items():
            self.assertEqual(record.values[key], val)

    def test_nonce_risk_and_readback_for_each_strategy(self):
        # Uses the same Command interface for each captured schema.
        for tag, spec in FORM_SPECS.items():
            with self.subTest(tag=tag):
                self.command.clear()
                fake = FakeONT(tag)
                key = next((name for name in spec.editable
                            if name in {"Enable", "Autoneg", "ProcFlag_0",
                                        "AllowDHCP6S_0", "ACLPolicy_0",
                                        "RadioStatus", "ServerEnable"}),
                           None)
                if key is None:
                    # A static route can change the enable flag too.
                    key = next(name for name in spec.editable
                               if name not in {"UserPassword", "Password"})
                new_value = "1"
                if key in {"DestIP", "DestIPMask", "GWIP", "InternalClient"}:
                    new_value = "192.0.2.2"
                preview = self._preview(fake, {key: new_value})

                def fake_post(zte, posted_tag, body, **kwargs):
                    self.assertEqual(posted_tag, tag)
                    self.assertTrue(zte.writes_enabled)
                    self.assertEqual(zte.session.post, zte.original_post)
                    self.assertEqual(
                        [field for field, _ in body],
                        [name for name in OBSERVED_APPLY_FIELDS[tag]
                         if name != "_sessionTOKEN"],
                    )
                    zte.current[key] = new_value
                    zte.post_count += 1
                    return "<synthetic-success/>"

                with patch(
                    "apps.zte_manager.services.f6201b_full_forms.post_menu",
                    side_effect=fake_post,
                ) as mocked:
                    outcome = self._apply(fake, preview)
                self.assertTrue(outcome["success"], tag)
                self.assertTrue(outcome["verified"], tag)
                mocked.assert_called_once()
                self.assertEqual(fake.post_count, 1)
                self.assertEqual(fake.session.post, fake.session.blocked)
                self.assertFalse(fake.writes_enabled)
                with self.assertRaisesRegex(PermissionError, "Prévia"):
                    self._apply(fake, preview)

    def test_tr069_secrets_masked_and_preserved_by_sentinel(self):
        fake = FakeONT("tr069_remotemgr_lua.lua")
        inspect = self.command.inspect(fake, fake.tag)
        exposed = str(inspect)
        self.assertNotIn("synthetic-password", exposed)
        self.assertEqual(inspect["instances"][0]["current"]["UserPassword"],
                         "••••••")
        preview = self._preview(fake, {"UserPassword": "synthetic-password"})
        self.assertNotIn("synthetic-password", str(preview))
        captured = {}

        def fake_post(_zte, _tag, fields, **kwargs):
            captured.update(dict(fields))
            return "<synthetic-success/>"

        with ExitStack() as mocks:
            mocks.enter_context(patch(
                "apps.zte_manager.services.f6201b_full_forms."
                "zte_security.aes_encrypt_value", return_value="AES"
            ))
            mocks.enter_context(patch(
                "apps.zte_manager.services.f6201b_full_forms."
                "zte_security.rsa_encrypt_text", return_value="RSA"
            ))
            mocks.enter_context(patch(
                "apps.zte_manager.services.f6201b_full_forms.post_menu",
                side_effect=fake_post,
            ))
            result = self._apply(fake, preview)
        self.assertEqual(captured["encode"], "RSA")
        self.assertEqual(captured["UserPassword"], "AES")
        self.assertEqual(captured["ConnectionRequestPassword"], "\t" * 6)
        self.assertTrue(result["success"])
        self.assertTrue(result["partial"])
        self.assertEqual(result["manual_verification_fields"], ["UserPassword"])

    def test_wan_encrypted_credentials_are_decrypted_and_recoded(self):
        tag = "wan_internet_lua.lua"
        fake = FakeONT(tag, encoded=("UserName", "Password"))
        fake.current["MTU"] = "1492"
        with ExitStack() as patches:
            patches.enter_context(patch(
                "apps.zte_manager.services.f6201b_full_forms."
                "zte_security.aes_decrypt_value",
                side_effect=lambda raw, *_: "plain-" + raw,
            ))
            patches.enter_context(patch(
                "apps.zte_manager.services.f6201b_full_forms."
                "zte_security.aes_encrypt_value",
                side_effect=lambda raw, *_: "aes-" + raw,
            ))
            patches.enter_context(patch(
                "apps.zte_manager.services.f6201b_full_forms."
                "zte_security.rsa_encrypt_text", return_value="new-RSA",
            ))
            captured = {}
            def fake_post(_zte, _tag, fields, **kwargs):
                captured.update(dict(fields))
                _zte.current["MTU"] = "1500"
                return "<synthetic-success/>"
            patches.enter_context(patch(
                "apps.zte_manager.services.f6201b_full_forms.post_menu",
                side_effect=fake_post,
            ))
            preview = self._preview(fake, {"MTU": "1500"})
            self.assertNotIn("plain-cipher-password", str(preview))
            outcome = self._apply(fake, preview)
        self.assertTrue(outcome["verified"])
        self.assertEqual(captured["UserName"], "aes-plain-cipher-username")
        self.assertEqual(captured["Password"], "aes-plain-cipher-password")
        self.assertEqual(captured["encode"], "new-RSA")

    def test_attendant_switch_and_uncertain_post_no_retry(self):
        fake = FakeONT("firewall_dmz_lua.lua")
        proposal = self._preview(fake, {"Enable": "1"})
        with self.assertRaisesRegex(PermissionError, "mudou"):
            self._apply(fake, proposal, attendant="different-tech")
        proposal = self._preview(fake, {"Enable": "1"})
        with patch("apps.zte_manager.services.f6201b_full_forms.post_menu",
                   side_effect=TimeoutError("synthetic")) as mocked:
            outcome = self._apply(fake, proposal)
        self.assertTrue(outcome["uncertain"])
        self.assertEqual(outcome["stage"], "post_or_response")
        mocked.assert_called_once()
        self.assertEqual(fake.session.post, fake.session.blocked)

    def test_no_post_if_live_config_changed_after_preview(self):
        fake = FakeONT("firewall_dmz_lua.lua")
        proposal = self._preview(fake, {"Enable": "1"})
        fake.current["WANCViewName"] = "different WAN"
        with self.assertRaisesRegex(RuntimeError, "mudou"):
            self._apply(fake, proposal)
        self.assertEqual(fake.post_count, 0)


if __name__ == "__main__":
    unittest.main()

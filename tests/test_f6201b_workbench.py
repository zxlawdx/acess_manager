"""Synthetic contract/regression tests: never use a live ONT or captured secrets."""
import os
import unittest
from unittest.mock import patch

from apps.zte_manager.services.f6201b_evidence import OBSERVED_APPLY_FIELDS
from apps.zte_manager.services.f6201b_workbench import (
    CapturedFormWorkbench, STRATEGIES, build_captured_payload, catalog,
)


class FakeSession:
    def __init__(self):
        self.post = self.blocked

    def blocked(self, *args, **kwargs):
        raise PermissionError("Transport must remain read-only")


class FakeZTE:
    def __init__(self, tag="bpdu_lua.lua"):
        self.tag = tag
        self.root = STRATEGIES[tag].root
        self.current = {"_InstID": "DEV.TEST.IF1"}
        for name in STRATEGIES[tag].editable:
            self.current[name] = "0"
        self.session = FakeSession()
        self.original_post = lambda *args, **kwargs: "TEST_ONLY"
        self.writes_enabled = False
        self.session_tmp_token = None
        self.views = []
        self.post_count = 0

    def get_view(self, view, **kwargs):
        self.views.append(view)
        self.session_tmp_token = "fresh-synthetic-token"

    def get_menu(self, tag, **kwargs):
        if tag != self.tag:
            raise AssertionError("wrong firmware endpoint")
        return ('<ajax_response_xml_root><IF_ERRORID>0</IF_ERRORID>'
                '<' + self.root + '><Instance></Instance></' + self.root + '>'
                '</ajax_response_xml_root>')

    def _parse_instances(self, raw):
        return {self.root: [dict(self.current)]}


class CapturedFormTests(unittest.TestCase):
    def setUp(self):
        patcher = patch.dict(os.environ, {
            "ZTE_F6201B_EXPERIMENTAL_WRITES": "1",
        })
        patcher.start()
        self.addCleanup(patcher.stop)
        self.zte = FakeZTE()
        self.workbench = CapturedFormWorkbench(clock=lambda: 100.0)

    def preview(self):
        return self.workbench.preview(
            self.zte, tag="bpdu_lua.lua", instance_id="DEV.TEST.IF1",
            changes={"BPDUEnable": "1"}, host="192.0.2.10", revision="r1",
        )

    def apply(self, nonce, **kwargs):
        return self.workbench.apply(
            self.zte, host=kwargs.get("host", "192.0.2.10"),
            revision=kwargs.get("revision", "r1"), nonce=nonce,
            confirmation=kwargs.get("confirmation", "APLICAR ROTA F6201B"),
            risk_ack=kwargs.get("risk_ack", True),
            original_post=self.zte.original_post,
        )

    def test_registry_tracks_all_25_captured_routes_without_inventing_support(self):
        result = catalog()
        rows = result["routes"]
        self.assertEqual(len(rows), 25)
        self.assertEqual({row["tag"] for row in rows}, set(OBSERVED_APPLY_FIELDS))
        states = [row["state"] for row in rows]
        self.assertEqual(states.count("supervised_lab"), 7)
        self.assertEqual(states.count("existing_adapter"), 4)
        self.assertEqual(states.count("needs_form_adapter"), 14)
        self.assertEqual(result["physical_validation"], "pending")

    def test_exact_payload_order_and_preserves_unmodified_values(self):
        zte = FakeZTE("upnp_upnp_lua.lua")
        zte.current.update({"EnableUPnPIGD": "0",
                            "ADPeriod": "7200", "TTL": "4"})
        payload = build_captured_payload(
            zte.tag, zte.current, {"EnableUPnPIGD": "1"}
        )
        self.assertEqual([key for key, value in payload],
                         [name for name in OBSERVED_APPLY_FIELDS[zte.tag]
                          if name != "_sessionTOKEN"])
        self.assertIn(("ADPeriod", "7200"), payload)
        self.assertIn(("TTL", "4"), payload)
        self.assertEqual(payload[0], ("IF_ACTION", "Apply"))
        self.assertNotIn("_sessionTOKEN", dict(payload))

    def test_missing_field_or_non_allowlisted_field_rejected(self):
        with self.assertRaisesRegex(ValueError, "GET incompleto"):
            build_captured_payload("upnp_upnp_lua.lua",
                                   {"_InstID": "DEV.TEST.IF1"},
                                   {"EnableUPnPIGD": "1"})
        with self.assertRaisesRegex(ValueError, "Campo"):
            build_captured_payload("bpdu_lua.lua", self.zte.current,
                                   {"AdminPassword": "guess"})

    def test_supervised_preview_apply_consumes_nonce_and_relocks_transport(self):
        preview = self.preview()
        self.assertEqual(preview["diff"]["BPDUEnable"],
                         {"before": "0", "after": "1"})
        self.assertTrue(preview["risk_ack_required"])

        def stub_post(zte, tag, payload, **kwargs):
            self.assertEqual(tag, "bpdu_lua.lua")
            self.assertIs(zte.session.post, zte.original_post)
            self.assertTrue(zte.writes_enabled)
            self.assertEqual(zte.session_tmp_token, "fresh-synthetic-token")
            self.assertEqual(payload[-1], ("Btn_apply_instCfgArea", ""))
            zte.post_count += 1
            zte.current["BPDUEnable"] = dict(payload)["BPDUEnable"]
            return "<synthetic-success/>"

        with patch("apps.zte_manager.services.f6201b_workbench.post_menu",
                   side_effect=stub_post):
            result = self.apply(preview["nonce"])
        self.assertTrue(result["verified"])
        self.assertEqual(self.zte.post_count, 1)
        self.assertIs(self.zte.session.post, self.zte.session.blocked)
        self.assertFalse(self.zte.writes_enabled)
        with self.assertRaisesRegex(PermissionError, "Nonce"):
            self.apply(preview["nonce"])

    def test_risk_ack_is_mandatory_and_consumes_nonce(self):
        preview = self.preview()
        with self.assertRaisesRegex(PermissionError, "risco"):
            self.apply(preview["nonce"], risk_ack=False)
        with self.assertRaises(PermissionError):
            self.apply(preview["nonce"])
        self.assertEqual(self.zte.post_count, 0)

    def test_rejects_stale_snapshot_without_issuing_post(self):
        preview = self.preview()
        self.zte.current["BPDUEnable"] = "1"  # changed in original ZTE UI
        with self.assertRaisesRegex(RuntimeError, "mudou"):
            self.apply(preview["nonce"])
        self.assertEqual(self.zte.post_count, 0)

    def test_firmware_schema_mismatch_blocks_preview(self):
        self.zte.current.pop("BPDUEnable")
        with self.assertRaisesRegex(ValueError, "GET incompleto"):
            self.preview()
        self.assertIsNone(self.workbench._pending)

    def test_unknown_route_and_bad_values_fail_before_write(self):
        with self.assertRaises(PermissionError):
            self.workbench.preview(
                self.zte, tag="tr069_remotemgr_lua.lua",
                instance_id="DEV.TEST.IF1", changes={"UserPassword": "x"},
                host="192.0.2.10", revision="r1")
        with self.assertRaisesRegex(ValueError, "0 ou 1"):
            self.workbench.preview(
                self.zte, tag="bpdu_lua.lua",
                instance_id="DEV.TEST.IF1", changes={"BPDUEnable": "2"},
                host="192.0.2.10", revision="r1")

    def test_opt_in_required_for_preview_and_apply(self):
        with patch.dict(os.environ, {"ZTE_F6201B_EXPERIMENTAL_WRITES": "0"}):
            with self.assertRaisesRegex(PermissionError, "ZTE_F6201B"):
                self.preview()
        preview = self.preview()
        with patch.dict(os.environ, {"ZTE_F6201B_EXPERIMENTAL_WRITES": "0"}):
            with self.assertRaises(PermissionError):
                self.apply(preview["nonce"])

    def test_timeout_consumes_nonce(self):
        preview = self.preview()
        self.workbench._clock = lambda: 100.0 + 121
        with self.assertRaisesRegex(PermissionError, "expirada"):
            self.apply(preview["nonce"])
        self.assertEqual(self.zte.post_count, 0)

    def test_uncertain_post_never_repeats_and_transport_is_restored(self):
        preview = self.preview()
        with patch("apps.zte_manager.services.f6201b_workbench.post_menu",
                   side_effect=TimeoutError("network test")) as mock_post:
            result = self.apply(preview["nonce"])
        self.assertTrue(result["uncertain"])
        self.assertEqual(result["stage"], "post_or_response")
        mock_post.assert_called_once()
        self.assertIs(self.zte.session.post, self.zte.session.blocked)
        self.assertFalse(self.zte.writes_enabled)

    def test_inspection_filters_to_nonsecret_editable_fields(self):
        zte = FakeZTE("upnp_upnp_lua.lua")
        zte.current["AdminPassword"] = "never-present"
        result = self.workbench.inspect(zte, zte.tag)
        self.assertTrue(result["available"])
        self.assertNotIn("AdminPassword", result["instances"][0]["current"])
        self.assertEqual(result["instances"][0]["id"], "DEV.TEST.IF1")


if __name__ == "__main__":
    unittest.main()

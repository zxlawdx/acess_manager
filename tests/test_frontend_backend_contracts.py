"""Real Vela route contract tests with fake ZTE service I/O.

These invoke the deployed handler functions and Pydantic request models.
No physical ONT is claimed; a mocked service stands in for each backend
operation and exercises the same public endpoints used by the GUI.
"""
from __future__ import annotations

import unittest
from unittest.mock import patch, Mock
from apps.zte_manager import api
from apps.zte_manager.services.error_policy import (
    SessionExpired, CapabilityUnconfirmed, PartialOperation
)


def context(data):
    return {"json": data}


class FrontendBackendContracts(unittest.TestCase):
    def test_wifi_ssid_write_forwards_real_validated_fields(self):
        expected = {"ssid": "Rede 5G", "enabled": True}
        with patch.object(api.zte_service, "set_ssid_config",
                          return_value={"success": True, "verified": True}) as action:
            actual=api.set_wifi_network(context({"ssid_id": "2", **expected}))
        action.assert_called_once_with("2", expected)
        self.assertTrue(actual["verified"])

    def test_wifi_invalid_number_rejected_before_device_io(self):
        with patch.object(api.zte_service, "set_wifi_radio") as action:
            result=api.set_radio(context({"band":"5GHz","dtim":99}))
        action.assert_not_called()
        self.assertEqual(result["code"], "INVALID_INPUT")
        self.assertNotIn("99", str(result))

    def test_dhcp_and_dns_forward_backend_results_not_frontend_simulations(self):
        with patch.object(api.zte_service, "set_dhcp_basic",
                          return_value={"success":True}) as action:
            r=api.update_dhcp(context({"enabled":True,"min_address":"192.0.2.100",
                "max_address":"192.0.2.200","lease_time":3600}))
        self.assertTrue(r["success"])
        self.assertEqual(action.call_args.args[0]["lease_time"],3600)
        with patch.object(api.zte_service,"set_dns",
                          return_value={"success":True,"verified":True}) as action:
            r=api.set_dns(context({"ipv4_1":"1.1.1.1","ipv4_2":"8.8.8.8"}))
        self.assertTrue(r["verified"])
        self.assertEqual(action.call_args.args[0]["ipv4_2"],"8.8.8.8")

    def test_diagnostics_use_real_validated_payload_and_expiry_is_typed(self):
        with patch.object(api.zte_service,"ping",
                          return_value={"success":True,"packets_received":4}) as action:
            r=api.ping(context({"host":"1.1.1.1","count":4}))
        self.assertEqual(r["packets_received"],4)
        self.assertEqual(action.call_args.args[0]["count"],4)
        with patch.object(api.zte_service,"traceroute",side_effect=SessionExpired()):
            failure=api.traceroute(context({"host":"1.1.1.1","max_hops":4}))
        self.assertEqual(failure["code"],"SESSION_EXPIRED")
        self.assertTrue(failure["retryable"])

    def test_capability_probe_is_unconfirmed_not_false_firmware_absence(self):
        with patch.object(api.zte_service,"probe_capabilities",
                          side_effect=CapabilityUnconfirmed()):
            result=api.capability_probe(context({"features":["wifi_status"]}))
        self.assertEqual(result["code"],"CAPABILITY_UNCONFIRMED")
        self.assertEqual(result["type"],"unconfirmed")
        self.assertNotEqual(result["type"],"unsupported")

    def test_profiles_and_attendance_use_actual_persisted_services(self):
        profile={"attendant":"qa","wifi":{"5GHz":{"auto_channel":True}},
                 "dns":{"ipv4_1":"1.1.1.1"}}
        with patch.object(api.zte_service,"save_profile",
                          return_value={"success":True}) as action:
            self.assertTrue(api.save_profile(context(profile))["success"])
        action.assert_called_once_with("qa",{"wifi":profile["wifi"],"dns":profile["dns"]})
        with patch.object(api.zte_service,"generate_attendance",
                          return_value={"report":"Resultado revisado"}) as action:
            self.assertEqual(api.generate_attendance(context({"diagnostic_id":2})),
                             {"report":"Resultado revisado"})
        action.assert_called_once_with(2)

    def test_failed_profile_apply_reports_partial_and_does_not_claim_success(self):
        with patch.object(api.zte_service,"apply_profile",
                          side_effect=PartialOperation(completed=2,total=4)):
            r=api.apply_profile(context({"attendant":"qa"}))
        self.assertEqual(r["code"],"OPERATION_PARTIAL")
        self.assertEqual((r["completed"],r["total"]),(2,4))
        self.assertEqual(r["type"],"partial")

    def test_history_uses_saved_session_and_only_bounded_reads(self):
        with patch.object(api.zte_service,"history",
                          return_value={"changes":[],"diagnostics":[]}) as action:
            self.assertEqual(api.history({"query":{"limit":"5"}}),
                             {"changes":[],"diagnostics":[]})
        action.assert_called_once_with(5)
        with patch.object(api.zte_service,"capture_snapshot",
                          return_value={"snapshot_id":20,"partial":False}) as action:
            r=api.capture_snapshot(context({"reason":"manual-ui"}))
        self.assertEqual(r["snapshot_id"],20)
        action.assert_called_once_with("manual-ui")


if __name__=="__main__":
    unittest.main()

"""F6201B support form options execute real independent callbacks.

All requests are mocked: these tests never contact a router or provider.
"""
import unittest

from apps.zte_manager.services.f6201b_support import run_f6201b_support


class SupportCheckboxTests(unittest.TestCase):
    def setUp(self):
        self.calls = []
        def read(section):
            self.calls.append(("get", section))
            return {"sections": {section: {
                "available": True, "data": [{"status": "ok"}]
            }}}
        def ping(config):
            self.calls.append(("ping", config))
            return {"verified": True, "resultado": "4/4", "perda_percentual": 0}
        def trace(config):
            self.calls.append(("trace", config))
            return {"verified": True, "hops": []}
        def speed(config):
            self.calls.append(("speed", config))
            return {"source": "workstation", "download_mbps": 100}
        def optimize():
            self.calls.append(("optimize", None))
            return {"success": True, "verified": True, "steps": []}
        self.funcs = dict(
            firmware="V9.3.10P7N7", read_section=read, ping=ping,
            traceroute=trace, speedtest=speed, optimize=optimize,
        )

    def test_all_selected_checkboxes_invoke_real_stages(self):
        result = run_f6201b_support(
            config={"mode": "general", "ping_host": "192.0.2.11",
                    "run_ping": True, "include_traceroute": True,
                    "include_speedtest": True, "auto_optimize_wifi": True,
                    "allow_speedtest_fallback": True},
            **self.funcs,
        )
        invoked = [call[0] for call in self.calls]
        self.assertEqual(invoked.count("ping"), 1)
        self.assertEqual(invoked.count("trace"), 1)
        self.assertEqual(invoked.count("speed"), 1)
        self.assertEqual(invoked.count("optimize"), 1)
        self.assertEqual(len(result["firmware_readings"]), 8)
        self.assertEqual(result["status"], "ok")
        self.assertEqual(len(result["remediations"]), 1)
        self.assertEqual(result["performed"][-1]["operation"],
                         "wifi_auto_optimization")

    def test_dns_lookup_is_explicitly_labelled_as_workstation(self):
        def lookup(host):
            self.calls.append(("dns", host))
            return {"source": "workstation_dns", "verified": True,
                    "addresses": ["192.0.2.7"]}
        result = run_f6201b_support(
            config={"mode": "general", "dns_host": "example.org"},
            dns_lookup=lookup, **self.funcs,
        )
        self.assertIn(("dns", "example.org"), self.calls)
        self.assertEqual(result["sections"]["dns_lookup"]["source"],
                         "workstation_dns")
        self.assertEqual(
            next(item["target"] for item in result["performed"]
                 if item["operation"] == "dns_lookup_pc"),
            "PC do atendente",
        )

    def test_unchecked_actions_do_not_run(self):
        result = run_f6201b_support(
            config={"mode": "wifi", "run_ping": False,
                    "include_traceroute": False,
                    "include_speedtest": False,
                    "auto_optimize_wifi": False},
            **self.funcs,
        )
        self.assertTrue(self.calls)
        self.assertEqual(set(x[0] for x in self.calls), {"get"})
        self.assertEqual(result["remediations"], [])

    def test_one_stage_failure_does_not_hide_others(self):
        def timed_out(config):
            raise TimeoutError("synthetic device timeout")
        funcs = dict(self.funcs, traceroute=timed_out)
        result = run_f6201b_support(
            config={"mode": "drops", "include_traceroute": True,
                    "include_speedtest": True},
            **funcs,
        )
        self.assertEqual(result["status"], "warning")
        self.assertIn("traceroute", result["errors"])
        self.assertIn("speedtest", result["sections"])
        self.assertEqual(len(result["firmware_readings"]), 5)
        self.assertNotIn("synthetic device timeout", str(result))

    def test_failed_auto_optimization_not_mislabeled_as_success(self):
        def failed():
            return {"success": False, "verified": False,
                    "uncertain": True, "steps": []}
        result = run_f6201b_support(
            config={"mode": "wifi", "run_ping": False,
                    "auto_optimize_wifi": True},
            **dict(self.funcs, optimize=failed),
        )
        self.assertEqual(result["status"], "warning")
        self.assertIn("auto_optimize_wifi", result["errors"])
        self.assertFalse(result["performed"][-1]["verified"])


if __name__ == "__main__":
    unittest.main()

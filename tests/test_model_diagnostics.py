"""Regression tests: realistic differences between ZTE families.

Fixtures contain invented values, no live credentials or customer data.
"""

import unittest
from types import SimpleNamespace
from unittest.mock import patch

from apps.zte_manager.services import model_diagnostic_service as diagnostics
from apps.zte_manager.services import multimodel_service as models
from apps.zte_manager.services.zte_service import ZTEService


def xml(node, records):
    elements = []
    for entry in records:
        props = "".join(
            f"<ParaName>{name}</ParaName><ParaValue>{value}</ParaValue>"
            for name, value in entry.items()
        )
        elements.append(f"<Instance>{props}</Instance>")
    return (
        "<ajax_response_xml_root><IF_ERRORSTR>SUCC</IF_ERRORSTR>"
        f"<{node}>{''.join(elements)}</{node}>"
        "</ajax_response_xml_root>"
    )


class ReadOnlyRouter:
    def __init__(self, response_by_tag):
        self.responses = response_by_tag
        self.calls = []
        self.base_url = "http://lab.invalid"
        self.session = self

    def get_view(self, name, **extras):
        self.calls.append(("view", name))

    def get_menu(self, name, **extras):
        self.calls.append(("menu", name))
        return self.responses[name]

    def get(self, url, params, timeout):
        self.calls.append(("vue", params["_tag"]))
        return SimpleNamespace(
            text=self.responses[params["_tag"]],
            raise_for_status=lambda: None,
        )


class FamilyDiagnosticTests(unittest.TestCase):
    def test_h2640_reports_dsl_separately_not_wan_internet(self):
        router = ReadOnlyRouter({
            "devmgr_statusmgr_lua.lua": xml(
                "OBJ_DEVINFO_ID", [{"ModelName": "H2640",
                                    "SerialNumber": "SECRET"}],
            ),
            "dsl_interface_status_lua.lua": xml(
                "OBJ_DSLINTERFACE_ID",
                [{"Status": "Up", "Downstream_current_rate": "48000",
                  "Upstream_noise_margin": "10.2", "Password": "SECRET"}],
            ),
        })
        report = diagnostics.diagnostic(router, "H2640", include_clients=False)
        self.assertTrue(report["read_only"])
        self.assertTrue(report["sections"]["dsl"]["available"])
        self.assertNotIn("wan", report["sections"])
        self.assertEqual(
            report["sections"]["dsl"]["data"][0]["downstream_kbps"], "48000"
        )
        self.assertNotIn("SECRET", str(report))
        self.assertFalse(any(x[0] == "post" for x in router.calls))

    def test_h388x_reads_alternate_wan_menu(self):
        router = ReadOnlyRouter({
            "devmgr_statusmgr_lua.lua": xml("OBJ_DEVINFO_ID", []),
            "wan_internet_lua.lua": xml(
                "ID_WAN_COMFIG",
                [{"ConnStatus": "Connected", "IPAddress": "private"}],
            ),
        })
        report = diagnostics.diagnostic(router, "H388X", include_clients=False)
        self.assertTrue(report["sections"]["wan"]["available"])
        self.assertEqual(
            report["sections"]["wan"]["data"][0]["status"], "Connected"
        )
        self.assertNotIn("private", str(report))
        self.assertIn(("menu", "wan_internet_lua.lua"), router.calls)

    def test_f8748_wan_counters_not_credentials(self):
        router = ReadOnlyRouter({
            "devmgr_statusmgr_lua.lua": xml("OBJ_DEVINFO_ID", []),
            "wan_internetstatus_lua.lua": xml(
                "ID_WAN_COMFIG",
                [{"ConnStatus": "Connected", "RxBytes": "1024",
                  "Password": "secret", "IPAddress": "192.0.2.1"}],
            ),
        })
        report = diagnostics.diagnostic(router, "F8748", include_clients=False)
        wan = report["sections"]["wan"]["data"][0]
        self.assertEqual(wan["rx_bytes"], "1024")
        self.assertNotIn("Password", wan)
        self.assertNotIn("192.0.2.1", str(report))

    def test_vue_protocol_uses_only_get(self):
        router = ReadOnlyRouter({
            "vue_mainwan_data": xml("ID_WAN_COMFIG", [{"ConnStatus": "Up"}]),
        })
        report = diagnostics.diagnostic(router, "SR7410", include_clients=False)
        self.assertTrue(report["sections"]["wan"]["available"])
        self.assertTrue(all(name == "vue" for name, _ in router.calls))

    def test_unknown_model_never_contacts_router(self):
        router = ReadOnlyRouter({})
        report = diagnostics.diagnostic(router, "F9999")
        self.assertFalse(report["supported"])
        self.assertEqual(router.calls, [])

    def test_session_prevents_cross_model_probes(self):
        service = ZTEService()
        service._zte = ReadOnlyRouter({})
        service._device_info = {"modelo": "H388X"}
        service._selected_model = "H388X"
        with self.assertRaisesRegex(ValueError, "perfil solicitado"):
            service.multimodel_probe("SR7410")
        with self.assertRaisesRegex(ValueError, "perfil solicitado"):
            service.multimodel_diagnostic("F6640")


if __name__ == "__main__":
    unittest.main()

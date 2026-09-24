import unittest
from unittest.mock import patch

from pydantic import ValidationError

from apps.zte_manager.model.zte_configuration import zte_mesh
from apps.zte_manager.schemas import MeshConfigRequest


class FakeMeshZTE:
    def __init__(self):
        self.views = []
        self.menu_tags = []
        self.parsed = {
            "OBJ_NETSPHERE_MAP_ID": [
                {
                    "_InstID": "DEV.MULTIAPCFG",
                    "Mode": "1",
                    "Enable": "1",
                }
            ],
            "OBJ_MAP_MASTER_ID": [
                {
                    "_InstID": "IGD",
                    "EnBandSteer": "1",
                }
            ],
            "OBJ_TEMP_DOMAIN_BS": [
                {
                    "_InstID": "IGD.WiFi.RD1.BS",
                    "BsRssiLmt24G": "-70",
                    "BsRssiLmt5G": "-75",
                }
            ],
        }

    def get_view(
        self,
        view,
        **kwargs,
    ):
        self.views.append(
            (
                view,
                kwargs,
            )
        )

    def get_menu(
        self,
        tag,
        **kwargs,
    ):
        self.menu_tags.append(
            (
                tag,
                kwargs,
            )
        )

        if tag != "wlan_NetSphere_Mode_lua.lua":
            raise RuntimeError(
                "unsupported"
            )

        return "<ajax_response/>"

    def _validar_resposta(
        self,
        xml,
    ):
        return True

    def _parse_instances(
        self,
        xml,
    ):
        return self.parsed


class FakeFallbackMeshZTE(FakeMeshZTE):
    def __init__(self):
        super().__init__()
        self.session_tmp_token = None

    def get_view(
        self,
        view,
        **kwargs,
    ):
        super().get_view(
            view,
            **kwargs,
        )

        if view == "wlanBasic":
            self.session_tmp_token = (
                "fresh-token"
            )

        return "<html></html>"

    def get_menu(
        self,
        tag,
        **kwargs,
    ):
        self.menu_tags.append(
            (
                tag,
                kwargs,
            )
        )

        if (
            tag
            == "wlan_NetSphere_Mode_lua.lua"
            and kwargs.get(
                "_sessionTOKEN"
            )
            == "fresh-token"
        ):
            return "<ajax_response/>"

        raise RuntimeError(
            "A sessão do ZTE expirou ou a view necessária não foi aberta."
        )


class FakeBrazilOiMeshZTE(FakeMeshZTE):
    def __init__(self):
        super().__init__()
        self.session_tmp_token = "token-that-browser-does-not-need"

    def get_view(
        self,
        view,
        **kwargs,
    ):
        self.views.append(
            (
                view,
                kwargs,
            )
        )

        return "<html></html>"

    def get_menu(
        self,
        tag,
        **kwargs,
    ):
        self.menu_tags.append(
            (
                tag,
                kwargs,
            )
        )

        if (
            tag
            == "braziloi_Localnet_NetSphere_Mode_lua.lua"
            and not kwargs
        ):
            return "<ajax_response/>"

        raise RuntimeError(
            "unsupported"
        )


class EasyMeshBackendTests(unittest.TestCase):
    def test_f670l_braziloi_backend_prefers_cookie_only_menu_data(self):
        zte = FakeBrazilOiMeshZTE()

        result = zte_mesh.mesh_status(
            zte
        )

        self.assertTrue(
            result["available"]
        )
        self.assertEqual(
            result["backend"]["tag"],
            "braziloi_Localnet_NetSphere_Mode_lua.lua",
        )
        self.assertEqual(
            result["backend"]["profile"],
            "f670l_v9_braziloi",
        )
        self.assertEqual(
            result["backend"]["menu_auth"],
            "cookie_only",
        )
        self.assertFalse(
            result["backend"]["used_session_token"]
        )

    def test_mesh_status_reads_hidden_netsphere_backend(self):
        zte = FakeMeshZTE()

        result = zte_mesh.mesh_status(
            zte
        )

        self.assertTrue(
            result["available"]
        )
        self.assertTrue(
            result["enabled"]
        )
        self.assertTrue(
            result["band_steering"]
        )
        self.assertEqual(
            result["mode_raw"],
            "1",
        )
        self.assertEqual(
            result["rssi_limit_24g"],
            -70,
        )
        self.assertEqual(
            result["rssi_limit_5g"],
            -75,
        )
        self.assertEqual(
            result["backend"]["tag"],
            "wlan_NetSphere_Mode_lua.lua",
        )

    def test_mesh_probe_falls_back_to_known_view_and_forwards_token(self):
        zte = FakeFallbackMeshZTE()

        result = zte_mesh.mesh_status(
            zte
        )

        self.assertTrue(
            result["available"]
        )
        self.assertEqual(
            result["backend"]["context_view"],
            "wlanBasic",
        )
        self.assertTrue(
            result["backend"]["used_session_token"]
        )
        self.assertIn(
            (
                "wlan_NetSphere_Mode_lua.lua",
                {
                    "_sessionTOKEN": "fresh-token"
                },
            ),
            zte.menu_tags,
        )

    @patch(
        "apps.zte_manager.model.zte_configuration.zte_mesh.post_menu"
    )
    def test_mesh_configuration_preserves_firmware_mode(
        self,
        mocked_post,
    ):
        zte = FakeMeshZTE()
        mocked_post.return_value = (
            "<ajax_response/>"
        )

        result = zte_mesh.configure_mesh(
            zte,
            {
                "enabled": True,
                "band_steering": True,
                "rssi_limit_24g": -68,
                "rssi_limit_5g": -74,
            },
        )

        self.assertTrue(
            result["success"]
        )

        fields = mocked_post.call_args.args[
            2
        ]

        self.assertIn(
            (
                "Mode",
                "1",
            ),
            fields,
        )
        self.assertIn(
            (
                "Enable",
                "1",
            ),
            fields,
        )
        self.assertIn(
            (
                "EnBandSteer",
                "1",
            ),
            fields,
        )
        self.assertIn(
            (
                "BsRssiLmt24G",
                "-68",
            ),
            fields,
        )

    @patch(
        "apps.zte_manager.model.zte_configuration.zte_mesh.post_menu"
    )
    def test_unsupported_optional_mesh_objects_are_not_written(
        self,
        mocked_post,
    ):
        zte = FakeMeshZTE()
        zte.parsed.pop(
            "OBJ_MAP_MASTER_ID"
        )
        zte.parsed.pop(
            "OBJ_TEMP_DOMAIN_BS"
        )
        mocked_post.return_value = (
            "<ajax_response/>"
        )

        zte_mesh.configure_mesh(
            zte,
            {
                "enabled": True,
                "band_steering": True,
                "rssi_limit_24g": -68,
                "rssi_limit_5g": -74,
            },
        )

        fields = mocked_post.call_args.args[
            2
        ]

        names = {
            item[0]
            for item in fields
        }

        self.assertNotIn(
            "EnBandSteer",
            names,
        )
        self.assertNotIn(
            "BsRssiLmt24G",
            names,
        )
        self.assertNotIn(
            "BsRssiLmt5G",
            names,
        )

    @patch(
        "apps.zte_manager.model.zte_configuration.zte_mesh.post_menu"
    )
    def test_pairing_uses_router_wps_button_action(
        self,
        mocked_post,
    ):
        zte = FakeMeshZTE()
        mocked_post.return_value = (
            "<ajax_response/>"
        )

        result = zte_mesh.start_mesh_pairing(
            zte
        )

        self.assertTrue(
            result["success"]
        )

        self.assertEqual(
            mocked_post.call_args.args[
                1
            ],
            "wlan_wps_btn_lua.lua",
        )

        self.assertIn(
            (
                "IF_ACTION",
                "WPSBTN",
            ),
            mocked_post.call_args.args[
                2
            ],
        )

    def test_rssi_schema_rejects_unsafe_value(self):
        with self.assertRaises(
            ValidationError
        ):
            MeshConfigRequest(
                enabled=True,
                rssi_limit_24g=-120,
                confirm=True,
            )


class EasyMeshFrontendContractTests(unittest.TestCase):
    def test_management_ui_contains_mesh_controls(self):
        from pathlib import Path

        root = Path(
            __file__
        ).resolve().parents[1]

        html = (
            root
            / "apps"
            / "zte_manager"
            / "templates"
            / "index.html"
        ).read_text(
            encoding="utf-8"
        )

        js = (
            root
            / "apps"
            / "zte_manager"
            / "static"
            / "js"
            / "management.js"
        ).read_text(
            encoding="utf-8"
        )

        for marker in (
            'data-management-tab="mesh"',
            'id="managementMeshRead"',
            'id="managementMeshApply"',
            'id="managementMeshPair"',
        ):
            self.assertIn(
                marker,
                html,
            )

        for marker in (
            '"/management/mesh"',
            '"/management/mesh/configure"',
            '"/management/mesh/pair"',
        ):
            self.assertIn(
                marker,
                js,
            )


if __name__ == "__main__":
    unittest.main()

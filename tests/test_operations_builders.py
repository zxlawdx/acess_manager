import unittest
from unittest.mock import patch

from apps.zte_manager.model.zte_configuration import (
    zte_advanced,
    zte_wlan_channel_configuration,
)


class OperationsBuilderTests(unittest.TestCase):
    def test_wifi_advanced_fields_are_mapped_without_rebuilding_state(self):
        current = {
            "Band": "5GHz",
            "MUMIMOEnable": "0",
            "DTIM": "1",
            "RtsCts": "2347",
        }

        zte_wlan_channel_configuration._apply_advanced(
            current,
            {
                "mu_mimo": True,
                "uplink_ofdma": True,
                "twt": True,
                "spatial_reuse": False,
                "rts_cts": 500,
                "dtim": 3,
                "preamble_type": "1",
            },
        )

        self.assertEqual(
            current["MUMIMOEnable"],
            "1",
        )
        self.assertEqual(
            current["UPLinkOFDMA"],
            "1",
        )
        self.assertEqual(
            current["TWTSupport"],
            "1",
        )
        self.assertEqual(
            current["SpatialReuse"],
            "0",
        )
        self.assertEqual(
            current["RtsCts"],
            "500",
        )
        self.assertEqual(
            current["DTIM"],
            "3",
        )

    def test_schedule_preserves_radio_states_when_disabling_timer(self):
        initial = {
            "timer_enabled": True,
            "timer_id": "IGD",
            "schedule": {
                "start_hour": "2",
                "start_minute": "0",
                "end_hour": "6",
                "end_minute": "0",
            },
            "radios": [
                {
                    "id": "DEV.WIFI.RD1",
                    "band": "2.4GHz",
                    "enabled": True,
                },
                {
                    "id": "DEV.WIFI.RD2",
                    "band": "5GHz",
                    "enabled": False,
                },
            ],
        }

        verified = {
            "available": True,
            "enabled": False,
            "schedule": initial["schedule"],
            "radios": initial["radios"],
        }

        class FakeZTE:
            def get_view(self, *args, **kwargs):
                return ""

            def _validar_resposta(self, value):
                return value

        with (
            patch.object(
                zte_advanced,
                "radio_power_status",
                return_value=initial,
            ),
            patch.object(
                zte_advanced,
                "wifi_schedule_status",
                return_value=verified,
            ),
            patch.object(
                zte_advanced,
                "post_menu",
                return_value="<IF_ERRORSTR>SUCC</IF_ERRORSTR>",
            ) as post,
        ):
            result = zte_advanced.set_wifi_schedule(
                FakeZTE(),
                {
                    "enabled": False,
                    "start_hour": 2,
                    "start_minute": 0,
                    "end_hour": 6,
                    "end_minute": 0,
                },
            )

        fields = dict(
            post.call_args.args[2]
        )

        self.assertEqual(
            fields["TimerEnable"],
            "0",
        )
        self.assertEqual(
            fields["RadioStatus_0"],
            "1",
        )
        self.assertEqual(
            fields["RadioStatus_1"],
            "0",
        )
        self.assertFalse(
            result["enabled"]
        )


if __name__ == "__main__":
    unittest.main()

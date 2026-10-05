from apps.zte_manager.services.profile_service import (
    HUAWEI_EG8041X7_DEFAULT_PROFILE,
    _normalize_profile,
)


def test_huawei_eg8041x7_default_profile_covers_observed_24g_fields():
    radio = HUAWEI_EG8041X7_DEFAULT_PROFILE["wifi"]["2.4GHz"]

    assert radio == {
        "auto_channel": True,
        "channel": None,
        "standard": "11ax",
        "country": "BR",
        "bandwidth": "Auto",
        "bandwidth_code": "0",
        "sgi": False,
        "beacon_interval": 100,
        "tx_power": "100%",
        "rts_cts": 2346,
        "dtim": 1,
        "airtime_fairness": False,
    }


def test_huawei_eg8041x7_default_profile_covers_observed_5g_fields():
    radio = HUAWEI_EG8041X7_DEFAULT_PROFILE["wifi"]["5GHz"]

    assert radio == {
        "auto_channel": True,
        "channel": None,
        "standard": "11ax",
        "country": "BR",
        "bandwidth": "Auto",
        "bandwidth_code": "4",
        "sgi": False,
        "beacon_interval": 100,
        "tx_power": "100%",
        "rts_cts": 2346,
        "dtim": 1,
        "airtime_fairness": False,
        "band_steering": False,
    }


def test_normalize_huawei_profile_keeps_new_default_radio_fields():
    normalized = _normalize_profile(
        {"wifi": {}},
        default_profile=HUAWEI_EG8041X7_DEFAULT_PROFILE,
    )

    assert normalized["wifi"]["2.4GHz"]["rts_cts"] == 2346
    assert normalized["wifi"]["2.4GHz"]["dtim"] == 1
    assert normalized["wifi"]["2.4GHz"]["airtime_fairness"] is False
    assert normalized["wifi"]["5GHz"]["band_steering"] is False

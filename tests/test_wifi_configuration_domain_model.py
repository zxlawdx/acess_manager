from apps.zte_manager.infrastructure.huawei.wifi import (
    HuaweiWifiMapper,
    HuaweiWifiMappingError,
    eg8041x7_wifi_capabilities,
    eg8041x7_wifi_defaults,
)
from apps.zte_manager.model.wifi import WifiRadioConfiguration
from apps.zte_manager.schemas import WifiRadioRequest
from apps.zte_manager.services.huawei_wifi_domain_runtime import (
    HuaweiWifiDomainRuntimeService,
)


def _records(**values):
    return [{key: value for key, value in values.items()}]


def test_missing_current_values_remain_none_instead_of_defaults():
    current = HuaweiWifiMapper.radio_from_records("2.4ghz", [])
    defaults = eg8041x7_wifi_defaults().radio_2g

    assert current.channel is None
    assert current.channel_width is None
    assert current.mode is None
    assert current.tx_power is None
    assert current.dtim_period is None
    assert current.beacon_period is None
    assert current.rts_threshold is None
    assert defaults.channel == "auto"
    assert defaults.dtim_period == 1
    assert current != defaults


def test_huawei_2g_current_values_are_normalized():
    current = HuaweiWifiMapper.radio_from_records(
        "2.4ghz",
        _records(
            Channel="0",
            AutoChannelEnable="1",
            X_HW_HT20="0",
            X_HW_Standard="11ax",
            TransmitPower="100",
            RegulatoryDomain="BR",
            X_HW_AirtimeFairness="0",
            DtimPeriod="1",
            BeaconPeriod="100",
            RTSThreshold="2346",
        ),
    )

    assert current.channel == "auto"
    assert current.channel_width == "auto_20_40"
    assert current.mode == "b_g_n_ax"
    assert current.tx_power == 100
    assert current.regulatory_domain == "BR"
    assert current.airtime_fairness is False
    assert current.dtim_period == 1
    assert current.beacon_period == 100
    assert current.rts_threshold == 2346


def test_huawei_5g_current_values_are_normalized():
    current = HuaweiWifiMapper.radio_from_records(
        "5ghz",
        _records(
            Channel="36",
            AutoChannelEnable="0",
            X_HW_HT20="4",
            X_HW_Standard="11ax",
            TransmitPower="100",
            RegulatoryDomain="BR",
            X_HW_AirtimeFairness="0",
            BandSteeringPolicy="0",
        ),
    )

    assert current.channel == "36"
    assert current.channel_width == "auto_20_40_80_160"
    assert current.mode == "a_n_ac_ax"
    assert current.band_steering is False


def test_mode_aliases_are_normalized_without_vendor_strings():
    assert HuaweiWifiMapper.mode_from_device("2.4ghz", "802.11b/g/n") == "b_g_n"
    assert HuaweiWifiMapper.mode_from_device("2.4ghz", "b,g,n,ax") == "b_g_n_ax"
    assert HuaweiWifiMapper.mode_from_device("5ghz", "802.11a/n/ac") == "a_n_ac"
    assert HuaweiWifiMapper.mode_from_device("5ghz", "a,n,ac,ax") == "a_n_ac_ax"


def test_channel_normalization_distinguishes_auto_from_fixed_channel():
    assert HuaweiWifiMapper.channel_from_device("0", "1") == "auto"
    assert HuaweiWifiMapper.channel_from_device("11", "0") == "11"
    assert HuaweiWifiMapper.channel_from_device(None, None) is None


def test_channel_width_normalization_maps_only_confirmed_firmware_enums():
    assert HuaweiWifiMapper.channel_width_from_device("2.4ghz", "0") == "auto_20_40"
    assert (
        HuaweiWifiMapper.channel_width_from_device("5ghz", "4")
        == "auto_20_40_80_160"
    )
    assert HuaweiWifiMapper.channel_width_from_device("5ghz", "99") is None


def test_auto_without_dfs_is_a_distinct_5g_supported_value():
    capabilities = eg8041x7_wifi_capabilities().radio_5g
    assert "auto" in capabilities.channel.supported
    assert "auto_without_dfs" in capabilities.channel.supported
    assert "auto" != "auto_without_dfs"


def test_eg8041x7_2g_capabilities_match_observed_surface():
    capabilities = eg8041x7_wifi_capabilities().radio_2g
    assert capabilities.read is True
    assert capabilities.write is True
    assert capabilities.channel.supported == (
        "auto", "1", "2", "3", "4", "5", "6", "7",
        "8", "9", "10", "11", "12", "13",
    )
    assert capabilities.channel_width.supported == ("auto_20_40", "20", "40")
    assert capabilities.mode.supported == ("b", "g", "b_g", "b_g_n", "b_g_n_ax")
    assert capabilities.airtime_fairness is True
    assert capabilities.band_steering is False


def test_eg8041x7_5g_capabilities_include_full_known_sets():
    capabilities = eg8041x7_wifi_capabilities().radio_5g
    assert capabilities.channel.supported[0] == "auto"
    assert capabilities.channel.supported[-1] == "auto_without_dfs"
    assert "144" in capabilities.channel.supported
    assert "161" in capabilities.channel.supported
    assert capabilities.channel_width.supported == (
        "auto_20_40", "20", "40", "auto_20_40_80", "auto_20_40_80_160"
    )
    assert capabilities.mode.supported == ("a", "a_n", "a_n_ac", "a_n_ac_ax")
    assert capabilities.band_steering is True


def test_confirmed_huawei_mapping_round_trip_for_default_width_and_mode():
    radio = WifiRadioConfiguration(
        channel="auto",
        channel_width="auto_20_40",
        mode="b_g_n_ax",
        tx_power=100,
        regulatory_domain="BR",
        dtim_period=1,
        beacon_period=100,
        rts_threshold=2346,
    )
    legacy = HuaweiWifiMapper.to_legacy_radio("2.4ghz", radio)

    assert legacy["auto_channel"] is True
    assert legacy["bandwidth_code"] == "0"
    assert legacy["standard"] == "11ax"
    assert legacy["tx_power"] == 100
    assert legacy["country"] == "BR"
    assert legacy["dtim"] == 1
    assert legacy["beacon_interval"] == 100
    assert legacy["rts_cts"] == 2346


def test_unconfirmed_huawei_width_mapping_fails_closed():
    radio = WifiRadioConfiguration(channel_width="40")
    try:
        HuaweiWifiMapper.to_legacy_radio("5ghz", radio)
    except HuaweiWifiMappingError as exc:
        assert "validação física" in str(exc)
    else:
        raise AssertionError("unconfirmed CGI width enum must not be invented")


def test_legacy_current_shape_keeps_missing_fields_none():
    normalized = HuaweiWifiMapper.radio_from_records("2.4ghz", [])
    current = HuaweiWifiDomainRuntimeService._legacy_current_radio(
        "2.4ghz", [], normalized
    )

    assert current["beacon_interval"] is None
    assert current["rts_cts"] is None
    assert current["dtim"] is None
    assert current["tx_power"] is None
    assert current["country"] is None


def test_legacy_wifi_radio_request_remains_compatible_during_migration():
    request = WifiRadioRequest(
        band="5GHz",
        auto_channel=True,
        standard="11ax",
        country="BR",
        bandwidth="Auto",
        bandwidth_code="4",
        tx_power="100%",
        dtim=1,
        beacon_interval=100,
        rts_cts=2346,
        airtime_fairness=False,
        band_steering=False,
    )

    payload = request.model_dump(exclude_none=True)
    assert payload["band"] == "5GHz"
    assert payload["bandwidth_code"] == "4"
    assert payload["standard"] == "11ax"

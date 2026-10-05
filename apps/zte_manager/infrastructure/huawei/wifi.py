from __future__ import annotations

from dataclasses import replace
from typing import Any, Iterable

from apps.zte_manager.model.wifi import (
    SupportedValueSet,
    WifiCapabilities,
    WifiConfiguration,
    WifiRadioCapabilities,
    WifiRadioConfiguration,
)


class HuaweiWifiMappingError(ValueError):
    pass


def _value(records: Iterable[dict[str, Any]], *keys: str) -> Any | None:
    wanted = {key.casefold() for key in keys}
    for record in records:
        for key, value in record.items():
            if str(key).casefold() in wanted and value not in (None, ""):
                return value
    return None


def _bool01(value: Any | None) -> bool | None:
    if value is None:
        return None
    if value in (True, 1, "1", "true", "True", "on", "ON"):
        return True
    if value in (False, 0, "0", "false", "False", "off", "OFF"):
        return False
    return None


def _int(value: Any | None) -> int | None:
    if value in (None, ""):
        return None
    try:
        return int(str(value).strip().rstrip("%"))
    except (TypeError, ValueError):
        return None


class HuaweiWifiMapper:
    """Translate only mappings confirmed for the EG8041X7-10.

    Unknown Huawei firmware enums are intentionally left unmapped instead of
    guessing a protocol value. The legacy writer remains the fallback for
    still-unvalidated mutations during the migration.
    """

    @staticmethod
    def channel_from_device(channel: Any | None, auto_enabled: Any | None) -> str | None:
        auto = _bool01(auto_enabled)
        raw = None if channel is None else str(channel).strip()
        if auto is True or raw == "0":
            return "auto"
        if raw and raw.isdigit():
            return raw
        return None

    @staticmethod
    def channel_width_from_device(band: str, raw: Any | None) -> str | None:
        value = None if raw is None else str(raw).strip()
        known = {
            ("2.4ghz", "0"): "auto_20_40",
            ("5ghz", "4"): "auto_20_40_80_160",
        }
        if (band, value) in known:
            return known[(band, value)]
        labels = {
            "20 mhz": "20",
            "40 mhz": "40",
            "auto 20/40 mhz": "auto_20_40",
            "auto 20/40/80 mhz": "auto_20_40_80",
            "auto 20/40/80/160 mhz": "auto_20_40_80_160",
        }
        return labels.get(str(raw or "").strip().casefold())

    @staticmethod
    def mode_from_device(band: str, raw: Any | None) -> str | None:
        value = str(raw or "").strip().casefold()
        if not value:
            return None
        if value == "11ax":
            return "b_g_n_ax" if band == "2.4ghz" else "a_n_ac_ax"
        normalized = value.replace("802.11", "").replace(" ", "")
        aliases = {
            "b": "b",
            "g": "g",
            "b,g": "b_g",
            "b/g": "b_g",
            "b,g,n": "b_g_n",
            "b/g/n": "b_g_n",
            "b,g,n,ax": "b_g_n_ax",
            "b/g/n/ax": "b_g_n_ax",
            "a": "a",
            "a,n": "a_n",
            "a/n": "a_n",
            "a,n,ac": "a_n_ac",
            "a/n/ac": "a_n_ac",
            "a,n,ac,ax": "a_n_ac_ax",
            "a/n/ac/ax": "a_n_ac_ax",
        }
        return aliases.get(normalized)

    @classmethod
    def radio_from_records(
        cls,
        band: str,
        records: Iterable[dict[str, Any]],
    ) -> WifiRadioConfiguration:
        rows = list(records)
        channel_raw = _value(rows, "Channel")
        auto_raw = _value(rows, "AutoChannelEnable")
        width_raw = _value(rows, "X_HW_HT20")
        standard_raw = _value(rows, "X_HW_Standard", "Standard")
        steering_raw = _value(rows, "BandSteeringPolicy")
        return WifiRadioConfiguration(
            channel=cls.channel_from_device(channel_raw, auto_raw),
            channel_width=cls.channel_width_from_device(band, width_raw),
            mode=cls.mode_from_device(band, standard_raw),
            tx_power=_int(_value(rows, "TransmitPower")),
            regulatory_domain=(
                str(_value(rows, "RegulatoryDomain")).strip()
                if _value(rows, "RegulatoryDomain") is not None
                else None
            ),
            airtime_fairness=_bool01(_value(rows, "X_HW_AirtimeFairness")),
            band_steering=(
                _bool01(steering_raw) if band == "5ghz" else None
            ),
            dtim_period=_int(_value(rows, "DtimPeriod")),
            beacon_period=_int(_value(rows, "BeaconPeriod")),
            rts_threshold=_int(_value(rows, "RTSThreshold")),
        )

    @staticmethod
    def to_legacy_radio(
        band: str,
        config: WifiRadioConfiguration,
    ) -> dict[str, Any]:
        """Compatibility mapper for the existing Huawei writer.

        Only firmware mappings physically confirmed by the current integration
        are emitted. Unknown mutations fail closed instead of inventing codes.
        """
        legacy: dict[str, Any] = {}
        if config.channel is not None:
            if config.channel == "auto":
                legacy["auto_channel"] = True
                legacy["channel"] = None
            elif config.channel == "auto_without_dfs":
                legacy["auto_channel"] = True
                legacy["auto_channel_scope"] = "requires_physical_validation"
            elif config.channel.isdigit():
                legacy["auto_channel"] = False
                legacy["channel"] = int(config.channel)
            else:
                raise HuaweiWifiMappingError("Canal Huawei não mapeado.")

        if config.channel_width is not None:
            known_width = {
                ("2.4ghz", "auto_20_40"): "0",
                ("5ghz", "auto_20_40_80_160"): "4",
            }
            raw = known_width.get((band, config.channel_width))
            if raw is None:
                raise HuaweiWifiMappingError(
                    "Largura Huawei requer validação física do enum CGI."
                )
            legacy["bandwidth_code"] = raw

        if config.mode is not None:
            known_mode = {
                ("2.4ghz", "b_g_n_ax"): "11ax",
                ("5ghz", "a_n_ac_ax"): "11ax",
            }
            raw_mode = known_mode.get((band, config.mode))
            if raw_mode is None:
                raise HuaweiWifiMappingError(
                    "Modo Huawei requer validação física do enum CGI."
                )
            legacy["standard"] = raw_mode

        mapping = {
            "tx_power": "tx_power",
            "regulatory_domain": "country",
            "airtime_fairness": "airtime_fairness",
            "band_steering": "band_steering",
            "dtim_period": "dtim",
            "beacon_period": "beacon_interval",
            "rts_threshold": "rts_cts",
        }
        for source, target in mapping.items():
            value = getattr(config, source)
            if value is not None:
                legacy[target] = value
        return legacy


def eg8041x7_wifi_defaults() -> WifiConfiguration:
    return WifiConfiguration(
        radio_2g=WifiRadioConfiguration(
            channel="auto",
            channel_width="auto_20_40",
            mode="b_g_n_ax",
            tx_power=100,
            regulatory_domain="BR",
            airtime_fairness=False,
            dtim_period=1,
            beacon_period=100,
            rts_threshold=2346,
        ),
        radio_5g=WifiRadioConfiguration(
            channel="auto",
            channel_width="auto_20_40_80_160",
            mode="a_n_ac_ax",
            tx_power=100,
            regulatory_domain="BR",
            airtime_fairness=False,
            band_steering=False,
            dtim_period=1,
            beacon_period=100,
            rts_threshold=2346,
        ),
    )


def eg8041x7_wifi_capabilities() -> WifiCapabilities:
    return WifiCapabilities(
        radio_2g=WifiRadioCapabilities(
            supported=True,
            read=True,
            write=True,
            channel=SupportedValueSet(
                supported=("auto", *(str(i) for i in range(1, 14))),
                default="auto",
            ),
            channel_width=SupportedValueSet(
                supported=("auto_20_40", "20", "40"),
                default="auto_20_40",
            ),
            mode=SupportedValueSet(
                supported=("b", "g", "b_g", "b_g_n", "b_g_n_ax"),
                default="b_g_n_ax",
            ),
            tx_power=True,
            regulatory_domain=True,
            airtime_fairness=True,
            dtim_period=True,
            beacon_period=True,
            rts_threshold=True,
        ),
        radio_5g=WifiRadioCapabilities(
            supported=True,
            read=True,
            write=True,
            channel=SupportedValueSet(
                supported=(
                    "auto", "36", "40", "44", "48", "52", "56", "60", "64",
                    "100", "104", "108", "112", "116", "120", "124", "128",
                    "132", "136", "140", "144", "149", "153", "157", "161",
                    "auto_without_dfs",
                ),
                default="auto",
            ),
            channel_width=SupportedValueSet(
                supported=(
                    "auto_20_40", "20", "40", "auto_20_40_80",
                    "auto_20_40_80_160",
                ),
                default="auto_20_40_80_160",
            ),
            mode=SupportedValueSet(
                supported=("a", "a_n", "a_n_ac", "a_n_ac_ax"),
                default="a_n_ac_ax",
            ),
            tx_power=True,
            regulatory_domain=True,
            airtime_fairness=True,
            band_steering=True,
            dtim_period=True,
            beacon_period=True,
            rts_threshold=True,
        ),
    )

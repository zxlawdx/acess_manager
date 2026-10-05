from __future__ import annotations

from typing import Any

from apps.zte_manager.infrastructure.huawei.wifi import (
    HuaweiWifiMapper,
    eg8041x7_wifi_capabilities,
    eg8041x7_wifi_defaults,
)
from apps.zte_manager.model.wifi import (
    WifiConfiguration,
    WifiConfigurationDescriptor,
    WifiRadioConfiguration,
)
from apps.zte_manager.services.huawei_captured_features import (
    WLAN_ADV_API_PAGE,
    WLAN_ADV_COMMON_PAGE,
    WLAN_LIST_PAGE,
    _record_domain,
)
from apps.zte_manager.services.huawei_eg8041x7_runtime import (
    HuaweiEG8041X7RuntimeService,
)


class HuaweiWifiDomainRuntimeService(HuaweiEG8041X7RuntimeService):
    """Incremental normalized Wi-Fi facade over the validated Huawei runtime.

    Existing mutation/profile paths remain available through the parent class.
    New readers distinguish observed current state from recommended defaults and
    static supported values.
    """

    @property
    def capabilities(self) -> dict[str, dict]:
        capabilities = super().capabilities
        capabilities["wifi"] = eg8041x7_wifi_capabilities().as_dict()
        return capabilities

    @staticmethod
    def _raw_value(records: list[dict[str, Any]], *keys: str) -> Any | None:
        wanted = {key.casefold() for key in keys}
        for record in records:
            for key, value in record.items():
                if str(key).casefold() in wanted and value not in (None, ""):
                    return value
        return None

    def _raw_wifi_records(self, band: str) -> list[dict[str, Any]]:
        captured = self._require_captured()
        display, instance, _basic_page, adv_page = captured._wifi_pages(band)
        _html, records = captured._records(
            adv_page,
            WLAN_LIST_PAGE,
            WLAN_ADV_COMMON_PAGE,
            WLAN_ADV_API_PAGE,
        )
        exact_domain = (
            "InternetGatewayDevice.LANDevice.1."
            f"WLANConfiguration.{instance}"
        )
        relevant = [
            item
            for item in records
            if (
                _record_domain(item) == exact_domain
                or exact_domain + "." in _record_domain(item)
                or str(item.get("SsidInst") or "") == instance
            )
        ]
        return relevant or records

    def normalized_wifi_configuration(self) -> WifiConfiguration:
        """Return only values actually observed in the Huawei response.

        No recommended/default value is injected here. Missing firmware fields
        remain None by design.
        """
        records_2g = self._raw_wifi_records("2.4GHz")
        records_5g = self._raw_wifi_records("5GHz")
        return WifiConfiguration(
            radio_2g=HuaweiWifiMapper.radio_from_records("2.4ghz", records_2g),
            radio_5g=HuaweiWifiMapper.radio_from_records("5ghz", records_5g),
        )

    def wifi_configuration_descriptor(self) -> dict[str, Any]:
        descriptor = WifiConfigurationDescriptor(
            current=self.normalized_wifi_configuration(),
            defaults=eg8041x7_wifi_defaults(),
            capabilities=eg8041x7_wifi_capabilities(),
        )
        return descriptor.as_dict()

    @classmethod
    def _legacy_current_radio(
        cls,
        band: str,
        records: list[dict[str, Any]],
        normalized: WifiRadioConfiguration,
    ) -> dict[str, Any]:
        width_labels = {
            "20": "20 MHz",
            "40": "40 MHz",
            "auto_20_40": "Auto 20/40 MHz",
            "auto_20_40_80": "Auto 20/40/80 MHz",
            "auto_20_40_80_160": "Auto 20/40/80/160 MHz",
        }
        channel = normalized.channel
        raw_standard = cls._raw_value(records, "X_HW_Standard", "Standard")
        raw_width = cls._raw_value(records, "X_HW_HT20")
        raw_frag = cls._raw_value(records, "FragThreshold")
        raw_scope = cls._raw_value(records, "X_HW_AutoChannelScope")
        raw_steering = cls._raw_value(records, "BandSteeringPolicy")
        return {
            "auto_channel": channel == "auto" if channel is not None else None,
            "channel": (
                None
                if channel in (None, "auto", "auto_without_dfs")
                else int(channel) if channel.isdigit() else channel
            ),
            "standard": str(raw_standard) if raw_standard is not None else None,
            "country": normalized.regulatory_domain,
            "bandwidth": width_labels.get(normalized.channel_width),
            "bandwidth_code": str(raw_width) if raw_width is not None else None,
            "sgi": None,
            "beacon_interval": normalized.beacon_period,
            "tx_power": (
                f"{normalized.tx_power}%"
                if normalized.tx_power is not None
                else None
            ),
            "rts_cts": normalized.rts_threshold,
            "dtim": normalized.dtim_period,
            "frag_threshold": (
                int(raw_frag)
                if raw_frag is not None and str(raw_frag).isdigit()
                else None
            ),
            "band_steering": (
                normalized.band_steering if band == "5ghz" else None
            ),
            "band_steering_policy": (
                str(raw_steering) if raw_steering is not None else None
            ),
            "airtime_fairness": normalized.airtime_fairness,
            "auto_channel_scope": (
                str(raw_scope) if raw_scope is not None else None
            ),
        }

    def current_configuration(self) -> dict:
        """Compatibility payload containing observed values only.

        This intentionally preserves the historical profile shape while
        removing defaults that previously masqueraded as CURRENT values.
        Consumers can migrate to ``wifi_configuration_descriptor`` for the
        normalized contract.
        """
        with self._lock:
            records_2g = self._raw_wifi_records("2.4GHz")
            records_5g = self._raw_wifi_records("5GHz")
            normalized = WifiConfiguration(
                radio_2g=HuaweiWifiMapper.radio_from_records(
                    "2.4ghz", records_2g
                ),
                radio_5g=HuaweiWifiMapper.radio_from_records(
                    "5ghz", records_5g
                ),
            )
            dns = self.dns_status()
            dns.pop("_search_rows", None)
            return {
                "wifi": {
                    "2.4GHz": self._legacy_current_radio(
                        "2.4ghz", records_2g, normalized.radio_2g
                    ),
                    "5GHz": self._legacy_current_radio(
                        "5ghz", records_5g, normalized.radio_5g
                    ),
                },
                "dns": {
                    "domain_name": dns.get("domain_name") or "",
                    "ipv4_1": dns.get("ipv4_1") or "",
                    "ipv4_2": dns.get("ipv4_2") or "",
                    "ipv6_1": dns.get("ipv6_1") or "",
                    "ipv6_2": dns.get("ipv6_2") or "",
                    "hosts": dns.get("hosts") or [],
                },
            }

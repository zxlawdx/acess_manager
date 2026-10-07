from __future__ import annotations

from typing import Any

from apps.zte_manager.infrastructure.huawei import HuaweiFamilyAwareWebClient
from apps.zte_manager.infrastructure.huawei.protocol import (
    HuaweiAuthFlow,
    HuaweiProtocolFamily,
    protocol_family_from_observations,
)
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
from apps.zte_manager.services.huawei_pon import (
    PON_STATE_PAGE,
    HuaweiPonStateReader,
)


class HuaweiWifiDomainRuntimeService(HuaweiEG8041X7RuntimeService):
    """Normalized Huawei runtime plus protocol-family discovery.

    Existing mutation/profile paths remain available through the parent class.
    Wi-Fi readers distinguish observed current state from recommended defaults
    and static supported values. Multi-repo knowledge is added only through
    conservative runtime evidence; a model name never grants a new capability.
    """

    def __init__(self, **kwargs) -> None:
        kwargs.setdefault("client_factory", HuaweiFamilyAwareWebClient)
        super().__init__(**kwargs)
        self._pon_reader: HuaweiPonStateReader | None = None
        self._protocol: dict[str, object] = {
            "family": HuaweiProtocolFamily.UNKNOWN.value,
            "auth_flow": HuaweiAuthFlow.UNKNOWN.value,
            "evidence": [],
        }

    @property
    def capabilities(self) -> dict[str, dict]:
        capabilities = super().capabilities
        capabilities["wifi"] = eg8041x7_wifi_capabilities().as_dict()
        return capabilities

    @property
    def protocol(self) -> dict[str, object]:
        return {
            "family": str(self._protocol.get("family") or "unknown"),
            "auth_flow": str(self._protocol.get("auth_flow") or "unknown"),
            "evidence": list(self._protocol.get("evidence") or []),
        }

    def _refresh_protocol_from_client(self) -> None:
        client = self._client
        descriptor = getattr(client, "protocol_descriptor", None)
        if not callable(descriptor):
            return
        data = descriptor() or {}
        family = str(data.get("family") or "unknown")
        auth_flow = str(data.get("auth_flow") or "unknown")
        evidence = [str(value) for value in data.get("evidence") or () if value]
        if family != HuaweiProtocolFamily.UNKNOWN.value:
            self._protocol["family"] = family
        if auth_flow != HuaweiAuthFlow.UNKNOWN.value:
            self._protocol["auth_flow"] = auth_flow
        self._protocol["evidence"] = list(
            dict.fromkeys([
                *list(self._protocol.get("evidence") or []),
                *evidence,
            ])
        )

    def _pon_operations(self, *, available: bool) -> dict[str, object]:
        return {
            "read": bool(available),
            "write": False,
            "verified": False,
            "state": "READ_SUPPORTED" if available else "UNKNOWN",
            "source": "runtime_probe",
            "external_reference": "siedgustavo/huawei-ont-stats:EG8021V5",
            "physical_validation": False,
        }

    def _read_pon_and_promote(self) -> dict[str, Any]:
        if self._client is None:
            raise RuntimeError("Conecte-se a uma ONT Huawei antes de ler PON.")
        if self._pon_reader is None:
            self._pon_reader = HuaweiPonStateReader(self._client)
        data = self._pon_reader.read()
        self._capabilities["pon"] = self._pon_operations(available=True)
        self._snapshot_store("pon", data)

        family, evidence = protocol_family_from_observations((PON_STATE_PAGE,))
        if (
            str(self._protocol.get("family") or "unknown")
            == HuaweiProtocolFamily.UNKNOWN.value
        ):
            self._protocol["family"] = family.value
        self._protocol["evidence"] = list(
            dict.fromkeys([
                *list(self._protocol.get("evidence") or []),
                *evidence,
            ])
        )
        return data

    def _probe_pon_state(self) -> None:
        if self._client is None:
            return
        self._pon_reader = HuaweiPonStateReader(self._client)
        try:
            self._read_pon_and_promote()
        except Exception:
            self._capabilities["pon"] = self._pon_operations(available=False)

    def connect(self, *args, **kwargs):
        result = super().connect(*args, **kwargs)
        self._refresh_protocol_from_client()
        self._probe_pon_state()
        self._refresh_protocol_from_client()
        result["protocol"] = self.protocol
        result["capabilities"] = self.capabilities
        return result

    def disconnect(self) -> None:
        super().disconnect()
        self._pon_reader = None
        self._protocol = {
            "family": HuaweiProtocolFamily.UNKNOWN.value,
            "auth_flow": HuaweiAuthFlow.UNKNOWN.value,
            "evidence": [],
        }

    def pon_status(self, *, refresh: bool = False) -> dict[str, Any]:
        with self._lock:
            cached = self._snapshot_cached("pon")
            if cached is not None and not refresh:
                return cached
            return self._read_pon_and_promote()

    def _feature_reader(self, feature: str):
        if feature == "pon":
            return self.pon_status
        return super()._feature_reader(feature)

    def capability_catalog(self) -> dict:
        data = super().capability_catalog()
        operations = dict(self._capabilities.get("pon") or {})
        if operations:
            available = bool(operations.get("read"))
            data.setdefault("features", {})["pon"] = {
                "key": "pon",
                "label": "PON / ONT state",
                "writable": False,
                "dangerous": False,
                "notes": (
                    "Capability de leitura promovida somente após probe "
                    "não destrutivo com resposta PON reconhecível."
                ),
                "operations": operations,
                "verified": False,
                "evidence_states": (
                    ["DISCOVERED", "READ_SUPPORTED"]
                    if available
                    else ["UNKNOWN"]
                ),
                "state": "READ_SUPPORTED" if available else "UNKNOWN",
            }
            data.setdefault("state_definitions", {}).update({
                "DISCOVERED": "Endpoint reconhecido por probe não destrutivo.",
                "READ_SUPPORTED": (
                    "Endpoint existe, resposta é reconhecível e parser concluiu."
                ),
                "UNKNOWN": "Sem evidência suficiente para declarar suporte.",
            })
        data["protocol"] = self.protocol
        return data

    def probe_capabilities(self, features=None) -> dict:
        requested = list(features or self._capabilities.keys() or ["ipv4_filter"])
        regular = [feature for feature in requested if feature != "pon"]
        if regular:
            result = super().probe_capabilities(regular)
        else:
            result = {
                "adapter": "huawei-webui",
                "vendor": self.vendor,
                "profile": self.profile_key,
                "features": [],
            }

        if "pon" in requested:
            error = None
            try:
                self.pon_status(refresh=True)
                available = True
            except Exception as exc:
                available = False
                error = type(exc).__name__
                self._capabilities["pon"] = self._pon_operations(available=False)
            operations = dict(self._capabilities.get("pon") or {})
            result["features"].append({
                "feature": "pon",
                "label": "PON / ONT state",
                "available": available,
                "status": "confirmed" if available else "inconclusive",
                "probeable": True,
                "writable": False,
                "dangerous": False,
                "verified": False,
                "operations": operations,
                "error": error,
            })
        result["protocol"] = self.protocol
        return result

    def read_capability(
        self,
        feature: str,
        *,
        refresh: bool = False,
    ) -> dict:
        if feature != "pon":
            return super().read_capability(feature, refresh=refresh)
        with self._lock:
            operations = dict(self._capabilities.get("pon") or {})
            if not operations.get("read"):
                raise ValueError("Capability Huawei PON ainda não confirmada.")
            data = self.pon_status(refresh=refresh)
            return {
                "feature": "pon",
                "label": "PON / ONT state",
                "available": True,
                "writable": False,
                "objects": {"items": data},
                "capability": operations,
                "protocol": self.protocol,
            }

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

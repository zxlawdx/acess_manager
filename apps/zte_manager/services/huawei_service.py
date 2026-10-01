from __future__ import annotations

import logging
from threading import RLock
from uuid import uuid4

from apps.zte_manager.infrastructure.huawei import (
    HuaweiDetector,
    HuaweiWebClient,
)
from apps.zte_manager.model.device_adapters.huawei import (
    HuaweiProfile,
    HuaweiUnknownProfile,
    HuaweiWebAdapter,
    canonical_huawei_model,
    resolve_huawei_profile,
)
from apps.zte_manager.repositories.history_repository import history_repository
from apps.zte_manager.services.attendance_report_service import AttendanceReportService
from apps.zte_manager.services.huawei_ipv4_filter_service import (
    HuaweiIPv4FilterRule,
    HuaweiIPv4FilterService,
)
from apps.zte_manager.services.huawei_captured_features import (
    HuaweiCapturedFeatureService,
)
from apps.zte_manager.services.tr069_profile_service import (
    tr069_provider_profiles,
)

logger = logging.getLogger(__name__)


class HuaweiService:
    vendor = "huawei"

    def __init__(
        self,
        *,
        client_factory=HuaweiWebClient,
        detector=HuaweiDetector,
    ) -> None:
        self._client_factory = client_factory
        self._detector = detector
        self._lock = RLock()
        self._client: HuaweiWebClient | None = None
        self._ipv4_filter: HuaweiIPv4FilterService | None = None
        self._captured: HuaweiCapturedFeatureService | None = None
        self._profile: HuaweiProfile | None = None
        self._capabilities: dict[str, dict[str, bool]] = {}
        self._history_session_id: int | None = None
        self._device_info: dict = {}
        self.current_host: str | None = None
        self.current_attendant: str | None = None
        self.model: str | None = None
        self.model_verified = False
        self.model_source: str | None = None
        self.session_revision = uuid4().hex

    @property
    def connected(self) -> bool:
        return self._client is not None

    @property
    def profile_key(self) -> str | None:
        return self._profile.key if self._profile is not None else None

    @property
    def capabilities(self) -> dict[str, dict[str, bool]]:
        return {
            key: dict(value)
            for key, value in self._capabilities.items()
        }

    @property
    def writes_enabled(self) -> bool:
        return any(
            bool(
                operations.get("create")
                or operations.get("update")
                or operations.get("delete")
                or operations.get("write")
            )
            for operations in self._capabilities.values()
        )

    @property
    def device_info(self) -> dict:
        return dict(self._device_info)

    def connect(
        self,
        ip: str,
        username: str,
        password: str,
        *,
        https: bool = False,
        attendant: str | None = None,
        model_hint: str | None = None,
    ) -> dict:
        with self._lock:
            manual_profile = resolve_huawei_profile(
                model_hint,
                unknown=False,
            )

            if self._can_reuse(ip, username, password, https):
                self.current_attendant = (
                    attendant.strip()
                    if attendant and attendant.strip()
                    else self.current_attendant
                    or "default"
                )
                if manual_profile is not None and (
                    self._profile is None
                    or manual_profile.key != self._profile.key
                ):
                    raise ValueError(
                        "O profile Huawei escolhido mudou. "
                        "Desconecte e conecte novamente."
                    )
                return self._connect_response(reused_session=True)

            self.disconnect()
            client = self._client_factory(
                host=ip,
                username=username,
                password=password,
                https=https,
            )
            client.login()

            detection = self._detector.detect_authenticated(client)
            detected_profile = resolve_huawei_profile(
                detection.model,
                unknown=False,
            )

            if (
                manual_profile is not None
                and detected_profile is not None
                and manual_profile.key != detected_profile.key
            ):
                client.close()
                raise ValueError(
                    "O modelo Huawei escolhido diverge do modelo "
                    "identificado pelo equipamento."
                )

            profile = (
                detected_profile
                or manual_profile
                or HuaweiUnknownProfile(
                    detection.model
                    or model_hint
                    or "Huawei"
                )
            )

            selected_model = (
                profile.model
                if profile.key != "huawei_unknown"
                else canonical_huawei_model(
                    detection.model
                    or model_hint
                    or "Huawei"
                )
                or "Huawei"
            )

            model_verified = bool(
                detected_profile is not None
                or manual_profile is not None
            )
            model_source = (
                "detected"
                if detected_profile is not None
                else "manual_profile"
                if manual_profile is not None
                else "unknown"
            )

            ipv4_filter = HuaweiIPv4FilterService(
                client,
                model=selected_model,
                capability=profile.ipv4_filter,
            )
            operations = profile.ipv4_filter.as_dict()

            # Unknown Huawei devices may expose the read page, but the lab
            # evidence must never be generalized into write permission.
            if profile.key == "huawei_unknown":
                probed = ipv4_filter.capability(
                    probe_read=True
                )
                operations["read"] = bool(
                    probed.get("read")
                )
                operations["create"] = False
                operations["update"] = False
                operations["delete"] = False
                operations["verified"] = False

            captured = HuaweiCapturedFeatureService(
                client,
                model=selected_model,
            )

            feature_capabilities: dict[str, dict[str, bool]] = {
                "ipv4_filter": operations,
                **{
                    key: dict(value)
                    for key, value in profile.captured_features.items()
                },
            }

            self._client = client
            self._ipv4_filter = ipv4_filter
            self._captured = captured
            self._profile = profile
            self._capabilities = feature_capabilities
            self.current_host = ip
            self.current_attendant = (
                attendant.strip()
                if attendant and attendant.strip()
                else "default"
            )
            self.model = selected_model
            self.model_verified = model_verified
            self.model_source = model_source
            self.session_revision = uuid4().hex
            self._device_info = {
                "fabricante": "Huawei",
                "modelo": selected_model,
            }

            logger.info("[device-detect] vendor=huawei")
            logger.info(
                "[device-detect] model_raw=%s",
                detection.model_raw or model_hint or "unknown",
            )
            logger.info(
                "[device-detect] model_normalized=%s",
                selected_model,
            )
            logger.info(
                "[device-profile] selected=%s",
                profile.key,
            )
            logger.info(
                "[device-capability] ipv4_filter "
                "read=%d create=%d update=%d delete=%d verified=%d",
                int(bool(operations.get("read"))),
                int(bool(operations.get("create"))),
                int(bool(operations.get("update"))),
                int(bool(operations.get("delete"))),
                int(bool(operations.get("verified"))),
            )

            self._start_history()
            return self._connect_response(reused_session=False)

    def _can_reuse(
        self,
        ip: str,
        username: str,
        password: str,
        https: bool,
    ) -> bool:
        if self._client is None:
            return False
        scheme = "https" if https else "http"
        raw = ip.rstrip("/")
        base = (
            raw
            if raw.startswith(("http://", "https://"))
            else f"{scheme}://{raw}"
        )
        return bool(
            self._client.base_url == base
            and self._client.username == username
            and self._client.password == password
        )

    def _connect_response(
        self,
        *,
        reused_session: bool,
    ) -> dict:
        return {
            "success": True,
            "vendor": self.vendor,
            "host": self.current_host,
            "attendant": self.current_attendant,
            "reused_session": reused_session,
            "model": self.model,
            "model_verified": self.model_verified,
            "model_source": self.model_source,
            "profile": self.profile_key,
            "provider": type(self).__name__,
            "session_revision": self.session_revision,
            "writes_enabled": self.writes_enabled,
            "device": self.device_info,
            "adapter": "huawei-webui",
            "capabilities": self.capabilities,
        }

    def _start_history(self) -> None:
        try:
            self._history_session_id = history_repository.start_session(
                host=self.current_host,
                attendant=self.current_attendant,
                device=self._device_info,
            )
        except Exception as exc:
            logger.warning(
                "history_start_failed provider=huawei error_type=%s",
                type(exc).__name__,
            )
            self._history_session_id = None
            return

        try:
            history_repository.save_snapshot(
                self._history_session_id,
                "connect",
                {
                    "device": self._device_info,
                    "provider": type(self).__name__,
                    "profile": self.profile_key,
                    "capabilities": self.capabilities,
                },
            )
        except Exception as exc:
            logger.warning(
                "history_snapshot_failed provider=huawei error_type=%s",
                type(exc).__name__,
            )

    def disconnect(self) -> None:
        with self._lock:
            if self._history_session_id is not None:
                try:
                    history_repository.end_session(
                        self._history_session_id
                    )
                except Exception as exc:
                    logger.warning(
                        "history_end_failed provider=huawei error_type=%s",
                        type(exc).__name__,
                    )

            if self._client is not None:
                try:
                    self._client.close()
                except Exception as exc:
                    logger.warning(
                        "huawei_session_close_failed error_type=%s",
                        type(exc).__name__,
                    )

            self._client = None
            self._ipv4_filter = None
            self._captured = None
            self._profile = None
            self._capabilities = {}
            self._history_session_id = None
            self._device_info = {}
            self.current_host = None
            self.current_attendant = None
            self.model = None
            self.model_verified = False
            self.model_source = None
            self.session_revision = uuid4().hex

    def _require_ipv4_filter(self) -> HuaweiIPv4FilterService:
        if self._ipv4_filter is None:
            raise RuntimeError(
                "Conecte-se a uma ONT Huawei antes de usar IPv4 Filtering."
            )
        return self._ipv4_filter

    def _require_captured(self) -> HuaweiCapturedFeatureService:
        if self._captured is None or self._profile is None:
            raise RuntimeError(
                "Conecte-se a uma ONT Huawei antes de consultar este recurso."
            )
        if self._profile.key != "huawei_eg8041x7_10":
            raise PermissionError(
                "Este recurso ainda não foi validado para o modelo Huawei conectado."
            )
        return self._captured

    def _audit_captured(
        self,
        *,
        operation: str,
        target: str,
        result: dict,
        after: dict | list | None = None,
    ) -> None:
        if self._history_session_id is None:
            return
        verified = bool(result.get("verified"))
        outcome = (
            "verified"
            if verified
            else "uncertain"
            if result.get("uncertain")
            else "failed"
        )
        try:
            history_repository.save_change(
                self._history_session_id,
                operation=operation,
                target=str(target or "")[:128],
                before=None,
                after=after,
                success=verified,
                message=(
                    "Read-back semântico Huawei"
                    if verified
                    else "device_result_not_confirmed"
                ),
                outcome=outcome,
            )
        except Exception as exc:
            logger.warning(
                "huawei_audit_failed operation=%s error_type=%s",
                operation,
                type(exc).__name__,
            )

    @staticmethod
    def _rule_from_config(
        config,
        *,
        domain: str = "",
    ) -> HuaweiIPv4FilterRule:
        if not isinstance(config, dict):
            raise ValueError(
                "Parâmetros IPv4 Filtering inválidos."
            )
        return HuaweiIPv4FilterRule(
            domain=domain,
            name=str(config.get("name") or ""),
            protocol=str(config.get("protocol") or ""),
            direction=str(config.get("direction") or ""),
            lan_start_ip=str(config.get("lan_start_ip") or ""),
            lan_end_ip=str(config.get("lan_end_ip") or ""),
            wan_start_ip=str(config.get("wan_start_ip") or ""),
            wan_end_ip=str(config.get("wan_end_ip") or ""),
            lan_tcp_port=str(config.get("lan_tcp_port") or ""),
            lan_udp_port=str(config.get("lan_udp_port") or ""),
            wan_tcp_port=str(config.get("wan_tcp_port") or ""),
            wan_udp_port=str(config.get("wan_udp_port") or ""),
        )

    def device_status(self) -> dict:
        """Return the authenticated Huawei session identity without ZTE probes."""
        with self._lock:
            if not self.connected:
                raise RuntimeError(
                    "Conecte-se a uma ONT Huawei antes de consultar o equipamento."
                )
            return {
                "fabricante": "Huawei",
                "modelo": self.model or self._device_info.get("modelo") or "Huawei",
                "host": self.current_host,
                "profile": self.profile_key,
                "provider": type(self).__name__,
                "model_verified": self.model_verified,
                "capabilities": self.capabilities,
            }

    # =========================================================
    # HUAWEI CAPTURED FEATURES — EG8041X7-10
    # =========================================================

    def optical_status(self):
        with self._lock:
            return self._require_captured().optical_status()

    def wan_status(self):
        with self._lock:
            return self._require_captured().wan_status()

    def pppoe_status(self, reveal_password=False):
        with self._lock:
            return self._require_captured().pppoe_status(
                reveal_password=reveal_password
            )

    def lan_clients(self):
        with self._lock:
            return self._require_captured().lan_clients()

    def wifi_clients(self):
        with self._lock:
            return self._require_captured().wifi_clients()

    def lan_ports(self):
        with self._lock:
            return self._require_captured().lan_ports()

    def wifi_networks(self, reveal_password=False):
        with self._lock:
            return self._require_captured().wifi_networks(
                reveal_password=reveal_password
            )

    def set_ssid_config(self, ssid_id, config):
        with self._lock:
            result = self._require_captured().set_ssid_config(
                ssid_id,
                config,
            )
            self._audit_captured(
                operation="huawei_wifi_basic_update",
                target=str(ssid_id),
                result=result,
                after={
                    key: value
                    for key, value in dict(config or {}).items()
                    if key != "password"
                },
            )
            return result

    def wifi_radios(self):
        with self._lock:
            return self._require_captured().wifi_radios()

    def wifi_channels(self, band=None, bandwidth=None, country="BRI"):
        with self._lock:
            return self._require_captured().wifi_channels(
                band=band,
                bandwidth=bandwidth,
                country=country,
            )

    def set_wifi_radio(self, band, config):
        with self._lock:
            result = self._require_captured().set_wifi_radio(
                band,
                config,
            )
            self._audit_captured(
                operation="huawei_wifi_radio_update",
                target=str(band),
                result=result,
                after=dict(config or {}),
            )
            return result

    def radio_power_status(self):
        with self._lock:
            return self._require_captured().radio_power_status()

    def set_radio_power(self, band, enabled):
        with self._lock:
            result = self._require_captured().set_radio_power(
                band,
                enabled,
            )
            self._audit_captured(
                operation="huawei_wifi_power",
                target=str(band),
                result=result,
                after={"enabled": bool(enabled)},
            )
            return result

    def dhcp_status(self):
        with self._lock:
            return self._require_captured().dhcp_status()

    def set_dhcp_basic(self, config):
        with self._lock:
            result = self._require_captured().set_dhcp_basic(
                dict(config or {})
            )
            self._audit_captured(
                operation="huawei_dhcp_update",
                target="LAN / DHCP",
                result=result,
                after=dict(config or {}),
            )
            return result

    def save_dhcp_reservation(self, config):
        raise PermissionError(
            "A captura validou edição de reserva existente, não CREATE de reserva DHCP Huawei."
        )

    def delete_dhcp_reservation(self, instance_id):
        raise PermissionError(
            "DELETE de reserva DHCP Huawei ainda não foi capturado."
        )

    def dns_status(self):
        with self._lock:
            result = self._require_captured().dns_status()
            result.pop("_search_rows", None)
            return result

    def set_dns(self, config):
        with self._lock:
            result = self._require_captured().set_dns(
                dict(config or {})
            )
            safe = {
                key: value
                for key, value in dict(config or {}).items()
                if "pass" not in str(key).lower()
            }
            self._audit_captured(
                operation="huawei_dns_update",
                target="DNS",
                result=result,
                after=safe,
            )
            return result

    def dmz_status(self):
        with self._lock:
            status = self._require_captured().dmz_status()
            if not status.get("available"):
                return []
            return [{
                "_InstID": status.get("id") or "",
                "Enable": "1" if status.get("enabled") else "0",
                "InternalClient": status.get("internal_client") or "",
                "WANCViewName": status.get("wan") or "",
            }]

    def set_dmz(self, config):
        with self._lock:
            result = self._require_captured().set_dmz(
                dict(config or {})
            )
            self._audit_captured(
                operation="huawei_dmz_update",
                target="DMZ",
                result=result,
                after=dict(config or {}),
            )
            return result

    def tr069_management_status(self):
        with self._lock:
            return self._require_captured().tr069_management_status()

    def tr069_setup(self):
        with self._lock:
            return self._require_captured().tr069_setup()

    def set_management_tr069(self, config, *, confirm=True):
        with self._lock:
            result = self._require_captured().set_management_tr069(
                dict(config or {}),
                confirm=confirm,
            )
            self._audit_captured(
                operation="huawei_tr069_url_update",
                target="ACS",
                result=result,
                after={
                    "url": (
                        dict(config or {}).get("url")
                        or dict(config or {}).get("URL")
                    )
                },
            )
            return result

    def apply_tr069_provider(
        self,
        name: str,
        wan_name: str,
        *,
        password=None,
        connection_request_password=None,
    ):
        # The physical capture validated the ACS URL mutation only.
        # Keep existing Huawei credentials untouched instead of inventing
        # username/password form parameters that were never captured.
        profiles = tr069_provider_profiles.list()
        profile = next(
            (item for item in profiles if item.get("name") == name),
            None,
        )
        if not profile:
            raise ValueError("Perfil ACS não encontrado.")
        url = str(profile.get("url") or "").strip()
        if not url:
            raise ValueError("O perfil ACS não possui URL.")
        setup = self.tr069_setup()
        candidates = setup.get("wan_candidates") or []
        if candidates and wan_name and not any(
            item.get("name") == wan_name
            for item in candidates
        ):
            raise ValueError(
                "A WAN selecionada não foi identificada como TR069 na Huawei."
            )
        return self.set_management_tr069(
            {"url": url},
            confirm=True,
        )

    def firewall_management_status(self):
        with self._lock:
            return self._require_captured().firewall_management_status()

    def set_management_firewall(self, config, *, confirm=False):
        with self._lock:
            result = self._require_captured().set_management_firewall(
                dict(config or {}),
                confirm=confirm,
            )
            self._audit_captured(
                operation="huawei_firewall_level_update",
                target="Firewall",
                result=result,
                after=dict(config or {}),
            )
            return result

    def account_status(self):
        return {
            "available": False,
            "vendor": "huawei",
            "message": (
                "A captura atual não validou leitura/alteração da conta administrativa Huawei."
            ),
        }

    def upnp_status(self):
        return {
            "available": False,
            "vendor": "huawei",
            "message": "UPnP Huawei ainda não foi validado nesta captura.",
        }

    def set_upnp(self, config):
        raise PermissionError(
            "UPnP Huawei ainda não foi validado nesta captura."
        )

    def wps_status(self):
        return []

    def set_wps(self, band, mode):
        raise PermissionError(
            "Alteração WPS Huawei ainda não foi validada."
        )

    def band_steering_status(self):
        return {
            "available": False,
            "vendor": "huawei",
        }

    def set_band_steering(self, enabled):
        raise PermissionError(
            "Band Steering Huawei ainda não foi validado semanticamente."
        )

    def configure_band_steering(self, config):
        raise PermissionError(
            "Band Steering Huawei ainda não foi validado semanticamente."
        )

    def list_ipv4_filters(self) -> dict:
        with self._lock:
            result = self._require_ipv4_filter().list_ipv4_filters()
            # The session profile is authoritative for write permissions.
            result["capability"] = dict(
                self._capabilities.get("ipv4_filter") or {}
            )
            result["vendor"] = self.vendor
            result["model"] = self.model
            result["profile"] = self.profile_key
            return result

    def create_ipv4_filter(self, config) -> dict:
        with self._lock:
            rule = self._rule_from_config(config)
            result = self._require_ipv4_filter().create_ipv4_filter(rule)
            self._audit_ipv4_filter(
                operation="huawei_ipv4_filter_create",
                target=rule.name,
                before=None,
                after=result.get("rule") or rule.as_dict(),
                result=result,
            )
            return result

    def update_ipv4_filter(
        self,
        instance_or_domain,
        config,
    ) -> dict:
        with self._lock:
            service = self._require_ipv4_filter()
            current = service.list_ipv4_filters().get("rules", [])
            domain = str(instance_or_domain)
            before = next(
                (
                    item
                    for item in current
                    if item.get("domain") == domain
                    or item.get("domain", "").endswith("." + domain)
                ),
                None,
            )
            rule = self._rule_from_config(
                config,
                domain=domain,
            )
            result = service.update_ipv4_filter(
                instance_or_domain,
                rule,
            )
            self._audit_ipv4_filter(
                operation="huawei_ipv4_filter_update",
                target=rule.name,
                before=before,
                after=result.get("rule") or rule.as_dict(),
                result=result,
            )
            return result

    def delete_ipv4_filter(
        self,
        instance_or_domain,
    ) -> dict:
        with self._lock:
            result = self._require_ipv4_filter().delete_ipv4_filter(
                instance_or_domain
            )
            previous = result.get("previous")
            self._audit_ipv4_filter(
                operation="huawei_ipv4_filter_delete",
                target=(
                    previous.get("name")
                    if isinstance(previous, dict)
                    else str(instance_or_domain)
                ),
                before=previous,
                after=None,
                result=result,
            )
            return result

    def _audit_ipv4_filter(
        self,
        *,
        operation,
        target,
        before,
        after,
        result,
    ) -> None:
        if self._history_session_id is None:
            return
        outcome = (
            "verified"
            if result.get("verified")
            else "uncertain"
            if result.get("uncertain")
            else "failed"
        )
        history_repository.save_change(
            self._history_session_id,
            operation=operation,
            target=str(target or "")[:128],
            before=before,
            after=after,
            success=bool(result.get("verified")),
            message=(
                "Read-back semântico Huawei"
                if result.get("verified")
                else result.get("error")
            ),
            outcome=outcome,
        )

    def _feature_reader(self, feature: str):
        readers = {
            "ipv4_filter": self.list_ipv4_filters,
            "wan": self.wan_status,
            "optical": self.optical_status,
            "dhcp": self.dhcp_status,
            "dns": self.dns_status,
            "dmz": self.dmz_status,
            "wifi_basic": self.wifi_networks,
            "wifi_radio": self.wifi_radios,
            "tr069_url": self.tr069_management_status,
            "firewall_level": self.firewall_management_status,
            "alg": self.firewall_management_status,
            "igmp": self.firewall_management_status,
            "dos": self.firewall_management_status,
        }
        try:
            return readers[feature]
        except KeyError as exc:
            raise ValueError(
                f"Capability Huawei desconhecida: {feature}."
            ) from exc

    def capability_catalog(self) -> dict:
        with self._lock:
            if self._profile is None:
                raise RuntimeError(
                    "Conecte-se a uma ONT Huawei antes de consultar capabilities."
                )
            adapter = HuaweiWebAdapter(
                self.model,
                profile=self._profile,
            )
            data = adapter.describe()
            for key, feature in data.get("features", {}).items():
                operations = dict(
                    self._capabilities.get(key) or {}
                )
                feature["operations"] = operations
                feature["verified"] = bool(
                    operations.get("verified")
                )
                feature["writable"] = bool(
                    operations.get("create")
                    or operations.get("update")
                    or operations.get("delete")
                    or operations.get("write")
                )
            data["vendor"] = self.vendor
            data["profile"] = self.profile_key
            return data

    def probe_capabilities(self, features=None) -> dict:
        with self._lock:
            requested = list(
                features
                or self._capabilities.keys()
                or ["ipv4_filter"]
            )
            unknown = [
                feature
                for feature in requested
                if feature not in self._capabilities
            ]
            if unknown:
                raise ValueError(
                    "Capabilities Huawei desconhecidas: "
                    + ", ".join(unknown)
                )

            results = []
            for feature in requested:
                operations = dict(
                    self._capabilities.get(feature) or {}
                )
                available = bool(operations.get("read"))
                error = None
                if available:
                    try:
                        self._feature_reader(feature)()
                    except Exception as exc:
                        available = False
                        error = type(exc).__name__

                if (
                    feature == "ipv4_filter"
                    and self._profile is not None
                    and self._profile.key == "huawei_unknown"
                ):
                    probe = self._require_ipv4_filter().capability(
                        probe_read=True
                    )
                    available = bool(probe.get("read"))
                    operations["read"] = available
                    operations["create"] = False
                    operations["update"] = False
                    operations["delete"] = False
                    operations["verified"] = False
                    self._capabilities[feature] = operations

                results.append({
                    "feature": feature,
                    "label": (
                        HuaweiWebAdapter(
                            self.model,
                            profile=self._profile,
                        )
                        .features[feature]
                        .label
                    ),
                    "available": available,
                    "status": (
                        "confirmed"
                        if available
                        else "inconclusive"
                    ),
                    "probeable": True,
                    "writable": bool(
                        operations.get("create")
                        or operations.get("update")
                        or operations.get("delete")
                        or operations.get("write")
                    ),
                    "dangerous": bool(
                        HuaweiWebAdapter(
                            self.model,
                            profile=self._profile,
                        )
                        .features[feature]
                        .dangerous
                    ),
                    "verified": bool(
                        operations.get("verified")
                    ),
                    "operations": operations,
                    "error": error,
                })

            return {
                "adapter": "huawei-webui",
                "vendor": self.vendor,
                "profile": self.profile_key,
                "features": results,
            }

    def capability_shape(self, feature: str) -> dict:
        with self._lock:
            operations = dict(
                self._capabilities.get(feature) or {}
            )
            if not operations:
                raise ValueError(
                    "Capability Huawei desconhecida."
                )
            data = self._feature_reader(feature)()
            if isinstance(data, list):
                count = len(data)
                keys = sorted({
                    key
                    for row in data
                    if isinstance(row, dict)
                    for key in row
                    if not str(key).startswith("_")
                })
            elif isinstance(data, dict):
                count = 1
                keys = sorted(
                    key
                    for key in data
                    if not str(key).startswith("_")
                )
            else:
                count = 0
                keys = []
            return {
                "feature": feature,
                "available": True,
                "count": count,
                "keys": keys,
            }

    def read_capability(self, feature: str) -> dict:
        with self._lock:
            operations = dict(
                self._capabilities.get(feature) or {}
            )
            if not operations:
                raise ValueError(
                    "Capability Huawei desconhecida."
                )
            data = self._feature_reader(feature)()
            spec = HuaweiWebAdapter(
                self.model,
                profile=self._profile,
            ).features[feature]
            return {
                "feature": feature,
                "label": spec.label,
                "available": True,
                "writable": bool(
                    operations.get("create")
                    or operations.get("update")
                    or operations.get("delete")
                    or operations.get("write")
                ),
                "objects": {
                    "items": data
                },
                "capability": operations,
            }

    def generate_attendance(self, diagnostic_id=None) -> dict:
        with self._lock:
            if not self._history_session_id:
                raise RuntimeError(
                    "Conecte-se ao equipamento antes de gerar a OS."
                )
            timeline = history_repository.session_timeline(
                self._history_session_id
            )
            diagnostic = history_repository.diagnostic(
                diagnostic_id,
                session_id=self._history_session_id,
            )
            if diagnostic_id and (
                not diagnostic
                or diagnostic.get("session_id")
                != self._history_session_id
            ):
                raise ValueError(
                    "Diagnóstico não pertence à sessão atual."
                )
            if not diagnostic:
                diagnostic = {
                    "mode": "general",
                    "sections": {},
                    "findings": [],
                    "status": "info",
                }
            report = AttendanceReportService().build(
                diagnostic=diagnostic,
                timeline=timeline,
            )
            return {
                **report,
                "diagnostic_id": diagnostic.get("history_id"),
                "session_id": self._history_session_id,
            }

    def capture_snapshot(
        self,
        reason="manual",
    ) -> dict:
        with self._lock:
            if self._history_session_id is None:
                raise RuntimeError(
                    "Conecte-se ao equipamento antes de capturar histórico."
                )
            payload = {
                "device": self.device_info,
                "provider": type(self).__name__,
                "profile": self.profile_key,
                "capabilities": self.capabilities,
            }
            try:
                payload["ipv4_filter"] = self.list_ipv4_filters()
                partial = False
            except Exception as exc:
                payload["ipv4_filter"] = {
                    "_error": type(exc).__name__
                }
                partial = True
            snapshot_id = history_repository.save_snapshot(
                self._history_session_id,
                reason,
                payload,
            )
            return {
                "success": True,
                "snapshot_id": snapshot_id,
                "payload": payload,
                "partial": partial,
                "failed_sections": (
                    ["ipv4_filter"] if partial else []
                ),
            }

    def history(self, limit=50):
        return history_repository.recent(limit)

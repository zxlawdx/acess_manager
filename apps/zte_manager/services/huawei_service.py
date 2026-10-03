from __future__ import annotations

import ast
import logging
import re
import time
from copy import deepcopy
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
    HUAWEI_EG8041X7_FULLY_INTEGRATED,
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
from apps.zte_manager.services.huawei_mapped_surface import (
    HUAWEI_MAPPED_FEATURES,
    HUAWEI_MAPPED_WRITES,
    HuaweiMappedSurfaceService,
)
from apps.zte_manager.services.tr069_profile_service import (
    tr069_provider_profiles,
)
from apps.zte_manager.services.profile_service import (
    profile_service,
)
from apps.zte_manager.services.named_preset_service import (
    named_preset_service,
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
        self._mapped: HuaweiMappedSurfaceService | None = None
        self._profile: HuaweiProfile | None = None
        self._capabilities: dict[str, dict[str, bool]] = {}
        self._history_session_id: int | None = None
        self._device_info: dict = {}
        # Parsed/normalized state for exactly one authenticated Huawei
        # session. Never store raw HTML, cookies, credentials or X_HW_Token.
        self._session_snapshot: dict[str, object] = {}
        self._snapshot_identity: tuple[str, ...] | None = None
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

    _SNAPSHOT_SECRET_FIELDS = frozenset({
        "password", "passwd", "pass_word", "pppoe_password",
        "pppoepassword", "wifi_password", "wifipassword",
        "acs_password", "connection_request_password",
        "cookie", "cookiehttp", "authorization",
        "x_hw_token", "hwonttoken", "onttoken", "token",
        "psk", "wpa_psk", "pre_shared_key", "presharedkey",
        "keypassphrase", "secret", "credential", "senha",
    })

    @classmethod
    def _snapshot_secret_key(cls, key: object) -> bool:
        normalized = str(key).strip().casefold().replace("-", "_")
        compact = normalized.replace("_", "")
        if normalized in {"password_hidden", "has_password", "secret_exists"}:
            return False
        if normalized in cls._SNAPSHOT_SECRET_FIELDS:
            return True
        if (
            compact.endswith("password")
            or compact.endswith("passwd")
            or compact.endswith("token")
            or compact.endswith("secret")
            or compact.endswith("credential")
            or "presharedkey" in compact
            or compact.endswith("psk")
        ):
            return True
        return False

    @classmethod
    def _snapshot_safe(cls, value):
        """Return a cache-safe copy of normalized provider data."""
        if isinstance(value, dict):
            safe = {}
            for key, item in value.items():
                if cls._snapshot_secret_key(key):
                    continue
                safe[str(key)] = cls._snapshot_safe(item)
            return safe
        if isinstance(value, (list, tuple)):
            return [cls._snapshot_safe(item) for item in value]
        return deepcopy(value)

    def _current_snapshot_identity(self) -> tuple[str, ...]:
        return (
            self.vendor,
            str(self.current_host or ""),
            str(self.model or ""),
            str(self.profile_key or ""),
            str(self.session_revision or ""),
        )

    def _clear_session_snapshot(self) -> None:
        self._session_snapshot = {}
        self._snapshot_identity = None

    def _ensure_session_snapshot(self) -> None:
        identity = self._current_snapshot_identity()
        if self._snapshot_identity != identity:
            self._session_snapshot = {}
            self._snapshot_identity = identity

    def _snapshot_cached(self, key: str):
        self._ensure_session_snapshot()
        if key not in self._session_snapshot:
            return None
        return deepcopy(self._session_snapshot[key])

    def _snapshot_store(self, key: str, value):
        self._ensure_session_snapshot()
        safe = self._snapshot_safe(value)
        self._session_snapshot[key] = safe
        return deepcopy(safe)

    def _snapshot_read(self, key: str, loader, *, refresh: bool = False):
        cached = None if refresh else self._snapshot_cached(key)
        if cached is not None:
            return cached
        return self._snapshot_store(key, loader())

    def _snapshot_patch_list(
        self,
        key: str,
        item: dict,
        *,
        identity_fields: tuple[str, ...],
    ) -> list[dict]:
        current = self._snapshot_cached(key)
        rows = list(current) if isinstance(current, list) else []
        replacement = self._snapshot_safe(item)
        replaced = False
        for index, row in enumerate(rows):
            if not isinstance(row, dict):
                continue
            if any(
                str(row.get(field) or "") == str(replacement.get(field) or "")
                and replacement.get(field) not in (None, "")
                for field in identity_fields
            ):
                rows[index] = replacement
                replaced = True
                break
        if not replaced:
            rows.append(replacement)
        return self._snapshot_store(key, rows)

    def session_snapshot(self) -> dict:
        """Public normalized session state; never causes router I/O."""
        with self._lock:
            self._ensure_session_snapshot()
            return {
                "vendor": self.vendor,
                "host": self.current_host,
                "model": self.model,
                "profile": self.profile_key,
                "session_revision": self.session_revision,
                "loaded_resources": sorted(self._session_snapshot),
                "state": deepcopy(self._session_snapshot),
            }

    def warm_session_snapshot(self, *, refresh: bool = False) -> dict:
        """Load the normalized state for all integrated Huawei read domains.

        This is the only broad read pass. Ordinary navigation consumes the
        resulting snapshot and explicit refreshes remain resource-scoped.
        Derived readers (DHCP static, DNS hosts, radio power, TR-069 setup)
        are intentionally omitted because their source resource is already
        loaded here.
        """
        with self._lock:
            if not self.connected:
                raise RuntimeError(
                    "Conecte-se a uma ONT Huawei antes de carregar a sessão."
                )

            readers = (
                ("device", self.device_status),
                ("optical", self.optical_status),
                ("wan", self.wan_status),
                ("pppoe", self.pppoe_status),
                ("lan_clients", self.lan_clients),
                ("wifi_clients", self.wifi_clients),
                ("lan_ports", self.lan_ports),
                ("wifi_networks", self.wifi_networks),
                ("wifi_radios", self.wifi_radios),
                ("layer3", self.layer3_status),
                ("lan_ipv4", self.lan_ipv4_status),
                ("ipv6_lan", self.ipv6_lan_status),
                ("dhcp", self.dhcp_status),
                ("dns", self.dns_status),
                ("dmz", self.dmz_status),
                ("tr069", self.tr069_management_status),
                ("firewall_level", self.firewall_level_status),
                ("alg", self.alg_status),
                ("igmp", self.igmp_status),
                ("dos", self.dos_status),
                ("ipv6_firewall", self.ipv6_firewall_status),
                ("internet_control", self.internet_control_status),
                ("ipv4_filter", self.list_ipv4_filters),
            )

            loaded: list[str] = []
            cached: list[str] = []
            failed: dict[str, str] = {}
            for key, reader in readers:
                if not refresh and self._snapshot_cached(key) is not None:
                    cached.append(key)
                    continue
                try:
                    reader(refresh=refresh)
                    loaded.append(key)
                except Exception as exc:
                    failed[key] = type(exc).__name__
                    logger.warning(
                        "huawei_snapshot_warm_failed resource=%s error_type=%s",
                        key,
                        type(exc).__name__,
                    )

            snapshot = self.session_snapshot()
            return {
                "success": not failed,
                "partial": bool(failed),
                "loaded": loaded,
                "cached": cached,
                "failed": failed,
                "loaded_resources": snapshot["loaded_resources"],
                "session_revision": self.session_revision,
            }

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
            mapped = HuaweiMappedSurfaceService(
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
            self._mapped = mapped
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
            self._clear_session_snapshot()
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
            self._mapped = None
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
            self._clear_session_snapshot()

    def _require_ipv4_filter(self) -> HuaweiIPv4FilterService:
        if self._ipv4_filter is None:
            raise RuntimeError(
                "Conecte-se a uma ONT Huawei antes de usar IPv4 Filtering."
            )
        return self._ipv4_filter

    def _require_captured(self) -> HuaweiCapturedFeatureService:
        if self._captured is None:
            raise RuntimeError(
                "Conecte-se a uma ONT Huawei antes de consultar este recurso."
            )
        return self._captured

    def _require_mapped(self) -> HuaweiMappedSurfaceService:
        if self._mapped is None:
            raise RuntimeError(
                "Conecte-se a uma ONT Huawei antes de consultar o mapeamento WebUI."
            )
        return self._mapped

    def _audit_captured(
        self,
        *,
        operation: str,
        target: str,
        result: dict,
        before: dict | list | None = None,
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
            audit_after = self._snapshot_safe(after)
            if isinstance(audit_after, dict):
                audit_after = dict(audit_after)
                audit_after["_verified"] = verified
                if result.get("readback") is not None:
                    audit_after["_readback"] = self._snapshot_safe(
                        result.get("readback")
                    )
            history_repository.save_change(
                self._history_session_id,
                operation=operation,
                target=str(target or "")[:128],
                before=self._snapshot_safe(before),
                after=audit_after,
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

    def device_status(self, *, refresh: bool = False) -> dict:
        """Return identity from the parsed session snapshot."""
        with self._lock:
            if not self.connected:
                raise RuntimeError(
                    "Conecte-se a uma ONT Huawei antes de consultar o equipamento."
                )

            def load():
                details: dict = {}
                try:
                    details = self._require_captured().device_status()
                except Exception as exc:
                    logger.warning(
                        "huawei_device_status_partial error_type=%s",
                        type(exc).__name__,
                    )

                raw_uptime = details.get("uptime")
                uptime_days = None
                try:
                    if raw_uptime not in (None, ""):
                        uptime_days = int(float(raw_uptime)) // 86400
                except (TypeError, ValueError):
                    uptime_days = None

                return {
                    **details,
                    "fabricante": details.get("fabricante") or "Huawei",
                    "modelo": (
                        details.get("modelo")
                        or self.model
                        or self._device_info.get("modelo")
                        or "Huawei"
                    ),
                    "host": self.current_host,
                    "profile": self.profile_key,
                    "provider": type(self).__name__,
                    "model_verified": self.model_verified,
                    "capabilities": self.capabilities,
                    "uptime_dias": uptime_days,
                    "cpu": details.get("cpu") or {},
                }

            return self._snapshot_read(
                "device", load, refresh=refresh
            )

    # =========================================================
    # HUAWEI CAPTURED FEATURES — EG8041X7-10
    # =========================================================

    def current_configuration(self) -> dict:
        with self._lock:
            radios = {
                item["banda"]: item
                for item in self.wifi_radios()
            }
            dns = self.dns_status()
            dns.pop("_search_rows", None)

            wifi: dict[str, dict] = {}
            for band in ("2.4GHz", "5GHz"):
                radio = radios.get(band) or {}
                channel = str(radio.get("canal") or "0")
                auto = bool(
                    radio.get("canal_automatico")
                    or channel in {"", "0", "Auto"}
                )
                wifi[band] = {
                    "auto_channel": auto,
                    "channel": (
                        None
                        if auto
                        else int(channel)
                        if channel.isdigit()
                        else channel
                    ),
                    "standard": radio.get("padrao") or "",
                    "country": radio.get("pais") or "BR",
                    "bandwidth": radio.get("largura") or "Auto",
                    "bandwidth_code": radio.get("bandwidth_code") or "",
                    "sgi": bool(radio.get("sgi", False)),
                    "beacon_interval": int(
                        radio.get("beacon_interval") or 100
                    ),
                    "tx_power": radio.get("potencia") or "100%",
                    "rts_cts": int(radio.get("rts_cts") or 2346),
                    "dtim": int(radio.get("dtim") or 1),
                    "frag_threshold": int(
                        radio.get("frag_threshold") or 2346
                    ),
                    "band_steering": bool(
                        radio.get("band_steering", False)
                    ),
                    "band_steering_policy": (
                        radio.get("band_steering_policy") or ""
                    ),
                    "airtime_fairness": bool(
                        radio.get("airtime_fairness", False)
                    ),
                    "auto_channel_scope": (
                        radio.get("auto_channel_scope") or ""
                    ),
                }

            return {
                "wifi": wifi,
                "dns": {
                    "domain_name": dns.get("domain_name") or "",
                    "ipv4_1": dns.get("ipv4_1") or "",
                    "ipv4_2": dns.get("ipv4_2") or "",
                    "ipv6_1": dns.get("ipv6_1") or "",
                    "ipv6_2": dns.get("ipv6_2") or "",
                    "hosts": dns.get("hosts") or [],
                },
            }

    def capture_profile(self, attendant=None):
        with self._lock:
            owner = (
                attendant
                or self.current_attendant
                or "default"
            )
            return profile_service.save_profile(
                owner,
                self.current_configuration(),
            )

    def _apply_profile_payload(
        self,
        profile: dict,
        *,
        operation: str,
        target: str,
    ) -> dict:
        captured = self._require_captured()
        steps: list[dict] = []
        omitted: list[str] = []

        for band in ("2.4GHz", "5GHz"):
            config = dict(
                (profile.get("wifi") or {}).get(band)
                or {}
            )
            if not config:
                continue

            # Ignore only vendor-specific fields that do not exist in the Huawei
            # WLAN Advanced form. Every captured Huawei field stays writable.
            supported = {
                "auto_channel",
                "channel",
                "country",
                "tx_power",
                "beacon_interval",
                "rts_cts",
                "dtim",
                "frag_threshold",
                "band_steering",
                "band_steering_policy",
                "airtime_fairness",
                "auto_channel_scope",
                "bandwidth_code",
                "bandwidth",
                "standard",
                "sgi",
            }
            safe_config = {
                key: value
                for key, value in config.items()
                if key in supported and value is not None
            }
            for key in config:
                if (
                    key not in supported
                    and config.get(key) not in (None, "", False)
                ):
                    omitted.append(f"Wi-Fi {band}: {key}")

            # Perfis históricos usam BRI; a WebUI Huawei capturada submeteu BR.
            if str(safe_config.get("country") or "").upper() == "BRI":
                safe_config["country"] = "BR"

            try:
                result = captured.set_wifi_radio(
                    band,
                    safe_config,
                )
                verified = bool(result.get("verified"))
                if verified and isinstance(result.get("readback"), dict):
                    self._snapshot_patch_list(
                        "wifi_radios",
                        result["readback"],
                        identity_fields=("banda", "id"),
                    )
                steps.append({
                    "name": f"Wi-Fi {band}",
                    "success": verified,
                    "verified": verified,
                    "detail": (
                        "Canal/RF confirmado por read-back."
                        if verified
                        else "A alteração não foi confirmada pela releitura."
                    ),
                })
            except Exception as exc:
                steps.append({
                    "name": f"Wi-Fi {band}",
                    "success": False,
                    "verified": False,
                    "detail": str(exc),
                })
                break

        if all(step.get("success") for step in steps):
            dns = dict(profile.get("dns") or {})
            if dns:
                try:
                    result = captured.set_dns(dns)
                    verified = bool(result.get("verified"))
                    if verified and isinstance(result.get("readback"), dict):
                        readback = dict(result["readback"])
                        readback.pop("_search_rows", None)
                        self._snapshot_store("dns", readback)
                    steps.append({
                        "name": "DNS / hosts",
                        "success": verified,
                        "verified": verified,
                        "detail": (
                            "DNS e hosts confirmados por read-back."
                            if verified
                            else "A alteração DNS não foi confirmada."
                        ),
                    })
                except Exception as exc:
                    steps.append({
                        "name": "DNS / hosts",
                        "success": False,
                        "verified": False,
                        "detail": str(exc),
                    })

        success = bool(steps) and all(
            bool(step.get("success"))
            for step in steps
        )
        result = {
            "success": success,
            "verified": success,
            "audit_outcome": (
                "verified"
                if success
                else "failed"
            ),
            "steps": steps,
            "not_included": omitted,
        }
        self._audit_captured(
            operation=operation,
            target=target,
            result=result,
            after=profile,
        )
        return result

    def apply_profile(self, attendant=None):
        with self._lock:
            owner = (
                attendant
                or self.current_attendant
                or "default"
            )
            return self._apply_profile_payload(
                profile_service.get_profile(owner),
                operation="huawei_profile_apply",
                target=owner,
            )

    def apply_named_preset(self, attendant: str, name: str):
        with self._lock:
            profile = named_preset_service.get(
                attendant,
                name,
            )
            return self._apply_profile_payload(
                profile,
                operation="huawei_named_profile_apply",
                target=name,
            )

    def optical_status(self, *, refresh: bool = False):
        with self._lock:
            return self._snapshot_read(
                "optical",
                self._require_captured().optical_status,
                refresh=refresh,
            )

    def wan_status(self, *, refresh: bool = False):
        with self._lock:
            return self._snapshot_read(
                "wan",
                self._require_captured().wan_status,
                refresh=refresh,
            )

    def pppoe_status(
        self,
        reveal_password=False,
        *,
        refresh: bool = False,
    ):
        with self._lock:
            if reveal_password:
                # Explicit operator action may return the live password, but
                # this branch never stores the result in the session snapshot
                # or history.
                return self._require_captured().pppoe_status(
                    reveal_password=True
                )
            return self._snapshot_read(
                "pppoe",
                lambda: self._require_captured().pppoe_status(
                    reveal_password=False
                ),
                refresh=refresh,
            )

    def lan_clients(self, *, refresh: bool = False):
        with self._lock:
            return self._snapshot_read(
                "lan_clients",
                self._require_captured().lan_clients,
                refresh=refresh,
            )

    def wifi_clients(self, *, refresh: bool = False):
        with self._lock:
            return self._snapshot_read(
                "wifi_clients",
                self._require_captured().wifi_clients,
                refresh=refresh,
            )

    def lan_ports(self, *, refresh: bool = False):
        with self._lock:
            return self._snapshot_read(
                "lan_ports",
                self._require_captured().lan_ports,
                refresh=refresh,
            )

    def wifi_networks(
        self,
        reveal_password=False,
        *,
        refresh: bool = False,
    ):
        with self._lock:
            # The validated Huawei parser never exposes the PSK. Keep this
            # path snapshot-backed even if the generic UI asks to reveal it.
            return self._snapshot_read(
                "wifi_networks",
                lambda: self._require_captured().wifi_networks(
                    reveal_password=False
                ),
                refresh=refresh,
            )

    def set_ssid_config(self, ssid_id, config):
        with self._lock:
            cached = self._snapshot_cached("wifi_networks") or []
            before = next(
                (
                    item for item in cached
                    if str(item.get("id") or "") == str(ssid_id)
                ),
                None,
            )
            result = self._require_captured().set_ssid_config(
                ssid_id,
                config,
            )
            if result.get("verified") and isinstance(
                result.get("readback"), dict
            ):
                self._snapshot_patch_list(
                    "wifi_networks",
                    result["readback"],
                    identity_fields=("id", "banda"),
                )
            self._audit_captured(
                operation="huawei_wifi_basic_update",
                target=str(ssid_id),
                result=result,
                before=before,
                after={
                    key: value
                    for key, value in dict(config or {}).items()
                    if key != "password"
                },
            )
            result["snapshot_resource"] = "wifi_networks"
            return result

    def wifi_radios(self, *, refresh: bool = False):
        with self._lock:
            return self._snapshot_read(
                "wifi_radios",
                self._require_captured().wifi_radios,
                refresh=refresh,
            )

    def wifi_channels(self, band=None, bandwidth=None, country="BRI"):
        with self._lock:
            return self._require_captured().wifi_channels(
                band=band,
                bandwidth=bandwidth,
                country=country,
            )

    def set_wifi_radio(self, band, config):
        with self._lock:
            cached = self._snapshot_cached("wifi_radios") or []
            before = next(
                (
                    item for item in cached
                    if str(item.get("banda") or "") == str(band)
                ),
                None,
            )
            result = self._require_captured().set_wifi_radio(
                band,
                config,
            )
            if result.get("verified") and isinstance(
                result.get("readback"), dict
            ):
                self._snapshot_patch_list(
                    "wifi_radios",
                    result["readback"],
                    identity_fields=("banda", "id"),
                )
            self._audit_captured(
                operation="huawei_wifi_radio_update",
                target=str(band),
                result=result,
                before=before,
                after=dict(config or {}),
            )
            result["snapshot_resource"] = "wifi_radios"
            return result

    def radio_power_status(self, *, refresh: bool = False):
        with self._lock:
            return [
                {
                    "band": item.get("banda"),
                    "enabled": bool(item.get("ativo")),
                }
                for item in self.wifi_networks(refresh=refresh)
            ]

    def set_radio_power(self, band, enabled):
        with self._lock:
            cached = self._snapshot_cached("wifi_networks") or []
            before = next(
                (
                    item for item in cached
                    if str(item.get("banda") or "") == str(band)
                ),
                None,
            )
            result = self._require_captured().set_radio_power(
                band,
                enabled,
            )
            if result.get("verified") and isinstance(
                result.get("readback"), dict
            ):
                self._snapshot_patch_list(
                    "wifi_networks",
                    result["readback"],
                    identity_fields=("id", "banda"),
                )
            self._audit_captured(
                operation="huawei_wifi_power",
                target=str(band),
                result=result,
                before=before,
                after={"enabled": bool(enabled)},
            )
            result["snapshot_resource"] = "wifi_networks"
            return result

    def wifi_schedule_status(self):
        with self._lock:
            return self._require_mapped().read_feature(
                "wifi_schedule"
            )

    def set_wifi_schedule(self, config):
        with self._lock:
            values = dict(config or {})
            request = values.pop("_request", None)
            if isinstance(request, dict):
                return self.mapped_write_request(
                    request.get("path"),
                    request.get("payload") or values,
                    referer=(
                        request.get("referer")
                        or "/html/amp/wifische/WlanSchedule.asp"
                    ),
                    token_page=(
                        request.get("token_page")
                        or "/html/amp/wifische/WlanSchedule.asp"
                    ),
                    readback_path=(
                        request.get("readback_path")
                        or "/html/amp/wifische/WlanSchedule.asp"
                    ),
                )
            raise ValueError(
                "O material mapeado não contém um payload semântico de "
                "agenda Wi-Fi; use /huawei/mapped/write com a requisição "
                "capturada exata."
            )

    def layer3_status(self, *, refresh: bool = False):
        with self._lock:
            return self._snapshot_read(
                "layer3",
                self._require_captured().layer3_status,
                refresh=refresh,
            )

    def lan_ipv4_status(self, *, refresh: bool = False):
        with self._lock:
            return self._snapshot_read(
                "lan_ipv4",
                self._require_captured().lan_ipv4_status,
                refresh=refresh,
            )

    def ipv6_lan_status(self, *, refresh: bool = False):
        with self._lock:
            return self._snapshot_read(
                "ipv6_lan",
                self._require_captured().ipv6_lan_status,
                refresh=refresh,
            )

    def dhcp_static_status(self, *, refresh: bool = False):
        with self._lock:
            return {
                "reservations": (
                    self.dhcp_status(refresh=refresh)
                    .get("reservations")
                    or []
                )
            }

    def dns_host_status(self, *, refresh: bool = False):
        with self._lock:
            return {
                "hosts": (
                    self.dns_status(refresh=refresh)
                    .get("hosts")
                    or []
                )
            }

    def dhcp_status(self, *, refresh: bool = False):
        with self._lock:
            return self._snapshot_read(
                "dhcp",
                self._require_captured().dhcp_status,
                refresh=refresh,
            )

    def set_dhcp_basic(self, config):
        with self._lock:
            cached = self._snapshot_cached("dhcp") or {}
            before = deepcopy(cached.get("basic"))
            result = self._require_captured().set_dhcp_basic(
                dict(config or {})
            )
            readback = result.get("readback")
            if result.get("verified") and isinstance(readback, dict):
                updated = deepcopy(cached)
                updated["basic"] = readback
                self._snapshot_store("dhcp", updated)
            self._audit_captured(
                operation="huawei_dhcp_update",
                target="LAN / DHCP",
                result=result,
                before=before,
                after=dict(config or {}),
            )
            result["snapshot_resource"] = "dhcp"
            return result

    def save_dhcp_reservation(self, config):
        with self._lock:
            values = dict(config or {})
            instance_id = values.get("id")
            cached = self._snapshot_cached("dhcp") or {}
            before = next(
                (
                    row for row in cached.get("reservations") or []
                    if str(row.get("_InstID") or "") == str(instance_id)
                    or str(row.get("_InstID") or "").endswith(
                        "." + str(instance_id)
                    )
                ),
                None,
            ) if instance_id else None
            if instance_id:
                result = self._require_captured().update_dhcp_reservation(
                    instance_id,
                    ip=str(values.get("ip") or ""),
                    mac=str(values.get("mac") or ""),
                )
            else:
                result = self._require_captured().create_dhcp_reservation(
                    ip=str(values.get("ip") or ""),
                    mac=str(values.get("mac") or ""),
                )
            readback = result.get("readback")
            if result.get("verified") and isinstance(readback, dict):
                updated = deepcopy(cached)
                rows = list(updated.get("reservations") or [])
                matched = False
                for index, row in enumerate(rows):
                    if (
                        row.get("_InstID") == readback.get("_InstID")
                        or (
                            readback.get("_InstID")
                            and str(row.get("_InstID") or "").endswith(
                                "." + str(readback["_InstID"]).split(".")[-1]
                            )
                        )
                    ):
                        rows[index] = readback
                        matched = True
                        break
                if not matched:
                    rows.append(readback)
                updated["reservations"] = rows
                self._snapshot_store("dhcp", updated)
            self._audit_captured(
                operation=(
                    "huawei_dhcp_static_update"
                    if instance_id
                    else "huawei_dhcp_static_create"
                ),
                target=str(instance_id or "new"),
                result=result,
                before=before,
                after={
                    "ip": values.get("ip"),
                    "mac": values.get("mac"),
                },
            )
            result["snapshot_resource"] = "dhcp"
            return result

    def delete_dhcp_reservation(self, instance_id):
        with self._lock:
            cached = self._snapshot_cached("dhcp") or {}
            before = next(
                (
                    row for row in cached.get("reservations") or []
                    if str(row.get("_InstID") or "") == str(instance_id)
                    or str(row.get("_InstID") or "").endswith(
                        "." + str(instance_id)
                    )
                ),
                None,
            )
            result = self._require_captured().delete_dhcp_reservation(
                instance_id
            )
            if result.get("verified"):
                deleted = str(
                    (result.get("readback") or {}).get("deleted")
                    or instance_id
                )
                updated = deepcopy(cached)
                updated["reservations"] = [
                    row
                    for row in updated.get("reservations") or []
                    if (
                        str(row.get("_InstID") or "") != deleted
                        and not str(row.get("_InstID") or "").endswith(
                            "." + deleted.split(".")[-1]
                        )
                    )
                ]
                self._snapshot_store("dhcp", updated)
            self._audit_captured(
                operation="huawei_dhcp_static_delete",
                target=str(instance_id),
                result=result,
                before=before,
                after={"deleted": str(instance_id)},
            )
            result["snapshot_resource"] = "dhcp"
            return result

    def dns_status(self, *, refresh: bool = False):
        with self._lock:
            def load():
                result = self._require_captured().dns_status()
                result.pop("_search_rows", None)
                return result
            return self._snapshot_read(
                "dns", load, refresh=refresh
            )

    def set_dns(self, config):
        with self._lock:
            before = self._snapshot_cached("dns")
            result = self._require_captured().set_dns(
                dict(config or {})
            )
            readback = result.get("readback")
            if result.get("verified") and isinstance(readback, dict):
                readback = dict(readback)
                readback.pop("_search_rows", None)
                self._snapshot_store("dns", readback)
            safe = {
                key: value
                for key, value in dict(config or {}).items()
                if "pass" not in str(key).lower()
            }
            self._audit_captured(
                operation="huawei_dns_update",
                target="DNS",
                result=result,
                before=before,
                after=safe,
            )
            result["snapshot_resource"] = "dns"
            return result

    def dmz_status(self, *, refresh: bool = False):
        with self._lock:
            def load():
                status = self._require_captured().dmz_status()
                if not status.get("available"):
                    return []
                return [{
                    "_InstID": status.get("id") or "",
                    "Enable": "1" if status.get("enabled") else "0",
                    "InternalClient": status.get("internal_client") or "",
                    "WANCViewName": status.get("wan") or "",
                }]
            return self._snapshot_read(
                "dmz", load, refresh=refresh
            )

    def set_dmz(self, config):
        with self._lock:
            before = self._snapshot_cached("dmz")
            result = self._require_captured().set_dmz(
                dict(config or {})
            )
            readback = result.get("readback")
            if result.get("verified") and isinstance(readback, dict):
                public = [] if not readback.get("available") else [{
                    "_InstID": readback.get("id") or "",
                    "Enable": "1" if readback.get("enabled") else "0",
                    "InternalClient": readback.get("internal_client") or "",
                    "WANCViewName": readback.get("wan") or "",
                }]
                self._snapshot_store("dmz", public)
            self._audit_captured(
                operation="huawei_dmz_update",
                target="DMZ",
                result=result,
                before=before,
                after=dict(config or {}),
            )
            result["snapshot_resource"] = "dmz"
            return result

    def tr069_management_status(self, *, refresh: bool = False):
        with self._lock:
            return self._snapshot_read(
                "tr069",
                self._require_captured().tr069_management_status,
                refresh=refresh,
            )

    def tr069_setup(self, *, refresh: bool = False):
        with self._lock:
            status = self.tr069_management_status(refresh=refresh)
            server = status.get("server") or {}
            return {
                "available": status.get("available") is True,
                "acs_secret_exists": True,
                "request_secret_exists": True,
                "wan_candidates": [
                    {
                        "name": item.get("nome") or item.get("id"),
                        "services": item.get("services") or "",
                    }
                    for item in self.wan_status(refresh=refresh)
                    if "TR069" in str(
                        item.get("services") or ""
                    ).upper()
                ],
                "current": {
                    key: server.get(key)
                    for key in (
                        "URL", "UserName", "PeriodicInformEnable",
                        "PeriodicInformInterval", "DefaultWan",
                        "ConnectionRequestUsername",
                    )
                },
                "limited": True,
                "note": (
                    "Captura Huawei validou alteração da URL ACS; "
                    "credenciais TR-069 permanecem preservadas."
                ),
            }

    def set_management_tr069(self, config, *, confirm=True):
        with self._lock:
            before = self._snapshot_cached("tr069")
            result = self._require_captured().set_management_tr069(
                dict(config or {}),
                confirm=confirm,
            )
            if result.get("verified") and isinstance(
                result.get("readback"), dict
            ):
                self._snapshot_store("tr069", result["readback"])
            self._audit_captured(
                operation="huawei_tr069_url_update",
                target="ACS",
                result=result,
                before=before,
                after={
                    "url": (
                        dict(config or {}).get("url")
                        or dict(config or {}).get("URL")
                    )
                },
            )
            result["snapshot_resource"] = "tr069"
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

    def alg_status(self, *, refresh: bool = False):
        with self._lock:
            return self._snapshot_read(
                "alg",
                self._require_captured().alg_status,
                refresh=refresh,
            )

    def igmp_status(self, *, refresh: bool = False):
        with self._lock:
            return self._snapshot_read(
                "igmp",
                self._require_captured().igmp_status,
                refresh=refresh,
            )

    def dos_status(self, *, refresh: bool = False):
        with self._lock:
            return self._snapshot_read(
                "dos",
                self._require_captured().dos_status,
                refresh=refresh,
            )

    def ipv6_firewall_status(self, *, refresh: bool = False):
        with self._lock:
            return self._snapshot_read(
                "ipv6_firewall",
                self._require_captured().ipv6_firewall_status,
                refresh=refresh,
            )

    def internet_control_status(self, *, refresh: bool = False):
        with self._lock:
            return self._snapshot_read(
                "internet_control",
                self._require_captured().internet_control_status,
                refresh=refresh,
            )

    def update_captured_feature(self, feature: str, config: dict):
        with self._lock:
            service = self._require_captured()
            values = dict(config or {})
            before = self._snapshot_cached(feature)
            writers = {
                "layer3": service.set_layer3_ports,
                "lan_ipv4": service.set_lan_ipv4,
                "ipv6_lan": service.set_ipv6_lan,
                "alg": service.set_alg,
                "igmp": service.set_igmp,
                "dos": service.set_dos,
                "ipv6_firewall": service.set_ipv6_firewall,
                "internet_control": service.set_internet_control,
                "firewall_level": service.set_management_firewall,
            }

            capability = dict(
                self._capabilities.get(feature)
                or {}
            )
            if (
                feature not in self._capabilities
                and feature not in HUAWEI_MAPPED_FEATURES
            ):
                raise ValueError(
                    f"Capability Huawei desconhecida: {feature}."
                )

            if feature == "dhcp_static":
                action = str(
                    values.pop("action", None)
                    or values.pop("_action", None)
                    or "update"
                ).strip().lower()
                instance = (
                    values.pop("id", None)
                    or values.pop("instance_or_domain", None)
                )
                if action in {"delete", "remove"}:
                    if not instance:
                        raise ValueError(
                            "Informe id/instance_or_domain da reserva DHCP Huawei."
                        )
                    result = service.delete_dhcp_reservation(instance)
                elif instance:
                    result = service.update_dhcp_reservation(
                        instance,
                        ip=str(values.get("ip") or values.get("Yiaddr") or ""),
                        mac=str(values.get("mac") or values.get("Chaddr") or ""),
                    )
                else:
                    result = service.create_dhcp_reservation(
                        ip=str(values.get("ip") or values.get("Yiaddr") or ""),
                        mac=str(values.get("mac") or values.get("Chaddr") or ""),
                    )
            elif feature == "dns_host":
                action = str(
                    values.pop("action", None)
                    or values.pop("_action", None)
                    or "update"
                ).strip().lower()
                instance = (
                    values.pop("id", None)
                    or values.pop("instance_or_domain", None)
                )
                if action in {"delete", "remove"}:
                    if not instance:
                        raise ValueError(
                            "Informe id/instance_or_domain do DNS Host Huawei."
                        )
                    result = service.delete_dns_host(instance)
                elif instance:
                    result = service.update_dns_host(
                        instance,
                        ip=str(values.get("ip") or values.get("IPAddress") or ""),
                        domain_name=str(
                            values.get("domain_name")
                            or values.get("DomainName")
                            or values.get("name")
                            or ""
                        ),
                    )
                else:
                    result = service.create_dns_host(
                        ip=str(values.get("ip") or values.get("IPAddress") or ""),
                        domain_name=str(
                            values.get("domain_name")
                            or values.get("DomainName")
                            or values.get("name")
                            or ""
                        ),
                    )
            elif feature in HUAWEI_MAPPED_WRITES:
                result = self.mapped_write_feature(
                    feature,
                    values,
                )
            elif feature == "diagnostics_webui":
                operation = str(
                    values.pop("operation", "diagnostics_run")
                )
                result = self.mapped_write_feature(
                    operation,
                    values,
                )
            else:
                try:
                    writer = writers[feature]
                except KeyError as exc:
                    # No model/profile denial here. A captured raw request can
                    # be supplied for any mapped page using _request.
                    request = values.pop("_request", None)
                    if isinstance(request, dict):
                        result = self.mapped_write_request(
                            request.get("path"),
                            request.get("payload") or values,
                            referer=request.get("referer") or "/index.asp",
                            token_page=request.get("token_page"),
                            readback_path=request.get("readback_path"),
                            readback_method=request.get("readback_method") or "GET",
                            readback_payload=request.get("readback_payload") or {},
                        )
                    else:
                        raise ValueError(
                            "Informe _request com o endpoint Huawei mapeado "
                            f"para a capability {feature}."
                        ) from exc
                else:
                    result = writer(values)
            readback = result.get("readback")
            if result.get("verified") and isinstance(readback, dict):
                if feature == "dhcp_static":
                    state = self._snapshot_cached("dhcp") or {}
                    rows = list(state.get("reservations") or [])
                    deleted = str(readback.get("deleted") or "")
                    if deleted:
                        rows = [
                            row for row in rows
                            if str(row.get("_InstID") or "") != deleted
                            and not str(row.get("_InstID") or "").endswith(
                                "." + deleted.split(".")[-1]
                            )
                        ]
                    else:
                        replaced = False
                        for index, row in enumerate(rows):
                            if row.get("_InstID") == readback.get("_InstID"):
                                rows[index] = readback
                                replaced = True
                                break
                        if not replaced:
                            rows.append(readback)
                    state["reservations"] = rows
                    self._snapshot_store("dhcp", state)
                elif feature == "dns_host":
                    state = self._snapshot_cached("dns") or {}
                    rows = list(state.get("hosts") or [])
                    deleted = str(readback.get("deleted") or "")
                    if deleted:
                        rows = [
                            row
                            for row in rows
                            if str(row.get("id") or "") != deleted
                        ]
                    else:
                        replaced = False
                        for index, row in enumerate(rows):
                            if row.get("id") == readback.get("id"):
                                rows[index] = readback
                                replaced = True
                                break
                        if not replaced:
                            rows.append(readback)
                    state["hosts"] = rows
                    self._snapshot_store("dns", state)
                elif feature == "firewall_level":
                    self._snapshot_store(
                        "firewall_level",
                        {
                            "available": True,
                            "firewall": readback,
                        },
                    )
                else:
                    self._snapshot_store(feature, readback)
            self._audit_captured(
                operation=f"huawei_{feature}_update",
                target=feature,
                result=result,
                before=before,
                after=dict(config or {}),
            )
            result["snapshot_resource"] = (
                "dhcp" if feature == "dhcp_static"
                else "dns" if feature == "dns_host"
                else feature
            )
            return result

    def firewall_level_status(self, *, refresh: bool = False):
        with self._lock:
            return self._snapshot_read(
                "firewall_level",
                self._require_captured().firewall_level_status,
                refresh=refresh,
            )

    def firewall_management_status(self, *, refresh: bool = False):
        """Compatibility aggregate composed entirely from snapshot readers."""
        with self._lock:
            firewall = self.firewall_level_status(refresh=refresh)
            dos = self.dos_status(refresh=refresh)
            ipv6 = self.ipv6_firewall_status(refresh=refresh)
            alg = self.alg_status(refresh=refresh)
            igmp = self.igmp_status(refresh=refresh)
            internet = self.internet_control_status(refresh=refresh)
            return {
                "available": any((
                    firewall.get("available"),
                    bool(dos),
                    bool(ipv6),
                    bool(alg),
                    bool(igmp),
                    bool(internet),
                )),
                "firewall": firewall.get("firewall") or {},
                "dos": dos,
                "ipv6_firewall": ipv6.get(
                    "X_HW_IPv6FWDFireWallEnable", ""
                ),
                "alg": alg,
                "igmp": igmp.get("IGMPEnable", ""),
                "internet_control": internet.get("Enable", ""),
            }

    def set_management_firewall(self, config, *, confirm=False):
        with self._lock:
            before = self._snapshot_cached("firewall_level")
            result = self._require_captured().set_management_firewall(
                dict(config or {}),
                confirm=confirm,
            )
            if result.get("verified") and isinstance(
                result.get("readback"), dict
            ):
                self._snapshot_store(
                    "firewall_level",
                    {
                        "available": True,
                        "firewall": result["readback"],
                    },
                )
            self._audit_captured(
                operation="huawei_firewall_level_update",
                target="Firewall",
                result=result,
                before=before,
                after=dict(config or {}),
            )
            result["snapshot_resource"] = "firewall_level"
            return result

    _DIAGNOSTICS_PAGE = "/html/bbsp/maintenance/diagnosecommon.asp"
    _PING_RESULT_PATH = "/html/bbsp/maintenance/GetPingResult.asp"
    _TRACE_RESULT_PATH = "/html/bbsp/maintenance/GetRouteResult.asp"
    _PING_ACTION = (
        "/html/bbsp/maintenance/complex.cgi?"
        "x=InternetGatewayDevice.IPPingDiagnostics&"
        "RUNSTATE_FLAG=Ping&"
        "RequestFile=html/bbsp/maintenance/diagnosecommon.asp"
    )
    _TRACE_ACTION = (
        "/html/bbsp/maintenance/complex.cgi?"
        "x=InternetGatewayDevice.TraceRouteDiagnostics&"
        "RUNSTATE_FLAG=Traceroute&"
        "RequestFile=html/bbsp/maintenance/diagnosecommon.asp"
    )
    _DIAGNOSTIC_SPLIT = "[@#@]"

    @staticmethod
    def _decode_diagnostic_result(source: object) -> tuple[str, str]:
        text = str(source or "").lstrip("\ufeff").strip()
        if not text:
            return "", ""

        # Huawei returns a JavaScript string expression from Get*Result.asp.
        # literal_eval decodes quoted/escaped string literals without eval().
        if text[:1] in {"'", '"'}:
            try:
                decoded = ast.literal_eval(text)
            except (SyntaxError, ValueError):
                decoded = text
            if isinstance(decoded, str):
                text = decoded

        if HuaweiService._DIAGNOSTIC_SPLIT not in text:
            return text.strip(), ""

        output, state = text.split(
            HuaweiService._DIAGNOSTIC_SPLIT,
            1,
        )
        return output.strip(), state.strip()

    @staticmethod
    def _diagnostic_complete(state: str) -> bool:
        return "complete" in str(state or "").casefold()

    @staticmethod
    def _diagnostic_terminal_failure(state: str) -> bool:
        value = str(state or "").casefold()
        if not value:
            return False
        if any(
            marker in value
            for marker in ("requested", "doing", "none", "start")
        ):
            return False
        return not HuaweiService._diagnostic_complete(state)

    def _poll_huawei_diagnostic(
        self,
        path: str,
        *,
        deadline_seconds: float,
    ) -> tuple[str, str, bool]:
        if self._client is None:
            raise RuntimeError(
                "Conecte-se a uma ONT Huawei antes de executar diagnóstico."
            )

        deadline = time.monotonic() + max(1.0, float(deadline_seconds))
        last_output = ""
        last_state = ""

        while True:
            source = self._client.post_read(
                path,
                {},
                referer=self._DIAGNOSTICS_PAGE,
            )
            output, state = self._decode_diagnostic_result(source)
            if output:
                last_output = output
            if state:
                last_state = state

            if self._diagnostic_complete(last_state):
                return last_output, last_state, True
            if self._diagnostic_terminal_failure(last_state):
                return last_output, last_state, False
            if time.monotonic() >= deadline:
                return last_output, last_state or "Timeout", False

            time.sleep(1.0)

    @staticmethod
    def _parse_ping_output(
        output: str,
        *,
        requested_count: int,
    ) -> dict:
        text = str(output or "")
        transmitted = None
        received = None
        loss = None
        minimum = average = maximum = None

        packets = re.search(
            r"(\d+)\s+packets?\s+transmitted.*?"
            r"(\d+)\s+(?:packets?\s+)?received",
            text,
            re.I | re.S,
        )
        if packets:
            transmitted = int(packets.group(1))
            received = int(packets.group(2))

        loss_match = re.search(
            r"(\d+(?:\.\d+)?)\s*%\s*packet\s+loss",
            text,
            re.I,
        )
        if loss_match:
            loss = float(loss_match.group(1))
            if loss.is_integer():
                loss = int(loss)

        rtt = re.search(
            r"(?:round-trip|rtt)[^=]*=\s*"
            r"(\d+(?:\.\d+)?)/(\d+(?:\.\d+)?)/"
            r"(\d+(?:\.\d+)?)",
            text,
            re.I,
        )
        if rtt:
            minimum = float(rtt.group(1))
            average = float(rtt.group(2))
            maximum = float(rtt.group(3))

        success = received
        failure = (
            max(0, transmitted - received)
            if transmitted is not None and received is not None
            else None
        )
        if transmitted is None and received is not None:
            transmitted = requested_count
            failure = max(0, requested_count - received)

        return {
            "sucesso": success,
            "falha": failure,
            "perda_percentual": loss,
            "minimo_ms": minimum,
            "medio_ms": average,
            "maximo_ms": maximum,
        }

    @staticmethod
    def _parse_traceroute_hops(output: str) -> list[dict]:
        hops = []
        for raw_line in str(output or "").splitlines():
            line = raw_line.strip()
            match = re.match(r"^(\d+)\s+(.+)$", line)
            if not match:
                continue

            number = int(match.group(1))
            body = match.group(2).strip()
            latencies = [
                float(value)
                for value in re.findall(
                    r"(\d+(?:\.\d+)?)\s*ms",
                    body,
                    re.I,
                )
            ]
            address_match = re.search(
                r"(?:(?:\d{1,3}\.){3}\d{1,3}|"
                r"(?:[0-9a-f]{0,4}:){2,}[0-9a-f:]+)",
                body,
                re.I,
            )
            hops.append({
                "numero": number,
                "ip": address_match.group(0) if address_match else "",
                "latencias_ms": latencies,
                "timeout": "*" in body and not latencies,
                "linha": body,
            })
        return hops

    @staticmethod
    def _diagnostic_transport_failed(result: dict) -> bool:
        status = result.get("http_status")
        return (
            status is not None
            and not 200 <= int(status) < 400
            and not result.get("uncertain")
        )

    def ping(self, config):
        with self._lock:
            values = dict(config or {})
            host = str(values.get("host") or "").strip()
            if not host:
                raise ValueError("Informe o destino do ping.")

            count = max(1, int(values.get("count") or 4))
            data_size = max(32, int(values.get("data_size") or 56))
            timeout_ms = max(1000, int(values.get("timeout") or 5000))
            interface = str(values.get("interface") or "").strip()

            payload = {
                "x.Host": host,
                "x.DiagnosticsState": "Requested",
                "x.NumberOfRepetitions": str(count),
                "x.DSCP": str(values.get("dscp") or 0),
                "x.DataBlockSize": str(data_size),
                "x.Timeout": str(timeout_ms),
                "RUNSTATE_FLAG.value": "START",
            }
            if interface:
                payload["x.Interface"] = interface

            submitted = self._require_mapped().write_request(
                self._PING_ACTION,
                payload,
                referer=self._DIAGNOSTICS_PAGE,
                token_page=self._DIAGNOSTICS_PAGE,
            )
            if self._diagnostic_transport_failed(submitted):
                raise RuntimeError(
                    "A ONT Huawei recusou o início do ping."
                )

            output, state, complete = self._poll_huawei_diagnostic(
                self._PING_RESULT_PATH,
                deadline_seconds=min(
                    60.0,
                    max(
                        12.0,
                        (count * timeout_ms / 1000.0) + 5.0,
                    ),
                ),
            )
            result = {
                "provider": "huawei",
                "host": host,
                "interface": interface,
                "ip_version": str(values.get("ip_version") or "IPv4"),
                "diagnostics_state": state,
                "resultado": output or (
                    f"Diagnóstico Huawei finalizado em estado {state or 'desconhecido'}."
                ),
                "verified": complete,
                "success": complete,
                "uncertain": not complete and not self._diagnostic_terminal_failure(state),
                **self._parse_ping_output(
                    output,
                    requested_count=count,
                ),
            }
            self._audit_captured(
                operation="diagnostic_ping",
                target=host,
                result=result,
                before=None,
                after={
                    "host": host,
                    "interface": interface,
                    "count": count,
                    "data_size": data_size,
                    "timeout": timeout_ms,
                },
            )
            return result

    def traceroute(self, config):
        with self._lock:
            values = dict(config or {})
            host = str(values.get("host") or "").strip()
            if not host:
                raise ValueError("Informe o destino do traceroute.")

            interface = str(values.get("interface") or "").strip()
            data_size = max(
                38,
                int(values.get("data_size") or 38),
            )
            timeout_ms = max(2000, int(values.get("timeout") or 5000))

            protocol = str(values.get("protocol") or "AUTO").strip().upper()
            protocol_code = values.get("protocol_code")
            if protocol_code in (None, "") and protocol == "AUTO":
                # Physically captured EG8041X7-10 WebUI payload.
                protocol_code = "0"

            payload = {
                "x.DiagnosticsState": "Requested",
                "x.Host": host,
                "x.DataBlockSize": str(data_size),
                "RUNSTATE_FLAG.value": "START",
            }
            if interface:
                payload["x.Interface"] = interface
            if protocol_code not in (None, ""):
                payload["x.X_HW_ProtocolType"] = str(protocol_code)

            submitted = self._require_mapped().write_request(
                self._TRACE_ACTION,
                payload,
                referer=self._DIAGNOSTICS_PAGE,
                token_page=self._DIAGNOSTICS_PAGE,
            )
            if self._diagnostic_transport_failed(submitted):
                raise RuntimeError(
                    "A ONT Huawei recusou o início do traceroute."
                )

            output, state, complete = self._poll_huawei_diagnostic(
                self._TRACE_RESULT_PATH,
                deadline_seconds=min(
                    60.0,
                    max(20.0, (timeout_ms / 1000.0) + 15.0),
                ),
            )
            result = {
                "provider": "huawei",
                "host": host,
                "interface": interface,
                "ip_version": str(values.get("ip_version") or "IPv4"),
                "protocol": protocol,
                "protocol_code": (
                    str(protocol_code)
                    if protocol_code not in (None, "")
                    else ""
                ),
                "diagnostics_state": state,
                "hops": self._parse_traceroute_hops(output),
                "resultado": output or (
                    f"Diagnóstico Huawei finalizado em estado {state or 'desconhecido'}."
                ),
                "verified": complete,
                "success": complete,
                "uncertain": not complete and not self._diagnostic_terminal_failure(state),
            }
            self._audit_captured(
                operation="diagnostic_traceroute",
                target=host,
                result=result,
                before=None,
                after={
                    "host": host,
                    "interface": interface,
                    "data_size": data_size,
                    "protocol": protocol,
                    "protocol_code": (
                        str(protocol_code)
                        if protocol_code not in (None, "")
                        else ""
                    ),
                },
            )
            return result

    def mapped_catalog(self):
        with self._lock:
            data = self._require_mapped().catalog()
            data["model"] = self.model
            data["profile"] = self.profile_key
            return data

    def mapped_read_feature(self, feature):
        with self._lock:
            return self._require_mapped().read_feature(feature)

    def mapped_read_request(
        self,
        path,
        *,
        method="GET",
        payload=None,
        referer="/index.asp",
        token_page=None,
    ):
        with self._lock:
            return self._require_mapped().read_request(
                path,
                method=method,
                payload=payload,
                referer=referer,
                token_page=token_page,
            )

    def mapped_write_feature(self, operation, config=None):
        with self._lock:
            result = self._require_mapped().write_feature(
                operation,
                config,
            )
            self._audit_captured(
                operation=f"huawei_mapped_{operation}",
                target=operation,
                result=result,
                before=None,
                after=dict(config or {}),
            )
            return result

    def mapped_write_request(
        self,
        path,
        payload=None,
        *,
        referer="/index.asp",
        token_page=None,
        readback_path=None,
        readback_method="GET",
        readback_payload=None,
    ):
        with self._lock:
            result = self._require_mapped().write_request(
                path,
                payload,
                referer=referer,
                token_page=token_page,
                readback_path=readback_path,
                readback_method=readback_method,
                readback_payload=readback_payload,
            )
            self._audit_captured(
                operation="huawei_mapped_request",
                target="mapped_request",
                result=result,
                before=None,
                after={"submitted": True},
            )
            return result

    def port_forwarding_status(self):
        return self.mapped_read_feature("port_mapping")

    def sntp_management_status(self):
        return self.mapped_read_feature("sntp")

    def qos_management_status(self):
        return self.mapped_read_feature("qos_smart")

    def firmware_management_status(self):
        result = self.mapped_read_feature("firmware")
        result["model"] = self.model
        return result

    def wan_configurations(self):
        # Keep the normalized WAN collection for the existing management UI.
        return self.wan_status()

    def workstation_diagnostic(self):
        return self.mapped_read_feature("diagnostics_webui")

    def export_user_configuration(self):
        return self.mapped_read_feature("config_backup")

    def reboot(self):
        # Reboot page is mapped. The low-level mapped mutation endpoint is
        # intentionally exposed separately so the exact captured request can
        # be submitted without fabricating a firmware-specific form here.
        return self.mapped_read_feature("reboot")

    def account_status(self):
        return self.mapped_read_feature("account")

    def upnp_status(self):
        return self.mapped_read_feature("upnp")

    def set_upnp(self, config):
        values = dict(config or {})
        request = values.pop("_request", None)
        if not isinstance(request, dict):
            raise ValueError(
                "Informe _request com o endpoint/payload Huawei mapeado."
            )
        return self.mapped_write_request(
            request.get("path"),
            request.get("payload") or values,
            referer=request.get("referer") or "/html/bbsp/upnp/upnp.asp",
            token_page=request.get("token_page") or "/html/bbsp/upnp/upnp.asp",
            readback_path=request.get("readback_path") or "/html/bbsp/upnp/upnp.asp",
        )

    def wps_status(self):
        return self.wifi_networks()

    def set_wps(self, band, mode):
        networks = self.wifi_networks()
        target = next(
            (
                row for row in networks
                if str(row.get("banda") or "").lower().startswith(
                    "5" if "5" in str(band) else "2"
                )
            ),
            None,
        )
        if not target:
            raise ValueError("SSID Huawei não encontrado para a banda.")
        return self.set_ssid_config(
            target.get("id"),
            {"wps_enabled": str(mode).lower() not in {"0", "off", "false", "disabled"}},
        )

    def band_steering_status(self):
        radios = self.wifi_radios()
        values = [
            row.get("band_steering")
            for row in radios
            if row.get("band_steering") is not None
        ]
        return {
            "available": bool(radios),
            "vendor": "huawei",
            "enabled": any(bool(value) for value in values),
            "radios": radios,
        }

    def set_band_steering(self, enabled):
        return self.configure_band_steering(
            {"band_steering": bool(enabled)}
        )

    def configure_band_steering(self, config):
        results = []
        for radio in self.wifi_radios():
            band = radio.get("banda")
            if not band:
                continue
            payload = dict(config or {})
            payload.setdefault("channel", radio.get("canal"))
            payload.setdefault(
                "auto_channel",
                bool(radio.get("canal_automatico")),
            )
            results.append(
                self.set_wifi_radio(band, payload)
            )
        return {
            "success": bool(results) and all(
                item.get("verified") for item in results
            ),
            "results": results,
        }

    def list_ipv4_filters(self, *, refresh: bool = False) -> dict:
        with self._lock:
            def load():
                result = self._require_ipv4_filter().list_ipv4_filters()
                # The session profile is authoritative for write permissions.
                result["capability"] = dict(
                    self._capabilities.get("ipv4_filter") or {}
                )
                result["vendor"] = self.vendor
                result["model"] = self.model
                result["profile"] = self.profile_key
                return result
            return self._snapshot_read(
                "ipv4_filter", load, refresh=refresh
            )

    def create_ipv4_filter(self, config) -> dict:
        with self._lock:
            rule = self._rule_from_config(config)
            result = self._require_ipv4_filter().create_ipv4_filter(rule)
            if result.get("verified") and isinstance(
                result.get("rule"), dict
            ):
                state = self._snapshot_cached("ipv4_filter") or {
                    "rules": [],
                    "capability": dict(
                        self._capabilities.get("ipv4_filter") or {}
                    ),
                    "vendor": self.vendor,
                    "model": self.model,
                    "profile": self.profile_key,
                }
                rows = [
                    item for item in state.get("rules") or []
                    if item.get("domain") != result["rule"].get("domain")
                ]
                rows.append(result["rule"])
                state["rules"] = rows
                self._snapshot_store("ipv4_filter", state)
            result["snapshot_resource"] = "ipv4_filter"
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
            cached_state = self._snapshot_cached("ipv4_filter")
            current = (
                cached_state.get("rules", [])
                if isinstance(cached_state, dict)
                else service.list_ipv4_filters().get("rules", [])
            )
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
            if result.get("verified") and isinstance(
                result.get("rule"), dict
            ):
                state = cached_state or {
                    "rules": current,
                    "capability": dict(
                        self._capabilities.get("ipv4_filter") or {}
                    ),
                    "vendor": self.vendor,
                    "model": self.model,
                    "profile": self.profile_key,
                }
                rows = list(state.get("rules") or [])
                replaced = False
                for index, item in enumerate(rows):
                    if (
                        item.get("domain") == result["rule"].get("domain")
                        or item.get("domain") == domain
                        or str(item.get("domain") or "").endswith("." + domain)
                    ):
                        rows[index] = result["rule"]
                        replaced = True
                        break
                if not replaced:
                    rows.append(result["rule"])
                state["rules"] = rows
                self._snapshot_store("ipv4_filter", state)
            result["snapshot_resource"] = "ipv4_filter"
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
            cached_state = self._snapshot_cached("ipv4_filter")
            result = self._require_ipv4_filter().delete_ipv4_filter(
                instance_or_domain
            )
            previous = result.get("previous")
            if result.get("verified"):
                state = cached_state or {
                    "rules": [],
                    "capability": dict(
                        self._capabilities.get("ipv4_filter") or {}
                    ),
                    "vendor": self.vendor,
                    "model": self.model,
                    "profile": self.profile_key,
                }
                deleted = str(
                    result.get("deleted_domain")
                    or instance_or_domain
                )
                state["rules"] = [
                    item for item in state.get("rules") or []
                    if (
                        str(item.get("domain") or "") != deleted
                        and not str(item.get("domain") or "").endswith(
                            "." + deleted
                        )
                    )
                ]
                self._snapshot_store("ipv4_filter", state)
            result["snapshot_resource"] = "ipv4_filter"
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
            "layer3": self.layer3_status,
            "lan_ipv4": self.lan_ipv4_status,
            "ipv6_lan": self.ipv6_lan_status,
            "dhcp": self.dhcp_status,
            "dhcp_static": self.dhcp_static_status,
            "dns": self.dns_status,
            "dns_host": self.dns_host_status,
            "dmz": self.dmz_status,
            "wifi_basic": self.wifi_networks,
            "wifi_radio": self.wifi_radios,
            "tr069_url": self.tr069_management_status,
            "firewall_level": self.firewall_level_status,
            "alg": self.alg_status,
            "igmp": self.igmp_status,
            "dos": self.dos_status,
            "ipv6_firewall": self.ipv6_firewall_status,
            "internet_control": self.internet_control_status,
        }
        if feature in readers:
            return readers[feature]
        if feature in HUAWEI_MAPPED_FEATURES:
            def mapped_reader(*, refresh: bool = False):
                # Generic mapped pages are live reads; refresh is accepted to
                # keep the capability reader signature uniform.
                return self.mapped_read_feature(feature)
            return mapped_reader
        raise ValueError(
            f"Capability Huawei desconhecida: {feature}."
        )

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
                writable = bool(
                    operations.get("create")
                    or operations.get("update")
                    or operations.get("delete")
                    or operations.get("write")
                )
                states = ["CAPTURED"]
                if operations.get("read"):
                    states.append("READ_IMPLEMENTED")
                if writable:
                    states.append("WRITE_CAPTURED")
                    if operations.get("verified"):
                        states.append("WRITE_PHYSICALLY_VERIFIED")
                if (
                    self.profile_key == "huawei_eg8041x7_10"
                    and key in HUAWEI_EG8041X7_FULLY_INTEGRATED
                ):
                    states.append("FULLY_INTEGRATED")
                feature["operations"] = operations
                feature["verified"] = bool(
                    operations.get("verified")
                )
                feature["writable"] = writable
                feature["evidence_states"] = states
                feature["state"] = states[-1]
            data["state_definitions"] = {
                "CAPTURED": "Endpoint/objeto apareceu no material capturado.",
                "READ_IMPLEMENTED": "Parser + serviço + API de leitura integrados.",
                "WRITE_CAPTURED": "Mutation/payload apareceu no material físico.",
                "WRITE_PHYSICALLY_VERIFIED": (
                    "Mutation exercitada fisicamente com read-back positivo."
                ),
                "FULLY_INTEGRATED": (
                    "Backend, UI, capability, histórico, read-back e testes."
                ),
                "OBSERVED_ONLY": (
                    "Observado na WebUI, ainda sem integração end-to-end."
                ),
                "UNSUPPORTED": (
                    "Somente para evidência concreta de impossibilidade."
                ),
                "NOT_YET_VALIDATED": (
                    "Não há evidência física suficiente para liberar a operação."
                ),
            }
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
                        self._feature_reader(feature)(refresh=True)
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

    def capability_shape(
        self,
        feature: str,
        *,
        refresh: bool = False,
    ) -> dict:
        with self._lock:
            operations = dict(
                self._capabilities.get(feature) or {}
            )
            if not operations:
                raise ValueError(
                    "Capability Huawei desconhecida."
                )
            data = self._feature_reader(feature)(refresh=refresh)
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

    def read_capability(
        self,
        feature: str,
        *,
        refresh: bool = False,
    ) -> dict:
        with self._lock:
            operations = dict(
                self._capabilities.get(feature) or {}
            )
            if not operations:
                raise ValueError(
                    "Capability Huawei desconhecida."
                )
            data = self._feature_reader(feature)(refresh=refresh)
            spec = HuaweiWebAdapter(
                self.model,
                profile=self._profile,
            ).features[feature]
            response = {
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
            if feature in HUAWEI_MAPPED_FEATURES:
                response["mapped_write"] = (
                    self._require_mapped().write_schema(feature)
                )
            return response

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
            session = self.session_snapshot()
            payload = {
                "device": self.device_info,
                "provider": type(self).__name__,
                "profile": self.profile_key,
                "capabilities": self.capabilities,
                "session_revision": self.session_revision,
                "state": session.get("state") or {},
            }
            partial = False
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
                "failed_sections": [],
            }

    def history(self, limit=50):
        return history_repository.recent(limit)

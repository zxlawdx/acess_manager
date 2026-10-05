from __future__ import annotations

import logging
import os
from copy import deepcopy
from typing import Any, Callable

from apps.zte_manager.infrastructure.huawei import (
    HuaweiMutationTransport,
    HuaweiResponseParser,
)
from apps.zte_manager.model.device_adapters.huawei import canonical_huawei_model
from apps.zte_manager.services.huawei_captured_features import (
    DNS_PAGE,
    HuaweiCapturedFeatureService,
    _record_domain,
)
from apps.zte_manager.services.huawei_service import HuaweiService


logger = logging.getLogger(__name__)
_MODEL = "EG8041X7-10"
_TRACE_VALUES = {"1", "true", "yes", "basic", "raw", "unsafe"}
_SECRET_FRAGMENTS = (
    "password",
    "passwd",
    "preshared",
    "psk",
    "token",
    "cookie",
    "authorization",
)


def _trace_enabled() -> bool:
    return str(os.getenv("HUAWEI_HTTP_TRACE") or "").strip().casefold() in _TRACE_VALUES


def _safe_debug(value: Any, *, key: str = "") -> Any:
    normalized = str(key or "").casefold()
    if any(fragment in normalized for fragment in _SECRET_FRAGMENTS):
        return "<redacted>"
    if isinstance(value, dict):
        return {
            str(item_key): _safe_debug(item_value, key=str(item_key))
            for item_key, item_value in value.items()
        }
    if isinstance(value, (list, tuple)):
        return [_safe_debug(item) for item in value]
    return value


def _profile_trace(event: str, **fields: Any) -> None:
    if not _trace_enabled():
        return
    safe = _safe_debug(fields)
    suffix = " ".join(
        f"{name}={value!r}"
        for name, value in safe.items()
    )
    message = f"[HUAWEI PROFILE] {event}"
    if suffix:
        message += " " + suffix
    logger.info(message)
    print(message, flush=True)


def _friendly_failure(text: object, fallback: str) -> str:
    value = " ".join(str(text or "").split()).strip()
    if not value:
        value = fallback
    # Keep the API/frontend error concise and prevent raw firmware HTML/URLs
    # from leaking into the operator-facing response.
    if len(value) > 180 or "<html" in value.casefold() or "http://" in value.casefold():
        value = fallback
    return value


def _unsupported_dns_search_delete(domain: str) -> dict[str, Any]:
    return {
        "operation": "delete",
        "target": domain,
        "success": False,
        "accepted": False,
        "verified": False,
        "confirmed_by_response": False,
        "verified_by_readback": False,
        "readback_attempts": 0,
        "uncertain": False,
        "unsupported_delete": True,
        "error_code": "unsupported_delete",
        "error_message": (
            "A remoção de DNS Search List ainda não possui endpoint físico "
            "confirmado neste firmware; nenhuma exclusão foi enviada."
        ),
    }


def _dns_preflight_failure(
    code: str,
    message: str,
    *,
    operation: str,
    target: str,
) -> dict[str, Any]:
    return {
        "operation": operation,
        "target": target,
        "success": False,
        "accepted": False,
        "verified": False,
        "confirmed_by_response": False,
        "verified_by_readback": False,
        "readback_attempts": 0,
        "uncertain": False,
        "error_code": code,
        "error_message": message,
    }


class HuaweiEG8041X7CapturedFeatureService(HuaweiCapturedFeatureService):
    """EG8041X7-10 mutation semantics proven by physical WebUI captures.

    The base parser remains responsible for Huawei JS records. This subclass
    narrows mutation confirmation and DNS behavior to the physical contract of
    this firmware without changing other Huawei models.
    """

    def _post_verified(
        self,
        *,
        path: str,
        request_file: str,
        payload: dict[str, str],
        verifier: Callable[[], Any] | None,
    ) -> dict[str, Any]:
        page = self._page(request_file)
        token = self.client.extract_token(page)
        body = {**payload, "x.X_HW_Token": token}

        transport: HuaweiMutationTransport = self.client.post_form(
            path,
            body,
            referer=request_file,
        )
        parsed = HuaweiResponseParser.parse(
            http_status=transport.http_status,
            body=transport.body,
            content_type=transport.content_type,
        )

        verified = None
        readback_attempts = 0
        last_readback_error: Exception | None = None
        if verifier is not None and parsed.accepted:
            delays = (0.35, 0.55, 0.8, 1.0, 1.4, 1.8)[: self.readback_tries]
            for readback_attempts, delay in enumerate(delays, start=1):
                self.sleep(delay)
                try:
                    verified = verifier()
                    last_readback_error = None
                except Exception as exc:  # surfaced below; never silently pass
                    last_readback_error = exc
                    verified = None
                    logger.exception(
                        "huawei_eg8041x7_readback_failed path=%s attempt=%s",
                        path,
                        readback_attempts,
                    )
                if verified:
                    break

        if verifier is not None:
            verified_by_readback = bool(verified)
            final_verified = verified_by_readback
            success = bool(parsed.accepted and verified_by_readback)
        else:
            verified_by_readback = False
            final_verified = bool(parsed.confirmed)
            success = bool(parsed.accepted)

        error_message = parsed.error_message
        error_code = parsed.error_code
        if parsed.accepted and verifier is not None and not verified_by_readback:
            if last_readback_error is not None:
                error_code = "readback_error"
                error_message = _friendly_failure(
                    str(last_readback_error),
                    "A alteração foi aceita, mas a releitura do estado Huawei falhou.",
                )
            else:
                error_code = "readback_mismatch"
                error_message = (
                    "A alteração foi aceita, mas a releitura não confirmou "
                    "o estado esperado."
                )

        uncertain = bool(
            transport.timed_out
            or transport.connection_uncertain
            or (parsed.accepted and verifier is not None and not verified_by_readback)
        )
        if not parsed.accepted and not (
            transport.timed_out or transport.connection_uncertain
        ):
            uncertain = False

        return {
            "success": success,
            "accepted": parsed.accepted,
            "confirmed_by_response": bool(parsed.confirmed),
            "verified": final_verified,
            "verified_by_readback": verified_by_readback,
            "readback_attempts": readback_attempts,
            "uncertain": uncertain,
            "http_status": transport.http_status,
            "response_type": parsed.response_type,
            "error_code": error_code,
            "error_message": error_message,
            "response_data": (
                parsed.data
                if isinstance(parsed.data, (dict, list))
                else None
            ),
            "readback": verified if verified else None,
        }

    def _write_dns_search(
        self,
        *,
        dns_server: str,
        domain_name: str,
        interface: str,
        instance_or_domain: str | None = None,
    ) -> dict[str, Any]:
        result = super()._write_dns_search(
            dns_server=dns_server,
            domain_name=domain_name,
            interface=interface,
            instance_or_domain=instance_or_domain,
        )
        result["operation"] = "update" if instance_or_domain else "create"
        return result

    def set_dns(self, config: dict[str, Any]) -> dict[str, Any]:
        values = dict(config or {})
        current = self.dns_status()
        rows = list(current.get("_search_rows") or [])

        requested = {
            "ipv4_1": str(values.get("ipv4_1", current.get("ipv4_1") or "") or ""),
            "ipv4_2": str(values.get("ipv4_2", current.get("ipv4_2") or "") or ""),
            "ipv6_1": str(values.get("ipv6_1", current.get("ipv6_1") or "") or ""),
            "ipv6_2": str(values.get("ipv6_2", current.get("ipv6_2") or "") or ""),
        }
        requested_domain_name = str(
            values.get("domain_name", current.get("domain_name") or "") or ""
        )
        default_interface = str(
            values.get("interface")
            or next(
                (
                    item.get("Interface")
                    for item in rows
                    if item.get("Interface")
                ),
                "",
            )
            or ""
        )

        ipv4_rows = [
            item for item in rows
            if ":" not in str(item.get("DNSServer") or "")
        ]
        ipv6_rows = [
            item for item in rows
            if ":" in str(item.get("DNSServer") or "")
        ]
        slots = (
            ("ipv4_1", ipv4_rows, 0),
            ("ipv4_2", ipv4_rows, 1),
            ("ipv6_1", ipv6_rows, 0),
            ("ipv6_2", ipv6_rows, 1),
        )

        search_plan: list[dict[str, Any]] = []
        expectations: dict[str, dict[str, str]] = {}
        preflight_errors: list[dict[str, Any]] = []

        for key, group, index in slots:
            expected_server = requested[key]
            existing = group[index] if len(group) > index else None
            existing_domain = _record_domain(existing or {})
            existing_server = str((existing or {}).get("DNSServer") or "")
            existing_domain_name = str((existing or {}).get("DomainName") or "")
            existing_interface = str((existing or {}).get("Interface") or "")
            effective_interface = default_interface or existing_interface
            effective_domain_name = requested_domain_name or existing_domain_name

            expectations[key] = {
                "server": expected_server,
                "domain": existing_domain,
                "domain_name": effective_domain_name,
                "interface": effective_interface,
            }

            if not expected_server:
                if existing is not None and existing_server:
                    preflight_errors.append(
                        _unsupported_dns_search_delete(existing_domain)
                    )
                continue

            if not effective_interface:
                preflight_errors.append(
                    _dns_preflight_failure(
                        "dns_interface_required",
                        "A interface WAN vinculada ao DNS não foi identificada; nenhum POST foi enviado.",
                        operation="update" if existing else "create",
                        target=existing_domain or key,
                    )
                )
                continue

            if not effective_domain_name:
                preflight_errors.append(
                    _dns_preflight_failure(
                        "dns_domain_required",
                        "O firmware exige DomainName para DNS Search List; nenhum POST inválido foi enviado.",
                        operation="update" if existing else "create",
                        target=existing_domain or key,
                    )
                )
                continue

            if (
                existing is not None
                and existing_server == expected_server
                and existing_domain_name == effective_domain_name
                and existing_interface == effective_interface
            ):
                continue

            search_plan.append({
                "slot": key,
                "operation": "update" if existing else "create",
                "dns_server": expected_server,
                "domain_name": effective_domain_name,
                "interface": effective_interface,
                "domain": existing_domain,
            })

        # DNS Search List deletion is deliberately not guessed. The physical
        # firmware source supplied for this model exposes HOSTS del.cgi but no
        # confirmed SearList deletion action. Abort before *any* DNS mutation so
        # a profile cannot leave a half-applied DNS state.
        if preflight_errors:
            first = preflight_errors[0]
            return {
                "success": False,
                "accepted": False,
                "confirmed_by_response": False,
                "verified": False,
                "verified_by_readback": False,
                "readback_attempts": 0,
                "uncertain": False,
                "semantic_verified": False,
                "response_type": "preflight",
                "error_code": first.get("error_code"),
                "error_message": first.get("error_message"),
                "results": preflight_errors,
                "readback": current,
            }

        results: list[dict[str, Any]] = []
        for item in search_plan:
            result = self._write_dns_search(
                dns_server=item["dns_server"],
                domain_name=item["domain_name"],
                interface=item["interface"],
                instance_or_domain=item["domain"] or None,
            )
            result["slot"] = item["slot"]
            result["target"] = item["domain"] or "InternetGatewayDevice.X_HW_DNS.SearList"
            results.append(result)
            if result.get("verified") is not True:
                break

        search_ok = all(item.get("verified") is True for item in results)
        if search_ok and "hosts" in values:
            requested_hosts = [
                item for item in list(values.get("hosts") or [])
                if isinstance(item, dict)
            ]
            actual_hosts = list(current.get("hosts") or [])
            requested_ids = {
                str(item.get("id") or "")
                for item in requested_hosts
                if item.get("id")
            }
            requested_values = {
                (
                    str(item.get("ip") or item.get("IPAddress") or ""),
                    str(
                        item.get("nome")
                        or item.get("name")
                        or item.get("domain_name")
                        or item.get("DomainName")
                        or ""
                    ),
                )
                for item in requested_hosts
                if (item.get("ip") or item.get("IPAddress"))
                and (
                    item.get("nome")
                    or item.get("name")
                    or item.get("domain_name")
                    or item.get("DomainName")
                )
            }

            for item in requested_hosts:
                host_id = str(item.get("id") or "")
                ip = str(item.get("ip") or item.get("IPAddress") or "")
                name = str(
                    item.get("nome")
                    or item.get("name")
                    or item.get("domain_name")
                    or item.get("DomainName")
                    or ""
                )
                if not ip or not name:
                    continue
                identity = (ip, name)
                if host_id:
                    existing = next(
                        (
                            row for row in actual_hosts
                            if str(row.get("id") or "") == host_id
                        ),
                        None,
                    )
                    if existing and (
                        str(existing.get("ip") or ""),
                        str(existing.get("nome") or ""),
                    ) == identity:
                        continue
                    result = self.update_dns_host(
                        host_id,
                        ip=ip,
                        domain_name=name,
                    )
                    result["operation"] = "update_host"
                elif identity not in {
                    (
                        str(existing.get("ip") or ""),
                        str(existing.get("nome") or ""),
                    )
                    for existing in actual_hosts
                }:
                    result = self.create_dns_host(
                        ip=ip,
                        domain_name=name,
                    )
                    result["operation"] = "create_host"
                else:
                    continue
                results.append(result)
                if result.get("verified") is not True:
                    break

            if all(item.get("verified") is True for item in results):
                for item in actual_hosts:
                    host_id = str(item.get("id") or "")
                    identity = (
                        str(item.get("ip") or ""),
                        str(item.get("nome") or ""),
                    )
                    if (
                        host_id
                        and host_id not in requested_ids
                        and identity not in requested_values
                    ):
                        result = self.delete_dns_host(host_id)
                        result["operation"] = "delete_host"
                        results.append(result)
                        if result.get("verified") is not True:
                            break

        final = self.dns_status()
        final_rows = list(final.get("_search_rows") or [])
        semantic_verified = True

        for key, expected in expectations.items():
            expected_server = expected["server"]
            existing_domain = expected["domain"]
            if not expected_server:
                # The only supported empty case is one where the slot did not
                # exist before. Existing entries would have failed preflight.
                if existing_domain:
                    semantic_verified = False
                    break
                continue

            candidates = final_rows
            if existing_domain:
                candidates = [
                    row for row in final_rows
                    if _record_domain(row) == existing_domain
                ]
            matched = any(
                str(row.get("DNSServer") or "") == expected_server
                and str(row.get("DomainName") or "") == expected["domain_name"]
                and str(row.get("Interface") or "") == expected["interface"]
                for row in candidates
            )
            if not matched:
                semantic_verified = False
                break

        if semantic_verified and "hosts" in values:
            expected_hosts = {
                (
                    str(item.get("ip") or item.get("IPAddress") or ""),
                    str(
                        item.get("nome")
                        or item.get("name")
                        or item.get("domain_name")
                        or item.get("DomainName")
                        or ""
                    ),
                )
                for item in list(values.get("hosts") or [])
                if isinstance(item, dict)
                and (item.get("ip") or item.get("IPAddress"))
            }
            final_hosts = {
                (str(item.get("ip") or ""), str(item.get("nome") or ""))
                for item in final.get("hosts") or []
                if item.get("ip") and item.get("nome")
            }
            semantic_verified = final_hosts == expected_hosts

        operation_verified = all(
            item.get("verified") is True
            for item in results
        ) if results else True
        verified = bool(operation_verified and semantic_verified)

        first_failure = next(
            (item for item in results if item.get("verified") is not True),
            None,
        )
        error_code = None
        error_message = None
        if not verified:
            if first_failure:
                error_code = first_failure.get("error_code") or "dns_operation_failed"
                error_message = first_failure.get("error_message")
            if not error_message:
                error_code = error_code or "dns_readback_mismatch"
                error_message = (
                    "As operações DNS foram enviadas, mas a releitura não "
                    "confirmou o estado solicitado."
                )

        return {
            "success": verified,
            "accepted": all(
                item.get("accepted") is not False
                for item in results
            ) if results else True,
            "confirmed_by_response": all(
                item.get("confirmed_by_response") is True
                for item in results
            ) if results else False,
            "verified": verified,
            "verified_by_readback": semantic_verified,
            "readback_attempts": sum(
                int(item.get("readback_attempts") or 0)
                for item in results
            ),
            "uncertain": any(
                item.get("uncertain") is True
                for item in results
            ) or (bool(results) and not semantic_verified),
            "semantic_verified": semantic_verified,
            "response_type": "composite",
            "error_code": error_code,
            "error_message": error_message,
            "results": results,
            "readback": final,
        }


class HuaweiEG8041X7RuntimeService(HuaweiService):
    """HuaweiService specialization for the physically mapped EG8041X7-10."""

    def connect(self, *args, **kwargs):
        result = super().connect(*args, **kwargs)
        if canonical_huawei_model(self.model) == _MODEL and self._client is not None:
            self._captured = HuaweiEG8041X7CapturedFeatureService(
                self._client,
                model=self.model,
            )
        # Keep the public provider contract stable even though the runtime has
        # a model-specific specialization behind HuaweiService.
        result["provider"] = "HuaweiService"
        return result

    @staticmethod
    def _dns_profile_equivalent(current: dict, requested: dict) -> bool:
        scalar_keys = (
            "domain_name",
            "ipv4_1",
            "ipv4_2",
            "ipv6_1",
            "ipv6_2",
        )
        if any(
            str(current.get(key) or "") != str(requested.get(key) or "")
            for key in scalar_keys
        ):
            return False

        def host_set(value: Any) -> set[tuple[str, str]]:
            return {
                (
                    str(item.get("ip") or item.get("IPAddress") or ""),
                    str(
                        item.get("nome")
                        or item.get("name")
                        or item.get("DomainName")
                        or ""
                    ),
                )
                for item in list(value or [])
                if isinstance(item, dict)
            }

        return host_set(current.get("hosts")) == host_set(requested.get("hosts"))

    @staticmethod
    def _step_reason(
        name: str,
        result: dict[str, Any],
        changed_fields: list[str],
    ) -> str:
        if result.get("error_message"):
            return _friendly_failure(
                result.get("error_message"),
                f"{name}: a operação não pôde ser confirmada.",
            )
        if result.get("accepted") is False:
            return f"{name}: o firmware recusou a alteração."
        if result.get("accepted") is True and not result.get("verified"):
            fields = ", ".join(changed_fields[:6]) or "estado solicitado"
            return (
                "A alteração foi aceita, mas a releitura não confirmou "
                f"os campos: {fields}."
            )
        return f"{name}: a alteração não foi confirmada."

    def _apply_profile_payload(
        self,
        profile: dict,
        *,
        operation: str,
        target: str,
    ) -> dict:
        if canonical_huawei_model(self.model) != _MODEL:
            return super()._apply_profile_payload(
                profile,
                operation=operation,
                target=target,
            )

        captured = self._require_captured()
        steps: list[dict[str, Any]] = []
        omitted: list[str] = []
        unchanged: list[str] = []
        before_config = self.current_configuration()

        _profile_trace("current", current=before_config)
        _profile_trace("requested", requested=profile)

        def equivalent(key: str, left: Any, right: Any) -> bool:
            if key == "country":
                normalize = lambda value: (
                    "BR" if str(value or "").upper() == "BRI"
                    else str(value or "").upper()
                )
                return normalize(left) == normalize(right)
            if key == "tx_power":
                normalize = lambda value: str(value or "").strip().rstrip("%")
                return normalize(left) == normalize(right)
            if key == "bandwidth":
                def normalize(value: Any) -> str:
                    text = " ".join(str(value or "").strip().split()).casefold()
                    return "auto" if text.startswith("auto") else text
                return normalize(left) == normalize(right)
            if key == "bandwidth_code":
                return str(left or "").strip() == str(right or "").strip()
            if key == "standard":
                def normalize(value: Any) -> str:
                    text = str(value or "").strip()
                    if text in {"11ax", "b,g,n,ax", "a,n,ac,ax"}:
                        return "11ax"
                    return text
                return normalize(left) == normalize(right)
            if key in {
                "auto_channel",
                "sgi",
                "band_steering",
                "airtime_fairness",
            }:
                return bool(left) == bool(right)
            if key in {
                "channel",
                "beacon_interval",
                "rts_cts",
                "dtim",
                "frag_threshold",
            }:
                if left in (None, "") and right in (None, ""):
                    return True
                try:
                    return int(left) == int(right)
                except (TypeError, ValueError):
                    return False
            return str(left if left is not None else "") == str(
                right if right is not None else ""
            )

        applied_after: dict[str, Any] = {"wifi": {}}

        for band in ("2.4GHz", "5GHz"):
            config = dict((profile.get("wifi") or {}).get(band) or {})
            if not config:
                continue

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
                if key in supported
                and value is not None
                and not (
                    key in {"bandwidth_code", "auto_channel_scope"}
                    and value == ""
                )
            }
            for key in config:
                if key not in supported and config.get(key) not in (None, "", False):
                    omitted.append(f"Wi-Fi {band}: {key}")

            if str(safe_config.get("country") or "").upper() == "BRI":
                safe_config["country"] = "BR"

            current = dict((before_config.get("wifi") or {}).get(band) or {})
            changed = {
                key: value
                for key, value in safe_config.items()
                if not equivalent(key, current.get(key), value)
            }

            if bool(safe_config.get("auto_channel")) and safe_config.get("channel") in (
                None,
                "",
                0,
                "0",
                "Auto",
            ):
                changed.pop("channel", None)

            _profile_trace(
                "diff",
                band=band,
                changed=changed,
                changed_fields=sorted(changed),
            )

            if not changed:
                unchanged.append(f"Wi-Fi {band}")
                continue

            name = f"Wi-Fi {band}"
            _profile_trace("applying", step=name, config=changed)
            try:
                result = captured.set_wifi_radio(band, changed)
                _profile_trace("result", step=name, result=result)
            except Exception as exc:
                logger.exception("huawei_profile_step_failed step=%s", name)
                reason = _friendly_failure(
                    str(exc),
                    "A configuração do rádio falhou antes da confirmação por releitura.",
                )
                _profile_trace(
                    "exception",
                    step=name,
                    error_type=type(exc).__name__,
                    error=reason,
                )
                steps.append({
                    "name": name,
                    "step": f"wifi:{band}",
                    "success": False,
                    "verified": False,
                    "changed_fields": sorted(changed),
                    "reason": reason,
                    "detail": reason,
                })
                break

            verified = bool(result.get("verified"))
            reason = None if verified else self._step_reason(
                name,
                result,
                sorted(changed),
            )
            step = {
                "name": name,
                "step": f"wifi:{band}",
                "success": verified,
                "verified": verified,
                "accepted": result.get("accepted"),
                "confirmed_by_response": result.get("confirmed_by_response"),
                "verified_by_readback": result.get("verified_by_readback"),
                "readback_attempts": result.get("readback_attempts", 0),
                "response_type": result.get("response_type"),
                "error_code": result.get("error_code"),
                "changed_fields": sorted(changed),
                "reason": reason,
                "detail": (
                    "Campos alterados e confirmados por read-back."
                    if verified
                    else reason
                ),
            }
            steps.append(step)
            if not verified:
                break

            if isinstance(result.get("readback"), dict):
                self._snapshot_patch_list(
                    "wifi_radios",
                    result["readback"],
                    identity_fields=("banda", "id"),
                )
                applied_after["wifi"][band] = result["readback"]

        if all(step.get("success") for step in steps):
            dns = dict(profile.get("dns") or {})
            if dns:
                current_dns = dict(before_config.get("dns") or {})
                dns_changed = not self._dns_profile_equivalent(current_dns, dns)
                _profile_trace(
                    "diff",
                    step="DNS / hosts",
                    changed=dns_changed,
                    current=current_dns,
                    requested=dns,
                )
                if not dns_changed:
                    unchanged.append("DNS / hosts")
                else:
                    name = "DNS / hosts"
                    _profile_trace("applying", step=name, config=dns)
                    try:
                        result = captured.set_dns(dns)
                        _profile_trace("result", step=name, result=result)
                    except Exception as exc:
                        logger.exception("huawei_profile_step_failed step=%s", name)
                        reason = _friendly_failure(
                            str(exc),
                            "A configuração DNS falhou antes da confirmação por releitura.",
                        )
                        _profile_trace(
                            "exception",
                            step=name,
                            error_type=type(exc).__name__,
                            error=reason,
                        )
                        steps.append({
                            "name": name,
                            "step": "dns",
                            "success": False,
                            "verified": False,
                            "changed_fields": sorted(dns),
                            "reason": reason,
                            "detail": reason,
                        })
                    else:
                        verified = bool(result.get("verified"))
                        reason = None if verified else self._step_reason(
                            name,
                            result,
                            sorted(dns),
                        )
                        steps.append({
                            "name": name,
                            "step": "dns",
                            "success": verified,
                            "verified": verified,
                            "accepted": result.get("accepted"),
                            "confirmed_by_response": result.get("confirmed_by_response"),
                            "verified_by_readback": result.get("verified_by_readback"),
                            "readback_attempts": result.get("readback_attempts", 0),
                            "response_type": result.get("response_type"),
                            "error_code": result.get("error_code"),
                            "changed_fields": sorted(dns),
                            "reason": reason,
                            "detail": (
                                "DNS e hosts confirmados por read-back."
                                if verified
                                else reason
                            ),
                        })
                        if verified and isinstance(result.get("readback"), dict):
                            readback = deepcopy(result["readback"])
                            readback.pop("_search_rows", None)
                            self._snapshot_store("dns", readback)
                            applied_after["dns"] = readback

        success = all(bool(step.get("success")) for step in steps)
        result: dict[str, Any] = {
            "success": success,
            "verified": success,
            "audit_outcome": "verified" if success else "failed",
            "steps": steps,
            "unchanged": unchanged,
            "not_included": omitted,
        }

        failed = next((step for step in steps if not step.get("success")), None)
        if failed:
            reason = str(failed.get("reason") or failed.get("detail") or "Falha não confirmada.")
            error = _friendly_failure(
                f"Falha ao aplicar {failed.get('name')}: {reason}",
                f"Falha ao aplicar {failed.get('name')}: a alteração não foi confirmada.",
            )
            result.update({
                "error": error,
                "step": failed.get("step") or failed.get("name"),
                "reason": reason,
                "error_code": failed.get("error_code"),
            })

        if steps:
            self._audit_captured(
                operation=operation,
                target=target,
                result=result,
                before=before_config,
                after=applied_after,
            )
        return result

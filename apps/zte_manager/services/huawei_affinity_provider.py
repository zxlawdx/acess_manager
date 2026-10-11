from __future__ import annotations

import re
from copy import deepcopy
from typing import Any

from apps.zte_manager.infrastructure.huawei.affinity_client import (
    HuaweiAffinityNegotiatingWebClient,
)
from apps.zte_manager.infrastructure.huawei.protocol import HuaweiAuthFlow
from apps.zte_manager.infrastructure.huawei.single_write import SingleWriteHttpTransport
from apps.zte_manager.services.huawei_hg8347r_runtime import HuaweiHG8347RRuntime
from apps.zte_manager.services.huawei_mapped_surface import HUAWEI_MAPPED_WRITES
from apps.zte_manager.services.huawei_unified_provider import HuaweiUnifiedProvider


class HuaweiAffinityUnifiedProvider(HuaweiUnifiedProvider):
    """Production Huawei provider through Phase 5 plus explicit lab controls.

    Phase 4 adds same-TCP authentication when a strict transport profile proves
    it. Phase 5 adds a clean-room HG8347R reader. ``lab_mode`` is deliberately
    session-local and opt-in: it exposes mapped/raw mutation experiments without
    pretending those writes are physically validated for every Huawei model.
    """

    def __init__(self, **kwargs) -> None:
        kwargs.setdefault("client_factory", HuaweiAffinityNegotiatingWebClient)
        super().__init__(**kwargs)
        self._phase5_runtime: HuaweiHG8347RRuntime | None = None
        self._lab_mode = False

    @property
    def _phase5_active(self) -> bool:
        return self._phase5_runtime is not None

    @property
    def lab_mode(self) -> bool:
        return bool(self._lab_mode)

    @property
    def writes_enabled(self) -> bool:
        if self._lab_mode and self.connected:
            return True
        return super().writes_enabled

    @property
    def capabilities(self) -> dict[str, dict]:
        data = super().capabilities
        if self._phase5_active:
            # The inherited EG8041 family descriptor is not evidence for this
            # firmware. Phase 5 publishes only the AJAX client reader plus lab
            # controls when explicitly enabled.
            for feature in (
                "wifi",
                "wifi_basic",
                "wifi_radio",
                "wifi_advanced",
                "wifi_channel_discovery",
                "wifi_traffic",
                "ipv4_filter",
            ):
                data.pop(feature, None)
            data["clients"] = dict(
                self._capabilities.get("clients")
                or self._ops(
                    read=True,
                    update=False,
                    verified=True,
                    physical_validation=False,
                    evidence="clean-room+runtime_probe:HG8347R:getajax",
                    state="READ_SUPPORTED",
                )
            )

        if self._lab_mode and self.connected:
            data["lab_mapped_write"] = self._ops(
                read=True,
                update=True,
                verified=False,
                physical_validation=False,
                evidence="operator_enabled_lab_mode:mapped_or_exact_request",
                state="EXPERIMENTAL",
            )
            data["reboot"] = self._ops(
                read=True,
                update=True,
                verified=False,
                physical_validation=False,
                evidence="operator_enabled_lab_mode:known_profile_or_exact_request",
                state="EXPERIMENTAL",
            )
        return data

    # ------------------------------------------------------------------
    # Phase 5: HG8347R clean-room runtime

    def _probe_phase5_candidate(self):
        if self._client is None:
            return None
        if getattr(self._client, "auth_flow", None) not in {
            HuaweiAuthFlow.RAND_COUNT,
            HuaweiAuthFlow.RAND_COUNT.value,
        }:
            return None
        runtime = HuaweiHG8347RRuntime(self._client)
        try:
            signature = runtime.source_signature()
        except Exception:
            return None
        if not bool(signature.get("compatible")) or not bool(signature.get("strong_fingerprint")):
            return None
        return runtime, signature

    def _configure_phase5_runtime(
        self,
        runtime: HuaweiHG8347RRuntime,
        signature: dict[str, Any],
    ) -> None:
        self._phase5_runtime = runtime
        self._phase3_runtime = None
        self._phase2_runtime = None
        self._phase2_profile = None
        self._ipv4_filter = None
        self._family_compatible = True
        self.model = HuaweiHG8347RRuntime.MODEL
        self.model_verified = True
        self.model_source = "runtime_hg8347r_ajax_fingerprint"
        self._device_info.update({
            "fabricante": "Huawei",
            "modelo": self.model,
        })
        self._clear_session_snapshot()
        self._family_descriptor = {
            "protocol_family": "amp_bbsp",
            "firmware_family": "HG8347R/BJUNICOM-V3R017-like",
            "cfg_mode": None,
            "compatible": True,
            "model": self.model,
            "strong_fingerprint": True,
            "source": signature.get("source") or HuaweiHG8347RRuntime.SOURCE,
            "evidence": list(signature.get("evidence") or []),
            "endpoints": deepcopy(signature.get("endpoints") or {}),
            "physical_validation": False,
            "phase": 5,
        }
        self._force_specialized_read_only(
            "phase5_hg8347r_clean_room_clients_only",
            preserve_existing_reads=False,
        )
        self._promote_specialized_reader(
            "clients",
            lambda: runtime.clients(refresh=True),
            endpoint_evidence=HuaweiHG8347RRuntime.USER_DEVICE_AJAX,
        )

    def connect(self, *args, **kwargs):
        self._phase5_runtime = None
        self._lab_mode = False
        result = super().connect(*args, **kwargs)

        # Earlier, stronger specialized fingerprints retain precedence. HG8347R
        # is considered only when the session remained on the generic AMP/BBSP
        # path after Phases 1-3.
        if not (
            self._phase3_active
            or self._phase2_active
            or self._hg8145x6_active
        ):
            candidate = self._probe_phase5_candidate()
            if candidate is not None:
                runtime, signature = candidate
                self._configure_phase5_runtime(runtime, signature)

        result.update({
            "model": self.model,
            "model_verified": self.model_verified,
            "model_source": self.model_source,
            "device": self.device_info,
            "family": self.family_descriptor,
            "capabilities": self.capabilities,
            "writes_enabled": self.writes_enabled,
            "lab_mode": self.lab_mode,
            "provider": type(self).__name__,
        })
        return result

    def disconnect(self) -> None:
        self._phase5_runtime = None
        self._lab_mode = False
        super().disconnect()

    def clients(self, *, refresh: bool = False) -> list[dict]:
        if self._phase5_active:
            runtime = self._phase5_runtime
            if runtime is None:
                raise RuntimeError("Runtime HG8347R Phase-5 não está ativo.")
            return self._snapshot_read(
                "phase5_clients",
                lambda: runtime.clients(refresh=refresh),
                refresh=refresh,
            )
        return super().clients(refresh=refresh)

    def lan_clients(self, *, refresh: bool = False):
        if not self._phase5_active:
            return super().lan_clients(refresh=refresh)
        return [
            item for item in self.clients(refresh=refresh)
            if item.get("connection_type") == "lan"
        ]

    def wifi_clients(self, *, refresh: bool = False):
        if not self._phase5_active:
            return super().wifi_clients(refresh=refresh)
        return [
            item for item in self.clients(refresh=refresh)
            if item.get("connection_type") == "wifi"
        ]

    def _specialized_block_write(self):
        if self._phase5_active:
            raise RuntimeError(
                "HG8347R Phase-5 não herda writers EG8041. Para laboratório, "
                "ative lab_mode e use uma mutation mapeada ou request capturada exata."
            )
        return super()._specialized_block_write()

    # ------------------------------------------------------------------
    # Explicit lab mode

    def set_lab_mode(self, enabled: bool) -> dict[str, Any]:
        if not self.connected:
            raise RuntimeError("Conecte-se a uma Huawei antes de alterar o modo lab.")
        self._lab_mode = bool(enabled)
        return self.lab_status()

    def lab_status(self) -> dict[str, Any]:
        api_reboot = bool(self._phase3_active)
        legacy_hg8245h = bool(
            str(self.model or "").upper() == "HG8245H"
            and getattr(self._client, "auth_flow", None)
            in {HuaweiAuthFlow.RAND_COUNT, HuaweiAuthFlow.RAND_COUNT.value}
        )
        return {
            "enabled": self.lab_mode,
            "vendor": "huawei",
            "model": self.model,
            "phase5_hg8347r": self._phase5_active,
            "writes_enabled": self.writes_enabled,
            "mapped_operations": sorted(HUAWEI_MAPPED_WRITES) if self._mapped is not None else [],
            "raw_relative_write": self._mapped is not None,
            "reboot": {
                "api_hg8245h": api_reboot,
                "legacy_hg8245h_single_write": legacy_hg8245h,
                "exact_request": self._mapped is not None,
                "hg8347r_known_endpoint": False,
            },
            "warning": (
                "Modo lab executa mutations reais na ONT. Operações sem "
                "physical_validation são experimentais e nunca recebem retry cego."
            ),
        }

    def _require_lab(self) -> None:
        if not self._lab_mode:
            raise RuntimeError(
                "Modo lab Huawei desativado. Ative-o explicitamente antes de mutations experimentais."
            )

    def lab_write(
        self,
        *,
        operation: str | None = None,
        path: str | None = None,
        payload: dict[str, Any] | None = None,
        referer: str = "/index.asp",
        token_page: str | None = None,
        readback_path: str | None = None,
        readback_method: str = "GET",
        readback_payload: dict[str, Any] | None = None,
        readback_expect: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        self._require_lab()
        if self._mapped is None:
            raise RuntimeError(
                "Esta família Huawei não expõe a superfície AMP/BBSP mapeada; "
                "use um writer específico do protocolo."
            )
        key = str(operation or "").strip()
        if key:
            result = self.mapped_write_feature(key, dict(payload or {}))
        else:
            relative = str(path or "").strip()
            if not relative:
                raise ValueError("Informe operation ou path para o write de laboratório.")
            result = self.mapped_write_request(
                relative,
                dict(payload or {}),
                referer=referer,
                token_page=token_page,
                readback_path=readback_path,
                readback_method=readback_method,
                readback_payload=dict(readback_payload or {}),
                readback_expect=(dict(readback_expect) if readback_expect else None),
            )
        return {
            **result,
            "lab_mode": True,
            "experimental": True,
        }

    def _lab_api_reboot(self, variant: str) -> dict[str, Any]:
        client = self._client
        if client is None:
            raise RuntimeError("Sessão Huawei indisponível.")
        variants = {
            "reboot": (
                "/api/system/reboot",
                '<?xml version="1.0" encoding="UTF-8"?><request><Reboot>1</Reboot></request>',
            ),
            "deviceinfo_restart": (
                "/api/system/deviceinfo",
                '<?xml version="1.0" encoding="UTF-8"?><request><Restart/></request>',
            ),
        }
        if variant not in variants:
            raise ValueError(
                "Variante HG8245H API inválida. Use reboot ou deviceinfo_restart."
            )
        path, body = variants[variant]
        token = (
            client.session.headers.get("__RequestVerificationToken")
            or getattr(client, "_session_token", None)
        )
        headers = {
            "Content-Type": "text/xml",
            "Referer": client.base_url + "/html/index.html",
        }
        if token:
            headers["__RequestVerificationToken"] = str(token)
        # Exactly one destructive request. We intentionally do not try the
        # second known variant after a failure because the first may have been
        # accepted despite a lost response/token rotation.
        response = client.session.post(
            client.url(path),
            data=body,
            headers=headers,
            timeout=client.timeout,
            allow_redirects=False,
        )
        text = str(response.text or "")[:2000]
        lower = text.casefold()
        accepted = bool(
            response.status_code in {200, 204}
            and "<error" not in lower
            and "errorcode" not in lower
            and "<html" not in lower
        )
        return {
            "success": accepted,
            "accepted": accepted,
            "submitted": True,
            "experimental": True,
            "lab_mode": True,
            "protocol": "api_sestoken",
            "variant": variant,
            "path": path,
            "http_status": response.status_code,
            "verified": False,
            "uncertain": accepted,
            "note": "Reboot não é reenviado automaticamente; confirme pela queda/retorno do equipamento.",
        }

    def _lab_legacy_hg8245h_reboot(self) -> dict[str, Any]:
        client = self._client
        if client is None:
            raise RuntimeError("Sessão Huawei indisponível.")
        reset_page = "/html/ssmp/reset/reset.asp"
        source = client.get_page(reset_page)
        token = client.extract_token(source)
        path = (
            "/html/ssmp/reset/set.cgi?"
            "x=InternetGatewayDevice.X_HW_DEBUG.SMP.DM.ResetBoard&"
            "RequestFile=html/ssmp/reset/reset.asp"
        )
        transport = SingleWriteHttpTransport(
            client.base_url,
            timeout=client.timeout,
            verify_tls=bool(getattr(client.session, "verify", False)),
        )
        result = transport.post(
            path,
            {"x.X_HW_Token": token},
            referer=client.url(reset_page),
            cookie_header=transport.cookie_header(client.session),
        ).as_dict()
        return {
            **result,
            "success": True,
            "accepted": None,
            "submitted": True,
            "experimental": True,
            "lab_mode": True,
            "protocol": "legacy_randcount_single_write",
            "path": path,
            "verified": False,
            "uncertain": True,
            "note": "O firmware pode reiniciar antes de responder; confirme pela indisponibilidade temporária da WebUI.",
        }

    def _lab_discover_reboot_form(self) -> dict[str, Any]:
        if self._client is None or self._mapped is None:
            return {
                "success": False,
                "requires_exact_request": True,
                "reason": "reboot_surface_unavailable",
            }
        page = "/html/ssmp/reboot/reboot.asp"
        try:
            source = self._client.get_page(page)
        except Exception as exc:
            return {
                "success": False,
                "requires_exact_request": True,
                "reason": f"reboot_page:{type(exc).__name__}",
            }

        # Only auto-submit an unambiguous POST form whose action itself names
        # reboot/reset. Anything more complex must be supplied from a browser
        # capture through the exact-request lab API.
        for match in re.finditer(r"<form\b([^>]*)>(.*?)</form>", source, re.I | re.S):
            attrs, body = match.groups()
            method = re.search(r"\bmethod=[\"']([^\"']+)", attrs, re.I)
            action = re.search(r"\baction=[\"']([^\"']+)", attrs, re.I)
            if not action or (method and method.group(1).upper() != "POST"):
                continue
            target = action.group(1).strip()
            if not target.startswith("/"):
                target = "/" + target.lstrip("./")
            if not any(marker in target.casefold() for marker in ("reboot", "reset", "set.cgi")):
                continue
            payload: dict[str, str] = {}
            for tag in re.findall(r"<input\b[^>]*>", body, re.I | re.S):
                name = re.search(r"\bname=[\"']([^\"']+)", tag, re.I)
                if not name or "token" in name.group(1).casefold():
                    continue
                value = re.search(r"\bvalue=[\"']([^\"']*)", tag, re.I)
                payload[name.group(1)] = value.group(1) if value else ""
            result = self.mapped_write_request(
                target,
                payload,
                referer=page,
                token_page=page,
            )
            return {
                **result,
                "experimental": True,
                "lab_mode": True,
                "auto_discovered": True,
                "verified": False,
                "uncertain": True,
            }

        return {
            "success": False,
            "experimental": True,
            "lab_mode": True,
            "requires_exact_request": True,
            "reboot_page_available": True,
            "reason": "no_unambiguous_post_form",
            "note": "Capture a mutation do botão Reboot e envie-a em request.path/payload.",
        }

    def lab_reboot(
        self,
        *,
        variant: str = "reboot",
        request: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        self._require_lab()

        if request:
            values = dict(request)
            if values.get("single_write"):
                if self._client is None:
                    raise RuntimeError("Sessão Huawei indisponível.")
                token_page = str(values.get("token_page") or values.get("referer") or "/index.asp")
                source = self._client.get_page(token_page)
                payload = dict(values.get("payload") or {})
                payload["x.X_HW_Token"] = self._client.extract_token(source)
                transport = SingleWriteHttpTransport(
                    self._client.base_url,
                    timeout=self._client.timeout,
                    verify_tls=bool(getattr(self._client.session, "verify", False)),
                )
                raw = transport.post(
                    str(values.get("path") or ""),
                    payload,
                    referer=self._client.url(str(values.get("referer") or token_page)),
                    cookie_header=transport.cookie_header(self._client.session),
                ).as_dict()
                return {
                    **raw,
                    "success": True,
                    "submitted": True,
                    "experimental": True,
                    "lab_mode": True,
                    "verified": False,
                    "uncertain": True,
                }
            return self.lab_write(
                path=str(values.get("path") or ""),
                payload=dict(values.get("payload") or {}),
                referer=str(values.get("referer") or "/index.asp"),
                token_page=(str(values["token_page"]) if values.get("token_page") else None),
            )

        if self._phase3_active:
            return self._lab_api_reboot(variant)

        if (
            str(self.model or "").upper() == "HG8245H"
            and getattr(self._client, "auth_flow", None)
            in {HuaweiAuthFlow.RAND_COUNT, HuaweiAuthFlow.RAND_COUNT.value}
        ):
            return self._lab_legacy_hg8245h_reboot()

        return self._lab_discover_reboot_form()

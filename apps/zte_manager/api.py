import logging
import re
import traceback
from pathlib import Path
from typing import Any, Callable
from uuid import uuid4

from pydantic import ValidationError

from vela.api import api

from apps.zte_manager.schemas import (
    ACSConfigRequest,
    ACSParameterRequest,
    AdminPasswordRequest,
    AgentRequest,
    AttendantRequest,
    NamedPresetRequest,
    NamedPresetSaveRequest,
    TR069ProviderSaveRequest,
    TR069ProviderDeleteRequest,
    TR069ProviderApplyRequest,
    AttendanceReportRequest,
    AutomaticDiagnosticRequest,
    BandSteeringConfigRequest,
    BandSteeringRequest,
    BackupCompareRequest,
    BatchManagementRequest,
    BridgeModeRequest,
    BufferbloatRequest,
    CapabilityProbeRequest,
    ConnectRequest,
    DhcpBasicRequest,
    DhcpReservationRequest,
    DiagnosticRemediationRequest,
    DmzRequest,
    DnsRequest,
    DriftRequest,
    FilterGlobalManagementRequest,
    FirewallManagementRequest,
    FirewallRuleManagementRequest,
    FirmwareRegisterRequest,
    FirmwareUpgradeRequest,
    GatewayCommandRequest,
    HuaweiFeatureUpdateRequest,
    HuaweiIPv4FilterDeleteRequest,
    HuaweiIPv4FilterRuleRequest,
    InventorySyncRequest,
    InventoryUpdateRequest,
    ManagementBackupRequest,
    ManagementProfileRequest,
    MeshConfigRequest,
    MeshPairRequest,
    MonitorStartRequest,
    NumericIdRequest,
    PingRequest,
    PortForwardRequest,
    ProfileRequest,
    QoSManagementRequest,
    RadioPowerRequest,
    RemoteAccessRequest,
    ResourceIdRequest,
    RestoreBackupRequest,
    SNTPManagementRequest,
    SpeedTestRequest,
    SupportDiagnosticRequest,
    TR069ManagementRequest,
    TracerouteRequest,
    UpnpRequest,
    WifiRadioRequest,
    WifiSSIDRequest,
    WifiScheduleRequest,
    WANActionRequest,
    WANCreateRequest,
    WANDeleteRequest,
    WANManagementRequest,
    WpsRequest,
    ZeroTouchRequest,
)
from apps.zte_manager.services.cpe_management_service import (
    cpe_management_service,
)
from apps.zte_manager.services.desktop_clipboard import copy_text as copy_desktop_text
from apps.zte_manager.services.desktop_capabilities import (
    get_desktop_capabilities,
)
from apps.zte_manager.services.zte_service import zte_service
from apps.zte_manager.services.device_service import device_service
from apps.zte_manager.services.tr069_profile_service import tr069_provider_profiles
from apps.zte_manager.services.error_policy import PublicFailure, classify



logger = logging.getLogger(__name__)


def _safe_action_code(value: object) -> str:
    """Only code identifiers, never URLs, IPs, credentials or user inputs."""
    safe = re.sub(r"[^a-zA-Z0-9_]", "_", str(value or "unknown"))[:64]
    return safe or "unknown"


def _sanitized_traceback(exc: BaseException) -> str:
    """Frame names/line numbers only; exclude exception text and code lines."""
    frames = traceback.extract_tb(exc.__traceback__, limit=8)
    return ";".join(
        f"{_safe_action_code(Path(frame.filename).stem)}."
        f"{_safe_action_code(frame.name)}:{frame.lineno}"
        for frame in frames
    )


# =========================================================
# HELPERS DA API VELA
# =========================================================


def _json(context: dict | None) -> dict:
    """Extrai o JSON enviado pelo frontend sem assumir que sempre existe."""
    if not context:
        return {}

    data = context.get("json") or {}

    return data if isinstance(data, dict) else {}


def _query(context: dict | None) -> dict:
    if not context:
        return {}

    data = context.get("query") or {}

    return data if isinstance(data, dict) else {}


def _bool(value, default=False):
    if value is None:
        return default

    if isinstance(value, bool):
        return value

    return str(value).strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
        "sim",
    }


def _validated(model, context):
    """
    O Vela entrega o body como dict. Mantemos Pydantic na borda da aplicação
    para não espalhar validação por Service/Model.
    """
    return model.model_validate(
        _json(context)
    )


def _safe_call(func: Callable[..., Any], *args: Any, **kwargs: Any) -> Any:
    """Vela error boundary: explicit typed failures, no protocol details.

    The current Vela runtime serializes returned dictionaries rather than
    propagating a FastAPI-style HTTPException. Keep the existing 'error' field
    for older clients and add stable machine codes for the desktop UI.
    """
    try:
        return func(*args, **kwargs)
    except ValidationError as erro:
        # Pydantic's raw message/input can contain submitted passwords.
        # Only use the static field path, never the rejected input.
        first = erro.errors(include_input=False)[0]
        location = first.get("loc", ())
        field = _safe_action_code(location[-1] if location else "input")
        return PublicFailure(
            "INVALID_INPUT", "validation",
            "Verifique o campo " + field.replace("_", " ") + ".",
        ).envelope()
    except Exception as erro:
        known = classify(erro)
        if known is not None:
            logger.warning(
                "api_action_failure action=%s code=%s failure_type=%s",
                _safe_action_code(getattr(func, "__name__", "unknown")),
                known.code,
                _safe_action_code(type(erro).__name__),
            )
            return known.envelope()

        # Unexpected driver errors may embed whole responses, credential
        # cookies and device URLs. Log only exception TYPES and sanitized
        # traceback FRAME names; send the technician an incident code.
        error_id = uuid4().hex
        logger.error(
            "api_internal_error error_id=%s action=%s error_type=%s frames=%s",
            error_id,
            _safe_action_code(getattr(func, "__name__", "unknown")),
            _safe_action_code(type(erro).__name__),
            _sanitized_traceback(erro),
        )
        envelope = PublicFailure(
            "INTERNAL_ERROR", "internal",
            "Ocorreu um erro interno. Informe o código " +
            error_id + " ao suporte.",
        ).envelope()
        envelope["error_id"] = error_id
        return envelope


def _active_provider_service():
    """Return Huawei provider only for an active Huawei DeviceSession.

    ZTE remains the direct service for legacy routes/tests while /connect is
    vendor-neutral.
    """
    if device_service.vendor == "huawei":
        return device_service
    return zte_service

def _call_device(method_name: str, *args, **kwargs):
    """Resolve provider methods inside the API error boundary."""
    return getattr(
        device_service,
        method_name,
    )(*args, **kwargs)


def _call_device_read(method_name: str, context=None, *args, **kwargs):
    """Read through the active provider with explicit Huawei refresh only.

    Ordinary GETs consume Huawei's normalized session snapshot. The router is
    touched again only when the operator sends ?refresh=1.
    """
    if device_service.vendor == "huawei":
        kwargs["refresh"] = _bool(
            _query(context).get("refresh")
        )
    return _call_device(
        method_name,
        *args,
        **kwargs,
    )


def _call_active_provider(method_name: str, *args, **kwargs):
    """Compatibility for provider-local state endpoints.

    Huawei always resolves through DeviceService. ZTE uses the module's
    current ZTEService object so tests/runtime injections keep the same
    progress/session state.
    """
    provider = (
        device_service
        if device_service.vendor == "huawei"
        else zte_service
    )
    return getattr(
        provider,
        method_name,
    )(*args, **kwargs)


# =========================================================
# SISTEMA / CONEXÃO
# =========================================================


@api.get("/health")
def health(context=None):
    return {
        "status": "ok",
        "service": "Access Manager",
        "runtime": "Vela Framework",
    }


@api.get("/desktop/capabilities")
def desktop_capabilities(context: dict | None = None) -> dict[str, object]:
    """The backend host determines clipboard safety; never trust User-Agent."""
    return get_desktop_capabilities()


@api.post("/desktop/clipboard")
def desktop_clipboard(context=None):
    """Copia texto pela API Win32, contornando falhas do QtWebEngine."""
    return _safe_call(
        copy_desktop_text,
        _json(context).get("text"),
    )


@api.post("/connect")
def connect(context=None):
    def action():
        data = _validated(
            ConnectRequest,
            context
        )

        return device_service.connect(
            ip=data.ip,
            username=data.username,
            password=data.password,
            https=data.https,
            attendant=data.attendant,
            model_hint=data.model_hint,
        )

    return _safe_call(
        action
    )


@api.post("/disconnect")
def disconnect(context=None):
    def action():
        device_service.disconnect()

        return {
            "success": True,
            "message": "Console local desconectado.",
        }

    return _safe_call(
        action
    )


@api.get("/connection/status")
def connection_status(context=None):
    if device_service.vendor == "huawei":
        return device_service.status()

    return {
        "connected": zte_service.connected,
        "attendant": zte_service.current_attendant,
        "host": zte_service.current_host,
        "model": (
            zte_service._selected_model
            or zte_service._device_info.get("modelo")
        ),
        "firmware": zte_service._device_info.get("firmware"),
        "model_verified": zte_service._model_verified,
        "session_revision": zte_service._session_revision,
        "vendor": "zte" if zte_service.connected else None,
        "profile": (
            zte_service._adapter.name
            if zte_service._adapter
            else None
        ),
        "provider": (
            type(zte_service).__name__
            if zte_service.connected
            else None
        ),
        "capabilities": {},
        "writes_enabled": (
            bool(
                getattr(
                    zte_service._zte,
                    "writes_enabled",
                    False,
                )
            )
            if zte_service.connected
            else False
        ),
    }


@api.get("/debug/security")
def security_status(context=None):
    return _safe_call(
        zte_service.security_status
    )


# =========================================================
# DEVICE
# =========================================================


@api.get("/device/status")
def device_status(context=None):
    return _safe_call(
        _call_device_read,
        "device_status",
        context,
    )


@api.get("/device/optical")
def optical_status(context=None):
    return _safe_call(
        _call_device_read,
        "optical_status",
        context,
    )


@api.get("/device/accounts")
def account_status(context=None):
    return _safe_call(
        _call_device,
        "account_status"
    )


@api.post("/device/password")
def change_admin_password(context=None):
    def action():
        data = _validated(
            AdminPasswordRequest,
            context
        )

        return device_service.change_admin_password(
            data.new_password
        )

    return _safe_call(
        action
    )


@api.post("/device/reboot")
def reboot_device(context=None):
    return _safe_call(
        _call_device,
        "reboot"
    )


# =========================================================
# WAN / PPPOE / LAN
# =========================================================


@api.get("/wan/status")
def wan_status(context=None):
    return _safe_call(
        _call_device_read,
        "wan_status",
        context,
    )


@api.get("/wan/pppoe")
def pppoe_status(context=None):
    query = _query(
        context
    )

    return _safe_call(
        _call_device_read,
        "pppoe_status",
        context,
        reveal_password=_bool(
            query.get("reveal_password")
        ),
    )


@api.get("/clients/wifi")
def wifi_clients(context=None):
    return _safe_call(
        _call_device_read,
        "wifi_clients",
        context,
    )


@api.get("/clients/lan")
def lan_clients(context=None):
    return _safe_call(
        _call_device_read,
        "lan_clients",
        context,
    )


@api.get("/lan/ports")
def lan_ports(context=None):
    return _safe_call(
        _call_device_read,
        "lan_ports",
        context,
    )


# =========================================================
# WIFI / SSID
# =========================================================


@api.get("/wifi/networks")
def wifi_networks(context=None):
    query = _query(
        context
    )

    return _safe_call(
        _call_device_read,
        "wifi_networks",
        context,
        reveal_password=_bool(
            query.get("reveal_password")
        ),
    )


@api.post("/wifi/network/update")
def set_wifi_network(context=None):
    def action():
        data = _validated(
            WifiSSIDRequest,
            context
        )

        if not data.ssid_id:
            raise ValueError(
                "Informe o identificador do SSID."
            )

        config = data.model_dump(
            exclude_none=True,
            exclude={"ssid_id"}
        )

        if not config:
            raise ValueError(
                "Nenhuma alteração foi informada."
            )

        return device_service.set_ssid_config(
            data.ssid_id,
            config
        )

    return _safe_call(
        action
    )


@api.get("/wifi/radios")
def get_radios(context=None):
    return _safe_call(
        _call_device_read,
        "wifi_radios",
        context,
    )


@api.get("/wifi/channels")
def get_channels(context=None):
    query = _query(
        context
    )

    return _safe_call(
        _call_device,
        "wifi_channels",
        band=query.get("band"),
        bandwidth=query.get("bandwidth"),
        country=query.get("country") or "BRI",
    )


@api.post("/wifi/radio/update")
def set_radio(context=None):
    def action():
        data = _validated(
            WifiRadioRequest,
            context
        )

        if not data.band:
            raise ValueError(
                "Informe a banda do rádio."
            )

        config = data.model_dump(
            exclude_none=True,
            exclude={"band"}
        )

        if not config:
            raise ValueError(
                "Nenhuma alteração foi informada."
            )

        return device_service.set_wifi_radio(
            data.band,
            config
        )

    return _safe_call(
        action
    )


@api.get("/wifi/power")
def wifi_power_status(context=None):
    return _safe_call(
        _call_device_read,
        "radio_power_status",
        context,
    )


@api.post("/wifi/power/update")
def set_wifi_power(context=None):
    def action():
        data = _validated(
            RadioPowerRequest,
            context
        )

        return device_service.set_radio_power(
            data.band,
            data.enabled
        )

    return _safe_call(
        action
    )


@api.get("/wifi/schedule")
def wifi_schedule_status(context=None):
    return _safe_call(
        _call_device,
        "wifi_schedule_status"
    )


@api.post("/wifi/schedule/update")
def set_wifi_schedule(context=None):
    def action():
        data = _validated(
            WifiScheduleRequest,
            context
        )

        return device_service.set_wifi_schedule(
            data.model_dump()
        )

    return _safe_call(
        action
    )


@api.get("/wifi/wps")
def wifi_wps_status(context=None):
    return _safe_call(
        _call_device,
        "wps_status"
    )


@api.post("/wifi/wps/update")
def set_wifi_wps(context=None):
    def action():
        data = _validated(
            WpsRequest,
            context
        )

        return device_service.set_wps(
            data.band,
            data.mode
        )

    return _safe_call(
        action
    )


@api.get("/wifi/band-steering")
def band_steering_status(context=None):
    return _safe_call(
        _call_device,
        "band_steering_status"
    )


@api.post("/wifi/band-steering/update")
def set_band_steering(context=None):
    def action():
        data = _validated(
            BandSteeringRequest,
            context
        )

        return device_service.set_band_steering(
            data.enabled
        )

    return _safe_call(
        action
    )


@api.post("/wifi/band-steering/configure")
def configure_band_steering(context=None):
    def action():
        data = _validated(
            BandSteeringConfigRequest,
            context
        )

        return device_service.configure_band_steering(
            data.model_dump(
                exclude_none=True
            )
        )

    return _safe_call(
        action
    )


# =========================================================
# UPNP / DNS
# =========================================================


@api.get("/upnp")
def upnp_status(context=None):
    return _safe_call(
        _call_device,
        "upnp_status"
    )


@api.post("/upnp/update")
def set_upnp(context=None):
    def action():
        data = _validated(
            UpnpRequest,
            context
        )

        return device_service.set_upnp(
            data.model_dump(
                exclude_none=True
            )
        )

    return _safe_call(
        action
    )


@api.get("/dns/status")
def dns_status(context=None):
    return _safe_call(
        _call_device_read,
        "dns_status",
        context,
    )


@api.post("/dns/update")
def set_dns(context=None):
    def action():
        data = _validated(
            DnsRequest,
            context
        )

        return device_service.set_dns(
            data.model_dump(
                exclude_none=True
            )
        )

    return _safe_call(
        action
    )


# =========================================================
# DIAGNÓSTICOS
# =========================================================


@api.post("/diagnostics/ping")
def ping(context=None):
    def action():
        data = _validated(
            PingRequest,
            context
        )

        return device_service.ping(
            data.model_dump()
        )

    return _safe_call(
        action
    )


@api.post("/diagnostics/traceroute")
def traceroute(context=None):
    def action():
        data = _validated(
            TracerouteRequest,
            context
        )

        return device_service.traceroute(
            data.model_dump()
        )

    return _safe_call(
        action
    )


# =========================================================
# CAPABILITIES / MULTI-FIRMWARE
# =========================================================


@api.post("/system/backup")
def export_configuration_backup(context=None):
    return _safe_call(
        _call_device,
        "export_user_configuration"
    )


@api.get("/device/capabilities")
def capability_catalog(context=None):
    return _safe_call(
        _active_provider_service().capability_catalog
    )


@api.post("/device/capabilities/probe")
def capability_probe(context=None):
    def action():
        data = _validated(
            CapabilityProbeRequest,
            context
        )

        return _active_provider_service().probe_capabilities(
            data.features or None
        )

    return _safe_call(
        action
    )


@api.get("/huawei/ipv4-filters")
def huawei_ipv4_filters(context=None):
    return _safe_call(
        device_service.list_ipv4_filters,
        refresh=_bool(_query(context).get("refresh")),
    )


@api.get("/huawei/session-snapshot")
def huawei_session_snapshot(context=None):
    return _safe_call(
        device_service.huawei_session_snapshot
    )


@api.post("/huawei/ipv4-filters/create")
def huawei_ipv4_filter_create(context=None):
    def action():
        data = _validated(
            HuaweiIPv4FilterRuleRequest,
            context,
        )
        return device_service.create_ipv4_filter(
            data.model_dump(
                exclude={"instance_or_domain"}
            )
        )

    return _safe_call(
        action
    )


@api.post("/huawei/ipv4-filters/update")
def huawei_ipv4_filter_update(context=None):
    def action():
        data = _validated(
            HuaweiIPv4FilterRuleRequest,
            context,
        )
        if data.instance_or_domain is None:
            raise ValueError(
                "Informe a instância da regra IPv4."
            )
        return device_service.update_ipv4_filter(
            data.instance_or_domain,
            data.model_dump(
                exclude={"instance_or_domain"}
            ),
        )

    return _safe_call(
        action
    )


@api.post("/huawei/ipv4-filters/delete")
def huawei_ipv4_filter_delete(context=None):
    def action():
        data = _validated(
            HuaweiIPv4FilterDeleteRequest,
            context,
        )
        return device_service.delete_ipv4_filter(
            data.instance_or_domain
        )

    return _safe_call(
        action
    )


@api.post("/huawei/features/update")
def huawei_feature_update(context=None):
    def action():
        data = _validated(
            HuaweiFeatureUpdateRequest,
            context,
        )
        return device_service.update_captured_feature(
            data.feature,
            data.config,
        )

    return _safe_call(action)


@api.get("/discovery/bootstrap")
def discovery_bootstrap(context=None):
    """Vendor-neutral UI bootstrap without device I/O."""
    try:
        if device_service.vendor == "huawei":
            status = device_service.status()
            capabilities = status.get("capabilities") or {}
            model = status.get("model") or "Huawei"
            return {
                "connected": status.get("connected", False),
                "vendor": "huawei",
                "model": model,
                "detected_model": model,
                "model_verified": status.get("model_verified", False),
                "profile": status.get("profile"),
                "provider": status.get("provider"),
                "capabilities": capabilities,
                # Huawei has its own native capability catalog/probe. Marking
                # this False sent the frontend into /multimodel/probe, which is
                # deliberately ZTE-only and caused "Nenhuma ONT ZTE conectada".
                "native_diagnostics_available": True,
                "session_revision": status.get("session_revision"),
                "firmware": None,
                "writes_enabled": status.get("writes_enabled", False),
                "catalog": {
                    "models": [{
                        "model": model,
                        "family": "huawei_webui",
                        "candidate_features": list(capabilities.keys()),
                    }]
                },
                "reason": None,
            }

        # This branch is intentionally ZTE-only: its catalog describes
        # ThinkLua/F6201B/Vue resources and must never run for Huawei.
        device = zte_service._device_info or {}
        return {
            "connected": zte_service.connected,
            "vendor": "zte",
            "model": (
                zte_service._selected_model
                or device.get("modelo")
                or device.get("model")
            ),
            "detected_model": device.get("modelo") or device.get("model"),
            "model_verified": zte_service._model_verified,
            "native_diagnostics_available": bool(
                zte_service.connected
                and zte_service._model_verified
                and zte_service._adapter is not None
                and zte_service._adapter.name in {
                    "zte-f670l-thinklua", "zte-f6600p-thinklua",
                    "zte-f6201b-thinklua",
                }
            ),
            "session_revision": zte_service._session_revision,
            "firmware": device.get("firmware"),
            "writes_enabled": (
                bool(getattr(zte_service._zte, "writes_enabled", False))
                if zte_service.connected else False
            ),
            "catalog": zte_service.multimodel_catalog(),
            "reason": (
                None if zte_service.connected
                else "Conecte-se a uma ONT para detectar recursos."
            ),
        }
    except Exception as error:
        return _safe_call(
            lambda: (_ for _ in ()).throw(error)
        )


@api.get("/multimodel/catalog")
def multimodel_catalog(context=None):
    if device_service.vendor == "huawei":
        def huawei_catalog():
            status = device_service.status()
            capabilities = status.get("capabilities") or {}
            return {
                "models": [{
                    "model": status.get("model") or "Huawei",
                    "family": "huawei_webui",
                    "candidate_features": list(capabilities.keys()),
                }]
            }
        return _safe_call(huawei_catalog)
    return _safe_call(
        zte_service.multimodel_catalog
    )


@api.post("/multimodel/diagnostic")
def multimodel_diagnostic(context=None):
    """Consulta por família somente leitura, sem ping/traceroute no roteador."""
    if device_service.vendor == "huawei":
        return _safe_call(
            lambda: {
                "model": device_service.status().get("model"),
                "family": "huawei_webui",
                "read_only": True,
                "sections": {},
                "reason": (
                    "Use Detectar recursos: Huawei possui probe nativo "
                    "por capability e não usa o diagnóstico ThinkLua."
                ),
            }
        )
    body = _json(context)
    requested = str(body.get("model") or "")[:50].strip()
    section = str(body.get("section") or "")[:32].strip() or None
    return _safe_call(
        zte_service.multimodel_diagnostic,
        requested or None,
        section,
    )


@api.post("/multimodel/mesh")
def multimodel_mesh(context=None):
    if device_service.vendor == "huawei":
        return _safe_call(
            lambda: {
                "available": False,
                "vendor": "huawei",
                "model": device_service.status().get("model"),
                "reason": (
                    "Resumo Mesh ThinkLua não se aplica à sessão Huawei."
                ),
            }
        )
    model = str(_json(context).get("model") or "")[:50].strip()
    return _safe_call(
        zte_service.multimodel_mesh,
        model or None,
    )


@api.post("/multimodel/probe")
def multimodel_probe(context=None):
    if device_service.vendor == "huawei":
        def huawei_probe():
            status = device_service.status()
            catalog = device_service.capability_catalog()
            features = []
            for key, spec in (catalog.get("features") or {}).items():
                operations = spec.get("operations") or {}
                features.append({
                    "feature": key,
                    "label": spec.get("label") or key,
                    "status": (
                        "detected"
                        if operations.get("read")
                        and operations.get("verified")
                        else "not_tested"
                    ),
                    "available": bool(operations.get("read")),
                    "verified": bool(operations.get("verified")),
                })
            return {
                "model": status.get("model"),
                "family": "huawei_webui",
                "capabilities": features,
                "candidate_features": [],
                "reason": None,
            }
        return _safe_call(huawei_probe)

    # O usuário pode informar modelo quando o firmware omite a identificação.
    # Não envia escrita ao roteador e limita o nome fornecido.
    body = _json(context)
    model = str(body.get("model") or "")[:50].strip()
    try:
        count = min(10, max(1, int(body.get("max_endpoints", 4))))
        # Modelos mapeados têm mais de dez rotas; não reiniciar no offset 10.
        start = min(1000, max(0, int(body.get("start", 0))))
    except (TypeError, ValueError):
        count, start = 4, 0
    return _safe_call(
        zte_service.multimodel_probe,
        model or None,
        count,
        start,
    )


# O aplicativo não concede nem restringe privilégios de roteador por operador.
# Cada serviço confirma o modelo, o formulário real e a sessão da ONT.
@api.get("/f6201b/write/status")
def f6201b_write_status(context=None):
    return _safe_call(zte_service.f6201b_write_status)


@api.get("/f6201b/write/ssids")
def f6201b_write_ssids(context=None):
    return _safe_call(zte_service.f6201b_write_ssids)


@api.post("/f6201b/write/preview")
def f6201b_write_preview(context=None):
    body = _json(context)
    ssid_id = str(body.get("ssid_id") or "")[:64]
    config = body.get("config")
    return _safe_call(
        zte_service.f6201b_write_preview, ssid_id, config
    )


@api.post("/f6201b/write/apply")
def f6201b_write_apply(context=None):
    body = _json(context)
    # Somente nonce e confirmação, nunca aceitar payload arbitrário no Apply.
    nonce = str(body.get("nonce") or "")[:100]
    confirmation = str(body.get("confirmation") or "")[:50]
    return _safe_call(zte_service.f6201b_write_apply, nonce, confirmation)


@api.post("/f6201b/write/update")
def f6201b_write_update(context=None):
    body = _json(context)
    return _safe_call(
        zte_service.f6201b_ssid_update,
        str(body.get("ssid_id") or "")[:64],
        body.get("config"),
    )


@api.get("/f6201b/wan/summary")
def f6201b_wan_summary(context=None):
    """Local read only; credentials are explicitly excluded."""
    return _safe_call(zte_service.f6201b_wan_summary)


@api.get("/f6201b/dns/status")
def f6201b_dns_status(context=None):
    return _safe_call(zte_service.f6201b_dns_status)


@api.post("/f6201b/dns/preview")
def f6201b_dns_preview(context=None):
    body = _json(context)
    return _safe_call(zte_service.f6201b_dns_preview, body.get("changes"))


@api.post("/f6201b/dns/apply")
def f6201b_dns_apply(context=None):
    body = _json(context)
    return _safe_call(
        zte_service.f6201b_dns_apply,
        str(body.get("nonce") or "")[:100],
        str(body.get("confirmation") or "")[:50],
    )


@api.post("/f6201b/dns/update")
def f6201b_dns_update(context=None):
    return _safe_call(
        zte_service.f6201b_dns_update,
        _json(context).get("changes"),
    )


# Formulários capturados F6201B: operações específicas por modelo.
# Laboratório F6201B: sete estratégias de formulário dedicadas e
# catálogo do estado das 25 rotas. POST recebe só o nonce da prévia;
# não aceita um body de configuração arbitrário.
@api.get("/f6201b/workbench/catalog")
def f6201b_workbench_catalog(context=None):
    return zte_service.captured_workbench_catalog()


@api.post("/f6201b/workbench/inspect")
def f6201b_workbench_inspect(context=None):
    tag = str(_json(context).get("tag") or "")[:100]
    return _safe_call(zte_service.captured_workbench_inspect, tag)


@api.post("/f6201b/workbench/preview")
def f6201b_workbench_preview(context=None):
    body = _json(context)
    return _safe_call(
        zte_service.captured_workbench_preview,
        str(body.get("tag") or "")[:100],
        str(body.get("instance_id") or "")[:128],
        body.get("changes"),
    )


@api.post("/f6201b/workbench/apply")
def f6201b_workbench_apply(context=None):
    body = _json(context)
    return _safe_call(
        zte_service.captured_workbench_apply,
        str(body.get("nonce") or "")[:100],
        str(body.get("confirmation") or "")[:50],
        body.get("risk_ack") is True,
    )


@api.post("/f6201b/workbench/update")
def f6201b_workbench_update(context=None):
    body = _json(context)
    return _safe_call(
        zte_service.captured_workbench_update,
        str(body.get("tag") or "")[:100],
        str(body.get("instance_id") or "")[:128],
        body.get("changes"),
    )


@api.get("/multimodel/mapped-routes")
def mapped_f6201b_routes(context=None):
    """Inventário de rotas GET do manifesto sanitizado, sem acessar ONT."""
    return zte_service.mapped_f6201b_routes()


@api.post("/multimodel/mapped-inspect")
def inspect_mapped_f6201b_route(context=None):
    """Rota estritamente allowlist; só devolve formato, nunca valores XML."""
    tag = str(_json(context).get("tag") or "").strip()[:100]
    return _safe_call(zte_service.inspect_mapped_f6201b_route, tag)


@api.get("/features/shape")
def feature_shape(context=None):
    feature = str(
        _query(context).get("feature") or ""
    ).strip()

    if not feature:
        return {
            "error": "Informe ?feature=.",
            "type": "validation",
        }

    return _safe_call(
        _active_provider_service().capability_shape,
        feature,
    )


@api.get("/features/read")
def read_feature(context=None):
    query = _query(
        context
    )

    feature = str(
        query.get("feature") or ""
    ).strip()

    if not feature:
        return {
            "error": "Informe a capability em ?feature=.",
            "type": "validation",
        }

    if device_service.vendor == "huawei":
        return _safe_call(
            device_service.read_capability,
            feature,
            refresh=_bool(query.get("refresh")),
        )
    return _safe_call(
        _active_provider_service().read_capability,
        feature
    )


# =========================================================
# DHCP / LAN / NAT
# =========================================================


@api.get("/network/dhcp")
def dhcp_status(context=None):
    return _safe_call(
        _call_device_read,
        "dhcp_status",
        context,
    )


@api.post("/network/dhcp/update")
def update_dhcp(context=None):
    def action():
        data = _validated(
            DhcpBasicRequest,
            context
        )

        return device_service.set_dhcp_basic(
            data.model_dump(
                exclude_none=True
            )
        )

    return _safe_call(
        action
    )


@api.post("/network/dhcp/reservation/save")
def save_dhcp_reservation(context=None):
    def action():
        data = _validated(
            DhcpReservationRequest,
            context
        )

        return device_service.save_dhcp_reservation(
            data.model_dump()
        )

    return _safe_call(
        action
    )


@api.post("/network/dhcp/reservation/delete")
def delete_dhcp_reservation(context=None):
    def action():
        data = _validated(
            ResourceIdRequest,
            context
        )

        return device_service.delete_dhcp_reservation(
            data.id
        )

    return _safe_call(
        action
    )


@api.get("/network/port-forwarding")
def port_forwarding_status(context=None):
    return _safe_call(
        _call_device,
        "port_forwarding_status"
    )


@api.post("/network/port-forwarding/save")
def save_port_forward(context=None):
    def action():
        data = _validated(
            PortForwardRequest,
            context
        )

        return device_service.save_port_forward(
            data.model_dump()
        )

    return _safe_call(
        action
    )


@api.post("/network/port-forwarding/delete")
def delete_port_forward(context=None):
    def action():
        data = _validated(
            ResourceIdRequest,
            context
        )

        return device_service.delete_port_forward(
            data.id,
            confirm=data.confirm,
        )

    return _safe_call(
        action
    )


@api.get("/network/dmz")
def dmz_status(context=None):
    return _safe_call(
        _call_device_read,
        "dmz_status",
        context,
    )


@api.post("/network/dmz/update")
def update_dmz(context=None):
    def action():
        data = _validated(
            DmzRequest,
            context
        )

        return device_service.set_dmz(
            data.model_dump()
        )

    return _safe_call(
        action
    )


# =========================================================
# DIAGNÓSTICO AUTOMÁTICO / HISTÓRICO
# =========================================================


@api.post("/diagnostics/automatic")
def automatic_diagnostic(context=None):
    def action():
        data = _validated(
            AutomaticDiagnosticRequest,
            context
        )

        return device_service.automatic_diagnostic(
            data.model_dump()
        )

    return _safe_call(
        action
    )


@api.get("/diagnostics/support/progress")
def support_diagnostic_progress(context=None):
    """Progress is in-memory and independent of the active ONT RLock."""
    return _safe_call(_call_active_provider, "support_progress")


@api.post("/diagnostics/support")
def support_diagnostic(context=None):
    def action():
        data = _validated(
            SupportDiagnosticRequest,
            context
        )

        return device_service.support_diagnostic(
            data.model_dump()
        )

    return _safe_call(
        action
    )


@api.post("/diagnostics/support/f6201b")
def support_diagnostic_f6201b(context=None):
    def action():
        data = _validated(SupportDiagnosticRequest, context)
        return zte_service.f6201b_support_diagnostic(data.model_dump())
    return _safe_call(action)


@api.post("/diagnostics/remediate")
def remediate_diagnostic(context=None):
    def action():
        data = _validated(
            DiagnosticRemediationRequest,
            context
        )

        return device_service.remediate_diagnostic(
            data.model_dump()
        )

    return _safe_call(
        action
    )


@api.get("/diagnostics/workstation")
def workstation_diagnostic(context=None):
    """Read-only comparison from the technician's computer (not the ONT)."""
    return _safe_call(_call_device, "workstation_diagnostic")


@api.post("/diagnostics/speedtest")
def speedtest(context=None):
    def action():
        data = _validated(
            SpeedTestRequest,
            context
        )

        return device_service.speedtest(
            data.model_dump()
        )

    return _safe_call(
        action
    )


@api.post("/diagnostics/attendance")
def generate_attendance(context=None):
    def action():
        data = _validated(
            AttendanceReportRequest,
            context
        )

        return _active_provider_service().generate_attendance(
            data.diagnostic_id
        )

    return _safe_call(
        action
    )


@api.post("/history/snapshot")
def capture_snapshot(context=None):
    reason = str(
        _json(context).get("reason")
        or "manual"
    )[:120]

    return _safe_call(
        _active_provider_service().capture_snapshot,
        reason
    )


@api.get("/history")
def history(context=None):
    query = _query(
        context
    )

    try:
        limit = int(
            query.get("limit") or 50
        )
    except (
        TypeError,
        ValueError,
    ):
        limit = 50

    return _safe_call(
        _active_provider_service().history,
        limit
    )


# =========================================================
# CONFIGURAÇÃO / PERFIS DO ATENDENTE
# =========================================================


@api.get("/configuration/current")
def current_configuration(context=None):
    return _safe_call(
        _call_device,
        "current_configuration"
    )


@api.get("/profiles")
def profiles(context=None):
    return {
        "profiles": zte_service.profiles()
    }


@api.post("/profiles/get")
def get_profile(context=None):
    def action():
        data = _validated(
            AttendantRequest,
            context
        )

        return zte_service.get_profile(
            data.attendant
        )

    return _safe_call(
        action
    )


@api.post("/profiles/save")
def save_profile(context=None):
    def action():
        data = _validated(
            ProfileRequest,
            context
        )

        return zte_service.save_profile(
            data.attendant,
            {
                "wifi": data.wifi,
                "dns": data.dns,
            }
        )

    return _safe_call(
        action
    )


# Named presets preserve all existing single-primary profile routes.
@api.post("/profiles/named/list")
def list_named_presets(context=None):
    def action():
        data = _validated(AttendantRequest, context)
        return {"names": zte_service.list_named_presets(data.attendant)}
    return _safe_call(action)


@api.post("/profiles/named/get")
def get_named_preset(context=None):
    def action():
        data = _validated(NamedPresetRequest, context)
        return zte_service.get_named_preset(data.attendant, data.name)
    return _safe_call(action)


@api.post("/profiles/named/save")
def save_named_preset(context=None):
    def action():
        data = _validated(NamedPresetSaveRequest, context)
        return zte_service.save_named_preset(
            data.attendant, data.name,
            {"wifi": data.wifi, "dns": data.dns},
        )
    return _safe_call(action)


@api.post("/profiles/named/delete")
def delete_named_preset(context=None):
    def action():
        data = _validated(NamedPresetRequest, context)
        return {"success": zte_service.delete_named_preset(
            data.attendant, data.name
        )}
    return _safe_call(action)


@api.post("/profiles/named/apply")
def apply_named_preset(context=None):
    def action():
        data = _validated(NamedPresetRequest, context)
        return device_service.apply_named_preset(data.attendant, data.name)
    return _safe_call(action)


@api.post("/profiles/capture")
def capture_profile(context=None):
    def action():
        data = _validated(
            AttendantRequest,
            context
        )

        return device_service.capture_profile(
            data.attendant
        )

    return _safe_call(
        action
    )


# Experimental F6201B profile uses the captured RF+DNS forms, NOT the
# unrestricted legacy batch shared by F6600P/F670L.
@api.post("/f6201b/profile/preview")
def f6201b_profile_preview(context=None):
    def action():
        data = _validated(AttendantRequest, context)
        return zte_service.f6201b_profile_preview(data.attendant)
    return _safe_call(action)


@api.post("/f6201b/profile/apply-saved")
def f6201b_profile_apply_saved(context=None):
    def action():
        data = _validated(AttendantRequest, context)
        return zte_service.f6201b_profile_apply_saved(data.attendant)
    return _safe_call(action)


@api.post("/f6201b/profile/apply")
def f6201b_profile_apply(context=None):
    body = _json(context)
    return _safe_call(
        zte_service.f6201b_profile_apply,
        str(body.get("nonce") or "")[:100],
        str(body.get("confirmation") or "")[:50],
    )


@api.post("/profiles/apply")
def apply_profile(context=None):
    def action():
        data = _validated(
            AttendantRequest,
            context
        )

        return device_service.apply_profile(
            data.attendant
        )

    return _safe_call(
        action
    )



# =========================================================
# CPE MANAGEMENT PLATFORM
# =========================================================


@api.get("/management/inventory")
def management_inventory(context=None):
    query = _query(
        context
    )

    try:
        limit = int(
            query.get(
                "limit"
            )
            or 500
        )
    except (
        TypeError,
        ValueError,
    ):
        limit = 500

    return _safe_call(
        cpe_management_service.devices,
        query=query.get(
            "q"
        ),
        status=query.get(
            "status"
        ),
        limit=limit,
    )


@api.post("/management/inventory/sync")
def management_inventory_sync(context=None):
    def action():
        data = _validated(
            InventorySyncRequest,
            context
        )

        return cpe_management_service.sync_inventory(
            device_service,
            data.model_dump(),
        )

    return _safe_call(
        action
    )


@api.post("/management/inventory/update")
def management_inventory_update(context=None):
    def action():
        data = _validated(
            InventoryUpdateRequest,
            context
        )

        values = data.model_dump(
            exclude_none=True,
            exclude={
                "device_id",
            },
        )

        return cpe_management_service.update_device(
            data.device_id,
            values,
        )

    return _safe_call(
        action
    )


@api.get("/management/profiles")
def management_profiles(context=None):
    return _safe_call(
        cpe_management_service.profiles
    )


@api.post("/management/profiles/save")
def management_profile_save(context=None):
    def action():
        data = _validated(
            ManagementProfileRequest,
            context
        )

        return cpe_management_service.save_profile(
            data.model_dump()
        )

    return _safe_call(
        action
    )


@api.post("/management/drift")
def management_drift(context=None):
    def action():
        data = _validated(
            DriftRequest,
            context
        )

        return cpe_management_service.drift(
            device_service,
            data.model_dump(),
        )

    return _safe_call(
        action
    )


@api.post("/management/drift/remediate")
def management_drift_remediate(context=None):
    def action():
        data = _validated(
            DriftRequest,
            context
        )

        return cpe_management_service.remediate_drift(
            device_service,
            data.model_dump(),
        )

    return _safe_call(
        action
    )


@api.post("/management/batch")
def management_batch_create(context=None):
    def action():
        data = _validated(
            BatchManagementRequest,
            context
        )

        return cpe_management_service.create_batch(
            device_service,
            data.model_dump(),
        )

    return _safe_call(
        action
    )


@api.get("/management/batch")
def management_batch_jobs(context=None):
    return _safe_call(
        cpe_management_service.batch_jobs
    )


@api.get("/management/batch/job")
def management_batch_job(context=None):
    query = _query(
        context
    )

    job_id = query.get(
        "id"
    )

    if not job_id:
        return {
            "error": "Informe ?id= do job.",
            "type": "validation",
        }

    return _safe_call(
        cpe_management_service.batch_job,
        int(
            job_id
        ),
    )


# =========================================================
# AGENTS / VPN / TERMINAL / IPERF
# =========================================================


@api.get("/management/agents")
def management_agents(context=None):
    return _safe_call(
        cpe_management_service.agents
    )


@api.post("/management/agents/save")
def management_agent_save(context=None):
    def action():
        data = _validated(
            AgentRequest,
            context
        )

        return cpe_management_service.save_agent(
            data.model_dump()
        )

    return _safe_call(
        action
    )


@api.post("/management/agents/test")
def management_agent_test(context=None):
    def action():
        data = _validated(
            NumericIdRequest,
            context
        )

        return cpe_management_service.test_agent(
            data.id
        )

    return _safe_call(
        action
    )


@api.get("/management/remote/sessions")
def management_remote_sessions(context=None):
    return _safe_call(
        cpe_management_service.remote_sessions
    )


@api.post("/management/remote/open")
def management_remote_open(context=None):
    def action():
        data = _validated(
            RemoteAccessRequest,
            context
        )

        return cpe_management_service.open_remote(
            device_service,
            data.model_dump(),
        )

    return _safe_call(
        action
    )


@api.post("/management/remote/close")
def management_remote_close(context=None):
    def action():
        data = _validated(
            NumericIdRequest,
            context
        )

        return cpe_management_service.close_remote(
            data.id
        )

    return _safe_call(
        action
    )


@api.post("/management/gateway/bufferbloat")
def management_gateway_bufferbloat(context=None):
    def action():
        data = _validated(
            BufferbloatRequest,
            context
        )

        return cpe_management_service.bufferbloat(
            data.model_dump()
        )

    return _safe_call(
        action
    )


@api.post("/management/gateway/command")
def management_gateway_command(context=None):
    def action():
        data = _validated(
            GatewayCommandRequest,
            context
        )

        return cpe_management_service.gateway_command(
            data.model_dump()
        )

    return _safe_call(
        action
    )


# =========================================================
# MONITORAMENTO / TOPOLOGIA / INCIDENTES
# =========================================================


@api.post("/management/monitor/start")
def management_monitor_start(context=None):
    def action():
        data = _validated(
            MonitorStartRequest,
            context
        )

        return cpe_management_service.start_monitor(
            device_service,
            data.model_dump(),
        )

    return _safe_call(
        action
    )


@api.get("/management/monitor/status")
def management_monitor_status(context=None):
    query = _query(
        context
    )

    run_id = query.get(
        "id"
    )

    if not run_id:
        return {
            "error": "Informe ?id= do monitor.",
            "type": "validation",
        }

    return _safe_call(
        cpe_management_service.monitor_status,
        int(
            run_id
        ),
    )


@api.post("/management/monitor/stop")
def management_monitor_stop(context=None):
    def action():
        data = _validated(
            NumericIdRequest,
            context
        )

        return cpe_management_service.stop_monitor(
            data.id
        )

    return _safe_call(
        action
    )


@api.get("/management/topology")
def management_topology(context=None):
    query = _query(
        context
    )

    device_id = query.get(
        "device_id"
    )

    if not device_id:
        return {
            "error": "Informe ?device_id=.",
            "type": "validation",
        }

    return _safe_call(
        cpe_management_service.topology,
        device_service,
        int(
            device_id
        ),
    )


@api.get("/management/incidents")
def management_incidents(context=None):
    return _safe_call(
        cpe_management_service.incidents,
        _query(
            context
        ).get(
            "status"
        ),
    )


@api.post("/management/incidents/correlate")
def management_incidents_correlate(context=None):
    data = _json(
        context
    )

    return _safe_call(
        cpe_management_service.correlate_incidents,
        data.get(
            "minimum_devices"
        )
        or 5,
    )


# =========================================================
# NETWORK CONTROL
# =========================================================


@api.get("/management/network")
def management_network_overview(context=None):
    return _safe_call(
        cpe_management_service.network_overview,
        device_service,
    )


@api.get("/management/mesh")
def management_mesh_status(context=None):
    return _safe_call(
        cpe_management_service.mesh_status,
        device_service,
    )


@api.post("/management/mesh/configure")
def management_mesh_configure(context=None):
    def action():
        data = _validated(
            MeshConfigRequest,
            context
        )

        return cpe_management_service.mesh_configure(
            device_service,
            data.model_dump(),
        )

    return _safe_call(
        action
    )


@api.post("/management/mesh/pair")
def management_mesh_pair(context=None):
    def action():
        data = _validated(
            MeshPairRequest,
            context
        )

        return cpe_management_service.mesh_pair(
            device_service,
            data.model_dump(),
        )

    return _safe_call(
        action
    )


@api.get("/management/qos")
def management_qos(context=None):
    return _safe_call(
        _call_device,
        "qos_management_status"
    )


@api.post("/management/qos/save")
def management_qos_save(context=None):
    def action():
        data = _validated(
            QoSManagementRequest,
            context
        )

        return cpe_management_service.qos_save(
            device_service,
            data.model_dump(),
        )

    return _safe_call(
        action
    )


@api.post("/management/qos/delete")
def management_qos_delete(context=None):
    def action():
        data = _validated(
            QoSManagementRequest,
            context
        )

        if not data.id:
            raise ValueError(
                "Informe o id da regra QoS."
            )

        return cpe_management_service.qos_delete(
            device_service,
            data.model_dump(),
        )

    return _safe_call(
        action
    )


@api.get("/management/firewall")
def management_firewall(context=None):
    return _safe_call(
        _call_device,
        "firewall_management_status"
    )


@api.post("/management/firewall/update")
def management_firewall_update(context=None):
    def action():
        data = _validated(
            FirewallManagementRequest,
            context
        )

        return cpe_management_service.firewall_set(
            device_service,
            data.model_dump(),
        )

    return _safe_call(
        action
    )


@api.get("/management/firewall/rules")
def management_firewall_rules(context=None):
    return _safe_call(
        cpe_management_service.firewall_rules,
        device_service,
    )


@api.post("/management/firewall/rules/save")
def management_firewall_rule_save(context=None):
    def action():
        data = _validated(
            FirewallRuleManagementRequest,
            context
        )

        return cpe_management_service.firewall_rule_save(
            device_service,
            data.model_dump(),
        )

    return _safe_call(
        action
    )


@api.post("/management/firewall/rules/delete")
def management_firewall_rule_delete(context=None):
    def action():
        data = _validated(
            FirewallRuleManagementRequest,
            context
        )

        return cpe_management_service.firewall_rule_delete(
            device_service,
            data.model_dump(),
        )

    return _safe_call(
        action
    )


@api.post("/management/firewall/filter-global")
def management_filter_global(context=None):
    def action():
        data = _validated(
            FilterGlobalManagementRequest,
            context
        )

        return cpe_management_service.filter_global_set(
            device_service,
            data.model_dump(),
        )

    return _safe_call(
        action
    )


@api.get("/management/sntp")
def management_sntp(context=None):
    return _safe_call(
        _call_device,
        "sntp_management_status"
    )


@api.post("/management/sntp/update")
def management_sntp_update(context=None):
    def action():
        data = _validated(
            SNTPManagementRequest,
            context
        )

        return cpe_management_service.sntp_set(
            device_service,
            data.model_dump(),
        )

    return _safe_call(
        action
    )


@api.get("/tr069/providers")
def list_tr069_providers(context=None):
    return _safe_call(lambda: {"profiles": tr069_provider_profiles.list()})


@api.post("/tr069/providers/save")
def save_tr069_provider(context=None):
    def action():
        data = _validated(TR069ProviderSaveRequest, context)
        return tr069_provider_profiles.save(data.profile)
    return _safe_call(action)


@api.post("/tr069/providers/delete")
def delete_tr069_provider(context=None):
    def action():
        data = _validated(TR069ProviderDeleteRequest, context)
        return {"success": tr069_provider_profiles.delete(data.name)}
    return _safe_call(action)


@api.get("/tr069/setup")
def tr069_setup(context=None):
    return _safe_call(
        _call_device_read,
        "tr069_setup",
        context,
    )


@api.post("/tr069/providers/apply")
def apply_tr069_provider(context=None):
    def action():
        data = _validated(TR069ProviderApplyRequest, context)
        if data.confirm is not True:
            raise ValueError("Confirme a aplicação dos parâmetros ACS.")
        return device_service.apply_tr069_provider(
            data.name, data.wan_name,
            password=data.password,
            connection_request_password=data.connection_request_password,
        )
    return _safe_call(action)


@api.get("/management/tr069")
def management_tr069(context=None):
    return _safe_call(
        _call_device_read,
        "tr069_management_status",
        context,
    )


@api.post("/management/tr069/update")
def management_tr069_update(context=None):
    def action():
        data = _validated(
            TR069ManagementRequest,
            context
        )

        return cpe_management_service.tr069_set(
            device_service,
            data.model_dump(),
        )

    return _safe_call(
        action
    )


@api.get("/management/wan")
def management_wan(context=None):
    return _safe_call(
        _call_device,
        "wan_configurations"
    )


@api.post("/management/wan/create")
def management_wan_create(context=None):
    def action():
        data = _validated(
            WANCreateRequest,
            context
        )

        return cpe_management_service.wan_create(
            device_service,
            data.model_dump(),
        )

    return _safe_call(
        action
    )


@api.post("/management/wan/update")
def management_wan_update(context=None):
    def action():
        data = _validated(
            WANManagementRequest,
            context
        )

        return cpe_management_service.wan_update(
            device_service,
            data.model_dump(),
        )

    return _safe_call(
        action
    )


@api.post("/management/wan/delete")
def management_wan_delete(context=None):
    def action():
        data = _validated(
            WANDeleteRequest,
            context
        )

        return cpe_management_service.wan_delete(
            device_service,
            data.model_dump(),
        )

    return _safe_call(
        action
    )


@api.post("/management/wan/action")
def management_wan_action(context=None):
    def action():
        data = _validated(
            WANActionRequest,
            context
        )

        return cpe_management_service.wan_action(
            device_service,
            data.model_dump(),
        )

    return _safe_call(
        action
    )


@api.post("/management/bridge")
def management_bridge(context=None):
    def action():
        data = _validated(
            BridgeModeRequest,
            context
        )

        return cpe_management_service.bridge(
            device_service,
            data.model_dump(),
        )

    return _safe_call(
        action
    )


# =========================================================
# BACKUP / FIRMWARE
# =========================================================


@api.get("/management/backups")
def management_backups(context=None):
    query = _query(
        context
    )

    device_id = query.get(
        "device_id"
    )

    return _safe_call(
        cpe_management_service.backups,
        (
            int(device_id)
            if device_id
            else None
        ),
    )


@api.post("/management/backups/create")
def management_backup_create(context=None):
    def action():
        data = _validated(
            ManagementBackupRequest,
            context
        )

        return cpe_management_service.backup(
            device_service,
            data.model_dump(),
        )

    return _safe_call(
        action
    )


@api.post("/management/backups/compare")
def management_backup_compare(context=None):
    def action():
        data = _validated(
            BackupCompareRequest,
            context
        )

        return cpe_management_service.compare_backups(
            data.model_dump()
        )

    return _safe_call(
        action
    )


@api.post("/management/backups/restore")
def management_backup_restore(context=None):
    def action():
        data = _validated(
            RestoreBackupRequest,
            context
        )

        return cpe_management_service.restore(
            device_service,
            data.model_dump(),
        )

    return _safe_call(
        action
    )


@api.get("/management/firmware")
def management_firmware(context=None):
    return _safe_call(
        cpe_management_service.firmware_list,
        _query(
            context
        ).get(
            "model"
        ),
    )


@api.post("/management/firmware/register")
def management_firmware_register(context=None):
    def action():
        data = _validated(
            FirmwareRegisterRequest,
            context
        )

        return cpe_management_service.firmware_register(
            data.model_dump()
        )

    return _safe_call(
        action
    )


@api.get("/management/firmware/status")
def management_firmware_status(context=None):
    return _safe_call(
        _call_device,
        "firmware_management_status"
    )


@api.post("/management/firmware/upgrade")
def management_firmware_upgrade(context=None):
    def action():
        data = _validated(
            FirmwareUpgradeRequest,
            context
        )

        return cpe_management_service.firmware_upgrade(
            device_service,
            data.model_dump(),
        )

    return _safe_call(
        action
    )


# =========================================================
# ACS / USP / ZERO TOUCH
# =========================================================


@api.get("/management/acs")
def management_acs_status(context=None):
    return _safe_call(
        cpe_management_service.acs_status
    )


@api.post("/management/acs/configure")
def management_acs_configure(context=None):
    def action():
        data = _validated(
            ACSConfigRequest,
            context
        )

        return cpe_management_service.configure_acs(
            data.model_dump()
        )

    return _safe_call(
        action
    )


@api.get("/management/acs/discover")
def management_acs_discover(context=None):
    query = _query(
        context
    )

    device_id = query.get(
        "device_id"
    )

    if not device_id:
        return {
            "error": "Informe ?device_id=.",
            "type": "validation",
        }

    return _safe_call(
        cpe_management_service.acs_discover,
        int(
            device_id
        ),
    )


@api.post("/management/acs/parameters")
def management_acs_parameters(context=None):
    def action():
        data = _validated(
            ACSParameterRequest,
            context
        )

        return cpe_management_service.acs_parameters(
            data.model_dump()
        )

    return _safe_call(
        action
    )


@api.post("/management/zero-touch")
def management_zero_touch(context=None):
    def action():
        data = _validated(
            ZeroTouchRequest,
            context
        )

        return cpe_management_service.zero_touch(
            device_service,
            data.model_dump(),
        )

    return _safe_call(
        action
    )

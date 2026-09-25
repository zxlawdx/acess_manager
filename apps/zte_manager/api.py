from pydantic import ValidationError

from vela.api import api

from apps.zte_manager.schemas import (
    ACSConfigRequest,
    ACSParameterRequest,
    AdminPasswordRequest,
    AgentRequest,
    AttendantRequest,
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
from apps.zte_manager.services.zte_service import zte_service


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


def _safe_call(func, *args, **kwargs):
    """
    Adapter da camada HTTP do Vela.

    O servidor interno atual serializa dict/list, mas não possui o mesmo
    mecanismo de HTTPException do FastAPI. Portanto erros conhecidos voltam
    em um envelope {"error": ...}; o app.js converte esse envelope em exceção.
    """
    try:
        return func(
            *args,
            **kwargs
        )

    except ValidationError as erro:
        primeiro = erro.errors()[0]
        campo = ".".join(
            str(item)
            for item in primeiro.get("loc", [])
        )

        mensagem = primeiro.get(
            "msg",
            "Dados inválidos."
        )

        return {
            "error": (
                f"{campo}: {mensagem}"
                if campo
                else mensagem
            ),
            "type": "validation",
        }

    except ValueError as erro:
        return {
            "error": str(erro),
            "type": "validation",
        }

    except RuntimeError as erro:
        return {
            "error": str(erro),
            "type": "state",
        }

    except TimeoutError as erro:
        return {
            "error": str(erro),
            "type": "timeout",
        }

    except Exception as erro:
        return {
            "error": str(erro),
            "type": "internal",
        }


# =========================================================
# SISTEMA / CONEXÃO
# =========================================================


@api.get("/health")
def health(context=None):
    return {
        "status": "ok",
        "service": "ZTE Automatic",
        "runtime": "Vela Framework",
    }


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

        return zte_service.connect(
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
        zte_service.disconnect()

        return {
            "success": True,
            "message": "Console local desconectado.",
        }

    return _safe_call(
        action
    )


@api.get("/connection/status")
def connection_status(context=None):
    return {
        "connected": zte_service.connected,
        "attendant": zte_service.current_attendant,
        "host": zte_service.current_host,
        # Estado para recuperar a SPA após reload do WebView.
        # Nunca retornar credenciais, cookies ou token da ONT.
        "model": (
            zte_service._device_info.get("modelo")
            or zte_service._selected_model
        ),
        "firmware": zte_service._device_info.get("firmware"),
        "writes_enabled": (
            bool(getattr(zte_service._zte, "writes_enabled", True))
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
        zte_service.device_status
    )


@api.get("/device/optical")
def optical_status(context=None):
    return _safe_call(
        zte_service.optical_status
    )


@api.get("/device/accounts")
def account_status(context=None):
    return _safe_call(
        zte_service.account_status
    )


@api.post("/device/password")
def change_admin_password(context=None):
    def action():
        data = _validated(
            AdminPasswordRequest,
            context
        )

        return zte_service.change_admin_password(
            data.new_password
        )

    return _safe_call(
        action
    )


@api.post("/device/reboot")
def reboot_device(context=None):
    return _safe_call(
        zte_service.reboot
    )


# =========================================================
# WAN / PPPOE / LAN
# =========================================================


@api.get("/wan/status")
def wan_status(context=None):
    return _safe_call(
        zte_service.wan_status
    )


@api.get("/wan/pppoe")
def pppoe_status(context=None):
    query = _query(
        context
    )

    return _safe_call(
        zte_service.pppoe_status,
        reveal_password=_bool(
            query.get("reveal_password")
        )
    )


@api.get("/clients/wifi")
def wifi_clients(context=None):
    return _safe_call(
        zte_service.wifi_clients
    )


@api.get("/clients/lan")
def lan_clients(context=None):
    return _safe_call(
        zte_service.lan_clients
    )


@api.get("/lan/ports")
def lan_ports(context=None):
    return _safe_call(
        zte_service.lan_ports
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
        zte_service.wifi_networks,
        reveal_password=_bool(
            query.get("reveal_password")
        )
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

        return zte_service.set_ssid_config(
            data.ssid_id,
            config
        )

    return _safe_call(
        action
    )


@api.get("/wifi/radios")
def get_radios(context=None):
    return _safe_call(
        zte_service.wifi_radios
    )


@api.get("/wifi/channels")
def get_channels(context=None):
    query = _query(
        context
    )

    return _safe_call(
        zte_service.wifi_channels,
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

        return zte_service.set_wifi_radio(
            data.band,
            config
        )

    return _safe_call(
        action
    )


@api.get("/wifi/power")
def wifi_power_status(context=None):
    return _safe_call(
        zte_service.radio_power_status
    )


@api.post("/wifi/power/update")
def set_wifi_power(context=None):
    def action():
        data = _validated(
            RadioPowerRequest,
            context
        )

        return zte_service.set_radio_power(
            data.band,
            data.enabled
        )

    return _safe_call(
        action
    )


@api.get("/wifi/schedule")
def wifi_schedule_status(context=None):
    return _safe_call(
        zte_service.wifi_schedule_status
    )


@api.post("/wifi/schedule/update")
def set_wifi_schedule(context=None):
    def action():
        data = _validated(
            WifiScheduleRequest,
            context
        )

        return zte_service.set_wifi_schedule(
            data.model_dump()
        )

    return _safe_call(
        action
    )


@api.get("/wifi/wps")
def wifi_wps_status(context=None):
    return _safe_call(
        zte_service.wps_status
    )


@api.post("/wifi/wps/update")
def set_wifi_wps(context=None):
    def action():
        data = _validated(
            WpsRequest,
            context
        )

        return zte_service.set_wps(
            data.band,
            data.mode
        )

    return _safe_call(
        action
    )


@api.get("/wifi/band-steering")
def band_steering_status(context=None):
    return _safe_call(
        zte_service.band_steering_status
    )


@api.post("/wifi/band-steering/update")
def set_band_steering(context=None):
    def action():
        data = _validated(
            BandSteeringRequest,
            context
        )

        return zte_service.set_band_steering(
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

        return zte_service.configure_band_steering(
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
        zte_service.upnp_status
    )


@api.post("/upnp/update")
def set_upnp(context=None):
    def action():
        data = _validated(
            UpnpRequest,
            context
        )

        return zte_service.set_upnp(
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
        zte_service.dns_status
    )


@api.post("/dns/update")
def set_dns(context=None):
    def action():
        data = _validated(
            DnsRequest,
            context
        )

        return zte_service.set_dns(
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

        return zte_service.ping(
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

        return zte_service.traceroute(
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
        zte_service.export_user_configuration
    )


@api.get("/device/capabilities")
def capability_catalog(context=None):
    return _safe_call(
        zte_service.capability_catalog
    )


@api.post("/device/capabilities/probe")
def capability_probe(context=None):
    def action():
        data = _validated(
            CapabilityProbeRequest,
            context
        )

        return zte_service.probe_capabilities(
            data.features or None
        )

    return _safe_call(
        action
    )


@api.get("/multimodel/catalog")
def multimodel_catalog(context=None):
    return _safe_call(
        zte_service.multimodel_catalog
    )


@api.post("/multimodel/diagnostic")
def multimodel_diagnostic(context=None):
    """Consulta por família somente leitura, sem ping/traceroute no roteador."""
    requested = str(_json(context).get("model") or "")[:50].strip()
    return _safe_call(
        zte_service.multimodel_diagnostic,
        requested or None,
    )


@api.post("/multimodel/mesh")
def multimodel_mesh(context=None):
    model = str(_json(context).get("model") or "")[:50].strip()
    return _safe_call(
        zte_service.multimodel_mesh,
        model or None,
    )


@api.post("/multimodel/probe")
def multimodel_probe(context=None):
    # O usuário pode informar modelo quando o firmware omite a identificação.
    # Não envia escrita ao roteador e limita o nome fornecido.
    model = str(_json(context).get("model") or "")[:50].strip()
    return _safe_call(
        zte_service.multimodel_probe,
        model or None,
    )


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
        zte_service.capability_shape,
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

    return _safe_call(
        zte_service.read_capability,
        feature
    )


# =========================================================
# DHCP / LAN / NAT
# =========================================================


@api.get("/network/dhcp")
def dhcp_status(context=None):
    return _safe_call(
        zte_service.dhcp_status
    )


@api.post("/network/dhcp/update")
def update_dhcp(context=None):
    def action():
        data = _validated(
            DhcpBasicRequest,
            context
        )

        return zte_service.set_dhcp_basic(
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

        return zte_service.save_dhcp_reservation(
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

        return zte_service.delete_dhcp_reservation(
            data.id
        )

    return _safe_call(
        action
    )


@api.get("/network/port-forwarding")
def port_forwarding_status(context=None):
    return _safe_call(
        zte_service.port_forwarding_status
    )


@api.post("/network/port-forwarding/save")
def save_port_forward(context=None):
    def action():
        data = _validated(
            PortForwardRequest,
            context
        )

        return zte_service.save_port_forward(
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

        return zte_service.delete_port_forward(
            data.id,
            confirm=data.confirm,
        )

    return _safe_call(
        action
    )


@api.get("/network/dmz")
def dmz_status(context=None):
    return _safe_call(
        zte_service.dmz_status
    )


@api.post("/network/dmz/update")
def update_dmz(context=None):
    def action():
        data = _validated(
            DmzRequest,
            context
        )

        return zte_service.set_dmz(
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

        return zte_service.automatic_diagnostic(
            data.model_dump()
        )

    return _safe_call(
        action
    )


@api.post("/diagnostics/support")
def support_diagnostic(context=None):
    def action():
        data = _validated(
            SupportDiagnosticRequest,
            context
        )

        return zte_service.support_diagnostic(
            data.model_dump()
        )

    return _safe_call(
        action
    )


@api.post("/diagnostics/remediate")
def remediate_diagnostic(context=None):
    def action():
        data = _validated(
            DiagnosticRemediationRequest,
            context
        )

        return zte_service.remediate_diagnostic(
            data.model_dump()
        )

    return _safe_call(
        action
    )


@api.post("/diagnostics/speedtest")
def speedtest(context=None):
    def action():
        data = _validated(
            SpeedTestRequest,
            context
        )

        return zte_service.speedtest(
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

        return zte_service.generate_attendance(
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
        zte_service.capture_snapshot,
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
        zte_service.history,
        limit
    )


# =========================================================
# CONFIGURAÇÃO / PERFIS DO ATENDENTE
# =========================================================


@api.get("/configuration/current")
def current_configuration(context=None):
    return _safe_call(
        zte_service.current_configuration
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


@api.post("/profiles/capture")
def capture_profile(context=None):
    def action():
        data = _validated(
            AttendantRequest,
            context
        )

        return zte_service.capture_profile(
            data.attendant
        )

    return _safe_call(
        action
    )


@api.post("/profiles/apply")
def apply_profile(context=None):
    def action():
        data = _validated(
            AttendantRequest,
            context
        )

        return zte_service.apply_profile(
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
            zte_service,
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
            zte_service,
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
            zte_service,
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
            zte_service,
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
            zte_service,
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
            zte_service,
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
        zte_service,
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
        zte_service,
    )


@api.get("/management/mesh")
def management_mesh_status(context=None):
    return _safe_call(
        cpe_management_service.mesh_status,
        zte_service,
    )


@api.post("/management/mesh/configure")
def management_mesh_configure(context=None):
    def action():
        data = _validated(
            MeshConfigRequest,
            context
        )

        return cpe_management_service.mesh_configure(
            zte_service,
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
            zte_service,
            data.model_dump(),
        )

    return _safe_call(
        action
    )


@api.get("/management/qos")
def management_qos(context=None):
    return _safe_call(
        zte_service.qos_management_status
    )


@api.post("/management/qos/save")
def management_qos_save(context=None):
    def action():
        data = _validated(
            QoSManagementRequest,
            context
        )

        return cpe_management_service.qos_save(
            zte_service,
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
            zte_service,
            data.model_dump(),
        )

    return _safe_call(
        action
    )


@api.get("/management/firewall")
def management_firewall(context=None):
    return _safe_call(
        zte_service.firewall_management_status
    )


@api.post("/management/firewall/update")
def management_firewall_update(context=None):
    def action():
        data = _validated(
            FirewallManagementRequest,
            context
        )

        return cpe_management_service.firewall_set(
            zte_service,
            data.model_dump(),
        )

    return _safe_call(
        action
    )


@api.get("/management/firewall/rules")
def management_firewall_rules(context=None):
    return _safe_call(
        cpe_management_service.firewall_rules,
        zte_service,
    )


@api.post("/management/firewall/rules/save")
def management_firewall_rule_save(context=None):
    def action():
        data = _validated(
            FirewallRuleManagementRequest,
            context
        )

        return cpe_management_service.firewall_rule_save(
            zte_service,
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
            zte_service,
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
            zte_service,
            data.model_dump(),
        )

    return _safe_call(
        action
    )


@api.get("/management/sntp")
def management_sntp(context=None):
    return _safe_call(
        zte_service.sntp_management_status
    )


@api.post("/management/sntp/update")
def management_sntp_update(context=None):
    def action():
        data = _validated(
            SNTPManagementRequest,
            context
        )

        return cpe_management_service.sntp_set(
            zte_service,
            data.model_dump(),
        )

    return _safe_call(
        action
    )


@api.get("/management/tr069")
def management_tr069(context=None):
    return _safe_call(
        zte_service.tr069_management_status
    )


@api.post("/management/tr069/update")
def management_tr069_update(context=None):
    def action():
        data = _validated(
            TR069ManagementRequest,
            context
        )

        return cpe_management_service.tr069_set(
            zte_service,
            data.model_dump(),
        )

    return _safe_call(
        action
    )


@api.get("/management/wan")
def management_wan(context=None):
    return _safe_call(
        zte_service.wan_configurations
    )


@api.post("/management/wan/create")
def management_wan_create(context=None):
    def action():
        data = _validated(
            WANCreateRequest,
            context
        )

        return cpe_management_service.wan_create(
            zte_service,
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
            zte_service,
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
            zte_service,
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
            zte_service,
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
            zte_service,
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
            zte_service,
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
            zte_service,
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
        zte_service.firmware_management_status
    )


@api.post("/management/firmware/upgrade")
def management_firmware_upgrade(context=None):
    def action():
        data = _validated(
            FirmwareUpgradeRequest,
            context
        )

        return cpe_management_service.firmware_upgrade(
            zte_service,
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
            zte_service,
            data.model_dump(),
        )

    return _safe_call(
        action
    )

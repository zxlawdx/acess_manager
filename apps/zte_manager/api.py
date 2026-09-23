from pydantic import ValidationError

from vela.api import api

from apps.zte_manager.schemas import (
    AdminPasswordRequest,
    AttendantRequest,
    AutomaticDiagnosticRequest,
    BandSteeringConfigRequest,
    BandSteeringRequest,
    CapabilityProbeRequest,
    ConnectRequest,
    DhcpBasicRequest,
    DhcpReservationRequest,
    DmzRequest,
    DnsRequest,
    PingRequest,
    PortForwardRequest,
    ProfileRequest,
    RadioPowerRequest,
    ResourceIdRequest,
    TracerouteRequest,
    UpnpRequest,
    WifiRadioRequest,
    WifiSSIDRequest,
    WifiScheduleRequest,
    WpsRequest,
)
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

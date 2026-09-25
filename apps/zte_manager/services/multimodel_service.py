"""Descoberta conservadora e somente leitura para famílias ZTE.

Perfis inspirados na documentação pública do juacas/zte_tracker; esta é uma
implementação independente. O nome do modelo sugere candidatos, mas somente
uma resposta XML válida confirma o endpoint e nenhum POST é feito aqui.
A família Vue exige uma implementação de autenticação separada.
"""

from __future__ import annotations

import json
import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class ReadEndpoint:
    view: str
    tag: str
    root: str
    params: tuple[tuple[str, str], ...] = ()
    request_type: str = "menuData"


# Protocolos conhecidos por família, não garantias por firmware/operadora.
FAMILY: dict[str, dict[str, ReadEndpoint]] = {
    "f6640": {
        "wifi_clients": ReadEndpoint("localNetStatus", "wlan_client_stat_lua.lua", "OBJ_WLAN_AD_ID"),
        "lan_clients": ReadEndpoint("localNetStatus", "accessdev_landevs_lua.lua", "OBJ_ACCESSDEV_ID"),
        "wan": ReadEndpoint(
            "ethWanStatus", "wan_internetstatus_lua.lua", "ID_WAN_COMFIG",
            (("TypeUplink", "2"), ("pageType", "1")),
        ),
    },
    "h288a": {
        "wifi_clients": ReadEndpoint("localNetStatus", "accessdev_ssiddev_lua.lua", "OBJ_ACCESSDEV_ID"),
        "lan_clients": ReadEndpoint("localNetStatus", "accessdev_landevs_lua.lua", "OBJ_ACCESSDEV_ID"),
        "wan": ReadEndpoint(
            "ethWanStatus", "wan_internetstatus_lua.lua", "ID_WAN_COMFIG",
            (("TypeUplink", "2"), ("pageType", "1")),
        ),
    },
    "h388x": {
        "wifi_clients": ReadEndpoint("localNetStatus", "accessdev_ssiddev_lua.lua", "OBJ_ACCESSDEV_ID"),
        "lan_clients": ReadEndpoint("localNetStatus", "accessdev_landevs_lua.lua", "OBJ_ACCESSDEV_ID"),
        "wan": ReadEndpoint(
            "ethWanStatus", "wan_internet_lua.lua", "ID_WAN_COMFIG",
            (("TypeUplink", "2"), ("pageType", "1")),
        ),
    },
    "h2640": {
        "wifi_clients": ReadEndpoint("localNetStatus", "accessdev_ssiddev_lua.lua", "OBJ_ACCESSDEV_ID"),
        "lan_clients": ReadEndpoint("localNetStatus", "accessdev_landevs_lua.lua", "OBJ_ACCESSDEV_ID"),
        "dsl": ReadEndpoint("dslWanStatus", "dsl_interface_status_lua.lua", "OBJ_DSLINTERFACE_ID"),
    },
    "vue": {
        "wifi_clients": ReadEndpoint(
            "", "vue_client_data", "OBJ_CLIENTS_ID",
            request_type="vueData",
        ),
        "lan_clients": ReadEndpoint(
            "localNetStatus", "localnet_lan_info_lua", "OBJ_LAN_INFO_ID",
            request_type="vueData",
        ),
        "wan": ReadEndpoint(
            "vue_home_device_data_no_update_sess", "vue_mainwan_data",
            "ID_WAN_COMFIG", request_type="vueData",
        ),
    },
}

MODEL_FAMILY = {
    "F6640": "f6640", "F6645P": "f6640", "F680": "f6640",
    "F6600P": "f6640", "F8748": "f6640",
    "H169A": "h288a", "H288A": "h288a", "H3600P": "h288a",
    "H3640": "h288a", "H6645P": "h288a", "H6745": "h288a",
    "H388X": "h388x", "H2640": "h2640",
    "E2631": "vue", "SR7410": "vue", "SR7110": "vue",
    # Perfil específico baseado na captura sanitizada F6201B V9.3.10P7N7.
    # Somente GET observado; não pressupor acesso de escrita.
    "F6201B": "f6201b_candidate",
}

# Endpoints de leitura adicionais documentados em zte_tracker/zteclient/README.md
# e zte_client.py. Apenas F6600P possui confirmação documentada de PON.
FAMILY["f6640"]["wifi_ssids"] = ReadEndpoint(
    "wlanBasic", "wlan_wlansssidconf_lua.lua", "OBJ_WLANAP_ID"
)
FAMILY["f6640"]["device_info"] = ReadEndpoint(
    "statusMgr", "devmgr_statusmgr_lua.lua", "OBJ_DEVINFO_ID"
)
for _family in ("h288a", "h388x", "h2640"):
    FAMILY[_family]["device_info"] = ReadEndpoint(
        "statusMgr", "devmgr_statusmgr_lua.lua", "OBJ_DEVINFO_ID"
    )

# O proprietário forneceu 244 eventos XHR/fetch, 93 combinações de rota e
# 78 menuViews do F6201B V9.3.10P7N7. As tags e objetos abaixo foram
# efetivamente OBSERVADOS. View="" executa GET menuData direto, sem inventar
# a associação menuView↔menuData. Apenas campos públicos não sensíveis
# são exibidos pelos renderizadores; estas entradas NUNCA habilitam POST.
FAMILY["f6201b_candidate"] = {
    "device_info": ReadEndpoint("", "devmgr_statusmgr_lua.lua", "OBJ_DEVINFO_ID"),
    "pon_optical": ReadEndpoint("", "optical_info_lua.lua", "OBJ_PON_OPTICALPARA_ID"),
    "wifi_clients": ReadEndpoint("", "wlan_homepage_lua.lua", "OBJ_ACCESSDEV_ID"),
    # A captura registra LEASES DHCP, não comprovação de cliente LAN online.
    "dhcp_leases": ReadEndpoint("", "Localnet_LanMgrIpv4_DHCPHostInfo_lua.lua", "OBJ_DHCPHOSTINFO_ID"),
    "wifi_ssids": ReadEndpoint("", "wlan_wlansssidconf_lua.lua", "OBJ_WLANAP_ID"),
    "wifi_radios": ReadEndpoint("", "wlan_wlanbasiconoff_lua.lua", "OBJ_WLANSETTING_ID"),
    "lan_ports": ReadEndpoint("", "status_lan_info_lua.lua", "OBJ_PON_PORT_BASIC_STATUS_ID"),
    "band_steering": ReadEndpoint("", "wlan_BandSteering_lua.lua", "OBJ_WLAN_BANDSTEERING_ID"),
    "wps": ReadEndpoint("", "wlan_wps_lua.lua", "OBJ_WPS_ID"),
    "mesh": ReadEndpoint("", "Localnet_NetSphere_Mode_lua.lua", "OBJ_NETSPHERE_MAP_ID"),
    "dns": ReadEndpoint("", "dns_localdns_lua.lua", "OBJ_DNS_ID"),
    "dhcp": ReadEndpoint("", "Localnet_LanMgrIpv4_DHCPBasicCfg_lua.lua", "OBJ_Br0AndDhcpsHosCfg_ID"),
    "route_table": ReadEndpoint("", "route_routetableipv4_lua.lua", "OBJ_ROUTETABLE_ID"),
    "arp": ReadEndpoint("", "arp_arptable_lua.lua", "OBJ_GETARPINST_ID"),
    "firewall": ReadEndpoint("", "firewall_config_lua.lua", "OBJ_FWLEVEL_ID"),
    "voip_status": ReadEndpoint("", "voipRegStatus_lua.lua", "OBJ_VOIPVPLINE_ID"),
    "tr069_status": ReadEndpoint("", "tr069_remotemgr_lua.lua", "OBJ_MANAGESERVER_ID"),
    "upnp": ReadEndpoint("", "upnp_upnp_lua.lua", "OBJ_UPNPCONFIG_ID"),
    "wifi_schedule": ReadEndpoint("", "wlan_wlanbasiconoff_lua.lua", "OBJ_WLANTIMECFG_ID"),
    "ping_history": ReadEndpoint("", "networkdiag_ping_lua.lua", "OBJ_DEVPING_ID"),
    "traceroute_history": ReadEndpoint("", "networkdiag_traceroute_lua.lua", "OBJ_TRACERT_ID"),
    # A WAN foi confirmada em runtime na aplicação, porém a captura
    # fornecida viu menu WAN vazio. Nunca inferir status se vier sem OBJ.
    "wan": ReadEndpoint("ethWanStatus", "wan_internetstatus_lua.lua",
                        "ID_WAN_COMFIG", (("TypeUplink", "2"), ("pageType", "1"))),
}

# PON é opt-in por modelo, não propriedade compartilhada das aliases.
PON_F6600P = ReadEndpoint(
    "ponopticalinfo", "optical_info_lua.lua", "OBJ_PON_OPTICALPARA_ID"
)

# Não armazenar respostas XML nem campos de clientes no relatório estrutural.
SENSITIVE_NAME = re.compile(
    r"(password|passwd|secret|token|credential|key|serial|mac|ssid|"
    r"host|ipaddress|imei|username|name)", re.I
)


def normalize_model(value: str | None) -> str:
    return re.sub(r"[^A-Z0-9]", "", (value or "").upper())


def find_family(model: str | None) -> tuple[str | None, str | None]:
    candidate = normalize_model(model)
    # Mais específico primeiro: H6645P antes de outros nomes parciais.
    for key in sorted(MODEL_FAMILY, key=len, reverse=True):
        if key in candidate:
            return key, MODEL_FAMILY[key]
    return None, None


# Diferenças documentadas por firmware no projeto zte_tracker.
# As aliases compartilham endpoints, mas NÃO atestam funções de escrita.
MODEL_EXTRAS: dict[str, tuple[str, ...]] = {
    "F6600P": ("pon_optical", "mesh_topology_candidate"),
    "F6201B": ("captured_get_routes_v9_3_10p7n7", "read_only"),
    "F8748": ("wan_traffic_counters",),
    "H2640": ("dsl_sync_not_internet",),
    "SR7410": ("vue_api",),
    "SR7110": ("vue_api",),
    "E2631": ("vue_api",),
}

DISCOVERY_NAMES = {
    "wifi_clients": "Clientes Wi-Fi",
    "lan_clients": "Clientes cabeados",
    "wan": "Status WAN",
    "dsl": "Sincronismo DSL",
    "wifi_ssids": "Configuração de SSIDs (leitura)",
    "device_info": "Identificação e firmware",
    "pon_optical": "Potência óptica GPON",
    "dhcp_leases": "Dispositivos com lease DHCP (não necessariamente online)",
    "wifi_radios": "Rádios Wi-Fi", "lan_ports": "Portas Ethernet",
    "band_steering": "Band Steering", "wps": "WPS", "mesh": "Mesh / roaming",
    "dns": "DNS local", "dhcp": "Servidor DHCP", "route_table": "Rotas IPv4",
    "arp": "Tabela ARP", "firewall": "Firewall", "voip_status": "Telefonia",
    "tr069_status": "TR-069 (status sem credenciais)", "upnp": "UPnP",
    "wifi_schedule": "Agendamento Wi-Fi",
    "ping_history": "Último ping (somente leitura)",
    "traceroute_history": "Último traceroute (somente leitura)",
}

def catalog() -> dict[str, Any]:
    return {
        "models": [
            {
                "model": model,
                "family": family,
                "protocol": "vue" if family == "vue" else "thinklua",
                "discovery": "read_only_probe",
                "candidate_features": list(FAMILY[family])
                    + (["pon_optical"] if model == "F6600P" else []),
                "firmware_differences": MODEL_EXTRAS.get(model, ()),
                "evidence": ("owner_capture_V9.3.10P7N7" if model == "F6201B"
                             else "zte_tracker_documented"),
            }
            for model, family in MODEL_FAMILY.items()
        ],
        "tracker_models": sum(1 for name in MODEL_FAMILY if name != "F6201B"),
        "experimental_models": ["F6201B"],
        "notes": (
            "O catálogo mostra candidatos zte_tracker, não garante compatibilidade. "
            "F6201B V9.3.10P7N7 tem rotas GET observadas em captura do "
            "proprietário; cada recurso continua exigindo XML válido. "
            "Outras versões não são validadas e nenhuma escrita é habilitada."
        ),
    }


def _fetch(zte, endpoint: ReadEndpoint) -> str:
    """Executa o fluxo correto de GET para a família escolhida."""
    if endpoint.request_type == "vueData":
        if endpoint.view:
            first = zte.session.get(
                zte.base_url + "/",
                params={"_type": "vueData", "_tag": endpoint.view},
                timeout=10,
            )
            first.raise_for_status()
        response = zte.session.get(
            zte.base_url + "/",
            params={"_type": "vueData", "_tag": endpoint.tag},
            timeout=10,
        )
        response.raise_for_status()
        return response.text

    # No F6640/H288A, o zte_tracker documenta acesso menuData direto
    # para clientes. Outros firmwares exigem uma menuView prévia (#75).
    # Primeiro tentamos o fluxo conservador com contexto; se somente a
    # VIEW não existir, uma leitura direta do MESMO tag documentado
    # pode funcionar. Nunca repetimos em erro explícito de sessão expirada.
    if not endpoint.view:
        return zte.get_menu(endpoint.tag, **dict(endpoint.params))
    try:
        zte.get_view(endpoint.view, Menu3Location=0)
    except Exception as error:
        if "session" in str(error).lower() or "login" in str(error).lower():
            raise
        # O menuData direto aparece nos exemplos oficiais do tracker;
        # não tentamos tags diferentes nem POST de configuração.
        return zte.get_menu(endpoint.tag, **dict(endpoint.params))
    return zte.get_menu(endpoint.tag, **dict(endpoint.params))


def read_clients(zte, model: str, kind: str) -> list[dict[str, Any]]:
    """Leitura de dispositivos normalizada para as telas existentes.

    Esta função é local ao atendimento: não registra/salva IP, MAC, hostname
    ou SSID em relatórios estruturais de suporte público.
    """
    if kind not in {"wifi_clients", "lan_clients"}:
        raise ValueError("Tipo de cliente desconhecido")

    selected, family = find_family(model)
    if not family:
        raise ValueError("O modelo não possui perfil de clientes.")

    endpoint = FAMILY[family].get(kind)
    if not endpoint:
        raise RuntimeError("Endpoint não documentado nesta família.")

    raw = _fetch(zte, endpoint)
    _shape(raw, endpoint.root)  # valida XML e objeto esperado antes de ler.
    root = ET.fromstring(raw)
    clients = []
    for entry in root.findall(f"{endpoint.root}/Instance"):
        children = list(entry)
        values = {}
        for pos in range(len(children) - 1):
            if children[pos].tag == "ParaName" and children[pos+1].tag == "ParaValue":
                values[(children[pos].text or "").strip()] = (
                    children[pos+1].text or ""
                )
        clients.append({
            "hostname": values.get("HostName") or values.get("DeviceName") or "Desconhecido",
            "ip": values.get("IPAddress") or values.get("IPAddr"),
            "mac": values.get("MACAddress") or values.get("MacAddr"),
            "ssid": values.get("ESSID") or values.get("AliasName") if kind == "wifi_clients" else None,
            "interface": values.get("Interface") or values.get("AliasName") if kind == "lan_clients" else None,
            "rssi": values.get("RSSI") if kind == "wifi_clients" else None,
            "tempo_conectado": values.get("LinkTime"),
        })
    return clients


def _shape(xml: str, expected_root: str) -> dict[str, Any]:
    if not xml or "SessionTimeout" in xml or "login_need_refresh" in xml:
        raise RuntimeError("Sessão expirada ou resposta vazia")

    root = ET.fromstring(xml)
    if root.tag != "ajax_response_xml_root":
        raise RuntimeError("Resposta não é XML ThinkLua")

    # Alguns firmwares incluem objeto válido junto com IF_ERRORID != 0.
    # Não interpretar XML estrutural de uma requisição rejeitada como prova.
    error_id = (root.findtext("IF_ERRORID") or "").strip()
    if error_id and error_id not in {"0", "0000"}:
        raise RuntimeError("O firmware rejeitou a consulta.")
    error = (root.findtext("IF_ERRORSTR") or "").strip()
    if error and error.upper() not in {"SUCC", "SUCCESS", "OK", "0"}:
        raise RuntimeError("Firmware não disponibilizou este menu")

    result = {}
    for node in root:
        if not (node.tag.startswith(("OBJ_", "ID_"))):
            continue
        instances = node.findall("Instance")
        fields = set()
        for instance in instances:
            children = list(instance)
            for i, child in enumerate(children[:-1]):
                if child.tag == "ParaName":
                    field = (child.text or "").strip()
                    if field and not SENSITIVE_NAME.search(field):
                        fields.add(field)
        result[node.tag] = {"records": len(instances), "fields": sorted(fields)}

    # Menus podem retornar 0 clientes: objeto vazio ainda é evidência de suporte.
    if expected_root not in result:
        raise RuntimeError("Objeto esperado não encontrado no firmware")

    return result


def probe(
    zte, model: str, *, max_endpoints: int = 4, start: int = 0
) -> dict[str, Any]:
    selected, family = find_family(model)
    if family is None:
        return {
            "model": model, "supported": False, "read_only": True,
            "reason": "Modelo sem perfil cadastrado; sem tentativa às cegas.",
            "endpoints": {},
        }

    candidates = dict(FAMILY[family])
    if selected == "F6600P":
        candidates["pon_optical"] = PON_F6600P
    start = max(0, min(int(start), len(candidates)))
    count = max(1, min(int(max_endpoints), 10))
    endpoints = {}
    session_expired = False
    for name, endpoint in list(candidates.items())[start:start + count]:
        try:
            xml = _fetch(zte, endpoint)
            # Faz a validação local mesmo quando implementação de ZTE mudar.
            endpoints[name] = {
                "available": True,
                "structure": _shape(xml, endpoint.root),
                "tag": endpoint.tag,
            }
        except Exception as exc:
            # HTTP 200 pode significar página de login, não funcionalidade.
            # Apenas categorias saneadas, nenhum HTML/token/credencial em UI.
            message = str(exc).lower()
            if "sessiontimeout" in message or "sessão expirada" in message:
                reason = "session_expired"
            elif "html" in message or "login" in message:
                reason = "login_page_instead_of_data"
            elif isinstance(exc, ET.ParseError):
                reason = "invalid_xml"
            elif isinstance(exc, ValueError):
                reason = "unexpected_firmware_response"
            elif "timeout" in type(exc).__name__.lower():
                reason = "network_timeout"
            else:
                reason = "not_exposed_or_permission_denied"
            endpoints[name] = {
                "available": False,
                "error_type": type(exc).__name__,
                "reason": reason,
                "tag": endpoint.tag,
            }
            if reason == "session_expired":
                session_expired = True
                break

    return {
        "model": selected, "family": family, "read_only": True,
        "supported": any(x["available"] for x in endpoints.values()),
        "endpoints": endpoints,
        "notes": ("F6201B: tags observadas na captura V9.3.10P7N7. "
                  "Disponibilidade depende de confirmação XML em runtime. "
                  "Somente GET, sem escrita." if selected == "F6201B" else
                  "Somente descoberta; escrita e backup requerem validação por firmware."),
        "capabilities": [
            {
                "feature": name,
                "label": DISCOVERY_NAMES.get(name, name),
                "available": item["available"],
                "writable": False,
                "source": ("owner_capture_V9.3.10P7N7" if selected == "F6201B"
                           else "zte_tracker endpoint profile"),
                "status": "detected" if item["available"] else "not_confirmed",
                "reason": item.get("reason"),
            }
            for name, item in endpoints.items()
        ],
        "candidate_features": [
            {
                "feature": name,
                "label": DISCOVERY_NAMES.get(name, name),
                "status": "not_tested",
                "writable": False,
            }
            for name in candidates if name not in endpoints
        ],
        "model_specific": list(MODEL_EXTRAS.get(selected, ())),
        "next_offset": min(len(candidates), start + count),
        "total_candidates": len(candidates),
        "session_expired": session_expired,
    }


def mesh_summary(zte, model: str) -> dict[str, Any]:
    """Consulta agregada da topologia sem retornar MAC/IP/nomes de clientes.

    O endpoint JSON só é tentado nas famílias F6640/F6600P documentadas.
    Nenhuma persistência de resposta bruta.
    """
    selected, family = find_family(model)
    if family != "f6640":
        return {
            "model": selected or model,
            "available": False,
            "reason": "Topologia JSON não documentada para esta família.",
        }

    zte.get_view("mmTopology", Menu3Location=0)
    response = zte.session.get(
        zte.base_url + "/",
        params={"_type": "menuData", "_tag": "topo_lua.lua"},
        timeout=10,
    )
    response.raise_for_status()

    # Este endpoint responde JSON, ao contrário dos outros menus ThinkLua.
    # Não serializar a resposta bruta: pode conter dados identificáveis.
    raw = response.text
    if "SessionTimeout" in raw or raw.lstrip().lower().startswith("<html"):
        raise RuntimeError("Sessão expirada ou menu Mesh não disponível.")

    data = json.loads(raw)
    if not isinstance(data, dict) or not isinstance(data.get("ad"), dict):
        raise RuntimeError("Formato de topologia não reconhecido.")

    devices = [
        item for item in data["ad"].values()
        if isinstance(item, dict) and item.get("MacAddr")
    ]
    access = {"lan": 0, "wifi_24": 0, "wifi_5": 0, "other": 0}
    for item in devices:
        band = {
            "0": "lan", "1": "wifi_24", "2": "wifi_5"
        }.get(str(item.get("AccessType", "")), "other")
        access[band] += 1

    return {
        "model": selected, "available": True,
        "agents": sum(
            1 for item in data.get("slave", []) if isinstance(item, dict)
        ),
        "controller": isinstance(data.get("master"), dict),
        "connected_devices": len(devices),
        "access": access,
        "note": "Resumo sem IP, MAC, SSID ou hostname; somente leitura.",
    }

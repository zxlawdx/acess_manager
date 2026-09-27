"""Catálogo completo dos GETs vistos no F6201B V9.3.10P7N7.

Gerado a partir do manifesto sanitizado entregue pelo operador: 92 rotas
GET (menuData/hiddenData). Mantém os endpoints sem estrutura/JSON como
referência, mas somente permite consultar XML com OBJ_* observado.
Retorno somente ESTRUTURAL: contagens e nomes de campos sanitizados.
Não faz POST para a ONT e não expõe nenhuma resposta bruta ou senha.
"""
from __future__ import annotations

import json
import xml.etree.ElementTree as ET

from apps.zte_manager.services import multimodel_service as mm
from apps.zte_manager.services.f6201b_evidence import CAPTURED_GET_VIEWS, CAPTURED_GET_ROOTS, GET_PARAMS, OBSERVED_APPLY_FIELDS


# categoria | _tag | OBJ esperado | _type | formato observado
_CAPTURE = """Firewall|firewall_homepage_lua.lua|OBJ_FWLEVEL_ID|menuData|XML
Wi-Fi|wlan_homepage_lua.lua|OBJ_ACCESSDEV_ID|menuData|XML
Sistema|sntp_data|OBJ_SNTP_ID|hiddenData|XML
LAN|accessdev_homepage_lua.lua||menuData|XML
Telefonia|voip_homepage_lua.lua|OBJ_VOIPSIPLINE_ID|menuData|XML
Fibra|topo_lua.lua||menuData|JSON
Fibra|optical_info_lua.lua|OBJ_PON_OPTICALPARA_ID|menuData|XML
WAN|wan_internetstatus_lua.lua||menuData|XML
WAN|tunnel_4in6_status_lua.lua||menuData|XML
WAN|l2tp_lua.lua|OBJ_L2TP_ID|menuData|XML
WAN|clearlink_lua.lua|OBJ_CLEAR_LINK_ID|menuData|XML
WAN|wan_internet_lua.lua||menuData|XML
WAN|tunnel_4in6_config_lua.lua||menuData|XML
Firewall|firewall_config_lua.lua|OBJ_FWLEVEL_ID|menuData|XML
Firewall|firewall_parentctrl_lua.lua||menuData|XML
WAN|ddns_lua.lua|OBJ_DDNSCLIENT_ID|menuData|XML
Sistema|sntp_lua.lua|OBJ_SNTP_ID|menuData|XML
WAN|portbinding_lua.lua|OBJ_PORT_BINDING_ID|menuData|XML
WAN|rip_lua.lua|OBJ_RIP_ID|menuData|XML
Multicast|multicast_mode_lua.lua|OBJ_IGMPMODE_ID|menuData|XML
WAN|Internet_PortLocate_lua.lua|OBJ_PORTLOCATE_ID|menuData|XML
Fibra|poninfo_loid_lua.lua|OBJ_PON_LOID_ID|menuData|XML
Fibra|poninfo_sn_lua.lua|OBJ_SN_INFO_ID|menuData|XML
LAN|status_lan_info_lua.lua|OBJ_PON_PORT_BASIC_STATUS_ID|menuData|XML
LAN|Localnet_LanMgrIpv4_DHCPHostInfo_lua.lua|OBJ_DHCPHOSTINFO_ID|menuData|XML
Wi-Fi|wlan_wlanbasiconoff_lua.lua|OBJ_WLANTIMECFG_ID|menuData|XML
Wi-Fi|wlan_macfilteraclpolicy_lua.lua|OBJ_WLANSETTING_ID|menuData|XML
Wi-Fi|wlan_wps_lua.lua|OBJ_WPS_ID|menuData|XML
Wi-Fi|wlan_sta_wlan_profile_lua.lua||menuData|XML
Wi-Fi|wlan_BandSteering_lua.lua|OBJ_WLAN_BANDSTEERING_ID|menuData|XML
Wi-Fi|Localnet_NetSphere_Mode_lua.lua|OBJ_NETSPHERE_MAP_ID|menuData|XML
Wi-Fi|wlan_wlanbasicadconf_lua.lua||menuData|XML_TRUNCATED
Wi-Fi|wlan_wlansssidconf_lua.lua|OBJ_WLANAP_ID|menuData|XML
LAN|Localnet_LanMgrIpv4_DHCPBasicCfg_lua.lua|OBJ_Br0AndDhcpsHosCfg_ID|menuData|XML
LAN|Localnet_LanMgrIpv4_DHCPStaticRule_lua.lua||menuData|XML
LAN|Localnet_LanDevDHCPSource_lua.lua|OBJ_LANDEVDHCPSOURCE_ID|menuData|XML
WAN|route_routedefault_lua.lua|OBJ_ROUTEDEFAULT_ID|menuData|XML
LAN|dhcp6s_hostinfo_lua.lua||menuData|XML
WAN|eth_interface_config_lua.lua|OBJ_LAN_PORT_CONF_ID|menuData|XML
WAN|upnp_upnp_lua.lua|OBJ_UPNPCONFIG_ID|menuData|XML
WAN|route_routedefaultipv6_lua.lua|OBJ_ROUTEDEFAULT6_ID|menuData|XML
WAN|route_routetableipv4_lua.lua|OBJ_ROUTETABLE_ID|menuData|XML
WAN|route_routestaticipv4_lua.lua||menuData|XML
WAN|route_routepolicyipv4_lua.lua||menuData|XML
WAN|upnp_portmap_lua.lua||menuData|XML
WAN|bpdu_lua.lua|OBJ_BPDU_ID|menuData|XML
WAN|dns_localdns_lua.lua|OBJ_DNS_ID|menuData|XML
Telefonia|voipRegStatus_lua.lua|OBJ_VOIPVPLINE_ID|menuData|XML
Telefonia|voip_voipbasic_lua.lua|OBJ_VOIPSIPLINE_ID|menuData|XML
Telefonia|Voip_SipIf_lua.lua|OBJ_VOIPBEARINFO_ID|menuData|XML
Telefonia|voipDmtTimer_lua.lua|OBJ_VOIPDMTIMER_ID|menuData|XML
Telefonia|Voip_SipService_lua.lua|OBJ_VOIPVPCALLTIMER_ID|menuData|XML
Telefonia|voip_sipadvanced_lua.lua|OBJ_VRTPADV_ID|menuData|XML
Telefonia|voip_voipsip_lua.lua|OBJ_VOIPSIP_ID|menuData|XML
Telefonia|Voip_sipdigitmap_lua.lua|OBJ_VOIPVOICEPROFILE_ID|menuData|XML
Telefonia|voip_sipmedia_lua.lua|OBJ_VOIPVPLINE_ID|menuData|XML
Telefonia|voip_sipslc_lua.lua|OBJ_VOIPSLCINF_ID|menuData|XML
Telefonia|voip_cid_sip_lua.lua|OBJ_VOIPDTMF_ID|menuData|XML
Telefonia|voip_fax_lua.lua|OBJ_VOIPFAXT38_ID|menuData|XML
Telefonia|Voip_Voip_QoS_lua.lua|OBJ_VOIPSIP_ID|menuData|XML
Telefonia|voip_protocolswitch_lua.lua|OBJ_VOIPEXT_ID|menuData|XML
Sistema|devmgr_statusmgr_lua.lua|OBJ_DEVINFO_ID|menuData|XML
Sistema|register_sn_model.lua||menuData|JSON
Sistema|devauth_accountmgr_lua.lua|OBJ_USERINFO_ID|menuData|XML
Sistema|web_login_timeout_lua.lua|OBJ_USERIF_ID|menuData|XML
Sistema|devmgr_access_model.lua||menuData|JSON
Sistema|log_syslogmgr_lua.lua|OBJ_LOG_ID|menuData|XML
Sistema|tr069_remotemgr_lua.lua|OBJ_MANAGESERVER_ID|menuData|XML
Sistema|scp_remotemgr_lua.lua|OBJ_SCPMGR_ID|menuData|XML
Diagnóstico|networkdiag_ping_lua.lua|OBJ_DEVPING_ID|menuData|XML
Diagnóstico|networkdiag_traceroute_lua.lua|OBJ_TRACERT_ID|menuData|XML
Diagnóstico|networkdiag_svcsimulation_lua.lua|OBJ_SIMULATION_PPPOE_GET_ID|menuData|XML
Sistema|ipv6_enable_lua.lua|OBJ_IPGLOBAL_ID|menuData|XML
Sistema|devmgr_lan_backup_lua.lua|OBJ_LAN_BACKUP_ID|menuData|XML
Sistema|mirror_mirrormgr_lua.lua|OBJ_MIRROR_ID|menuData|XML
Sistema|loopback_basic_lua.lua|OBJ_LOOPBACK_BASIC_ID|menuData|XML
LAN|arp_arptable_lua.lua|OBJ_GETARPINST_ID|menuData|XML
LAN|macinfo_mactable_lua.lua|OBJ_GETMACINST_ID|menuData|XML
Multicast|multilaser_digit_map_lua.lua|OBJ_DIGITMAP_ID|menuData|XML
Multicast|multilaser_olt_vlan_lua.lua|OBJ_OLTVLAN_ID|menuData|XML
Firewall|firewall_filterglobal_lua.lua|OBJ_FWBASE_ID|menuData|XML
Firewall|firewall_ipv4service_lua.lua|OBJ_FWSC_ID|menuData|XML
Firewall|firewall_alg_lua.lua|OBJ_FWALG_ID|menuData|XML
Firewall|firewall_dmz_lua.lua|OBJ_FWDMZ_ID|menuData|XML
Firewall|firewall_portforwarding_lua.lua||menuData|XML
Firewall|firewall_porttrigger_m.lua||menuData|XML
WAN|route_ripng_m.lua|OBJ_RIPNG_ID|menuData|XML
Multicast|multicast_igmpwan_lua.lua||menuData|XML
Multicast|multicast_mldwan_lua.lua||menuData|XML
Multicast|igmp_lua.lua|OBJ_IGMPPROXYC_ID|menuData|XML
Multicast|multicast_vlan_lua.lua||menuData|XML
Multicast|multicast_address_lua.lua|OBJ_IGMPADDLIMITUNTAG_ID|menuData|XML"""


def _rows():
    for line in _CAPTURE.splitlines():
        category, tag, root, request_type, fmt = line.split("|")
        yield {
            "category": category, "tag": tag, "root": root,
            "request_type": request_type, "response_format": fmt,
            "inspectable": fmt in {"XML", "JSON", "XML_TRUNCATED"},
        }


ALLOWED = {row["tag"]: row for row in _rows()}
for tag, view in CAPTURED_GET_VIEWS.items():
    if tag in ALLOWED:
        # Second capture resolves earlier unknown-XML records too.
        root = CAPTURED_GET_ROOTS.get(tag)
        if root and not ALLOWED[tag]["inspectable"]:
            ALLOWED[tag]["root"] = root
            ALLOWED[tag]["response_format"] = "XML"
            ALLOWED[tag]["inspectable"] = True
        continue
    root = CAPTURED_GET_ROOTS.get(tag, "")
    # A segunda captura também registra vistas e tabelas novas.
    # O inspetor valida XML/JSON recebidos ao vivo, sem expor valores.
    ALLOWED[tag] = {
        "category": "Captura complementar", "tag": tag, "root": root,
        "request_type": "menuData", "response_format":
            "XML" if root else "OUTRO",
        "inspectable": True,
    }


def catalog() -> dict:
    updated_routes = []
    for original in ALLOWED.values():
        route = dict(original)
        route["view"] = CAPTURED_GET_VIEWS.get(route["tag"])
        route["observed_apply"] = route["tag"] in OBSERVED_APPLY_FIELDS
        route["parameters"] = sorted(GET_PARAMS.get(route["tag"], {}))
        updated_routes.append(route)
    return {
        "model": "F6201B", "firmware": "V9.3.10P7N7",
        "origin": "owner_sanitized_capture",
        "total_get_routes": len(ALLOWED),
        "routes": updated_routes,
        "note": (
            "Inventário estrutural da captura; opções sem OBJ XML validável "
            "aparecem como referência. Inspeção somente GET sob demanda."
        ),
    }


def _structural_xml(raw: str, expected: str = "") -> dict:
    """Return only object counts and nonsensitive schema; no ParaValue."""
    root = ET.fromstring(raw)
    if root.tag != "ajax_response_xml_root":
        raise ValueError("A resposta não possui o envelope XML ThinkLua.")
    if (root.findtext("IF_ERRORID") or "0").strip() not in {"0", "0000"}:
        raise ValueError("A ONT recusou a leitura atual.")
    if "SessionTimeout" in raw or "login_need_refresh" in raw:
        raise ValueError("Sessão expirada; reconecte.")
    structures = {}
    for node in root:
        if not (node.tag.startswith(("OBJ_", "ID_")) or
                node.tag == "ALLDNSHOST"):
            continue
        instances = node.findall("Instance")
        names = set()
        for record in instances:
            children = list(record)
            for pos, item in enumerate(children[:-1]):
                if item.tag != "ParaName" or children[pos + 1].tag != "ParaValue":
                    continue
                field = (item.text or "").strip()
                if field and not mm.SENSITIVE_NAME.search(field):
                    names.add(field[:64])
        structures[node.tag] = {
            "records": len(instances),
            "fields": sorted(names)[:80],
        }
    if expected and expected not in structures:
        raise ValueError("O formulário não retornou o objeto esperado.")
    if not structures:
        raise ValueError("A resposta não contém objetos XML inspecionáveis.")
    return structures


def inspect(zte, tag: str) -> dict:
    """Inspect each captured GET on explicit operator request.

    XML and JSON routes are independent of POST permissions. Never expose
    firmware values, HTML, credential fields or raw router data.
    """
    route = ALLOWED.get(tag)
    if not route:
        raise ValueError("Rota não incluída na captura autorizada.")
    if tag == "wlan_sta_wlan_profile_lua.lua":
        # Scanning is an explicit user action, never automatic bootstrap.
        params = {**GET_PARAMS.get(tag, {}), "APGetFrom": "ScanAP"}
    else:
        params = GET_PARAMS.get(tag, {})
    if route["request_type"] == "hiddenData":
        response = zte.session.get(zte.base_url + "/", params={
            "_type": "hiddenData", "_tag": tag,
        }, timeout=10)
        response.raise_for_status()
        raw = response.text
    else:
        view = CAPTURED_GET_VIEWS.get(tag)
        if not view:
            return {"tag": tag, "available": False,
                    "reason": "Este GET ainda não tem menuView documentada."}
        zte.get_view(view, Menu3Location=0)
        raw = zte.get_menu(tag, **params)
    if not isinstance(raw, str) or not raw.strip():
        return {"tag": tag, "available": False,
                "reason": "A ONT retornou uma resposta vazia."}
    try:
        if route["response_format"] == "JSON":
            payload = json.loads(raw)
            if not isinstance(payload, (dict, list)):
                raise ValueError("JSON sem objeto ou lista.")
            fields = (
                sorted(str(k)[:64] for k in payload
                       if not mm.SENSITIVE_NAME.search(str(k)))[:80]
                if isinstance(payload, dict) else []
            )
            structure = {"type": type(payload).__name__,
                         "items": len(payload), "fields": fields}
        else:
            structure = _structural_xml(raw, route["root"])
    except (ET.ParseError, ValueError, TypeError):
        return {"tag": tag, "available": False,
                "reason": "A resposta não confirmou a estrutura capturada."}
    return {"tag": tag, "category": route["category"],
            "available": True, "structure": structure}

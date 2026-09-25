from __future__ import annotations

from .base import DeviceAdapter, EndpointSpec, FeatureSpec
from apps.zte_manager.services.multimodel_service import find_family, FAMILY


def _endpoint(
    view: str,
    tag: str,
    *object_keys: str,
    query: dict | None = None,
) -> EndpointSpec:
    return EndpointSpec(
        view=view,
        tag=tag,
        query=query or {},
        object_keys=tuple(object_keys),
    )


# Catálogo comum encontrado nos firmwares ThinkLua aparentados ao F6600P/F670L.
# O probe confirma em runtime o que o login/firmware realmente permite.
COMMON_FEATURES: dict[str, FeatureSpec] = {
    "wifi_advanced": FeatureSpec(
        "wifi_advanced",
        "Wi-Fi avançado",
        (_endpoint("wlanBasic", "wlan_wlanbasicadconf_lua.lua", "OBJ_WLANSETTING_ID"),),
        writable=True,
    ),
    "wifi_neighbor_scan": FeatureSpec(
        "wifi_neighbor_scan",
        "Scan de redes Wi-Fi vizinhas",
        (
            _endpoint(
                "wlanStaScanAP",
                "tot_wlan_wlan_profile_lua.lua",
                "OBJ_WLANGETNEBAP_ID",
                query={"APGetFrom": "ScanAP"},
            ),
            _endpoint(
                "wlanStaScanAP",
                "wlan_sta_wlan_profile_lua.lua",
                "OBJ_WLANGETNEBAP_ID",
                query={"APGetFrom": "ScanAP"},
            ),
        ),
        notes="Leitura de SSID/BSSID, sinal, ruído e canal quando o firmware expõe o scan.",
    ),
    "wifi_interference_schedule": FeatureSpec(
        "wifi_interference_schedule",
        "Gerenciador de interferência Wi-Fi",
        (_endpoint(
            "wlan_interference",
            "wlan_interference_lua.lua",
            "OBJ_WLAN_INTERFERENCE_ID",
        ),),
        notes="O menu controla o scan automático do firmware; a console usa o scan de vizinhança para pontuar canais.",
    ),
    "native_speedtest": FeatureSpec(
        "native_speedtest",
        "Speed Test nativo da ONT",
        (_endpoint(
            "homePage",
            "home_ais_lua.lua",
        ),),
        notes="Quando disponível, mede a partir da própria ONT. O servidor é descoberto pelo firmware.",
    ),
    "dns_lookup": FeatureSpec(
        "dns_lookup",
        "DNS Lookup nativo",
        (_endpoint(
            "networkDiag",
            "DiagnosisNsLookupReq_lua.lua",
        ),),
        notes="Usado para diferenciar DNS estático vazio de falha real de resolução.",
    ),
    "wifi_schedule": FeatureSpec(
        "wifi_schedule",
        "Agendamento Wi-Fi",
        (_endpoint(
            "wlanBasic",
            "wlan_wlanbasiconoff_lua.lua",
            "OBJ_WLANTIMECFG_ID",
            "OBJ_WLANTIME_ID",
        ),),
        writable=True,
    ),
    "band_steering": FeatureSpec(
        "band_steering",
        "Band Steering",
        (_endpoint(
            "smBandSteer",
            "mgts_bandsteer_lua.lua",
            "OBJ_MGTS_BANDSTEER_ID",
            "OBJ_BANDSTEER_ENABLE_ID",
        ),),
        writable=True,
    ),
    "dhcp_basic": FeatureSpec(
        "dhcp_basic",
        "Servidor DHCP IPv4",
        (_endpoint(
            "lanMgrIpv4",
            "Localnet_LanMgrIpv4_DHCPBasicCfg_lua.lua",
            "OBJ_Br0AndDhcpsHosCfg_ID",
            "OBJ_LANDNS_ID",
        ),),
        writable=True,
        notes="Mudança do IP LAN é propositalmente bloqueada pela console.",
    ),
    "dhcp_leases": FeatureSpec(
        "dhcp_leases",
        "Leases DHCP",
        (_endpoint(
            "lanMgrIpv4",
            "Localnet_LanMgrIpv4_DHCPHostInfo_lua.lua",
            "OBJ_DHCPHOSTINFO_ID",
        ),),
    ),
    "dhcp_reservations": FeatureSpec(
        "dhcp_reservations",
        "Reservas DHCP",
        (_endpoint(
            "lanMgrIpv4",
            "Localnet_LanMgrIpv4_DHCPStaticRule_lua.lua",
            "OBJ_DHCPBIND_ID",
        ),),
        writable=True,
    ),
    "port_forwarding": FeatureSpec(
        "port_forwarding",
        "Port Forwarding",
        (_endpoint("portForwarding", "firewall_portforwarding_lua.lua", "OBJ_FWPM_ID"),),
        writable=True,
        dangerous=True,
    ),
    "dmz": FeatureSpec(
        "dmz",
        "DMZ",
        (_endpoint("dmz", "firewall_dmz_lua.lua", "OBJ_FWDMZ_ID"),),
        writable=True,
        dangerous=True,
    ),
    "upnp_port_map": FeatureSpec(
        "upnp_port_map",
        "Mapeamentos UPnP",
        (_endpoint("upnp", "upnp_portmap_lua.lua", "OBJ_UPNPPORTMAP_ID"),),
    ),
    "service_control_ipv4": FeatureSpec(
        "service_control_ipv4",
        "Controle de serviços IPv4",
        (_endpoint(
            "localServiceCtrl",
            "firewall_ipv4service_lua.lua",
            "OBJ_FWSC_ID",
        ),),
        dangerous=True,
        notes="Somente leitura; alterar serviços pode remover o acesso de gerenciamento.",
    ),
    "service_control_ipv6": FeatureSpec(
        "service_control_ipv6",
        "Controle de serviços IPv6",
        (_endpoint(
            "localServiceCtrl",
            "firewall_ipv6service_lua.lua",
            "OBJ_FWSCv6_ID",
        ),),
        dangerous=True,
        notes="Somente leitura; alterar serviços pode remover o acesso de gerenciamento.",
    ),
    "firewall": FeatureSpec(
        "firewall",
        "Firewall",
        (_endpoint("firewall", "firewall_config_lua.lua", "OBJ_FWLEVEL_ID"),),
        dangerous=True,
        notes="Somente leitura na console para evitar perda de acesso remoto.",
    ),
    "firewall_filters": FeatureSpec(
        "firewall_filters",
        "Filtros globais",
        (_endpoint("filterCriteria", "firewall_filterglobal_lua.lua", "OBJ_FWBASE_ID"),),
        dangerous=True,
        notes="Somente leitura.",
    ),
    "ip_filter": FeatureSpec(
        "ip_filter",
        "Filtro IP",
        (_endpoint("filterCriteria", "firewall_ipfilter_lua.lua", "OBJ_FWIP_ID"),),
        dangerous=True,
        notes="Somente leitura.",
    ),
    "mac_filter": FeatureSpec(
        "mac_filter",
        "Filtro MAC",
        (_endpoint("filterCriteria", "firewall_macfilterv3_lua.lua", "OBJ_MACFILTER_ID"),),
        dangerous=True,
        notes="Somente leitura.",
    ),
    "parental_control": FeatureSpec(
        "parental_control",
        "Controle parental",
        (_endpoint("parentCtrl", "firewall_parentctrl_lua.lua", "OBJ_PARENT_CONTROL_ID"),),
        dangerous=True,
        notes="Somente leitura.",
    ),
    "ddns": FeatureSpec(
        "ddns",
        "DDNS",
        (_endpoint("ddns", "ddns_lua.lua", "OBJ_DDNSCLIENT_ID"),),
        notes="Credenciais nunca são retornadas em claro pela console.",
    ),
    "sntp": FeatureSpec(
        "sntp",
        "SNTP / NTP",
        (_endpoint("sntp", "sntp_lua.lua", "OBJ_SNTP_ID"),),
    ),
    "tr069": FeatureSpec(
        "tr069",
        "TR-069 / ACS",
        (_endpoint("remoteMgr", "tr069_remotemgr_lua.lua", "OBJ_MANAGESERVER_ID"),),
        dangerous=True,
        notes="Somente leitura; senhas são sempre mascaradas.",
    ),
    "route_table": FeatureSpec(
        "route_table",
        "Tabela de rotas IPv4",
        (_endpoint("routeIpv4", "route_routetableipv4_lua.lua", "OBJ_ROUTETABLE_ID"),),
    ),
    "qos_queue": FeatureSpec(
        "qos_queue",
        "QoS / filas",
        (_endpoint("qosQueue", "qos_queue_lua.lua"),),
    ),
    "qos_speed": FeatureSpec(
        "qos_speed",
        "QoS / policer",
        (_endpoint("qosSpeed", "qos_speed_lua.lua"),),
    ),
    "qos_shaper": FeatureSpec(
        "qos_shaper",
        "QoS / shaper",
        (_endpoint("qosShaper", "qos_shaper_lua.lua"),),
    ),
    "syslog": FeatureSpec(
        "syslog",
        "Logs do equipamento",
        (_endpoint("logMgr", "log_syslogmgr_lua.lua", "OBJ_LOG_ID"),),
    ),
    "firmware_management": FeatureSpec(
        "firmware_management",
        "Gerenciamento de firmware",
        (_endpoint(
            "firmwareUpgr",
            "upgrade_firmware_query_lua.lua",
        ),),
        dangerous=True,
        notes="Somente leitura/probe; upload de firmware não é automatizado.",
    ),
    "restore_config": FeatureSpec(
        "restore_config",
        "Restauração de configuração",
        (_endpoint(
            "usrCfgMgr",
            "db_usrcfg_upgrade_query_lua.lua",
        ),),
        dangerous=True,
        notes="Somente leitura/probe; importação automática foi bloqueada por segurança.",
    ),
    "factory_reset": FeatureSpec(
        "factory_reset",
        "Factory Reset",
        (_endpoint(
            "rebootAndReset",
            "db_resetmgr_lua.lua",
        ),),
        dangerous=True,
        notes="Somente probe; o POST Reset não é exposto pela aplicação.",
    ),
    "backup_config": FeatureSpec(
        "backup_config",
        "Backup da configuração",
        (),
        writable=True,
        dangerous=True,
        notes=(
            "Export usa o fluxo usrCfgMgr/updownload_prevent_ctl/do_download_usercfg; "
            "restauração não é automatizada."
        ),
    ),
}


class ThinkLuaAdapter(DeviceAdapter):
    name = "thinklua-generic"

    @property
    def features(self) -> dict[str, FeatureSpec]:
        return COMMON_FEATURES


class F6600PAdapter(ThinkLuaAdapter):
    name = "zte-f6600p-thinklua"


class F670LAdapter(ThinkLuaAdapter):
    name = "zte-f670l-thinklua"


class MultiFamilyReadOnlyAdapter(ThinkLuaAdapter):
    """Novos modelos: só declarar os endpoints verificados como candidatos.

    Os recursos legados de configuração da F670L não são automaticamente
    habilitados em firmwares de outras famílias.
    """

    name = "zte-multimodel-discovery"

    @property
    def features(self) -> dict[str, FeatureSpec]:
        _, family = find_family(self.model)
        endpoints = FAMILY.get(family or "", {})
        labels = {
            "wifi_clients": "Clientes Wi-Fi (inspeção)",
            "lan_clients": "Clientes cabeados (inspeção)",
            "wan": "Estado WAN (inspeção)",
            "dsl": "Linha DSL (inspeção)",
        }
        return {
            key: FeatureSpec(
                key, labels.get(key, key),
                (
                    EndpointSpec(
                        view=spec.view,
                        tag=spec.tag,
                        query=dict(spec.params),
                        object_keys=(spec.root,),
                    ),
                ),
                writable=False,
                notes="Somente leitura; funcionalidade depende de prova no firmware.",
            )
            for key, spec in endpoints.items()
        }


def select_adapter(
    model: str | None,
    firmware: str | None = None,
) -> DeviceAdapter:
    normalized = (model or "").upper().replace("-", "").replace(" ", "")

    if "F670L" in normalized:
        return F670LAdapter(model, firmware)

    if "F6600P" in normalized:
        return F6600PAdapter(model, firmware)

    key, family = find_family(normalized)
    if family:
        # Vue exige login e parser separados. Não anunciar menus ThinkLua.
        return MultiFamilyReadOnlyAdapter(model, firmware)

    # Fallback conservador: os recursos continuam dependendo de probe.
    return ThinkLuaAdapter(model, firmware)

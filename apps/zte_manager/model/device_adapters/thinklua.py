from __future__ import annotations

from .base import DeviceAdapter, EndpointSpec, FeatureSpec


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
        (_endpoint("tr069", "tr069_remotemgr_lua.lua", "OBJ_MANAGESERVER_ID"),),
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


def select_adapter(
    model: str | None,
    firmware: str | None = None,
) -> DeviceAdapter:
    normalized = (model or "").upper().replace("-", "").replace(" ", "")

    if "F670L" in normalized:
        return F670LAdapter(model, firmware)

    if "F6600P" in normalized:
        return F6600PAdapter(model, firmware)

    # Fallback conservador: os recursos continuam dependendo de probe.
    return ThinkLuaAdapter(model, firmware)

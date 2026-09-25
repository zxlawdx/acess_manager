"""F6201B V9.3.10P7N7: safe schema extracted from owner network capture.

Source: 209 authorized HTTP events; 179 GET, 30 POST.
Never store or commit the raw capture: it contains credentials, tokens,
WAN provisioning, Wi-Fi PSKs and sensitive account details.
This catalog records only endpoint names, view context and field NAMES.
HTTP 200 was not considered enough: all observed POST responses had
IF_ERRORID=0. The production adapter must still re-read after each write.
"""
from __future__ import annotations

CAPTURED_GET_VIEWS: dict[str, str] = {
    "status_lan_info_lua.lua": "localNetStatus",
    "dns_localdns_lua.lua": "dns",
    "dns_hostname_lua.lua": "dns",
    "bpdu_lua.lua": "bpdu",
    "upnp_portmap_lua.lua": "upnpportmapss",
    "upnp_upnp_lua.lua": "upnp",
    "route_routedefault_lua.lua": "routeIpv4",
    "route_routetableipv4_lua.lua": "routeIpv4",
    "route_routestaticipv4_lua.lua": "routeIpv4",
    "route_routepolicyipv4_lua.lua": "routeIpv4",
    "Localnet_LanMgrIpv4_DHCPHostInfo_lua.lua": "lanMgrIpv4",
    "Localnet_LanMgrIpv4_DHCPBasicCfg_lua.lua": "lanMgrIpv4",
    "Localnet_LanMgrIpv4_DHCPStaticRule_lua.lua": "lanMgrIpv4",
    "Localnet_LanDevDHCPSource_lua.lua": "lanMgrIpv4",
    "dhcp6s_hostinfo_lua.lua": "lanMgrIpv6",
    "addr6_lanaddr_lua.lua": "lanMgrIpv6",
    "prefix_staticprefix_lua.lua": "lanMgrIpv6",
    "prefix_prefixpool_lua.lua": "lanMgrIpv6",
    "dhcp6s_dhcpserver_lua.lua": "lanMgrIpv6",
    "ra_raservice_lua.lua": "lanMgrIpv6",
    "radhcp6s_portctrl_lua.lua": "lanMgrIpv6",
    "eth_interface_config_lua.lua": "lanPortconf",
    "wlan_wlanbasiconoff_lua.lua": "wlanBasic",
    "wlan_wlanbasicadconf_lua.lua": "wlanBasic",
    "wlan_wlansssidconf_lua.lua": "wlanBasic",
    "wlan_macfilteraclpolicy_lua.lua": "wlanAdvanced",
    "wlan_macfilterrule_lua.lua": "wlanAdvanced",
    "wlan_wps_lua.lua": "wps",
    "wlan_sta_wlan_profile_lua.lua": "wlanStaScanAP",
    "wlan_BandSteering_lua.lua": "wifibandsteer",
    "Localnet_NetSphere_Mode_lua.lua": "smNetSphereMAP",
    "voipRegStatus_lua.lua": "voipStatus",
    "voip_voipbasic_lua.lua": "voipBasic",
    "voipDmtTimer_lua.lua": "voipServices",
    "Voip_SipService_lua.lua": "voipServices",
    "voip_sipadvanced_lua.lua": "sipAdvanced",
    "devmgr_statusmgr_lua.lua": "statusMgr",
    "register_sn_model.lua": "RegisterSN",
    "devauth_accountmgr_lua.lua": "accountMgr",
    "log_syslogmgr_lua.lua": "logMgr",
    "tr069_remotemgr_lua.lua": "remoteMgr",
    "scp_remotemgr_lua.lua": "scpMgr",
    "networkdiag_ping_lua.lua": "networkDiag",
    "networkdiag_traceroute_lua.lua": "networkDiag",
    "networkdiag_svcsimulation_lua.lua": "networkDiag",
    "ipv6_enable_lua.lua": "IPv6SwitchMgr",
    "devmgr_lan_backup_lua.lua": "LANBackUp",
    "wlan_homepage_lua.lua": "homePage",
    "firewall_homepage_lua.lua": "homePage",
    "accessdev_homepage_lua.lua": "homePage",
    "voip_homepage_lua.lua": "homePage",
    "topo_lua.lua": "mmTopology",
    "optical_info_lua.lua": "ponopticalinfo",
    "wan_internet_lua.lua": "ethWanConfig",
    "clearlink_lua.lua": "clearlink",
    "firewall_config_lua.lua": "firewall",
    "firewall_filterglobal_lua.lua": "filterCriteria",
    "firewall_ipv4service_lua.lua": "localServiceCtrl",
    "firewall_alg_lua.lua": "alg",
    "firewall_dmz_lua.lua": "dmz",
    "firewall_portforwarding_lua.lua": "portForwarding",
    "firewall_porttrigger_m.lua": "portTrigger",
    "tunnel_4in6_status_lua.lua": "tunnel4in6Status",
    "wan_internetstatus_lua.lua": "ethWanStatus",
    "l2tp_lua.lua": "l2tpStatus",
}

# Exact observed form field order, excluding any sensitive VALUES.
# post_menu appends _sessionTOKEN last and computes Check from the final body.
SSID_APPLY_FIELDS: tuple[str, ...] = (
    "IF_ACTION", "Enable", "_InstID", "_WEPCONIG", "_PSKCONIG",
    "BeaconType", "WEPAuthMode", "WPAAuthMode", "11iAuthMode",
    "WPAEncryptType", "11iEncryptType", "WPA3AuthMode", "WPA3EncryptType",
    "_InstID_WEP0", "_InstID_WEP1", "_InstID_WEP2", "_InstID_WEP3",
    "_InstID_PSK", "MasterAuthServerIp", "BackupAuthServerIp",
    "MasterAcctServerIp", "BackupAcctServerIp", "_InstID_GUEST", "_GUEST", "ESSID",
    "ESSIDHideEnable", "EncryptionType", "KeyPassphrase", "WEPKeyIndex",
    "ShowWEPKey", "WEPKey00", "WEPKey01", "WEPKey02", "WEPKey03",
    "VapIsolationEnable", "MaxUserNum",
    "Btn_cancel_WLANSSIDConf", "Btn_apply_WLANSSIDConf",
    "encode", "_sessionTOKEN",
)

# Explicitly observed successful Apply (IF_ERRORID=0). Each write
# remains blocked until a dedicated form-specific adapter validates all
# secrets, existing fields and target identity.
OBSERVED_APPLY_FIELDS: dict[str, tuple[str, ...]] = {
    "wlan_wlansssidconf_lua.lua": SSID_APPLY_FIELDS,
    "dns_localdns_lua.lua": (
        "IF_ACTION", "_InstID", "SerIPAddress1", "SerIPAddress2",
        "SerIPv6Address1", "SerIPv6Address2",
        "Btn_cancel_LocalDnsServer", "Btn_apply_LocalDnsServer",
        "_sessionTOKEN",
    ),
    "wlan_BandSteering_lua.lua": (
        "IF_ACTION", "_InstID", "BsEnable", "BsRssiLmt24G",
        "BsRssiLmt5G", "BsBounceDwellTimeLmt", "BsTPLimit",
        "Btn_cancel_Mode", "Btn_apply_Mode", "_sessionTOKEN",
    ),
    "wlan_wps_lua.lua": (
        "IF_ACTION", "_InstID", "SSID_InstID", "Enable",
        "WPSMode", "WPSChoose", "Btn_apply_WPS", "_sessionTOKEN",
    ),
    "wlan_wlanbasicadconf_lua.lua": (
        "IF_ACTION", "_InstID", "BasicDataRates", "OpDataRates",
        "11nMode", "GreenField", "AutoChannelEnabled", "Band",
        "Channel", "Standard", "BandWidth", "AutoChRange", "MUMIMOEnable",
        "UPLinkOFDMA", "SSIDIsolationEnable", "CountryCode",
        "SGIEnabled", "BeaconInterval", "TxPower", "PreambleType",
        "_sessionTOKEN",
    ),
    "wan_internet_lua.lua": (
        "IF_ACTION", "_InstID", "uplink", "InstHasGot", "ControlType",
        "WANCName", "Enable", "mode", "ServList", "MTU", "linkMode",
        "TransType", "UserName", "Password", "AuthType",
        "ConnTrigger", "IdleTime0", "IdleTime1", "IpMode", "Addressingtype",
        "IPAddress0", "IPAddress1", "IPAddress2", "IPAddress3",
        "SubnetMask0", "SubnetMask1", "SubnetMask2", "SubnetMask3",
        "GateWay0", "GateWay1", "GateWay2", "GateWay3",
        "DNS10", "DNS11", "DNS12", "DNS13", "DNS20", "DNS21",
        "DNS22", "DNS23", "DNS30", "DNS31", "DNS32", "DNS33",
        "IsNAT", "IPv6AcquireMode", "Gua1", "Gua1PrefixLen",
        "Gateway6", "Pd", "PdLen", "Dns1v6", "Dns2v6", "Dns3v6",
        "IsPD", "Unnumbered", "IsSLAAC", "IsGUA", "IsPdAddr",
        "VlanEnable", "VLANID", "Priority", "Btn_cancel_internet",
        "Btn_apply_internet", "encode", "_sessionTOKEN",
    ),
    "upnp_upnp_lua.lua": (
        "IF_ACTION", "_InstID", "EnableUPnPIGD", "ADPeriod",
        "TTL", "_sessionTOKEN",
    ),
    "firewall_config_lua.lua": (
        "IF_ACTION", "_InstID", "Enable", "Level",
        "Btn_cancel_FirewallConf", "Btn_apply_FirewallConf", "_sessionTOKEN",
    ),
}

GET_PARAMS = {
    "wan_internetstatus_lua.lua": {"TypeUplink": "2", "pageType": "1"},
    "wan_internet_lua.lua": {"TypeUplink": "2", "pageType": "0"},
    "wlan_homepage_lua.lua": {"InstNum": "5"},
    "accessdev_homepage_lua.lua": {"InstNum": "5"},
}

# Newly recovered XML objects from second capture. View-only HTML and JSON
# routes are intentionally excluded from generic XML inspection.
CAPTURED_GET_ROOTS: dict[str, str] = {
    # HTTP capture truncated this >30KB response; production GET must
    # return complete well-formed XML before any parsing.
    "wlan_wlanbasicadconf_lua.lua": "OBJ_WLANSETTING_ID",
    "wan_internetstatus_lua.lua": "ID_WAN_COMFIG",
    "wan_internet_lua.lua": "ID_WAN_COMFIG",
    "dns_hostname_lua.lua": "",  # ALLDNSHOST is not OBJ XML
    "upnp_portmap_lua.lua": "OBJ_UPNPPORTMAP_ID",
    "route_routestaticipv4_lua.lua": "OBJ_ROUTESTATIC_ID",
    "route_routepolicyipv4_lua.lua": "OBJ_ROUTETPOLICY_ID",
    "Localnet_LanMgrIpv4_DHCPStaticRule_lua.lua": "OBJ_DHCPBIND_ID",
    "dhcp6s_hostinfo_lua.lua": "OBJ_DHCP6C_ID",
    "addr6_lanaddr_lua.lua": "OBJ_LANADDR6_ID",
    "prefix_staticprefix_lua.lua": "OBJ_STATIC_PREFIX_ID",
    "prefix_prefixpool_lua.lua": "OBJ_PREFIXPOOL_ID",
    "dhcp6s_dhcpserver_lua.lua": "OBJ_DHCP6S_ID",
    "ra_raservice_lua.lua": "OBJ_RAIS_ID",
    "radhcp6s_portctrl_lua.lua": "OBJ_IPV6BANPORT_ID",
    "wlan_macfilterrule_lua.lua": "OBJ_ACLCFG_ID",
    "wlan_sta_wlan_profile_lua.lua": "OBJ_WLANGETNEBAP_ID",
    "voip_voipbasic_lua.lua": "OBJ_VOIPSIPLINE_ID",
    "voipDmtTimer_lua.lua": "OBJ_VOIPDMTIMER_ID",
    "Voip_SipService_lua.lua": "OBJ_VOIPVPCALLFEATURE_ID",
    "voip_sipadvanced_lua.lua": "OBJ_VRTPADV_ID",
    "devmgr_statusmgr_lua.lua": "OBJ_DEVINFO_ID",
    "register_sn_model.lua": "",  # JSON
    "devauth_accountmgr_lua.lua": "OBJ_USERINFO_ID",
    "log_syslogmgr_lua.lua": "OBJ_LOG_ID",
    "networkdiag_svcsimulation_lua.lua": "OBJ_SIMULATION_PPPOE_GET_ID",
    "ipv6_enable_lua.lua": "OBJ_IPGLOBAL_ID",
    "devmgr_lan_backup_lua.lua": "OBJ_LAN_BACKUP_ID",
    "firewall_portforwarding_lua.lua": "OBJ_FWPM_ID",
    "firewall_porttrigger_m.lua": "OBJ_FWPT_ID",
    "tunnel_4in6_status_lua.lua": "",  # Valid response with no OBJ
    "l2tp_lua.lua": "OBJ_L2TP_ID",
}

# A mesma _tag dns_localdns usa um FORMULÁRIO DIFERENTE para DomainName.
DNS_DOMAIN_APPLY_FIELDS = (
    "IF_ACTION", "_InstID", "DomainName",
    "Btn_cancel_instCfgArea", "Btn_apply_instCfgArea",
    "_sessionTOKEN",
)

# Full KEY LISTS for the remaining successful Apply routes. No values,
# tokens, passwords or endpoint addresses are recorded.
_OTHER_APPLY = """
dns_hostname_lua.lua|IF_ACTION _InstID OBJID LeaseTime HostName IPAddress _sessionTOKEN
bpdu_lua.lua|IF_ACTION _InstID BPDUEnable Btn_cancel_instCfgArea Btn_apply_instCfgArea _sessionTOKEN
route_routedefault_lua.lua|IF_ACTION _InstID DefRTInterface Btn_cancel_RouteDefault Btn_apply_RouteDefault _sessionTOKEN
route_routestaticipv4_lua.lua|IF_ACTION _InstID DestIP DestIPMask GWIP Type Enable Alias Interface _sessionTOKEN
Localnet_LanMgrIpv4_DHCPBasicCfg_lua.lua|IF_ACTION IF_URL_HOST _InstID IPAddr SubMask OptEnable OptCode SubnetMask MinAddress MaxAddress IPRouters DNSServer1 DNSServer2 LeaseTime ServerEnable DnsServerSource OptValue DomainName Btn_cancel_DHCPBasicCfg Btn_apply_DHCPBasicCfg encode _sessionTOKEN
Localnet_LanDevDHCPSource_lua.lua|IF_ACTION _InstNum _InstID_0 ProcFlag_0 _InstID_1 ProcFlag_1 _InstID_2 ProcFlag_2 _InstID_3 ProcFlag_3 _InstID_4 ProcFlag_4 _InstID_5 ProcFlag_5 _InstID_6 ProcFlag_6 _InstID_7 ProcFlag_7 _InstID_8 ProcFlag_8 _InstID_9 ProcFlag_9 _InstID_10 ProcFlag_10 _InstID_11 ProcFlag_11 _InstID Btn_cancel_LanDevDHCPSource Btn_apply_LanDevDHCPSource _sessionTOKEN
addr6_lanaddr_lua.lua|IF_ACTION _InstID IPAddress Btn_cancel_IPv6LANAddr Btn_apply_IPv6LANAddr _sessionTOKEN
dhcp6s_dhcpserver_lua.lua|IF_ACTION _InstID _InstID_DNS IANAEnable IsPrefixAutoMode Enable ManualDNSEnable DNSAddr1 DNSAddr2 DNSAddr3 Ipv6DnsOrigin DnsRefreshTime Btn_cancel_IPv6DHCPServer Btn_apply_IPv6DHCPServer Btn_PrefixUpd_IPv6DHCPServer Btn_SelfUpd_IPv6DHCPServer _sessionTOKEN
ra_raservice_lua.lua|IF_ACTION _InstID IsPrefixAutoMode Enable AdvLinkMTUEnable S_AdvLinkMTU AdvPreferredRouterFlag MinRtrAdvInterval MaxRtrAdvInterval AdvManagedFlag AdvOtherConfigFlag PrefixMode Btn_cancel_RAService Btn_apply_RAService Btn_PrefixUpd_RAService Btn_SelfUpd_RAService _sessionTOKEN
radhcp6s_portctrl_lua.lua|IF_ACTION _InstNum _InstID_0 PortID_0 AllowDHCP6S_0 AllowRA_0 _InstID_1 PortID_1 AllowDHCP6S_1 AllowRA_1 _InstID_2 PortID_2 AllowDHCP6S_2 AllowRA_2 _InstID_3 PortID_3 AllowDHCP6S_3 AllowRA_3 _InstID_4 PortID_4 AllowDHCP6S_4 AllowRA_4 _InstID_5 PortID_5 AllowDHCP6S_5 AllowRA_5 _InstID_6 PortID_6 AllowDHCP6S_6 AllowRA_6 _InstID_7 PortID_7 AllowDHCP6S_7 AllowRA_7 _InstID_8 PortID_8 AllowDHCP6S_8 AllowRA_8 _InstID_9 PortID_9 AllowDHCP6S_9 AllowRA_9 _InstID_10 PortID_10 AllowDHCP6S_10 AllowRA_10 _InstID_11 PortID_11 AllowDHCP6S_11 AllowRA_11 _InstID PortID AllowDHCP6S AllowRA Btn_cancel_IPv6DHCPPortCtl Btn_apply_IPv6DHCPPortCtl _sessionTOKEN
eth_interface_config_lua.lua|IF_ACTION _InstID Autoneg MaxBitRate DuplexMode ModType Btn_cancel_lanInterface Btn_apply_lanInterface _sessionTOKEN
wlan_wlanbasiconoff_lua.lua|IF_ACTION RadioStatus TimerEnable _InstID_0 Band_0 RadioStatus_0 _InstID_1 Band_1 RadioStatus_1 _InstID Band TimeStartHour TimeStartMin TimeEndHour TimeEndMin Btn_cancel_WlanBasicAdConf Btn_apply_WlanBasicAdConf _sessionTOKEN
wlan_macfilteraclpolicy_lua.lua|IF_ACTION _InstNum _InstID_0 ACLPolicy_0 _InstID_1 ACLPolicy_1 _InstID_2 ACLPolicy_2 _InstID_3 ACLPolicy_3 _InstID_4 ACLPolicy_4 _InstID_5 ACLPolicy_5 _InstID_6 ACLPolicy_6 _InstID_7 ACLPolicy_7 _InstID Btn_cancel_MACFilterACLPolicy Btn_apply_MACFilterACLPolicy _sessionTOKEN
Localnet_NetSphere_Mode_lua.lua|IF_ACTION _InstID CurrentMode CurrentEnable Enable EnLegacyStaRoam RoamRssiLmt24G RoamRssiLmt5G Btn_cancel_Mode Btn_apply_Mode Btn_apply_Mode_Confirm _sessionTOKEN
tr069_remotemgr_lua.lua|IF_ACTION CertList DefaultWan URL UserName UserPassword ConnectionRequestUsername ConnectionRequestPassword PeriodicInformEnable PeriodicInformInterval SupportCertAuth select_CertID RemoteUpgradeCertAuth Btn_cancel_TR069BasicConf Btn_apply_TR069BasicConf encode _sessionTOKEN
firewall_alg_lua.lua|IF_ACTION _InstID IsFTPAlg IsH323Alg IsIPSECAlg IsL2TPAlg IsPPTPAlg IsRTSPAlg IsSIPAlg IsTFTPAlg Btn_cancel_Alg Btn_apply_Alg _sessionTOKEN
firewall_dmz_lua.lua|IF_ACTION _InstID Enable WANCViewName InternalClient sub_TempMacAddr0 sub_TempMacAddr1 sub_TempMacAddr2 sub_TempMacAddr3 sub_TempMacAddr4 sub_TempMacAddr5 Btn_cancel_Ipv4Dmz Btn_apply_Ipv4Dmz _sessionTOKEN
"""
for _line in _OTHER_APPLY.strip().splitlines():
    _tag, _fields = _line.split("|", 1)
    OBSERVED_APPLY_FIELDS[_tag] = tuple(_fields.split())

# Raw capture also includes PingDiagnosis and TraceRouteDiagnosis. These
# are active operations, not read-only Get and not firmware configuration.
OBSERVED_DIAGNOSTIC_ACTIONS = {
    "networkdiag_ping_lua.lua": (
        "IF_ACTION", "Host", "NumofRepeat", "DataBlockSize",
        "Timeout", "_sessionTOKEN",
    ),
    "networkdiag_traceroute_lua.lua": (
        "IF_ACTION", "Control", "Host", "MaxHopCount", "Timeout",
        "Protocol", "_sessionTOKEN",
    ),
}

CAPTURE_STATISTICS = {
    "total_http": 209, "get": 179, "post": 30,
    "successful_apply_events": 28,
    "successful_unique_apply_routes": len(OBSERVED_APPLY_FIELDS),
    "diagnostic_post_events": 2,
}

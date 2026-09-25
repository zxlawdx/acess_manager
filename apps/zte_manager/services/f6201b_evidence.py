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
    "MasterAcctServerIp", "BackupAcctServerIp", "_GUEST", "ESSID",
    "ESSIDHideEnable", "EncryptionType", "KeyPassphrase", "WEPKeyIndex",
    "ShowWEPKey", "WEPKey00", "WEPKey01", "WEPKey02", "WEPKey03",
    "VapIsolationEnable", "MaxUserNum", "encode", "_sessionTOKEN",
)

# Explicitly observed successful Apply (IF_ERRORID=0). Each write
# remains blocked until a dedicated form-specific adapter validates all
# secrets, existing fields and target identity.
OBSERVED_APPLY_FIELDS: dict[str, tuple[str, ...]] = {
    "wlan_wlansssidconf_lua.lua": SSID_APPLY_FIELDS,
    "dns_localdns_lua.lua": (
        "IF_ACTION", "_InstID", "SerIPAddress1", "SerIPAddress2",
        "SerIPv6Address1", "SerIPv6Address2", "_sessionTOKEN",
    ),
    "wlan_BandSteering_lua.lua": (
        "IF_ACTION", "_InstID", "BsEnable", "BsRssiLmt24G",
        "BsRssiLmt5G", "BsBounceDwellTimeLmt", "BsTPLimit",
        "_sessionTOKEN",
    ),
    "wlan_wps_lua.lua": (
        "IF_ACTION", "_InstID", "SSID_InstID", "Enable",
        "WPSMode", "WPSChoose", "_sessionTOKEN",
    ),
    "wlan_wlanbasicadconf_lua.lua": (
        "IF_ACTION", "_InstID", "BasicDataRates", "OpDataRates",
        "11nMode", "GreenField", "AutoChannelEnabled", "Band",
        "Channel", "Standard", "BandWidth", "MUMIMOEnable",
        "UPLinkOFDMA", "SSIDIsolationEnable", "CountryCode",
        "SGIEnabled", "BeaconInterval", "TxPower", "PreambleType",
        "_sessionTOKEN",
    ),
    "wan_internet_lua.lua": (
        "IF_ACTION", "_InstID", "uplink", "InstHasGot", "ControlType",
        "WANCName", "Enable", "mode", "ServList", "MTU", "linkMode",
        "TransType", "UserName", "Password", "AuthType",
        "ConnTrigger", "IdleTime0", "IdleTime1", "IpMode",
        "Addressingtype", "DNS10", "DNS11", "DNS12", "DNS13",
        "DNS20", "DNS21", "DNS22", "DNS23", "DNS30", "DNS31",
        "DNS32", "DNS33", "IsNAT", "IPv6AcquireMode", "Gua1PrefixLen",
        "IsPD", "Unnumbered", "IsSLAAC", "IsGUA", "IsPdAddr",
        "VlanEnable", "VLANID", "Priority", "encode", "_sessionTOKEN",
    ),
    "upnp_upnp_lua.lua": (
        "IF_ACTION", "_InstID", "EnableUPnPIGD", "ADPeriod",
        "TTL", "_sessionTOKEN",
    ),
    "firewall_config_lua.lua": (
        "IF_ACTION", "_InstID", "Enable", "Level", "_sessionTOKEN",
    ),
}

GET_PARAMS = {
    "wan_internetstatus_lua.lua": {"TypeUplink": "2", "pageType": "1"},
    "wan_internet_lua.lua": {"TypeUplink": "2", "pageType": "0"},
    "wlan_homepage_lua.lua": {"InstNum": "5"},
    "accessdev_homepage_lua.lua": {"InstNum": "5"},
}

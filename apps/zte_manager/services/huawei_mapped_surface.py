from __future__ import annotations

import re
from copy import deepcopy
from typing import Any
from urllib.parse import urlsplit

from apps.zte_manager.infrastructure.huawei import HuaweiWebClient
from apps.zte_manager.services.huawei_captured_features import (
    parse_huawei_js_records,
)


# Every group below comes from the WebUI surface present in the supplied
# EG8041X7-10 capture. Core flows that already have typed services remain in
# huawei_captured_features.py; this surface covers the rest without falling
# back to a ZTE implementation or denying the operation by profile.
HUAWEI_MAPPED_FEATURES: dict[str, dict[str, Any]] = {
    "wifi_schedule": {
        "label": "Wi-Fi Schedule",
        "pages": ["/html/amp/wifische/WlanSchedule.asp"],
    },
    "wifi_cover": {
        "label": "Wi-Fi Cover / Home Network",
        "pages": [
            "/html/amp/wificovercfg/wifiCover.asp",
            "/html/amp/wificoverinfo/wlancoverinfo.asp",
            "/html/amp/wificoverinfo/apNeighborList.asp",
            "/html/amp/wificoverinfo/apssidStat.asp",
            "/html/amp/wificoverinfo/apssidStation.asp",
        ],
        "reads": [
            {
                "path": "/html/amp/wificoverinfo/getTopoInfo.asp",
                "method": "POST",
                "referer": "/html/amp/wificoverinfo/wlancoverinfo.asp",
            },
        ],
    },
    "easymesh_topology": {
        "label": "EasyMesh topology",
        "pages": ["/html/amp/wlaninfo/easymeshTopo.asp"],
    },
    "ethernet_info": {
        "label": "Ethernet interfaces",
        "pages": ["/html/amp/ethinfo/ethinfo.asp"],
    },
    "ont_auth": {
        "label": "ONT authentication",
        "pages": ["/html/amp/ontauth/passwordcommon.asp"],
    },
    "port_isolation": {
        "label": "Port Isolation",
        "pages": ["/html/bbsp/portinfo/portisolate.asp"],
    },
    "ipv6_filter": {
        "label": "IPv6 Filtering",
        "pages": ["/html/bbsp/ipv6ipincoming/ipv6ipincoming.asp"],
    },
    "ipv6_port_mapping": {
        "label": "IPv6 Port Mapping",
        "pages": ["/html/bbsp/ipv6portmapping/ipv6portmapping.asp"],
    },
    "ipv6_default_route": {
        "label": "IPv6 Default Route",
        "pages": ["/html/bbsp/ipv6defaultroute/ipv6defaultroute.asp"],
    },
    "ipv6_static_route": {
        "label": "IPv6 Static Route",
        "pages": ["/html/bbsp/ipv6staticroute/ipv6staticroute.asp"],
    },
    "upnp": {
        "label": "UPnP",
        "pages": ["/html/bbsp/upnp/upnp.asp"],
    },
    "ddns": {
        "label": "DDNS",
        "pages": ["/html/bbsp/ddns/ddns.asp"],
    },
    "routing": {
        "label": "Routing / Static Route / Service Route",
        "pages": [
            "/html/bbsp/route/route.asp",
            "/html/bbsp/routeinfo/routeinfo.asp",
            "/html/bbsp/staticroute/staticroute.asp",
            "/html/bbsp/serviceroute/serviceroute.asp",
        ],
    },
    "port_mapping": {
        "label": "Port Mapping / Trigger",
        "pages": [
            "/html/bbsp/portmapping/portmapping.asp",
            "/html/bbsp/porttrigger/porttrigger.asp",
        ],
    },
    "mac_filter": {
        "label": "MAC filtering",
        "pages": [
            "/html/bbsp/macfilter/macfilter.asp",
            "/html/bbsp/wlanmacfilter/wlanmacfilter.asp",
        ],
    },
    "parental_control": {
        "label": "Parental control",
        "pages": [
            "/html/bbsp/parentalctrl/parentalctrlmac.asp",
            "/html/bbsp/parentalctrl/parentalctrlstatus.asp",
        ],
    },
    "port_acl": {
        "label": "Port ACL",
        "pages": ["/html/bbsp/portacl/newacl.asp"],
    },
    "lan_service": {
        "label": "LAN services",
        "pages": ["/html/bbsp/lanservicecfg/lanservicecfg.asp"],
    },
    "arp_ping": {
        "label": "ARP/Ping",
        "pages": ["/html/bbsp/arpping/arpping.asp"],
    },
    "firewall_log": {
        "label": "Firewall log",
        "pages": ["/html/bbsp/firewalllog/firewalllogview.asp"],
    },
    "wan_config": {
        "label": "WAN configuration",
        "pages": [
            "/html/bbsp/wan/wan.asp",
            "/html/bbsp/wan/wan.cus",
            "/html/bbsp/waninfo/waninfo.asp",
            "/html/bbsp/common/wan_list.asp",
            "/html/bbsp/common/wan_list_info.asp",
            "/html/bbsp/common/wan_list_cache_wan.asp",
            "/html/bbsp/common/wan_list_cache_wanipv6.asp",
            "/html/bbsp/common/getWanDynamicData.asp",
            "/html/bbsp/common/get_wan_list_ipdslite.asp",
            "/html/bbsp/common/get_wan_list_ipversion.asp",
            "/html/bbsp/common/get_wan_list_ipwanstat.asp",
            "/html/bbsp/common/get_wan_list_ispwlan.asp",
            "/html/bbsp/common/get_wan_list_policyroute.asp",
            "/html/bbsp/common/get_wan_list_pppdslite.asp",
            "/html/bbsp/common/get_wan_list_pppwanstat.asp",
            "/html/bbsp/common/get_wan_list_radiowanpara.asp",
            "/html/bbsp/common/get_wan_list_radiowanps.asp",
            "/html/bbsp/common/get_wan_list_v6iptunnel.asp",
            "/html/bbsp/common/get_wan_list_v6ppptunnel.asp",
            "/html/bbsp/common/get_wan_list_wanaccesstype.asp",
            "/html/bbsp/common/get_wan_list_wlaninfo.asp",
            "/html/bbsp/common/wanStateMonitor.asp",
            "/html/bbsp/common/wan_check.asp",
            "/html/bbsp/common/wan_control.asp",
            "/html/bbsp/common/wan_pageparse.asp",
            "/html/bbsp/common/wan_settings.asp",
            "/html/bbsp/common/wanaddressacquire.asp",
            "/html/bbsp/common/wandns.asp",
            "/html/bbsp/common/wanipv6state.asp",
        ],
        "reads": [
            {
                "path": "/html/bbsp/common/getwanlist.asp",
                "method": "POST",
                "referer": "/html/bbsp/wan/wan.asp",
                "token_page": "/html/bbsp/wan/wan.asp",
            },
            {
                "path": "/html/bbsp/common/get_wan_list_time.asp",
                "method": "POST",
                "referer": "/html/bbsp/wan/wan.asp",
            },
            {
                "path": "/html/bbsp/common/wanStateMonitor.asp",
                "method": "POST",
                "referer": "/html/bbsp/wan/wan.asp",
            },
            {
                "path": "/html/bbsp/common/wan_list_cache_wan.asp",
                "method": "POST",
                "referer": "/html/bbsp/wan/wan.asp",
            },
        ],
    },
    "user_devices": {
        "label": "User devices",
        "pages": [
            "/CustomApp/mainpage.asp",
            "/html/bbsp/common/lanuserinfo.asp",
            "/html/bbsp/common/dhcpinfo.asp",
            "/html/bbsp/userdevinfo/userdevinfo1.asp",
            "/html/bbsp/userdevinfo/userdetdevinfo.asp",
        ],
        "reads": [
            {
                "path": "/html/bbsp/common/GetLanUserDevInfo.asp",
                "method": "POST",
                "referer": "/html/bbsp/userdevinfo/userdevinfo1.asp",
            },
            {
                "path": "/html/bbsp/common/GetLanUserDhcpInfo.asp",
                "method": "POST",
                "referer": "/html/bbsp/userdevinfo/userdevinfo1.asp",
            },
            {
                "path": "/html/bbsp/userdevinfo/getuserdevinfo.asp",
                "method": "POST",
                "referer": "/html/bbsp/userdevinfo/userdevinfo1.asp",
            },
        ],
    },
    "vlan": {
        "label": "VLAN",
        "pages": ["/html/bbsp/vlanctc/vlanctc.asp"],
    },
    "qos_smart": {
        "label": "QoS Smart / statistics",
        "pages": [
            "/html/bbsp/qossmart/qossmart.asp",
            "/html/bbsp/qossmartstatistics/qossmartstatistics.asp",
            "/html/bbsp/qossmartstatistics/qossmartstatistics.cus",
            "/html/bbsp/qossmartstatistics/GetQosStatisticsResult.asp",
        ],
        "reads": [
            {
                "path": "/html/bbsp/qossmartstatistics/GetQosStatisticsResult.asp",
                "method": "POST",
                "referer": "/html/bbsp/qossmartstatistics/qossmartstatistics.asp",
            },
        ],
    },
    "dscp_to_pbit": {
        "label": "DSCP to P-bit",
        "pages": ["/html/bbsp/dscptopbit/dscptopbit.asp"],
    },
    "remote_packet_mirror": {
        "label": "Remote packet mirror",
        "pages": ["/html/bbsp/remotepktmirror/remotepktmirror.asp"],
        "reads": [
            {
                "path": (
                    "/html/bbsp/remotepktmirror/getchunkedcapt.cgi?"
                    "RequestFile=html/bbsp/remotepktmirror/remotepktmirror.asp"
                ),
                "method": "POST",
                "referer": "/html/bbsp/remotepktmirror/remotepktmirror.asp",
                "token_page": "/html/bbsp/remotepktmirror/remotepktmirror.asp",
            },
        ],
    },
    "sntp": {
        "label": "SNTP",
        "pages": ["/html/ssmp/sntp/sntp.asp"],
    },
    "reboot": {
        "label": "Reboot",
        "pages": ["/html/ssmp/reboot/reboot.asp"],
    },
    "firmware": {
        "label": "Firmware upgrade",
        "pages": ["/html/ssmp/fireware/firmware.asp"],
    },
    "config_backup": {
        "label": "Configuration file",
        "pages": ["/html/ssmp/cfgfile/cfgfile.asp"],
    },
    "security_check": {
        "label": "Security Check",
        "pages": ["/html/ssmp/securitycheck/securitycheck.asp"],
        "reads": [
            {
                "path": "/html/ssmp/securitycheck/getSecCheckStatus.asp",
                "method": "POST",
                "referer": "/html/ssmp/securitycheck/securitycheck.asp",
            },
        ],
    },
    "led": {
        "label": "LED configuration",
        "pages": ["/html/ssmp/ledcfg/ledcfg.asp"],
    },
    "collect": {
        "label": "Support collection",
        "pages": ["/html/ssmp/collect/collectInfo.asp"],
        "reads": [
            {
                "path": "/html/ssmp/common/getCollectStatus.asp",
                "method": "POST",
                "referer": "/html/ssmp/collect/collectInfo.asp",
            },
        ],
    },
    "speed_test": {
        "label": "Section speed test / iPerf",
        "pages": [
            "/html/ssmp/testspeed/testspeed.asp",
            "/html/ssmp/Sectionspeed/Sectionspeed.asp",
            "/html/ssmp/Sectionspeed/clientspeedResult.asp",
        ],
        "reads": [
            {
                "path": "/html/ssmp/Sectionspeed/clientspeedResult.asp",
                "method": "POST",
                "referer": "/html/ssmp/Sectionspeed/Sectionspeed.asp",
            },
        ],
    },
    "diagnostics_webui": {
        "label": "WebUI diagnostics",
        "pages": [
            "/html/bbsp/maintenance/diagnosecommon.asp",
            "/html/ssmp/maintain/smartdiagnose.asp",
            "/html/ssmp/maintain/multicast.asp",
        ],
        "reads": [
            {
                "path": "/html/bbsp/maintenance/GetPingDnsResult.asp",
                "method": "POST",
                "referer": "/html/bbsp/maintenance/diagnosecommon.asp",
            },
            {
                "path": "/html/bbsp/maintenance/GetPingResult.asp",
                "method": "POST",
                "referer": "/html/bbsp/maintenance/diagnosecommon.asp",
            },
            {
                "path": "/html/bbsp/maintenance/GetRouteResult.asp",
                "method": "POST",
                "referer": "/html/bbsp/maintenance/diagnosecommon.asp",
            },
            {
                "path": "/html/bbsp/maintenance/getEquipTestResultsmart.asp",
                "method": "POST",
                "referer": "/html/ssmp/maintain/smartdiagnose.asp",
            },
            {
                "path": "/html/amp/common/getSmartDiagnoseResult.asp",
                "method": "POST",
                "referer": "/html/ssmp/maintain/smartdiagnose.asp",
                "token_page": "/html/ssmp/maintain/smartdiagnose.asp",
            },
            {
                "path": "/html/bbsp/common/EquipTestResultsmart.asp",
                "method": "POST",
                "referer": "/html/ssmp/maintain/smartdiagnose.asp",
            },
        ],
    },
    "support_config": {
        "label": "Maintenance support configuration",
        "pages": ["/html/ssmp/mainupportcfg/mainupportconfig.asp"],
        "reads": [
            {
                "path": "/html/ssmp/mainupportcfg/getForbidLanFlag.asp",
                "method": "POST",
                "referer": "/html/ssmp/mainupportcfg/mainupportconfig.asp",
            },
        ],
    },
    "software_notice": {
        "label": "Software notice",
        "pages": ["/html/ssmp/softnotice/opensfnotice.asp"],
    },
    "account": {
        "label": "Account configuration",
        "pages": ["/html/ssmp/accoutcfg/accountadmin.asp"],
    },
    "logs": {
        "label": "Device logs",
        "pages": [
            "/html/ssmp/aplog/aplog.asp",
            "/html/ssmp/aplog/aplogview.asp",
            "/html/ssmp/debuglog/debuglog.asp",
            "/html/ssmp/debuglog/debuglogview.asp",
            "/html/ssmp/instrusionlog/instrusionlog.asp",
            "/html/ssmp/userlog/userlog.asp",
            "/html/ssmp/userlog/logview.asp",
        ],
    },
    "mirror_port": {
        "label": "Mirror port",
        "pages": ["/html/ssmp/mirrorportcfg/mirrorportconfig.asp"],
        "reads": [
            {
                "path": (
                    "/html/ssmp/mirrorportcfg/getmirrorport.cgi?"
                    "&RequestFile=/html/ssmp/mirrorportcfg/mirrorportconfig.asp"
                ),
                "method": "POST",
                "payload": {"MirrorPortGet": "0"},
                "referer": "/html/ssmp/mirrorportcfg/mirrorportconfig.asp",
            },
        ],
    },
    "voip_interface": {
        "label": "VoIP interface",
        "pages": ["/html/voip/voipinterface/voipinterface.asp"],
        "reads": [
            {
                "path": "/html/voip/voipinterface/voiceprofileinfoSIP.asp",
                "method": "POST",
                "referer": "/html/voip/voipinterface/voipinterface.asp",
            },
            {
                "path": "/html/voip/voipinterface/voiceprofileinfoH248.asp",
                "method": "POST",
                "referer": "/html/voip/voipinterface/voipinterface.asp",
            },
        ],
    },
}


# Mutations explicitly present in the supplied capture. Typed writers for the
# 21 lab cases are still preferred; these definitions expose the additional
# mapped writes and provide a common executor for every captured relative
# endpoint without inventing a different protocol.
HUAWEI_MAPPED_WRITES: dict[str, dict[str, Any]] = {
    "port_isolation": {
        "path": (
            "/html/bbsp/portinfo/set.cgi?"
            "&RequestFile=html/bbsp/portinfo/portisolate.asp"
        ),
        "referer": "/html/bbsp/portinfo/portisolate.asp",
        "token_page": "/html/bbsp/portinfo/portisolate.asp",
        "fields": (),
    },
    "dscp_to_pbit": {
        "path": (
            "/html/bbsp/dscptopbit/setajax.cgi?"
            "x=InternetGatewayDevice.QueueManagement."
            "X_HW_DscpToPbitMappingTable.1&"
            "RequestFile=html/bbsp/dscptopbit/dscptopbit.asp"
        ),
        "referer": "/html/bbsp/dscptopbit/dscptopbit.asp",
        "token_page": "/html/bbsp/dscptopbit/dscptopbit.asp",
        "fields": ("x.DscpToPbitMapping", "x.DefaultPbit"),
    },
    "speed_test": {
        "path": (
            "/html/ssmp/Sectionspeed/setajax.cgi?"
            "x=InternetGatewayDevice.X_HW_DataModel."
            "X_HW_IperfSpeedTest.IperfClient&"
            "RequestFile=html/ssmp/Sectionspeed/clientspeedResult.asp"
        ),
        "referer": "/html/ssmp/Sectionspeed/Sectionspeed.asp",
        "token_page": "/html/ssmp/Sectionspeed/Sectionspeed.asp",
        "fields": (
            "x.DiagnosticsState", "x.ServerAddr", "x.DestMac",
            "x.Bandwidth", "x.TestMode", "x.Port",
            "x.ProtocolType", "x.MaxTime", "x.Parallel",
        ),
    },
    "speed_test_mode": {
        "path": (
            "/html/ssmp/Sectionspeed/setselspeedmode.cgi?"
            "&RequestFile=html/ssmp/Sectionspeed/clientspeedResult.asp"
        ),
        "referer": "/html/ssmp/Sectionspeed/Sectionspeed.asp",
        "token_page": "/html/ssmp/Sectionspeed/Sectionspeed.asp",
        "fields": ("Speedscenes", "Sectionstatus"),
    },
    "diagnostics_prepare": {
        "path": (
            "/html/ssmp/maintain/HWDiagnoseOpt.cgi?"
            "&RequestFile=/html/ssmp/maintain/smartdiagnose.asp"
        ),
        "referer": "/html/ssmp/maintain/smartdiagnose.asp",
        "token_page": "/html/ssmp/maintain/smartdiagnose.asp",
        "fields": (),
    },
    "diagnostics_port_check": {
        "path": (
            "/html/ssmp/maintain/complexajax.cgi?"
            "x=InternetGatewayDevice.X_HW_DEBUG.BBSP.ExtendPortTransCheck&"
            "RUNSTATE_FLAG=EquipTest&"
            "RequestFile=/html/ssmp/maintain/smartdiagnose.asp"
        ),
        "referer": "/html/ssmp/maintain/smartdiagnose.asp",
        "token_page": "/html/ssmp/maintain/smartdiagnose.asp",
        "fields": ("x.portid", "RUNSTATE_FLAG.value"),
    },
    "diagnostics_run": {
        "path": "/html/ssmp/maintain/complex.cgi?RUNSTATE_FLAG=EquipTest",
        "referer": "/html/ssmp/maintain/smartdiagnose.asp",
        "token_page": "/html/ssmp/maintain/smartdiagnose.asp",
        "fields": ("RUNSTATE_FLAG.value",),
    },
    "user_devices": {
        "path": (
            "/html/bbsp/userdevinfo/setajax.cgi?"
            "x=InternetGatewayDevice.X_HW_FeatureList."
            "BBSPCustomization.UserDevInfo&RequestFile=nopage"
        ),
        "referer": "/html/bbsp/userdevinfo/userdevinfo1.asp",
        "token_page": "/html/bbsp/userdevinfo/userdevinfo1.asp",
        "fields": ("x.State",),
    },
    "wan_config": {
        "path": (
            "/html/bbsp/wan/complex.cgi?"
            "y=InternetGatewayDevice.WANDevice.1.WANConnectionDevice.1."
            "WANPPPConnection.1&"
            "n=InternetGatewayDevice.WANDevice.1.WANConnectionDevice.1."
            "WANPPPConnection.1.X_HW_IPv6.IPv6Prefix.1&"
            "m=InternetGatewayDevice.WANDevice.1.WANConnectionDevice.1."
            "WANPPPConnection.1.X_HW_IPv6.IPv6Address.1&"
            "RequestFile=html/bbsp/wan/confirmwancfginfo.html"
        ),
        "referer": "/html/bbsp/wan/wan.asp",
        "token_page": "/html/bbsp/wan/wan.asp",
        "fields": (
            "y.X_HW_IPv4Enable", "y.X_HW_IPv6Enable",
            "y.X_HW_IPv6MultiCastVLAN", "y.X_HW_SERVICELIST",
            "y.X_HW_ExServiceList", "y.X_HW_VLAN", "y.X_HW_PRI",
            "y.X_HW_PriPolicy", "y.X_HW_DefaultPri",
            "y.X_HW_MultiCastVLAN", "y.NATEnabled", "y.X_HW_NatType",
            "y.X_HW_BridgeEnable", "y.X_HW_LcpEchoReqCheck",
            "y.DNSEnabled", "y.MaxMRUSize", "y.X_HW_BindPhyPortInfo",
            "y.X_HW_NPTv6Enable", "m.Alias", "m.Origin", "m.IPAddress",
            "m.ChildPrefixBits", "m.AddrMaskLen", "m.DefaultGateway",
            "n.Alias", "n.Origin", "n.Prefix", "X_HW_OverrideAllowed",
            "y.Enable", "y.ConnectionType", "y.Username", "y.Password",
        ),
    },
}


HUAWEI_FEATURE_WRITE_OPERATIONS: dict[str, tuple[str, ...]] = {
    "port_isolation": ("port_isolation",),
    "dscp_to_pbit": ("dscp_to_pbit",),
    "speed_test": ("speed_test", "speed_test_mode"),
    "diagnostics_webui": (
        "diagnostics_prepare",
        "diagnostics_port_check",
        "diagnostics_run",
    ),
    "user_devices": ("user_devices",),
    "wan_config": ("wan_config",),
}


_WRITE_OPERATION_LABELS = {
    "port_isolation": "Aplicar isolamento de portas",
    "dscp_to_pbit": "Configurar DSCP para P-bit",
    "speed_test": "Executar teste de velocidade",
    "speed_test_mode": "Selecionar modo do teste",
    "diagnostics_prepare": "Preparar diagnóstico",
    "diagnostics_port_check": "Testar porta",
    "diagnostics_run": "Executar/encerrar diagnóstico",
    "user_devices": "Atualizar inventário de dispositivos",
    "wan_config": "Atualizar conexão WAN",
}


_WRITE_FIELD_LABELS = {
    "x.DscpToPbitMapping": "Mapeamento DSCP → P-bit",
    "x.DefaultPbit": "P-bit padrão",
    "x.DiagnosticsState": "Estado do teste",
    "x.ServerAddr": "Servidor de teste",
    "x.DestMac": "MAC de destino",
    "x.Bandwidth": "Largura de banda",
    "x.TestMode": "Direção do teste",
    "x.Port": "Porta",
    "x.ProtocolType": "Protocolo",
    "x.MaxTime": "Tempo máximo (s)",
    "x.Parallel": "Fluxos paralelos",
    "Speedscenes": "Cenário de velocidade",
    "Sectionstatus": "Estado da seção",
    "x.portid": "Identificador da porta",
    "RUNSTATE_FLAG.value": "Ação do diagnóstico",
    "x.State": "Estado do inventário",
    "y.X_HW_IPv4Enable": "IPv4 habilitado",
    "y.X_HW_IPv6Enable": "IPv6 habilitado",
    "y.X_HW_IPv6MultiCastVLAN": "VLAN multicast IPv6",
    "y.X_HW_SERVICELIST": "Serviços",
    "y.X_HW_ExServiceList": "Serviços adicionais",
    "y.X_HW_VLAN": "VLAN",
    "y.X_HW_PRI": "Prioridade 802.1p",
    "y.X_HW_PriPolicy": "Política de prioridade",
    "y.X_HW_DefaultPri": "Prioridade padrão",
    "y.X_HW_MultiCastVLAN": "VLAN multicast IPv4",
    "y.NATEnabled": "NAT habilitado",
    "y.X_HW_NatType": "Tipo de NAT",
    "y.X_HW_BridgeEnable": "Bridge habilitado",
    "y.X_HW_LcpEchoReqCheck": "Verificação LCP Echo",
    "y.DNSEnabled": "DNS habilitado",
    "y.MaxMRUSize": "MRU máximo",
    "y.X_HW_BindPhyPortInfo": "Vínculo de portas físicas",
    "y.X_HW_NPTv6Enable": "NPTv6 habilitado",
    "m.Alias": "Alias IPv6",
    "m.Origin": "Origem do endereço IPv6",
    "m.IPAddress": "Endereço IPv6",
    "m.ChildPrefixBits": "Bits de prefixo filho",
    "m.AddrMaskLen": "Tamanho da máscara IPv6",
    "m.DefaultGateway": "Gateway IPv6",
    "n.Alias": "Alias do prefixo",
    "n.Origin": "Origem do prefixo",
    "n.Prefix": "Prefixo IPv6",
    "X_HW_OverrideAllowed": "Permitir sobrescrita",
    "y.Enable": "Conexão habilitada",
    "y.ConnectionType": "Tipo de conexão",
    "y.Username": "Usuário PPPoE",
    "y.Password": "Senha PPPoE",
}


_WRITE_DEFAULTS = {
    "x.DscpToPbitMapping": "",
    "x.DefaultPbit": "0",
    "x.DiagnosticsState": "requested",
    "x.ServerAddr": "",
    "x.DestMac": "",
    "x.Bandwidth": "0",
    "x.TestMode": "UPLOAD",
    "x.Port": "5201",
    "x.ProtocolType": "TCP",
    "x.MaxTime": "10",
    "x.Parallel": "1",
    "Speedscenes": "1",
    "Sectionstatus": "0",
    "x.portid": "",
    "RUNSTATE_FLAG.value": "START",
    "x.State": "Creating",
}


_SESSION_SECRET_KEYS = frozenset({
    "x_hw_token", "hwonttoken", "onttoken", "cookie", "cookiehttp",
    "authorization",
})

_SECRET_KEYS = frozenset({
    *_SESSION_SECRET_KEYS,
    "password", "passwd", "passphrase", "secret",
    "credential", "presharedkey", "pre_shared_key", "psk",
    "keypassphrase", "acs_password", "pppoe_password",
})


def _relative_path(path: object) -> str:
    value = str(path or "").strip()
    if not value:
        raise ValueError("Informe o endpoint Huawei.")
    split = urlsplit(value)
    if split.scheme or split.netloc:
        raise ValueError(
            "O endpoint Huawei deve ser relativo à ONT conectada."
        )
    if not value.startswith("/"):
        value = "/" + value
    if "\x00" in value or ".." in split.path.split("/"):
        raise ValueError("Endpoint Huawei inválido.")
    return value


def _secret_key(key: object) -> bool:
    normalized = re.sub(r"[^a-z0-9]+", "_", str(key).casefold()).strip("_")
    compact = normalized.replace("_", "")
    if normalized in _SECRET_KEYS:
        return True
    return (
        compact.endswith("token")
        or compact.endswith("cookie")
        or compact.endswith("password")
        or compact.endswith("passwd")
        or compact.endswith("passphrase")
        or compact.endswith("secret")
        or compact.endswith("credential")
        or "presharedkey" in compact
        or compact.endswith("psk")
        or compact == "authorization"
    )


def _session_secret_key(key: object) -> bool:
    normalized = re.sub(r"[^a-z0-9]+", "_", str(key).casefold()).strip("_")
    compact = normalized.replace("_", "")
    return (
        normalized in _SESSION_SECRET_KEYS
        or compact.endswith("token")
        or compact.endswith("cookie")
        or compact == "authorization"
    )


def _safe_value(value):
    if isinstance(value, dict):
        return {
            str(key): _safe_value(item)
            for key, item in value.items()
            if not _secret_key(key)
        }
    if isinstance(value, (list, tuple)):
        return [_safe_value(item) for item in value]
    return deepcopy(value)


def _input_values(source: str) -> dict[str, str]:
    values: dict[str, str] = {}
    for match in re.finditer(
        r"<input\b[^>]*\b(?:name|id)=[\"']([^\"']+)[\"'][^>]*>",
        source or "",
        re.I | re.S,
    ):
        tag = match.group(0)
        key = match.group(1)
        value_match = re.search(
            r"\bvalue=[\"']([^\"']*)[\"']",
            tag,
            re.I | re.S,
        )
        if value_match and not _secret_key(key):
            values[key] = value_match.group(1)
    return values


class HuaweiMappedSurfaceService:
    """Complete mapped WebUI bridge for the authenticated Huawei session.

    It intentionally does not gate features by model/profile. The only hard
    boundary is that requests stay relative to the already connected Huawei
    host. Mutations are submitted once and never replayed after an auth loss.
    """

    def __init__(self, client: HuaweiWebClient, *, model: str | None = None):
        self.client = client
        self.model = model or ""

    @staticmethod
    def catalog() -> dict[str, Any]:
        features = []
        for key, spec in HUAWEI_MAPPED_FEATURES.items():
            writes = list(
                HUAWEI_FEATURE_WRITE_OPERATIONS.get(key, ())
            )
            features.append({
                "key": key,
                "label": spec["label"],
                "read": True,
                "write": bool(writes),
                "mapped_writes": writes,
                "page_count": len(spec.get("pages") or ()),
                "read_request_count": len(spec.get("reads") or ()),
            })
        return {
            "vendor": "huawei",
            "features": features,
            "raw_relative_requests": {
                "read": True,
                "write": True,
            },
        }

    @staticmethod
    def write_schema(feature: str) -> dict[str, Any]:
        key = str(feature or "").strip()
        operations = []
        for operation in HUAWEI_FEATURE_WRITE_OPERATIONS.get(key, ()):
            spec = HUAWEI_MAPPED_WRITES[operation]
            fields = []
            for field in spec.get("fields") or ():
                fields.append({
                    "key": field,
                    "label": _WRITE_FIELD_LABELS.get(
                        field,
                        re.sub(r"^[a-z]\.", "", field).replace("_", " "),
                    ),
                    "default": _WRITE_DEFAULTS.get(field, ""),
                    "secret": "password" in field.casefold(),
                })
            operations.append({
                "key": operation,
                "label": _WRITE_OPERATION_LABELS.get(
                    operation,
                    operation.replace("_", " ").title(),
                ),
                "fields": fields,
            })
        return {
            "available": bool(operations),
            "operations": operations,
        }

    def _normalize_page(self, path: str, source: str) -> dict[str, Any]:
        records = []
        for parsed in parse_huawei_js_records(source):
            # _args can repeat constructor values positionally and would
            # bypass key-based secret filtering. Constructor names are an
            # internal parser detail and are not useful to the operator.
            public = {
                str(key): value
                for key, value in parsed.items()
                if not str(key).startswith("_")
                and not _secret_key(key)
            }
            records.append(_safe_value(public))
        return {
            "path": path,
            "records": records,
            "inputs": _input_values(source),
            "record_count": len(records),
        }

    def read_request(
        self,
        path: str,
        *,
        method: str = "GET",
        payload: dict[str, Any] | None = None,
        referer: str = "/index.asp",
        token_page: str | None = None,
    ) -> dict[str, Any]:
        relative = _relative_path(path)
        verb = str(method or "GET").upper()
        clean_payload = {
            str(key): str(value)
            for key, value in dict(payload or {}).items()
            if not _session_secret_key(key)
        }
        if token_page:
            token_source = self.client.get_page(
                _relative_path(token_page)
            )
            clean_payload["x.X_HW_Token"] = (
                self.client.extract_token(token_source)
            )
        if verb == "GET":
            source = self.client.get_page(relative)
        elif verb == "POST":
            source = self.client.post_read(
                relative,
                clean_payload,
                referer=_relative_path(referer),
            )
        else:
            raise ValueError("Leitura Huawei aceita GET ou POST.")
        return {
            "success": True,
            "method": verb,
            "data": self._normalize_page(relative, source),
        }

    def read_feature(self, feature: str) -> dict[str, Any]:
        key = str(feature or "").strip()
        spec = HUAWEI_MAPPED_FEATURES.get(key)
        if not spec:
            raise ValueError(f"Funcionalidade Huawei mapeada desconhecida: {key}.")
        pages = []
        errors = []
        for path in spec.get("pages") or ():
            try:
                pages.append(
                    self.read_request(path)["data"]
                )
            except Exception as exc:
                errors.append({
                    "path": path,
                    "method": "GET",
                    "error": type(exc).__name__,
                })
        for request in spec.get("reads") or ():
            try:
                pages.append(
                    self.read_request(
                        request["path"],
                        method=request.get("method") or "POST",
                        payload=request.get("payload") or {},
                        referer=request.get("referer") or "/index.asp",
                        token_page=request.get("token_page"),
                    )["data"]
                )
            except Exception as exc:
                errors.append({
                    "path": request.get("path") or "",
                    "method": request.get("method") or "POST",
                    "error": type(exc).__name__,
                })
        return {
            "feature": key,
            "label": spec["label"],
            "available": bool(pages),
            "partial": bool(errors),
            "pages": pages,
            "errors": errors,
        }

    def write_request(
        self,
        path: str,
        payload: dict[str, Any] | None = None,
        *,
        referer: str = "/index.asp",
        token_page: str | None = None,
        readback_path: str | None = None,
        readback_method: str = "GET",
        readback_payload: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        relative = _relative_path(path)
        referer_path = _relative_path(referer)
        token_source = self.client.get_page(
            _relative_path(token_page or referer_path)
        )
        token = self.client.extract_token(token_source)

        form = {
            str(key): str(value)
            for key, value in dict(payload or {}).items()
            if not _session_secret_key(key)
        }
        form["x.X_HW_Token"] = token

        transport = self.client.post_form(
            relative,
            form,
            referer=referer_path,
        )
        result: dict[str, Any] = {
            "success": bool(
                transport.http_status is not None
                and 200 <= transport.http_status < 400
                and not transport.connection_uncertain
            ),
            "submitted": True,
            "http_status": transport.http_status,
            "timed_out": transport.timed_out,
            "connection_uncertain": transport.connection_uncertain,
            "verified": False,
            "uncertain": bool(
                transport.timed_out
                or transport.connection_uncertain
                or transport.http_status is None
            ),
        }

        if readback_path:
            try:
                readback = self.read_request(
                    readback_path,
                    method=readback_method,
                    payload=readback_payload,
                    referer=referer_path,
                )
                result["readback"] = readback["data"]
                result["verified"] = True
                result["success"] = True
                result["uncertain"] = False
            except Exception as exc:
                result["readback_error"] = type(exc).__name__

        return result

    def write_feature(
        self,
        operation: str,
        config: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        key = str(operation or "").strip()
        spec = HUAWEI_MAPPED_WRITES.get(key)
        if not spec:
            raise ValueError(
                f"Mutation Huawei mapeada desconhecida: {key}."
            )
        values = dict(config or {})
        fields = tuple(spec.get("fields") or ())
        payload = {
            field: values[field]
            for field in fields
            if field in values
        }
        readback_feature = {
            "speed_test_mode": "speed_test",
            "diagnostics_prepare": "diagnostics_webui",
            "diagnostics_port_check": "diagnostics_webui",
            "diagnostics_run": "diagnostics_webui",
        }.get(key, key)
        result = self.write_request(
            spec["path"],
            payload,
            referer=spec["referer"],
            token_page=spec["token_page"],
            readback_path=(
                HUAWEI_MAPPED_FEATURES.get(
                    readback_feature,
                    {},
                ).get("pages") or [None]
            )[0],
        )
        result["operation"] = key
        return result

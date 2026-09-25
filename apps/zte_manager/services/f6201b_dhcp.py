"""DHCP read model and captured-form integration for authenticated F6201B."""
from __future__ import annotations

from apps.zte_manager.services.f6201b_evidence import CAPTURED_GET_VIEWS


BASIC = "Localnet_LanMgrIpv4_DHCPBasicCfg_lua.lua"
LEASE = "Localnet_LanMgrIpv4_DHCPHostInfo_lua.lua"
IPV6 = "dhcp6s_dhcpserver_lua.lua"

UPDATE_MAPPING = {
    "enabled": "ServerEnable",
    "min_address": "MinAddress",
    "max_address": "MaxAddress",
    "dns_source": "DnsServerSource",
    "dns1": "DNSServer1",
    "dns2": "DNSServer2",
    "lease_time": "LeaseTime",
    "gateway": "IPRouters",
}


def _rows(zte, view, tag, root):
    zte.get_view(view, Menu3Location=0)
    raw = zte.get_menu(tag)
    zte._validar_resposta(raw)
    return zte._parse_instances(raw).get(root, [])


def status(zte):
    # Each read is isolated so unsupported optional firmware features do
    # not hide the main DHCP control or falsely claim leases are live hosts.
    basic = _rows(zte, CAPTURED_GET_VIEWS[BASIC], BASIC,
                  "OBJ_Br0AndDhcpsHosCfg_ID")
    if len(basic) != 1:
        raise RuntimeError(
            "A ONT não informou uma configuração única de servidor DHCP."
        )
    result = {
        "basic": basic[0],
        "leases": [], "reservations": [], "lan_dns": {},
        "capabilities": {
            "server_write": True, "gateway_write": True,
            "lease_read": False,
            "reservation_write": False, "ipv6_read": False,
            "ipv6_write": False,
        },
        "warnings": [],
    }
    try:
        leases = _rows(zte, "lanMgrIpv4", LEASE, "OBJ_DHCPHOSTINFO_ID")
        result["leases"] = leases
        result["capabilities"]["lease_read"] = True
    except (RuntimeError, ValueError, KeyError) as exc:
        result["warnings"].append("Concessões DHCP: " + str(exc))
    try:
        ipv6 = _rows(zte, CAPTURED_GET_VIEWS[IPV6], IPV6,
                     "OBJ_DHCP6S_ID")
        result["ipv6"] = ipv6
        result["capabilities"]["ipv6_read"] = bool(ipv6)
        # IPv6 writes exist as a separate dedicated captured form; its
        # required conditional fields must be checked before POST.
        result["capabilities"]["ipv6_write"] = bool(ipv6)
    except (RuntimeError, ValueError, KeyError) as exc:
        result["warnings"].append("DHCP IPv6: " + str(exc))
    return result


def change(workbench, zte, *, config, host, revision, attendant,
           original_post):
    if not isinstance(config, dict) or not config:
        raise ValueError("Informe pelo menos uma alteração DHCP.")
    if set(config) - set(UPDATE_MAPPING):
        raise ValueError(
            "O firmware não expôs os campos DHCP solicitados: " +
            ", ".join(sorted(set(config) - set(UPDATE_MAPPING)))
        )
    current = _rows(zte, CAPTURED_GET_VIEWS[BASIC], BASIC,
                    "OBJ_Br0AndDhcpsHosCfg_ID")
    if len(current) != 1 or not current[0].get("_InstID"):
        raise RuntimeError("Não foi possível selecionar o objeto DHCP real.")
    changes = {}
    for external, internal in UPDATE_MAPPING.items():
        if external not in config:
            continue
        value = config[external]
        if external == "enabled":
            if not isinstance(value, bool):
                raise ValueError("Ativar DHCP deve ser booleano.")
            value = "1" if value else "0"
        elif value is None:
            raise ValueError(external + " não pode ser nulo.")
        changes[internal] = str(value)
    return workbench.apply_changes(
        zte, host=host, revision=revision, attendant=attendant,
        tag=BASIC, instance_id=current[0]["_InstID"],
        changes=changes, original_post=original_post,
    )

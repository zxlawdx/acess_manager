"""DHCP read model and captured-form integration for authenticated F6201B."""
from __future__ import annotations
import xml.etree.ElementTree as ET

from apps.zte_manager.services.f6201b_evidence import CAPTURED_GET_VIEWS
from apps.zte_manager.model.zte_configuration import zte_security


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
    rows = zte._parse_instances(raw).get(root, [])
    if tag == BASIC:
        xml = ET.fromstring(raw)
        encrypted = {field.strip() for field in
                     (xml.findtext("encode") or "").split(",")
                     if field.strip()}
        fields = {"IPAddr", "MinAddress", "MaxAddress",
                  "DNSServer1", "DNSServer2"}
        if encrypted:
            if not fields.issubset(encrypted):
                raise RuntimeError(
                    "O GET DHCP não confirmou todos os campos AES esperados."
                )
            token = getattr(zte, "session_tmp_token", None)
            if not token:
                raise RuntimeError("O formulário DHCP não retornou token AES.")
            clean = []
            for original in rows:
                row = dict(original)
                for name in fields:
                    value = row.get(name) or ""
                    if value:
                        plain = zte_security.aes_decrypt_value(
                            value, token, token[::-1]
                        )
                        if plain == value:
                            raise RuntimeError(
                                "Falha na leitura do campo DHCP " + name
                            )
                        row[name] = plain
                clean.append(row)
            return clean
    return rows


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
            "server_write": False, "gateway_write": False,
            "lease_read": False,
            "reservation_write": False, "ipv6_read": False,
            "ipv6_write": False,
        },
        "warnings": [],
    }
    # Actual write availability depends on all captured fields in a live
    # menuView + XML, NOT on a hardcoded model or employee profile.
    try:
        from apps.zte_manager.services.f6201b_full_forms import (
            _load, _required_fields
        )
        forms = _load(zte, BASIC)
        ready = (
            len(forms) == 1 and
            forms[0].instance_id == basic[0].get("_InstID") and
            not _required_fields(BASIC, forms[0].values)
        )
        result["capabilities"]["server_write"] = bool(ready)
        result["capabilities"]["gateway_write"] = bool(
            ready and basic[0].get("IPRouters")
        )
        if not ready:
            result["warnings"].append(
                "A ONT não retornou o formulário completo para editar DHCP."
            )
    except (RuntimeError, KeyError, ValueError, ET.ParseError) as exc:
        result["warnings"].append(
            "Validação do formulário DHCP: " + str(exc)
        )

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
    # IPRouters was blank in the operator's captured Apply and absent
    # from its GET. Do not advertise or apply an unobservable gateway
    # write unless the authenticated firmware really returns the field.
    if "gateway" in config and not current[0].get("IPRouters"):
        raise ValueError(
            "A ONT não expôs a leitura do gateway DHCP; "
            "a alteração não pode ser verificada neste formulário."
        )
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

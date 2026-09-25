"""Per-form strategies for the fourteen remaining captured F6201B Apply routes.

All request schemas come from the operator's sanitized 209-event capture.
The adapter prepares a COMPLETE captured-order body from a *live* menuView,
XML menuData, and observable HTML form controls. Missing conditional fields
block Apply rather than being guessed. This is not a generic POST facility.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from html.parser import HTMLParser
import hashlib
import ipaddress
import json
import re
import secrets
import time
import xml.etree.ElementTree as ET

from apps.zte_manager.model.zte_configuration import zte_security
from apps.zte_manager.model.zte_configuration.zte_post import post_menu
from apps.zte_manager.services.f6201b_evidence import (
    CAPTURED_GET_VIEWS, CAPTURED_GET_ROOTS, GET_PARAMS, OBSERVED_APPLY_FIELDS,
)
from apps.zte_manager.services.f6201b_writes import (
    ExperimentalF6201BWrites, PREVIEW_TTL,
)

ID = "_InstID"
PASSWORDS = frozenset({"Password", "UserPassword", "ConnectionRequestPassword"})
PRIVATE = PASSWORDS | {"UserName", "ConnectionRequestUsername", "URL"}
NON_VALUES = {"IF_ACTION", "_sessionTOKEN", "encode"}
_BOOLEANS = {
    "Enable", "EnableUPnPIGD", "VlanEnable", "IsNAT", "BPDUEnable",
    "Autoneg", "TimerEnable", "RadioStatus", "IANAEnable",
    "IsPrefixAutoMode", "ManualDNSEnable", "ServerEnable",
    "AdvLinkMTUEnable", "AdvManagedFlag", "AdvOtherConfigFlag",
    "AllowDHCP6S", "AllowRA", "EnLegacyStaRoam",
    "PeriodicInformEnable", "SupportCertAuth", "RemoteUpgradeCertAuth",
}
_RSSI = {"RoamRssiLmt24G", "RoamRssiLmt5G"}


@dataclass(frozen=True)
class FormSpec:
    root: str
    editable: tuple[str, ...]
    dangerous: bool = True
    additional_roots: tuple[str, ...] = ()
    description: str = ""
    # Captured HTML sometimes carries fields that the XML object omits.
    # Do not substitute defaults unless independently defined by protocol.
    requires_page_fields: tuple[str, ...] = ()
    secrets: tuple[str, ...] = ()


_PORTS = tuple(
    item for index in range(12)
    for item in (f"AllowDHCP6S_{index}", f"AllowRA_{index}")
)
_POLICIES = tuple(f"ACLPolicy_{index}" for index in range(8))

FORM_SPECS: dict[str, FormSpec] = {
    "wlan_wps_lua.lua": FormSpec(
        "OBJ_WPS_ID", ("Enable", "WPSMode", "WPSChoose"),
        description="WPS por SSID com o vínculo confirmado na leitura atual.",
    ),
    "wan_internet_lua.lua": FormSpec(
        "ID_WAN_COMFIG",
        ("Enable", "WANCName", "ServList", "MTU", "linkMode",
         "TransType", "UserName", "Password", "AuthType", "ConnTrigger",
         "IpMode", "Addressingtype", "IsNAT", "IPv6AcquireMode",
         "Gua1", "Gua1PrefixLen", "Gateway6", "Pd", "PdLen",
         "Dns1v6", "Dns2v6", "Dns3v6", "IsPD", "IsSLAAC",
         "IsGUA", "IsPdAddr", "VlanEnable", "VLANID", "Priority"),
        secrets=("Password",),
        description="WAN/PPPoE: parâmetros condicionais preservados do formulário atual, credenciais recodificadas.",
    ),
    "route_routestaticipv4_lua.lua": FormSpec(
        "OBJ_ROUTESTATIC_ID",
        ("DestIP", "DestIPMask", "GWIP", "Type", "Enable", "Alias", "Interface"),
        requires_page_fields=("Type",),
        description="Edição de rota IPv4 existente; criação/exclusão não são presumidas pelo Apply observado.",
    ),
    "Localnet_LanMgrIpv4_DHCPBasicCfg_lua.lua": FormSpec(
        "OBJ_Br0AndDhcpsHosCfg_ID",
        ("ServerEnable", "MinAddress", "MaxAddress", "LeaseTime",
         "DNSServer1", "DNSServer2", "DnsServerSource", "DomainName"),
        additional_roots=("OBJ_LANDNS_ID",),
        description="DHCP IPv4: preserva IP/Submask LAN e todos os campos condicionais capturados.",
    ),
    "Localnet_LanDevDHCPSource_lua.lua": FormSpec(
        "OBJ_LANDEVDHCPSOURCE_ID", tuple(f"ProcFlag_{i}" for i in range(12)),
        description="DHCP Source: preserva integralmente o vetor de 12 instâncias.",
    ),
    "dhcp6s_dhcpserver_lua.lua": FormSpec(
        "OBJ_DHCP6S_ID",
        ("IANAEnable", "IsPrefixAutoMode", "Enable", "ManualDNSEnable",
         "DNSAddr1", "DNSAddr2", "DNSAddr3", "Ipv6DnsOrigin",
         "DnsRefreshTime"),
        additional_roots=("OBJ_LANDNS_ID", "OBJ_LANDNS6_ID"),
        description="DHCPv6: seleciona explicitamente a instância de DNS associada.",
    ),
    "ra_raservice_lua.lua": FormSpec(
        "OBJ_RAIS_ID",
        ("Enable", "AdvLinkMTUEnable", "S_AdvLinkMTU",
         "AdvPreferredRouterFlag", "MinRtrAdvInterval",
         "MaxRtrAdvInterval", "AdvManagedFlag", "AdvOtherConfigFlag",
         "PrefixMode"),
        description="Router Advertisement: preserva intervalo, prefixo e MTU sem inventar valores.",
    ),
    "radhcp6s_portctrl_lua.lua": FormSpec(
        "OBJ_IPV6BANPORT_ID", _PORTS,
        description="Política DHCPv6/RA por porta; vetor completo obrigatório.",
    ),
    "eth_interface_config_lua.lua": FormSpec(
        "OBJ_LAN_PORT_CONF_ID",
        ("Autoneg", "MaxBitRate", "DuplexMode", "ModType"),
        requires_page_fields=("ModType",),
        description="Configuração física LAN; exige o valor ModType observável no formulário atual.",
    ),
    "wlan_wlanbasiconoff_lua.lua": FormSpec(
        "OBJ_WLANTIMECFG_ID",
        ("RadioStatus", "TimerEnable", "TimeStartHour", "TimeStartMin",
         "TimeEndHour", "TimeEndMin", "RadioStatus_0", "RadioStatus_1"),
        additional_roots=("OBJ_WLANSETTING_ID",),
        description="Rádio e agendamento: conserva ambas as instâncias e o timer.",
    ),
    "wlan_macfilteraclpolicy_lua.lua": FormSpec(
        "OBJ_WLANSETTING_ID", _POLICIES,
        description="Políticas ACL Wi-Fi: serializa todas as posições do vetor capturado.",
    ),
    "Localnet_NetSphere_Mode_lua.lua": FormSpec(
        "OBJ_NETSPHERE_MAP_ID",
        ("Enable", "EnLegacyStaRoam", "RoamRssiLmt24G", "RoamRssiLmt5G"),
        additional_roots=("OBJ_MULTIAP_ROAM_ID", "OBJ_MAP_MASTER_ID"),
        description="NetSphere: preserva CurrentMode/CurrentEnable e confirmação original.",
    ),
    "tr069_remotemgr_lua.lua": FormSpec(
        "OBJ_MANAGESERVER_ID",
        ("DefaultWan", "URL", "UserName", "UserPassword",
         "ConnectionRequestUsername", "ConnectionRequestPassword",
         "PeriodicInformEnable", "PeriodicInformInterval",
         "SupportCertAuth", "select_CertID", "RemoteUpgradeCertAuth"),
        secrets=("UserPassword", "ConnectionRequestPassword"),
        description="ACS: senhas enviadas com sentinel de preservação ou AES/RSA por operação.",
    ),
    "firewall_dmz_lua.lua": FormSpec(
        "OBJ_FWDMZ_ID", ("Enable", "WANCViewName", "InternalClient"),
        description="DMZ: sub_TempMacAddr0…5 preservados somente se observados.",
    ),
}

assert len(FORM_SPECS) == 14


class LiveHtmlForm(HTMLParser):
    """Reads form values without executing firmware JavaScript or exposing HTML."""
    def __init__(self, expected: set[str]):
        super().__init__(convert_charrefs=True)
        self.expected = expected
        self.values: dict[str, str] = {}
        self._select: str | None = None
        self._selected: str | None = None
        self._first: str | None = None
        self._textarea: str | None = None
        self._buffer: list[str] = []

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        name = attrs.get("name") or attrs.get("id")
        if tag == "input" and name in self.expected:
            kind = attrs.get("type", "text").lower()
            if kind in {"button", "submit", "file"}:
                return
            if kind in {"checkbox", "radio"}:
                if "checked" in attrs:
                    self.values[name] = attrs.get("value", "1")
                elif kind == "checkbox":
                    self.values[name] = "0"
            else:
                self.values[name] = attrs.get("value", "")
        elif tag == "select" and name in self.expected:
            self._select, self._selected, self._first = name, None, None
        elif tag == "option" and self._select:
            value = attrs.get("value")
            if value is not None:
                if self._first is None:
                    self._first = value
                if "selected" in attrs:
                    self._selected = value
        elif tag == "textarea" and name in self.expected:
            self._textarea = name
            self._buffer = []

    def handle_data(self, data):
        if self._textarea:
            self._buffer.append(data)

    def handle_endtag(self, tag):
        if tag == "select" and self._select:
            value = self._selected if self._selected is not None else self._first
            if value is not None:
                self.values[self._select] = value
            self._select = self._selected = self._first = None
        if tag == "textarea" and self._textarea:
            self.values[self._textarea] = "".join(self._buffer)
            self._textarea = None


def _live_fields(raw: str, view_html: str, tag: str, zte):
    """Capture-order, exact-name read from current XML and current HTML."""
    root = ET.fromstring(raw)
    if root.tag != "ajax_response_xml_root" or root.findtext("IF_ERRORID") != "0":
        raise RuntimeError("GET não confirmou sucesso; confira a sessão.")
    objects = zte._parse_instances(raw)
    spec = FORM_SPECS[tag]
    rows = objects.get(spec.root, [])
    if not rows:
        raise RuntimeError("O firmware não retornou " + spec.root)
    names = set(OBSERVED_APPLY_FIELDS[tag])
    html = LiveHtmlForm(names)
    html.feed(view_html if isinstance(view_html, str) else "")
    html.close()
    # <encode> in menuData names the incoming AES-encrypted parameters.
    encode_fields: set[str] = set()
    for node in root.findall("encode"):
        encode_fields.update(part.strip() for part in
                             (node.text or "").split(",") if part.strip())
    return rows, objects, html.values, encode_fields


def _select(rows, instance_id):
    if not instance_id:
        if len(rows) != 1:
            raise ValueError("Selecione a instância para este Apply.")
        return rows[0], 0
    for index, row in enumerate(rows):
        if str(row.get(ID) or f"slot:{index}") == instance_id:
            return row, index
    raise ValueError("Instância não pertence à leitura atual.")


def _split_ipv4(value: str):
    try:
        address = ipaddress.IPv4Address(value)
    except ValueError:
        return None
    return str(address).split(".")


def _form_fields(tag: str, row: dict, index: int, rows: list,
                 objects: dict, html: dict) -> dict[str, str]:
    """Resolver implements ONLY captured equivalences, never unknown defaults."""
    schema = OBSERVED_APPLY_FIELDS[tag]
    merged = {k: str(v) for k, v in html.items() if k in schema}
    merged.update({k: str(v) for k, v in row.items() if k in schema})
    for key in schema:
        # The GET records for vector forms contain per-Instance fields, while
        # the original post uses corresponding indexed names. Zero-based,
        # exactly as the recorded form.
        indexed = re.fullmatch(r"(.+)_([0-9]+)", key)
        if indexed:
            base, number = indexed.group(1), int(indexed.group(2))
            # The radio schedule combines a timer object and two radio
            # instances. Do not read RadioStatus_i from the timer row.
            source_rows = (
                objects.get("OBJ_WLANSETTING_ID", [])
                if tag == "wlan_wlanbasiconoff_lua.lua" else rows
            )
            if number < len(source_rows) and base in source_rows[number]:
                merged[key] = str(source_rows[number][base])
                continue
        # A binding in a live XML Instance overrides hidden HTML defaults.
        if tag == "Localnet_LanMgrIpv4_DHCPBasicCfg_lua.lua" and (
                key == "IF_URL_HOST" and row.get("IPAddr")):
            merged[key] = str(row["IPAddr"])
            continue
        if tag == "wlan_wps_lua.lua" and key == "SSID_InstID" and row.get(ID):
            merged[key] = str(row[ID])
            continue
        if key == "_InstNum":
            expected = {
                "Localnet_LanDevDHCPSource_lua.lua": 12,
                "radhcp6s_portctrl_lua.lua": 12,
                "wlan_macfilteraclpolicy_lua.lua": 8,
            }.get(tag)
            if expected and len(rows) == expected:
                merged[key] = str(expected)
                continue
        if key in merged:
            continue
        if tag == "wlan_wps_lua.lua":
            if key == "SSID_InstID" and row.get(ID):
                merged[key] = str(row[ID])
            elif key == ID and row.get(ID):
                # Existing firmware WPS adapter uses -1 as the scope;
                # the actual SSID binding is carried by SSID_InstID.
                merged[key] = "-1"
            elif key == "WPSChoose" and row.get("WPSMode") == "0":
                merged[key] = "PBC" if row.get("Enable") == "1" else "Disabled"
        if key in merged:
            continue
        if tag == "Localnet_LanMgrIpv4_DHCPBasicCfg_lua.lua":
            if key == "IF_URL_HOST" and row.get("IPAddr"):
                merged[key] = str(row["IPAddr"])
            elif key == "DomainName":
                for item in objects.get("OBJ_LANDNS_ID", []):
                    if key in item:
                        merged[key] = str(item[key])
                        break
        if tag == "dhcp6s_dhcpserver_lua.lua" and key == "_InstID_DNS":
            candidates = [r for root in ("OBJ_LANDNS_ID", "OBJ_LANDNS6_ID")
                          for r in objects.get(root, []) if r.get(ID)]
            if len(candidates) == 1:
                merged[key] = str(candidates[0][ID])
        if tag == "ra_raservice_lua.lua" and key == "S_AdvLinkMTU":
            if "AdvLinkMTU" in row:
                merged[key] = str(row["AdvLinkMTU"])
        if tag == "Localnet_NetSphere_Mode_lua.lua":
            aliases = {"CurrentMode": "Mode", "CurrentEnable": "Enable"}
            alias = aliases.get(key)
            if alias in row:
                merged[key] = str(row[alias])
        if tag == "tr069_remotemgr_lua.lua" and key == "select_CertID":
            if "CertID" in row:
                merged[key] = str(row["CertID"])
        if tag == "firewall_dmz_lua.lua" and key.startswith("sub_TempMacAddr"):
            value = row.get("TempMacAddr") or row.get("MACAddr")
            if value and re.fullmatch(
                r"[0-9a-fA-F]{2}(?::[0-9a-fA-F]{2}){5}", str(value)
            ):
                octet = int(key[-1]) if key[-1].isdigit() else -1
                if 0 <= octet < 6:
                    merged[key] = str(value).split(":")[octet]
        if tag == "wan_internet_lua.lua":
            # The WAN Apply has four individual IPv4 octet inputs. Only
            # derive them when the GET returns a genuine IPv4 address.
            m = re.fullmatch(r"(IPAddress|SubnetMask|GateWay|DNS1|DNS2|DNS3)([0-3])", key)
            if m and m.group(1) in row:
                octets = _split_ipv4(str(row[m.group(1)]))
                if octets:
                    merged[key] = octets[int(m.group(2))]
        if key in merged:
            continue
        # These are schema/control metadata, not live configuration data.
        if key == "IF_ACTION":
            merged[key] = "Apply"
        elif key == ID and row.get(ID):
            merged[key] = str(row[ID])
        elif key == "_InstNum":
            # Device itself must expose instance count; derive ONLY when it
            # returned the complete row vector observed in the GET.
            if len(rows) == 12 and tag in {
                "Localnet_LanDevDHCPSource_lua.lua",
                "radhcp6s_portctrl_lua.lua",
            }:
                merged[key] = "12"
            elif len(rows) == 8 and tag == "wlan_macfilteraclpolicy_lua.lua":
                merged[key] = "8"
        elif key.startswith("Btn_"):
            merged[key] = ""
        elif key == "encode":
            # A new encode is constructed for WAN/ACS when re-encryption is
            # needed. Empty encode is the documented no-secret-change form.
            merged[key] = ""
    # IF_ACTION is always the captured Apply, never an HTML page's
    # unrelated default action left by an earlier form.
    merged["IF_ACTION"] = "Apply"
    # WPS _InstID is a special fixed scope irrespective of row _InstID.
    if tag == "wlan_wps_lua.lua":
        merged[ID] = "-1"
    return merged


def _validate_value(tag: str, key: str, value) -> str:
    if not isinstance(value, (str, int, float, bool)):
        raise ValueError("O valor de " + key + " deve ser escalar.")
    value = str(value)
    if len(value) > (256 if key in PASSWORDS else 255):
        raise ValueError(key + ": campo acima do tamanho máximo.")
    if key not in PASSWORDS and any(ord(c) < 32 for c in value):
        raise ValueError(key + ": contém caracteres de controle.")
    if key in PASSWORDS and any(ord(c) < 32 for c in value):
        raise ValueError("Senha contém caracteres de controle.")
    if (key in _BOOLEANS or key.startswith(("AllowRA_", "AllowDHCP6S_",
                                           "RadioStatus_", "ProcFlag_"))
            or key.startswith("Is") and key in OBSERVED_APPLY_FIELDS[tag]):
        if value not in {"0", "1"}:
            raise ValueError(key + " deve ser 0 ou 1.")
    if key in _RSSI:
        if not re.fullmatch(r"-?\d{1,3}", value) or not -120 <= int(value) <= 0:
            raise ValueError(key + ": RSSI fora de -120 a 0.")
    if key in {"MTU", "VLANID", "LeaseTime", "TimeStartHour", "TimeEndHour",
               "TimeStartMin", "TimeEndMin", "PeriodicInformInterval"}:
        if not value.isdecimal():
            raise ValueError(key + " exige número inteiro.")
    if key == "URL" and value and not value.startswith(("http://", "https://")):
        raise ValueError("ACS URL deve usar HTTP ou HTTPS.")
    if key in {"DestIP", "DestIPMask", "GWIP", "MinAddress", "MaxAddress",
               "DNSServer1", "DNSServer2", "InternalClient"} and value:
        if key == "InternalClient" and value == "0.0.0.0":
            return value
        try:
            ipaddress.IPv4Address(value)
        except ValueError:
            raise ValueError(key + " deve ser IPv4 válido.") from None
    return value


def _secrets_masked(spec: FormSpec, field_name: str, value: str) -> str:
    return "••••••" if field_name in PRIVATE and value else value


@dataclass
class LiveRecord:
    instance_id: str
    values: dict[str, str]
    secrets: set[str] = field(default_factory=set)
    encode_fields: set[str] = field(default_factory=set)
    # Passwords/credentials are never included in the UI or persisted history.


def _load(zte, tag: str) -> list[LiveRecord]:
    spec = FORM_SPECS[tag]
    view = CAPTURED_GET_VIEWS[tag]
    html = zte.get_view(view, Menu3Location=0)
    xml = zte.get_menu(tag, **GET_PARAMS.get(tag, {}))
    rows, objects, html_values, encoded = _live_fields(xml, html, tag, zte)
    out = []
    for index, row in enumerate(rows):
        # Never mix a stale page's selected WAN/rule/port with a different
        # instance returned by the firmware. Absent conditional inputs will
        # visibly block POST until a matching page context can be obtained.
        scoped = html_values
        if (tag in {
            "wan_internet_lua.lua", "route_routestaticipv4_lua.lua",
            "eth_interface_config_lua.lua",
        } and len(rows) > 1 and html_values.get(ID) not in {
            None, "", str(row.get(ID)),
        }):
            scoped = {}
        fields = _form_fields(tag, row, index, rows, objects, scoped)
        if tag == "tr069_remotemgr_lua.lua":
            for name in PASSWORDS & set(OBSERVED_APPLY_FIELDS[tag]):
                # Existing TR-069 implementation uses six tabs as the
                # browser's sentinel for preserving credentials unchanged.
                fields[name] = "\t" * 6
        elif tag == "wan_internet_lua.lua":
            if ("Password" in fields and "Password" not in encoded and
                    re.fullmatch(r"[*•#]{4,}", fields["Password"] or "")):
                raise RuntimeError(
                    "WAN apresentou senha mascarada; não é possível preservá-la."
                )
            token = getattr(zte, "session_tmp_token", None)
            if set(encoded) & {"UserName", "Password"} and not token:
                raise RuntimeError("WAN criptografada sem token de leitura.")
            for name in ("UserName", "Password"):
                if name in fields and name in encoded and fields[name]:
                    plain = zte_security.aes_decrypt_value(
                        fields[name], token, token[::-1]
                    )
                    # Strict: never post opaque ciphertext as plaintext.
                    if plain == fields[name]:
                        raise RuntimeError(
                            "Não foi possível preservar " + name + " criptografado."
                        )
                    fields[name] = plain
        ident = str(row.get(ID) or f"slot:{index}")
        out.append(LiveRecord(ident, fields, set(spec.secrets), encoded))
    return out


def _required_fields(tag: str, values: dict) -> list[str]:
    schema = OBSERVED_APPLY_FIELDS[tag]
    return [key for key in schema
            if key not in {"_sessionTOKEN"}
            and key not in values]


def _safe_fingerprint(values: dict[str, str], tag: str) -> str:
    """Protect the entire captured form, not just editable columns."""
    stable = {key: value for key, value in values.items()
              if key in OBSERVED_APPLY_FIELDS[tag] and
              key not in PASSWORDS and key != "encode"}
    return hashlib.sha256(json.dumps(
        stable, sort_keys=True, ensure_ascii=True
    ).encode("utf-8")).hexdigest()


def _assemble(tag: str, values: dict, changes: dict[str, str],
              encode: str = "") -> list[tuple[str, str]]:
    spec = FORM_SPECS[tag]
    if set(changes) - set(spec.editable):
        raise ValueError("Campo não autorizado neste formulário.")
    all_values = dict(values)
    all_values.update(changes)
    if "encode" in OBSERVED_APPLY_FIELDS[tag]:
        all_values["encode"] = encode
    missing = _required_fields(tag, all_values)
    if missing:
        raise ValueError("Formulário incompleto: " + ", ".join(missing))
    return [(name, all_values[name])
            for name in OBSERVED_APPLY_FIELDS[tag] if name != "_sessionTOKEN"]


def _encode_secrets(zte, tag: str, live: LiveRecord,
                    changes: dict[str, str]) -> tuple[dict, str]:
    values = dict(live.values)
    values.update(changes)
    if tag == "tr069_remotemgr_lua.lua":
        changed = [key for key in PASSWORDS if key in changes]
        if changed:
            if not getattr(zte, "public_key_pem", None):
                raise RuntimeError("A chave RSA do formulário ACS está ausente.")
            key = "".join(str(secrets.randbelow(10)) for _ in range(16))
            iv = "".join(str(secrets.randbelow(10)) for _ in range(16))
            for name in changed:
                values[name] = zte_security.aes_encrypt_value(
                    changes[name], key, iv
                )
            return values, zte_security.rsa_encrypt_text(
                f"{key}+{iv}", zte.public_key_pem
            )
        return values, ""
    if tag == "wan_internet_lua.lua":
        targets = [k for k in ("UserName", "Password")
                   if k in live.encode_fields and values.get(k)]
        # A captured WAN can have secret values that are not encrypted by
        # this firmware. In that case preserve the observed encoding choice.
        if targets:
            if not getattr(zte, "public_key_pem", None):
                raise RuntimeError("A chave RSA necessária à WAN não está disponível.")
            key = "".join(str(secrets.randbelow(10)) for _ in range(16))
            iv = "".join(str(secrets.randbelow(10)) for _ in range(16))
            for name in targets:
                values[name] = zte_security.aes_encrypt_value(values[name], key, iv)
            return values, zte_security.rsa_encrypt_text(
                f"{key}+{iv}", zte.public_key_pem
            )
    return values, ""


@dataclass
class Pending:
    nonce: str
    host: str
    revision: str
    attendant: str
    tag: str
    instance_id: str
    original_fingerprint: str
    changes: dict[str, str]
    created: float


class FullCapturedForms:
    """Command executor with one-use session-bound previews and DI clock."""
    def __init__(self, *, clock=time.monotonic, sleep=time.sleep):
        self._clock = clock
        self._sleep = sleep
        self._pending: Pending | None = None

    def clear(self):
        self._pending = None

    @staticmethod
    def _row(records: list[LiveRecord], instance_id: str):
        matched = [r for r in records if r.instance_id == instance_id]
        if len(matched) != 1:
            raise RuntimeError("Instância desapareceu após a prévia.")
        return matched[0]

    def inspect(self, zte, tag: str) -> dict:
        if tag not in FORM_SPECS:
            raise ValueError("Não existe Strategy para a rota.")
        records = _load(zte, tag)
        spec = FORM_SPECS[tag]
        return {
            "tag": tag, "available": True, "state": "supervised_lab",
            "instances": [
                {
                    "id": item.instance_id,
                    "current": {
                        key: _secrets_masked(spec, key, item.values[key])
                        for key in spec.editable if key in item.values
                    },
                    "secret_fields": list(spec.secrets),
                    "private_fields": sorted(set(spec.editable) & PRIVATE),
                    "missing": _required_fields(tag, item.values),
                    "ready": not _required_fields(tag, item.values),
                }
                for item in records
            ],
        }

    def preview(self, zte, *, tag: str, instance_id: str,
                changes: dict, host: str, revision: str, attendant: str) -> dict:
        self.clear()
        if not ExperimentalF6201BWrites.opted_in():
            raise PermissionError("Habilite ZTE_F6201B_EXPERIMENTAL_WRITES=1.")
        if tag not in FORM_SPECS:
            raise PermissionError("Não existe formulário capturado para esta rota.")
        if not isinstance(changes, dict) or not changes:
            raise ValueError("Selecione pelo menos uma alteração.")
        spec = FORM_SPECS[tag]
        if set(changes) - set(spec.editable):
            raise ValueError("Campo fora da lista do formulário selecionado.")
        clean = {name: _validate_value(tag, name, value)
                 for name, value in changes.items()}
        row = self._row(_load(zte, tag), instance_id)
        # Prove that all 25 captured keys (except server-supplied token) can
        # be obtained BEFORE storing a nonce. No partial arbitrary POST.
        _assemble(tag, row.values, {})
        changed = {
            k: v for k, v in clean.items()
            if k in PASSWORDS or str(row.values.get(k)) != v
        }
        if not changed:
            raise ValueError("Nenhuma diferença detectada.")
        # Dry-run using the captured schema, never echo raw payload.
        _assemble(tag, row.values, changed)
        nonce = secrets.token_urlsafe(24)
        self._pending = Pending(
            nonce, host, revision, attendant, tag, instance_id,
            _safe_fingerprint(row.values, tag), changed, self._clock()
        )
        return {
            "tag": tag, "instance_id": instance_id,
            "nonce": nonce, "expires_in_seconds": PREVIEW_TTL,
            "confirmation": "APLICAR ROTA F6201B", "risk_ack_required": True,
            "diff": {key: {
                "before": _secrets_masked(spec, key, row.values.get(key, "")),
                "after": _secrets_masked(spec, key, value) if key not in PRIVATE
                         else "•••• (alterado)",
            } for key, value in changed.items()},
            "note": "Operações sequenciais com releitura. Não reenviar POST ambíguo.",
        }

    def apply(self, zte, *, host: str, revision: str, attendant: str,
              nonce: str, confirmation: str, risk_ack: bool, original_post):
        p = self._pending
        self.clear()
        if not p or not secrets.compare_digest(p.nonce, str(nonce)):
            raise PermissionError("Prévia inválida ou já utilizada.")
        if not ExperimentalF6201BWrites.opted_in() or original_post is None:
            raise PermissionError("Transporte de laboratório não autorizado.")
        if confirmation != "APLICAR ROTA F6201B" or risk_ack is not True:
            raise PermissionError("Confirmação de risco obrigatória.")
        if (p.host != host or p.revision != revision or
                p.attendant != attendant or
                self._clock() - p.created > PREVIEW_TTL):
            raise PermissionError("Sessão/atendente mudou ou prévia expirou.")

        # All device actions below occur under ZTEService's RLock.
        live = self._row(_load(zte, p.tag), p.instance_id)
        if _safe_fingerprint(live.values, p.tag) != p.original_fingerprint:
            raise RuntimeError("A ONT mudou desde a prévia; gere outra.")
        fields, encode = _encode_secrets(zte, p.tag, live, p.changes)
        payload = _assemble(p.tag, fields, {}, encode=encode)
        # _load already invoked menuView immediately before menuData. Do not
        # open a different view between that GET and the captured Apply.
        blocked = zte.session.post
        previous = getattr(zte, "writes_enabled", False)
        try:
            zte.session.post = original_post
            zte.writes_enabled = True
            try:
                post_menu(zte, p.tag, payload, **GET_PARAMS.get(p.tag, {}))
            except Exception:
                # Network exception after sending cannot prove nonapplication.
                return {
                    "success": False, "uncertain": True,
                    "stage": "post_or_response", "tag": p.tag,
                    "detail": "Sem retry: confira o estado no painel da ONT.",
                }
        finally:
            zte.session.post = blocked
            zte.writes_enabled = previous

        expected = {k: v for k, v in p.changes.items() if k not in PASSWORDS}
        private = sorted(set(p.changes) & PASSWORDS)
        for _ in range(3):
            try:
                after = self._row(_load(zte, p.tag), p.instance_id)
                if all(after.values.get(k) == v for k, v in expected.items()):
                    return {
                        "success": True, "verified": not private,
                        "partial": bool(private), "tag": p.tag,
                        "verified_fields": sorted(expected),
                        "manual_verification_fields": private,
                        "detail": (
                            "Alterações verificadas por GET."
                            if not private else
                            "Campos legíveis conferidos. Confirme senhas "
                            "mediante autenticação funcional na ONT."
                        ),
                    }
            except (RuntimeError, OSError, ET.ParseError, ValueError):
                pass
            self._sleep(0.35)
        return {
            "success": False, "uncertain": True, "stage": "readback",
            "tag": p.tag, "detail": "Releitura não confirmou os valores esperados.",
        }

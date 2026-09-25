"""F6201B captured DNS Apply: opt-in, exact body, preview & read-back.

Both IPv4 and IPv6 DNS servers use the same captured server form; domain
and static hosts are separate forms handled by the expanded batch.
The user-provided capture included one successful DNS servers Apply with
the exact 7-field body. No raw capture data or customer values are stored.
"""
from __future__ import annotations

from dataclasses import dataclass
import ipaddress
import secrets
import time
import xml.etree.ElementTree as ET

from apps.zte_manager.model.zte_configuration.zte_post import post_menu
from apps.zte_manager.services.f6201b_writes import (
    ExperimentalF6201BWrites, EXACT_FIRMWARE, PREVIEW_TTL,
)
from apps.zte_manager.services.f6201b_evidence import OBSERVED_APPLY_FIELDS


@dataclass
class DNSSnapshot:
    nonce: str
    host: str
    instance_id: str
    previous: dict
    desired: dict
    created: float


def _read(zte):
    zte.get_view("dns", Menu3Location=0)
    xml = zte.get_menu("dns_localdns_lua.lua")
    zte._validar_resposta(xml)
    try:
        response = ET.fromstring(xml)
    except ET.ParseError:
        raise RuntimeError("Resposta DNS não é XML válido.") from None
    if (response.tag != "ajax_response_xml_root" or
            (response.findtext("IF_ERRORID") or "").strip() != "0"):
        raise RuntimeError("O firmware rejeitou a consulta DNS.")
    data = zte._parse_instances(xml).get("OBJ_DNS_ID", [])
    if len(data) != 1 or not data[0].get("_InstID"):
        raise RuntimeError("A ONT não expôs uma instância DNS inequívoca.")
    return data[0]


class ExperimentalF6201BDNS:
    def __init__(self):
        self._pending: DNSSnapshot | None = None

    def clear(self):
        self._pending = None

    @staticmethod
    def read(zte) -> dict:
        current = _read(zte)
        return {
            "ipv4_1": current.get("SerIPAddress1") or "",
            "ipv4_2": current.get("SerIPAddress2") or "",
            "ipv6_1": current.get("SerIPv6Address1") or "",
            "ipv6_2": current.get("SerIPv6Address2") or "",
        }

    def preview(self, zte, *, host, firmware, changes) -> dict:
        self.clear()
        if firmware != EXACT_FIRMWARE:
            raise PermissionError("DNS experimental não autorizado para este firmware.")
        allowed = {"ipv4_1", "ipv4_2", "ipv6_1", "ipv6_2"}
        if not isinstance(changes, dict) or not changes or set(changes) - allowed:
            raise ValueError("Somente servidores DNS IPv4/IPv6 são aceitos.")
        for key, value in changes.items():
            if not isinstance(value, str):
                raise ValueError("O endereço DNS deve ser uma string IPv4.")
            if key.startswith("ipv6"):
                if value.strip() in ("", "::"):
                    continue
                try:
                    ipaddress.IPv6Address(value.strip())
                except ipaddress.AddressValueError:
                    raise ValueError("Endereço IPv6 inválido.") from None
            else:
                if key == "ipv4_2" and value.strip() == "":
                    continue
                try:
                    ipaddress.IPv4Address(value.strip())
                except ipaddress.AddressValueError:
                    raise ValueError("Endereço IPv4 inválido.") from None
        current = _read(zte)
        before = {key: current.get(key, "") for key in (
            "SerIPAddress1", "SerIPAddress2",
            "SerIPv6Address1", "SerIPv6Address2"
        )}
        target = dict(before)
        for source, dest in (
            ("ipv4_1", "SerIPAddress1"),
            ("ipv4_2", "SerIPAddress2"),
            ("ipv6_1", "SerIPv6Address1"),
            ("ipv6_2", "SerIPv6Address2"),
        ):
            if source in changes:
                value = changes[source].strip()
                target[dest] = (value or "::") if source.startswith("ipv6") else value
        delta = {key: {"before": before[key], "after": target[key]}
                 for key in target if before[key] != target[key]}
        if not delta:
            raise ValueError("Nenhuma mudança de DNS encontrada.")
        nonce = secrets.token_urlsafe(24)
        self._pending = DNSSnapshot(
            nonce,host,current["_InstID"],before,target,time.monotonic()
        )
        return {
            "nonce": nonce, "expires_in_seconds": PREVIEW_TTL,
            "changes": delta, "operation": "dns_ipv4_ipv6", "model": "F6201B",
            "warning": "Alterar DNS pode afetar a conexão de clientes.",
        }

    def apply_changes(self, zte, *, host, firmware, changes,
                      original_post) -> dict:
        """One operator action; preflight and readback run on the same session."""
        try:
            proposal = self.preview(zte, host=host, firmware=firmware,
                                    changes=changes)
        except ValueError as exc:
            if "Nenhuma mudança" not in str(exc):
                raise
            return {"success": True, "verified": True, "noop": True,
                    "changed": []}
        return self.apply(
            zte, host=host, firmware=firmware, nonce=proposal["nonce"],
            confirmation="", original_post=original_post
        )

    def apply(self, zte, *, host, firmware, nonce, confirmation,
              original_post) -> dict:
        proposal = self._pending
        self.clear()
        if firmware != EXACT_FIRMWARE:
            raise PermissionError("DNS experimental bloqueado.")
        if not proposal or not secrets.compare_digest(
            proposal.nonce, str(nonce)
        ):
            raise PermissionError("Prévia de DNS inválida.")
        if proposal.host != host or time.monotonic()-proposal.created>PREVIEW_TTL:
            raise PermissionError("Prévia expirada ou equipamento alterado.")
        if original_post is None:
            raise PermissionError("Transporte de escrita não disponível.")
        current = _read(zte)
        if current["_InstID"] != proposal.instance_id or any(
            (current.get(key) or "") != (value or "")
            for key,value in proposal.previous.items()
        ):
            raise RuntimeError("DNS mudou após a prévia; não aplicar.")
        fields = {
            "IF_ACTION": "Apply", "_InstID": proposal.instance_id,
            **proposal.desired,
            "Btn_cancel_LocalDnsServer": "",
            "Btn_apply_LocalDnsServer": "",
        }
        schema = OBSERVED_APPLY_FIELDS["dns_localdns_lua.lua"]
        payload = [(key, fields[key]) for key in schema
                   if key != "_sessionTOKEN"]
        # A escrita só é liberada no escopo desta chamada. Nenhum fallback
        # nem POST repetido caso a resposta seja ambígua.
        original_block = zte.session.post
        previous_writes = getattr(zte, "writes_enabled", False)
        try:
            zte.get_view("dns", Menu3Location=0)
            zte.session.post = original_post
            zte.writes_enabled = True
            post_menu(zte, "dns_localdns_lua.lua", payload)
        finally:
            zte.session.post = original_block
            zte.writes_enabled = previous_writes
        # Não repetir POST se SUCC preceder propagação ao backend.
        observed = None
        for attempt in range(3):
            observed = _read(zte)
            if all((observed.get(key) or "") == (value or "")
                   for key,value in proposal.desired.items()):
                return {
                    "success": True, "verified": True,
                    "changed": sorted(
                        key for key in proposal.desired
                        if proposal.previous[key] != proposal.desired[key]
                    ),
                    "experimental": True,
                }
            if attempt < 2:
                time.sleep(0.35)
        raise RuntimeError(
            "DNS POST respondido, mas releitura não confirmou a mudança; "
            "confira a interface original antes de tentar novamente."
        )

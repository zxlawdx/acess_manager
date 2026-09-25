"""F6201B captured DNS Apply: opt-in, exact body, preview & read-back.

Only DNS IPv4 server addresses: no domain/host/WAN/ACS changes.
The user-provided capture included one successful DNS servers Apply with
the exact 7-field body. No raw capture data or customer values are stored.
"""
from __future__ import annotations

from dataclasses import dataclass
import ipaddress
import secrets
import time

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
        if firmware != EXACT_FIRMWARE or not ExperimentalF6201BWrites.opted_in():
            raise PermissionError("DNS experimental não autorizado para este firmware.")
        if not isinstance(changes, dict) or not changes or (
            set(changes) - {"ipv4_1", "ipv4_2"}
        ):
            raise ValueError("Somente servidores DNS IPv4 são aceitos.")
        for key, value in changes.items():
            if not isinstance(value, str):
                raise ValueError("O endereço DNS deve ser uma string IPv4.")
            if key == "ipv4_2" and value.strip() == "":
                continue  # servidor secundário opcional
            try:
                ipaddress.IPv4Address(value)
            except ipaddress.AddressValueError:
                raise ValueError("Endereço IPv4 inválido.") from None
        current = _read(zte)
        before = {key: current.get(key, "") for key in (
            "SerIPAddress1", "SerIPAddress2",
            "SerIPv6Address1", "SerIPv6Address2"
        )}
        target = dict(before)
        for source, dest in (("ipv4_1","SerIPAddress1"),
                             ("ipv4_2","SerIPAddress2")):
            if source in changes:
                target[dest] = changes[source].strip()
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
            "changes": delta, "operation": "dns_ipv4", "model": "F6201B",
            "warning": "Alterar DNS pode afetar a conexão de clientes.",
        }

    def apply(self, zte, *, host, firmware, nonce, confirmation,
              original_post) -> dict:
        proposal = self._pending
        self.clear()
        if firmware != EXACT_FIRMWARE or not ExperimentalF6201BWrites.opted_in():
            raise PermissionError("DNS experimental bloqueado.")
        if confirmation != "APLICAR DNS F6201B":
            raise PermissionError("Confirmação específica de DNS ausente.")
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

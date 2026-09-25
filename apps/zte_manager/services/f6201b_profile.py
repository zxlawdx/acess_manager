"""F6201B experimental profile: captured RF + DNS, with one preview.

This is NOT the generic F6600P profile command. Each changed radio uses
the exact captured F6201B advanced RF form, with a fresh menuView token
and current read-modify-write state. DNS delegates to the previously
captured guarded DNS adapter. There is no automatic rollback.
"""
from __future__ import annotations

from dataclasses import dataclass
import secrets
import time
import re
import xml.etree.ElementTree as ET

from apps.zte_manager.model.zte_configuration import (
    zte_wlan_channel_configuration as rf,
)
from apps.zte_manager.model.zte_configuration.zte_post import post_menu
from apps.zte_manager.model.zte_configuration import zte_dns
from apps.zte_manager.services.f6201b_evidence import (
    OBSERVED_APPLY_FIELDS, DNS_DOMAIN_APPLY_FIELDS,
)
from apps.zte_manager.services.f6201b_writes import (
    EXACT_FIRMWARE, PREVIEW_TTL, ExperimentalF6201BWrites,
)


RADIO_SCHEMA = OBSERVED_APPLY_FIELDS["wlan_wlanbasicadconf_lua.lua"]
RADIO_PROFILE_FIELDS = (
    "auto_channel", "channel", "standard", "country", "bandwidth",
    "sgi", "beacon_interval", "tx_power",
)
# Values are limited to the exact fields that the owner captured.
CAPTURED_RF_FIELDS = tuple(
    name for name in RADIO_SCHEMA
    if name not in {"IF_ACTION", "_InstID", "_sessionTOKEN"}
)

# V9.3.10P7N7 was physically homologated with AutoChRange serialized as
# "0". Some live menuData responses omit that hidden compatibility field,
# even though the Apply handler still expects it. Treat ONLY this captured,
# non-user-facing field as a firmware default; every other missing field
# continues to fail closed before any POST.
RF_CAPTURE_COMPAT_DEFAULTS = {
    "AutoChRange": "0",
}
SKIPPED_PROFILE_FEATURES = (
    "Senhas/SSIDs: editar e confirmar por rede na aba Wi-Fi",
    "Outras opções da ONT fora do perfil do atendente",
)


@dataclass
class BatchPreview:
    nonce: str
    host: str
    revision: str
    created: float
    radios: list[dict]
    dns_nonce: str | None
    domain: dict | None
    hosts: list[dict]


def _read_radios(zte) -> tuple[list[dict], dict]:
    raw = rf.get_channel(zte)
    root = ET.fromstring(raw)
    if (root.tag != "ajax_response_xml_root" or
            (root.findtext("IF_ERRORID") or "").strip() != "0"):
        raise RuntimeError("Formulário avançado do rádio não respondeu corretamente.")
    parsed = zte._parse_instances(raw)
    radios = parsed.get("OBJ_WLANSETTING_ID", [])
    if not radios:
        raise RuntimeError("A ONT não informou os rádios do perfil.")

    normalized = []
    for source in radios:
        radio = dict(source)
        for field, value in RF_CAPTURE_COMPAT_DEFAULTS.items():
            if radio.get(field) in (None, ""):
                radio[field] = value
        normalized.append(radio)

    # Keep parsed and the per-radio list consistent so channel validation
    # and the preview compare the exact same normalized snapshot.
    parsed = dict(parsed)
    parsed["OBJ_WLANSETTING_ID"] = normalized
    return normalized, parsed


def _build_target(data: dict, radio: dict, band: str, config: dict) -> dict:
    if not isinstance(config, dict) or set(config) - set(RADIO_PROFILE_FIELDS):
        raise ValueError("Configuração RF contém campos fora do perfil autorizado.")
    target = dict(radio)
    rf._apply_standard(target, band, config)
    rf._apply_channel(data, target, band, config)
    rf._apply_advanced(target, config)
    missing = [name for name in CAPTURED_RF_FIELDS
               if name not in radio or radio[name] is None
               or name not in target or target[name] is None]
    if missing:
        raise RuntimeError(
            "O formulário deste firmware não expôs os campos capturados: "
            + ", ".join(missing)
        )
    return target


def _domain_name_valid(value: str) -> bool:
    if value == "":
        return True
    if len(value) > 253 or not value.isascii():
        return False
    return all(re.fullmatch(r"[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?", label)
               for label in value.split("."))


def _read_hosts(zte) -> list[dict]:
    xml = zte_dns.dns_hosts_raw(zte)
    if not isinstance(xml, str):
        raise RuntimeError("A tabela de nomes DNS não retornou XML.")
    try:
        root = ET.fromstring(xml)
    except ET.ParseError:
        raise RuntimeError("Resposta de hosts DNS inválida.") from None
    if root.tag != "ajax_response_xml_root" or root.find("ALLDNSHOST") is None:
        raise RuntimeError("ALLDNSHOST não foi confirmado para este login.")
    return zte_dns._parse_hosts(xml)


def _temporarily_write(zte, original_post, operation):
    if original_post is None:
        raise PermissionError("Transporte de escrita original indisponível.")
    blocked = zte.session.post
    old_enabled = getattr(zte, "writes_enabled", False)
    try:
        zte.session.post = original_post
        zte.writes_enabled = True
        return operation()
    finally:
        zte.session.post = blocked
        zte.writes_enabled = old_enabled


class ExperimentalF6201BProfile:
    def __init__(self):
        self._pending: BatchPreview | None = None

    def clear(self):
        self._pending = None

    @staticmethod
    def _authorized(firmware):
        if firmware != EXACT_FIRMWARE:
            raise ValueError("Formulário RF indisponível neste firmware.")

    def preview(self, zte, *, host, revision, firmware, profile, dns_adapter):
        self.clear()
        dns_adapter.clear()
        self._authorized(firmware)
        # Read every requested radio BEFORE queuing any write.
        candidates, parsed = _read_radios(zte)
        proposals = []
        for band in ("2.4GHz", "5GHz"):
            config = profile.get("wifi", {}).get(band)
            if not config:
                continue
            found = [item for item in candidates if item.get("Band") == band]
            if len(found) != 1 or not found[0].get("_InstID"):
                available = ", ".join(sorted({
                    str(item.get("Band") or "?") for item in candidates
                }))
                raise RuntimeError(
                    "O perfil requer o rádio " + band +
                    ", mas a leitura avançada retornou: " + available +
                    ". Verifique o firmware e a sessão antes de aplicar."
                )
            before = found[0]
            target = _build_target(parsed, before, band, config)
            # A ONT informa o canal em operação (1, 6, 36...) mesmo
            # com AutoChannelEnabled=1. "NULL" no formulário significa
            # *configurar automático*, não exigir que o GET fique NULL.
            # Sem este filtro o simples perfil padrão dispara dois POSTs
            # de rádio redundantes a cada clique.
            unchanged_auto = (
                str(before.get("AutoChannelEnabled")) == "1"
                and str(target.get("AutoChannelEnabled")) == "1"
            )
            delta = {
                name: {"before": str(before[name]), "after": str(target[name])}
                for name in CAPTURED_RF_FIELDS
                if str(before[name]) != str(target[name])
                and not (name == "Channel" and unchanged_auto)
            }
            if delta:
                proposals.append({
                    "band": band, "instance_id": before["_InstID"],
                    "original": {name: str(before[name]) for name in CAPTURED_RF_FIELDS},
                    "desired": {name: str(target[name]) for name in CAPTURED_RF_FIELDS},
                    "changes": delta,
                })
        dns_nonce = None
        dns_delta = {}
        dns = profile.get("dns") or {}
        # Existing DNS adapter reads current values and validates IPv4.
        current_dns = dns_adapter.read(zte)
        requested = {}
        for key in ("ipv4_1", "ipv4_2", "ipv6_1", "ipv6_2"):
            value = dns.get(key)
            if value is not None and value != current_dns.get(key):
                requested[key] = value
        if requested:
            dns_preview = dns_adapter.preview(
                zte, host=host, firmware=firmware, changes=requested
            )
            dns_nonce = dns_preview["nonce"]
            dns_delta = dns_preview["changes"]
        domain_pending = None
        domain_value = dns.get("domain_name")
        if domain_value is not None:
            if not isinstance(domain_value, str) or not _domain_name_valid(domain_value):
                raise ValueError("Domínio DNS inválido.")
            from apps.zte_manager.services.f6201b_dns_writes import _read as _read_dns
            current_domain = _read_dns(zte)
            domain_before = current_domain.get("DomainName") or ""
            if domain_value != domain_before:
                domain_pending = {
                    "instance_id": current_domain["_InstID"],
                    "before": domain_before, "after": domain_value,
                }
        target_hosts = dns.get("hosts") or []
        if not isinstance(target_hosts, list) or len(target_hosts) > 32:
            raise ValueError("Máximo de 32 nomes DNS no perfil.")
        existing_hosts = _read_hosts(zte) if target_hosts else []
        existing_by_name = {item["nome"]: item for item in existing_hosts}
        host_changes = []
        names_seen = set()
        for target_host in target_hosts:
            if not isinstance(target_host, dict):
                raise ValueError("Entrada DNS incorreta no perfil.")
            name = str(target_host.get("nome") or "").strip()
            ip = str(target_host.get("ip") or "").strip()
            zte_dns._validate_host(name, ip)
            if name in names_seen:
                raise ValueError("Host DNS duplicado no perfil: " + name)
            names_seen.add(name)
            before = existing_by_name.get(name)
            if before is None or (before.get("ip") or "") != ip:
                host_changes.append({
                    "name": name, "after": ip,
                    "before": before.get("ip") if before else None,
                    "instance_id": before.get("id") if before else "-1",
                })
        if not proposals and not dns_delta and not domain_pending and not host_changes:
            # Identical configuration is a SUCCESSFUL preflight/no-op, not a
            # failed Apply; do not create a nonce or send a POST.
            return {
                "model": "F6201B", "operation": "profile_captured",
                "noop": True, "radios": [], "dns": {},
                "domain": None, "hosts": [],
                "not_included": list(SKIPPED_PROFILE_FEATURES),
                "message": "O padrão do atendente já está aplicado. "
                           "Nenhum POST é necessário.",
            }
        nonce = secrets.token_urlsafe(24)
        self._pending = BatchPreview(
            nonce, host, revision, time.monotonic(), proposals, dns_nonce,
            domain_pending, host_changes
        )
        return {
            "model": "F6201B", "operation": "profile_captured",
            "nonce": nonce, "expires_in_seconds": PREVIEW_TTL,
            "radios": [{"band": item["band"], "changes": item["changes"]}
                       for item in proposals],
            "dns": dns_delta,
            "domain": ({key: domain_pending[key]
                        for key in ("before", "after")}
                       if domain_pending else None),
            "hosts": [{"name": entry["name"], "before": entry["before"],
                       "after": entry["after"]} for entry in host_changes],
            "not_included": list(SKIPPED_PROFILE_FEATURES),
            "warning": (
                "Alterações sequenciais podem interromper a conexão; "
                "mantenha acesso local quando possível."
            ),
        }

    def apply_saved(self, zte, *, host, revision, firmware, profile,
                    original_post, dns_adapter):
        """One user action: inspect + apply the saved preset synchronously.

        The preview nonce is strictly an *internal* replay guard; the
        attendant is not asked for a second click or a typed phrase.
        The caller holds the service RLock across the entire workflow.
        If preflight fails no router POST is attempted. Changed fields are
        re-read after every successful POST by apply().
        """
        proposal = self.preview(
            zte, host=host, revision=revision, firmware=firmware,
            profile=profile, dns_adapter=dns_adapter,
        )
        if proposal.get("noop"):
            return {
                "success": True, "verified": True, "noop": True,
                "partial": False, "steps": [],
                "message": proposal["message"],
                "not_included": proposal["not_included"],
            }
        report = self.apply(
            zte, host=host, revision=revision, firmware=firmware,
            nonce=proposal["nonce"], confirmation="APLICAR PERFIL F6201B",
            original_post=original_post, dns_adapter=dns_adapter,
        )
        report["verified"] = report.get("success") is True
        report["noop"] = False
        return report

    def apply(self, zte, *, host, revision, firmware, nonce, confirmation,
              original_post, dns_adapter):
        proposal = self._pending
        self.clear()  # Even invalid attempts consume the nonce.
        self._authorized(firmware)
        if (proposal is None or
                not secrets.compare_digest(str(nonce), proposal.nonce) or
                proposal.host != host or proposal.revision != revision or
                time.monotonic() - proposal.created > PREVIEW_TTL):
            raise PermissionError("Prévia expirada ou sessão alterada. Gere outra.")
        if original_post is None:
            raise PermissionError("Transporte de escrita original ausente.")
        steps = []
        stage = "Pré-validação"
        # No retries and no automatic rollback. Stop at first uncertainty.
        try:
            for item in proposal.radios:
                stage = "Wi-Fi " + item["band"]
                radios, _ = _read_radios(zte)
                found = [r for r in radios
                         if r.get("_InstID") == item["instance_id"] and
                         r.get("Band") == item["band"]]
                # When AutoChannelEnabled=1 the actual operating Channel is
                # volatile: a channel scan may change it while preview is
                # waiting for confirmation. The mode itself is still checked.
                volatile = (
                    {"Channel"}
                    if item["original"].get("AutoChannelEnabled") == "1"
                    else set()
                )
                if len(found) != 1 or any(
                    str(found[0].get(key)) != value
                    for key, value in item["original"].items()
                    if key not in volatile
                ):
                    raise RuntimeError(
                        "Rádio " + item["band"] + " mudou após a prévia."
                    )
                fields = {"IF_ACTION": "Apply",
                          "_InstID": item["instance_id"], **item["desired"]}
                payload = [(name, fields[name]) for name in RADIO_SCHEMA
                           if name != "_sessionTOKEN"]
                # Fresh menuView token immediately before POST.
                zte.get_view("wlanBasic", Menu3Location=0)
                blocked = zte.session.post
                old_enabled = getattr(zte, "writes_enabled", False)
                try:
                    zte.session.post = original_post
                    zte.writes_enabled = True
                    post_menu(zte, "wlan_wlanbasicadconf_lua.lua", payload)
                finally:
                    zte.session.post = blocked
                    zte.writes_enabled = old_enabled
                # Verify only the changed fields, not unrelated volatile data.
                changed = item["changes"]
                verified, _ = _read_radios(zte)
                actual = next((r for r in verified
                    if r.get("_InstID") == item["instance_id"]), None)
                # Channel may be selected asynchronously by the firmware;
                # verify AutoChannelEnabled but never require Channel=NULL
                # once automatic mode has been enabled successfully.
                verify_changes = {
                    name: delta for name, delta in changed.items()
                    if not (name == "Channel" and
                            item["desired"].get("AutoChannelEnabled") == "1")
                }
                mismatch = [
                    name for name, expected in verify_changes.items()
                    if actual is None or
                       str(actual.get(name)) != expected["after"]
                ]
                if mismatch:
                    raise RuntimeError(
                        "A releitura de " + item["band"] +
                        " divergiu nos campos: " + ", ".join(mismatch)
                    )
                steps.append({
                    "name": "Wi-Fi " + item["band"], "success": True,
                    "detail": "Aplicado e confirmado por releitura.",
                })
            if proposal.domain:
                stage = "Domínio DNS"
                from apps.zte_manager.services.f6201b_dns_writes import _read as _read_dns
                domain = proposal.domain
                live = _read_dns(zte)
                if (live.get("_InstID") != domain["instance_id"] or
                        (live.get("DomainName") or "") != domain["before"]):
                    raise RuntimeError("Domínio DNS mudou após a prévia.")
                fields = {
                    "IF_ACTION": "Apply", "_InstID": domain["instance_id"],
                    "DomainName": domain["after"],
                    "Btn_cancel_instCfgArea": "",
                    "Btn_apply_instCfgArea": "",
                }
                payload = [(key, fields[key]) for key in DNS_DOMAIN_APPLY_FIELDS
                           if key != "_sessionTOKEN"]
                zte.get_view("dns", Menu3Location=0)
                _temporarily_write(zte, original_post, lambda: post_menu(
                    zte, "dns_localdns_lua.lua", payload
                ))
                if (_read_dns(zte).get("DomainName") or "") != domain["after"]:
                    raise RuntimeError("Domínio DNS não confirmado na releitura.")
                steps.append({
                    "name": "Domínio DNS", "success": True,
                    "detail": "Aplicado e confirmado.",
                })

            for host_item in proposal.hosts:
                stage = "Host DNS " + host_item["name"]
                current_hosts = _read_hosts(zte)
                matching = [row for row in current_hosts
                            if row.get("nome") == host_item["name"]]
                if len(matching) > 1:
                    raise RuntimeError("Host DNS duplicado na ONT.")
                live = matching[0] if matching else None
                if ((live.get("id") if live else "-1") != host_item["instance_id"]
                    or (live.get("ip") if live else None) != host_item["before"]):
                    raise RuntimeError("Host DNS mudou após a prévia.")
                fields = {
                    "IF_ACTION": "Apply",
                    "_InstID": host_item["instance_id"],
                    "OBJID": "DNS", "LeaseTime": "isDNSHOSTInst",
                    "HostName": host_item["name"],
                    "IPAddress": host_item["after"],
                }
                payload = [(key, fields[key])
                           for key in OBSERVED_APPLY_FIELDS["dns_hostname_lua.lua"]
                           if key != "_sessionTOKEN"]
                zte.get_view("dns", Menu3Location=0)
                _temporarily_write(zte, original_post, lambda: post_menu(
                    zte, "dns_hostname_lua.lua", payload
                ))
                confirmed = _read_hosts(zte)
                if not any(row["nome"] == host_item["name"] and
                           row.get("ip") == host_item["after"]
                           for row in confirmed):
                    raise RuntimeError("Host DNS não confirmado; revise antes de repetir.")
                steps.append({
                    "name": "Host DNS " + host_item["name"],
                    "success": True, "detail": "Aplicado e confirmado.",
                })

            if proposal.dns_nonce:
                stage = "Servidores DNS IPv4/IPv6"
                result = dns_adapter.apply(
                    zte, host=host, firmware=firmware,
                    nonce=proposal.dns_nonce,
                    confirmation="APLICAR DNS F6201B",
                    original_post=original_post,
                )
                if not result.get("verified"):
                    raise RuntimeError("DNS não confirmado por releitura.")
                steps.append({
                    "name": "DNS IPv4", "success": True,
                    "detail": "Aplicado e confirmado por releitura.",
                })
        except Exception as exc:
            steps.append({
                "name": stage, "success": False,
                # No raw XML or request bodies are returned.
                "detail": type(exc).__name__ + ": " + str(exc)[:240],
            })
            return {
                "success": False, "partial": bool(steps[:-1]),
                "failed_stage": stage,
                "steps": steps,
                "not_included": list(SKIPPED_PROFILE_FEATURES),
            }
        finally:
            dns_adapter.clear()
        return {
            "success": bool(steps), "partial": False,
            "steps": steps, "not_included": list(SKIPPED_PROFILE_FEATURES),
        }

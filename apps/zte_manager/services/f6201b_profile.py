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
import xml.etree.ElementTree as ET

from apps.zte_manager.model.zte_configuration import (
    zte_wlan_channel_configuration as rf,
)
from apps.zte_manager.model.zte_configuration.zte_post import post_menu
from apps.zte_manager.services.f6201b_evidence import OBSERVED_APPLY_FIELDS
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
SKIPPED_PROFILE_FEATURES = (
    "SSID/senha (perfil não possui esses campos)",
    "DNS IPv6", "domínio DNS", "hosts DNS estáticos",
)


@dataclass
class BatchPreview:
    nonce: str
    host: str
    revision: str
    created: float
    radios: list[dict]
    dns_nonce: str | None


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
    return radios, parsed


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


class ExperimentalF6201BProfile:
    def __init__(self):
        self._pending: BatchPreview | None = None

    def clear(self):
        self._pending = None

    @staticmethod
    def _authorized(firmware):
        if firmware != EXACT_FIRMWARE or not ExperimentalF6201BWrites.opted_in():
            raise PermissionError(
                "Ative ZTE_F6201B_EXPERIMENTAL_WRITES=1 e confirme o "
                "firmware F6201B V9.3.10P7N7 para testar o perfil."
            )

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
                raise RuntimeError("Rádio " + band + " não identificado de modo único.")
            before = found[0]
            target = _build_target(parsed, before, band, config)
            delta = {
                name: {"before": str(before[name]), "after": str(target[name])}
                for name in CAPTURED_RF_FIELDS
                if str(before[name]) != str(target[name])
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
        for key in ("ipv4_1", "ipv4_2"):
            value = dns.get(key)
            if value is not None and value != current_dns.get(key):
                requested[key] = value
        if requested:
            dns_preview = dns_adapter.preview(
                zte, host=host, firmware=firmware, changes=requested
            )
            dns_nonce = dns_preview["nonce"]
            dns_delta = dns_preview["changes"]
        if not proposals and not dns_delta:
            raise ValueError(
                "O equipamento já possui os valores suportados pelo perfil. "
                "Nenhuma alteração experimental necessária."
            )
        nonce = secrets.token_urlsafe(24)
        self._pending = BatchPreview(
            nonce, host, revision, time.monotonic(), proposals, dns_nonce
        )
        return {
            "model": "F6201B", "operation": "profile_captured",
            "nonce": nonce, "expires_in_seconds": PREVIEW_TTL,
            "radios": [{"band": item["band"], "changes": item["changes"]}
                       for item in proposals],
            "dns": dns_delta,
            "not_included": list(SKIPPED_PROFILE_FEATURES),
            "warning": (
                "Teste experimental: alterações sequenciais; falhas podem "
                "deixar um perfil parcial. Use acesso local por cabo."
            ),
        }

    def apply(self, zte, *, host, revision, firmware, nonce, confirmation,
              original_post, dns_adapter):
        proposal = self._pending
        self.clear()  # Even invalid attempts consume the nonce.
        self._authorized(firmware)
        if confirmation != "APLICAR PERFIL F6201B":
            raise PermissionError("Digite APLICAR PERFIL F6201B.")
        if (proposal is None or
                not secrets.compare_digest(str(nonce), proposal.nonce) or
                proposal.host != host or proposal.revision != revision or
                time.monotonic() - proposal.created > PREVIEW_TTL):
            raise PermissionError("Prévia expirada ou sessão alterada. Gere outra.")
        if original_post is None:
            raise PermissionError("Transporte de escrita original ausente.")
        steps = []
        # No retries and no automatic rollback. Stop at first uncertainty.
        try:
            for item in proposal.radios:
                radios, _ = _read_radios(zte)
                found = [r for r in radios
                         if r.get("_InstID") == item["instance_id"] and
                         r.get("Band") == item["band"]]
                if len(found) != 1 or any(
                    str(found[0].get(key)) != value
                    for key, value in item["original"].items()
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
                if actual is None or any(
                    str(actual.get(name)) != expected["after"]
                    for name, expected in changed.items()
                ):
                    raise RuntimeError(
                        "A releitura não confirmou o rádio " + item["band"]
                    )
                steps.append({
                    "name": "Wi-Fi " + item["band"], "success": True,
                    "detail": "Aplicado e confirmado por releitura.",
                })
            if proposal.dns_nonce:
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
                "name": "Etapa interrompida", "success": False,
                # No raw XML or request bodies are returned.
                "detail": type(exc).__name__ + ": " + str(exc)[:240],
            })
            return {
                "success": False, "partial": bool(steps[:-1]),
                "steps": steps,
                "not_included": list(SKIPPED_PROFILE_FEATURES),
            }
        finally:
            dns_adapter.clear()
        return {
            "success": bool(steps), "partial": False,
            "steps": steps, "not_included": list(SKIPPED_PROFILE_FEATURES),
        }

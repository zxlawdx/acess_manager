"""Command/Strategy layer for *captured* F6201B menuData forms.

The registry represents all 25 successful Apply routes observed on the
operator's V9.3.10P7N7 capture. Only routes whose GET representation can be
unambiguously round-tripped are eligible for supervised writes here.
Complex forms stay mapped with explicit blockers; the pre-existing SSID,
DNS, RF and profile implementations remain the owners of those workflows.

Never import the raw capture. No stored token, credential or captured value.
"""
from __future__ import annotations

from dataclasses import dataclass
import ipaddress
import os
import secrets
import time
import xml.etree.ElementTree as ET

from apps.zte_manager.model.zte_configuration.zte_post import post_menu
from apps.zte_manager.services.f6201b_evidence import (
    CAPTURED_GET_VIEWS, GET_PARAMS, OBSERVED_APPLY_FIELDS,
)
from apps.zte_manager.services.f6201b_writes import (
    EXACT_FIRMWARE, ExperimentalF6201BWrites, PREVIEW_TTL,
)
from apps.zte_manager.services.f6201b_full_forms import (
    FORM_SPECS, FullCapturedForms,
)

# These routes have an observed single-object GET matching all *data* fields
# of the captured Apply. Every extra field or mismatch fails closed.
# Value preservation comes from a *new* authenticated GET, never this catalog.
@dataclass(frozen=True)
class CapturedStrategy:
    root: str
    editable: tuple[str, ...]
    dangerous: bool = False


STRATEGIES: dict[str, CapturedStrategy] = {
    "bpdu_lua.lua": CapturedStrategy("OBJ_BPDU_ID", ("BPDUEnable",), True),
    "upnp_upnp_lua.lua": CapturedStrategy(
        "OBJ_UPNPCONFIG_ID", ("EnableUPnPIGD", "ADPeriod", "TTL"), True,
    ),
    "route_routedefault_lua.lua": CapturedStrategy(
        "OBJ_ROUTEDEFAULT_ID", ("DefRTInterface",), True,
    ),
    "addr6_lanaddr_lua.lua": CapturedStrategy(
        "OBJ_LANADDR6_ID", ("IPAddress",), True,
    ),
    "wlan_BandSteering_lua.lua": CapturedStrategy(
        "OBJ_WLAN_BANDSTEERING_ID",
        ("BsEnable", "BsRssiLmt24G", "BsRssiLmt5G",
         "BsBounceDwellTimeLmt", "BsTPLimit"),
    ),
    "firewall_config_lua.lua": CapturedStrategy(
        "OBJ_FWLEVEL_ID", ("Enable", "Level"), True,
    ),
    "firewall_alg_lua.lua": CapturedStrategy(
        "OBJ_FWALG_ID",
        ("IsFTPAlg", "IsH323Alg", "IsIPSECAlg", "IsL2TPAlg",
         "IsPPTPAlg", "IsRTSPAlg", "IsSIPAlg", "IsTFTPAlg"), True,
    ),
}

# Existing adapters have dedicated preservation/validation mechanisms.
INTEGRATED = {
    "dns_localdns_lua.lua": "DNS IPv4/IPv6 e domínio: Configuração padrão",
    "dns_hostname_lua.lua": "Hosts estáticos DNS: Configuração padrão",
    "wlan_wlansssidconf_lua.lua": "SSID, senha e isolamento: Wi-Fi",
    "wlan_wlanbasicadconf_lua.lua": "Rádio avançado: Configuração padrão",
}
REASONS = {
    "wan_internet_lua.lua": "WAN/PPPoE: campos condicionais, credenciais criptografadas e vínculo de interface requerem Strategy dedicada.",
    "tr069_remotemgr_lua.lua": "ACS/TR-069: dois campos de senha criptografados e certificados precisam de preservação por formulário.",
    "eth_interface_config_lua.lua": "O Apply inclui ModType, ausente no GET da captura; requer captura do campo efetivo.",
    "firewall_dmz_lua.lua": "Subcampos de MAC temporário não aparecem no objeto GET; não é seguro preenchê-los por suposição.",
    "wlan_wps_lua.lua": "SSID_InstID e WPSChoose são selecionados por formulário, não aparecem no objeto GET.",
    "wlan_wlanbasiconoff_lua.lua": "Apply combina rádio, timer e duas instâncias; exige tradução multiobjeto.",
    "wlan_macfilteraclpolicy_lua.lua": "Apply usa vetor por SSID com _InstNum; exige conservação integral das instâncias.",
    "Localnet_NetSphere_Mode_lua.lua": "CurrentMode/CurrentEnable e confirmação Mesh dependem do formulário atual.",
    "route_routestaticipv4_lua.lua": "Type não aparece no objeto GET, e Add difere de Apply de regra existente.",
    "Localnet_LanMgrIpv4_DHCPBasicCfg_lua.lua": "DHCP combina objetos e campo encode; exige adaptação sem alterar IP LAN involuntariamente.",
    "Localnet_LanDevDHCPSource_lua.lua": "Apply usa vetor de 12 posições, inclusive entradas não retornadas no GET.",
    "dhcp6s_dhcpserver_lua.lua": "DHCPv6 agrega OBJ_DHCP6S_ID e OBJ_LANDNS_ID com campos distintos.",
    "ra_raservice_lua.lua": "RA tem campos transformados S_AdvLinkMTU e prefixos condicionais.",
    "radhcp6s_portctrl_lua.lua": "Portas IPv6 exigem sincronizar vetor e seleção principal por instância.",
}


@dataclass
class CapturedPreview:
    nonce: str
    host: str
    revision: str
    attendant: str
    tag: str
    instance_id: str
    original: dict[str, str]
    desired: dict[str, str]
    created: float


def catalog() -> dict:
    """Capabilities/Factory metadata without suggesting that POST means support."""
    routes = []
    for tag in OBSERVED_APPLY_FIELDS:
        spec = STRATEGIES.get(tag)
        if spec:
            state = "supervised_lab"
            explanation = "Apply implementado com preflight, nonce e releitura."
        elif tag in FORM_SPECS:
            state = "supervised_lab"
            explanation = FORM_SPECS[tag].description
        elif tag in INTEGRATED:
            state = "existing_adapter"
            explanation = INTEGRATED[tag] + ". Homologação física independente."
        else:
            state = "needs_form_adapter"
            explanation = REASONS.get(tag, "Faltam validações de campos condicionais do formulário.")
        routes.append({
            "tag": tag,
            "view": CAPTURED_GET_VIEWS.get(tag),
            "state": state,
            "reason": explanation,
            "editable": (
                list(spec.editable) if spec else
                list(FORM_SPECS[tag].editable) if tag in FORM_SPECS else []
            ),
            "secret_fields": (
                list(FORM_SPECS[tag].secrets) if tag in FORM_SPECS else []
            ),
            "dangerous": (
                spec.dangerous if spec else
                FORM_SPECS[tag].dangerous if tag in FORM_SPECS else False
            ),
        })
    return {
        "model": "F6201B", "firmware": EXACT_FIRMWARE,
        "total_observed_apply_routes": len(OBSERVED_APPLY_FIELDS),
        "routes": routes,
        "writes_opted_in": ExperimentalF6201BWrites.opted_in(),
        "physical_validation": "pending",
    }


def _safe_value(key: str, value: object) -> str:
    if not isinstance(value, (str, int, bool, float)):
        raise ValueError("Os campos devem ser escalares.")
    result = str(value)
    if len(result) > 255 or any(ord(ch) < 32 for ch in result):
        raise ValueError("Valor inválido ou grande demais para " + key)
    if (key in {"BPDUEnable", "EnableUPnPIGD", "BsEnable", "Enable"}
            or key.startswith("Is") and key.endswith("Alg")):
        if result not in {"0", "1"}:
            raise ValueError("O campo " + key + " deve ser 0 ou 1.")
    if key == "IPAddress":
        try:
            ipaddress.IPv6Interface(result)
        except ValueError:
            raise ValueError("Informe um endereço IPv6 válido.") from None
    if key in {"ADPeriod", "TTL", "BsBounceDwellTimeLmt", "BsTPLimit"}:
        if not result.isdecimal():
            raise ValueError("O campo " + key + " exige inteiro não negativo.")
    if key.startswith("BsRssiLmt"):
        try:
            number = int(result)
        except ValueError:
            raise ValueError("RSSI deve ser um número inteiro.") from None
        if number < -120 or number > 0:
            raise ValueError("RSSI deve ficar entre -120 e 0.")
    return result


def build_captured_payload(
    tag: str, current: dict[str, str], changes: dict[str, str]
) -> list[tuple[str, str]]:
    """Exact evidence order; do not fabricate absent live GET fields."""
    spec = STRATEGIES[tag]
    schema = OBSERVED_APPLY_FIELDS[tag]
    if set(changes) - set(spec.editable):
        raise ValueError("Campo não permitido para este formulário.")
    if not current.get("_InstID"):
        raise ValueError("Instância de configuração não identificada.")
    needed = set(spec.editable)
    if not needed.issubset(current):
        raise ValueError(
            "GET incompleto: " + ", ".join(sorted(needed - set(current)))
        )
    fields = {"IF_ACTION": "Apply", "_InstID": current["_InstID"]}
    fields.update({key: str(current[key]) for key in spec.editable})
    fields.update(changes)
    payload = []
    for field in schema:
        if field == "_sessionTOKEN":
            continue  # post_menu appends session token itself, last.
        if field.startswith("Btn_"):
            payload.append((field, ""))
        elif field in fields:
            payload.append((field, fields[field]))
        else:
            raise ValueError("Campo não preservável neste firmware: " + field)
    return payload


class CapturedFormWorkbench:
    """Single-session Command object. Caller injects an authenticated ZTE."""
    def __init__(self, clock=time.monotonic):
        self._pending: CapturedPreview | None = None
        self._clock = clock
        self._full = FullCapturedForms(clock=clock)
        self._active: str | None = None

    def clear(self):
        self._pending = None
        self._full.clear()
        self._active = None

    @staticmethod
    def _read(zte, tag: str, instance_id: str | None = None) -> dict:
        spec = STRATEGIES[tag]
        view = CAPTURED_GET_VIEWS.get(tag)
        if not view:
            raise RuntimeError("MenuView não mapeada para a rota.")
        zte.get_view(view, Menu3Location=0)
        raw = zte.get_menu(tag, **GET_PARAMS.get(tag, {}))
        root = ET.fromstring(raw)
        if root.tag != "ajax_response_xml_root" or root.findtext("IF_ERRORID") != "0":
            raise RuntimeError("Firmware retornou XML inesperado ou erro de sessão.")
        records = zte._parse_instances(raw).get(spec.root, [])
        if not records:
            raise RuntimeError("Objeto esperado ausente: " + spec.root)
        if instance_id is None and len(records) != 1:
            raise ValueError("Selecione explicitamente uma instância.")
        matched = [item for item in records if
                   instance_id is None or item.get("_InstID") == instance_id]
        if len(matched) != 1 or not matched[0].get("_InstID"):
            raise RuntimeError("Instância solicitada não existe na sessão atual.")
        return matched[0]

    def inspect(self, zte, tag: str) -> dict:
        """Read-only values only for a spec with a verified, nonsecret field map."""
        if tag in FORM_SPECS:
            return self._full.inspect(zte, tag)
        if tag not in STRATEGIES:
            meta = next((r for r in catalog()["routes"] if r["tag"] == tag), None)
            if not meta:
                raise ValueError("Rota ausente da captura autorizada.")
            return {"tag": tag, "available": False, "state": meta["state"],
                    "reason": meta["reason"]}
        spec = STRATEGIES[tag]
        view = CAPTURED_GET_VIEWS[tag]
        zte.get_view(view, Menu3Location=0)
        raw = zte.get_menu(tag, **GET_PARAMS.get(tag, {}))
        root = ET.fromstring(raw)
        if root.tag != "ajax_response_xml_root" or root.findtext("IF_ERRORID") != "0":
            raise RuntimeError("GET rejeitado ou sessão expirada.")
        records = zte._parse_instances(raw).get(spec.root, [])
        if not records:
            return {"tag": tag, "available": False,
                    "reason": "Objeto XML esperado não retornado."}
        return {
            "tag": tag, "available": True, "state": "supervised_lab",
            "instances": [
                {"id": row.get("_InstID"),
                 "current": {field: row[field] for field in spec.editable
                             if field in row},
                 "missing": [field for field in spec.editable if field not in row]}
                for row in records if row.get("_InstID")
            ],
        }

    def preview(self, zte, *, tag: str, instance_id: str,
                changes: dict, host: str, revision: str,
                attendant: str) -> dict:
        self.clear()
        if tag in FORM_SPECS:
            result = self._full.preview(
                zte, tag=tag, instance_id=instance_id, changes=changes,
                host=host, revision=revision, attendant=attendant,
            )
            self._active = "full"
            return result
        if tag not in STRATEGIES:
            raise PermissionError("Rota sem adaptador de gravação supervisionada.")
        self._active = "simple"
        if not isinstance(changes, dict) or not changes:
            raise ValueError("Escolha pelo menos um campo para alterar.")
        spec = STRATEGIES[tag]
        if set(changes) - set(spec.editable):
            raise ValueError("O campo solicitado não está na lista de edição.")
        clean = {key: _safe_value(key, value) for key, value in changes.items()}
        current = self._read(zte, tag, instance_id)
        desired = {field: str(current[field]) for field in spec.editable
                   if field in current}
        # Validates that *every* captured data field can be preserved.
        build_captured_payload(tag, current, clean)
        diff = {key: {"before": desired[key], "after": value}
                for key, value in clean.items() if desired[key] != value}
        if not diff:
            raise ValueError("A configuração já possui esses valores.")
        desired.update(clean)
        nonce = secrets.token_urlsafe(24)
        self._pending = CapturedPreview(
            nonce, host, revision, attendant, tag, instance_id,
            {key: desired[key] if key not in diff else diff[key]["before"]
             for key in spec.editable},
            desired, self._clock(),
        )
        return {"tag": tag, "instance_id": instance_id, "nonce": nonce,
                "expires_in_seconds": PREVIEW_TTL,
                "impact_warning": spec.dangerous, "diff": diff,
                "physical_validation": "pending",
                "note": "Confirme backup e Ethernet antes de aplicar."}

    def apply_changes(self, zte, *, host: str, revision: str,
                      attendant: str, tag: str, instance_id: str,
                      changes: dict, original_post) -> dict:
        """One user request: all preflight checks then exactly one device Apply.

        An internal one-use nonce is never an additional operator challenge.
        The service RLock serializes GET/view/POST and prevents session races.
        """
        proposal = self.preview(
            zte, tag=tag, instance_id=instance_id, changes=changes,
            host=host, revision=revision, attendant=attendant,
        )
        return self.apply(
            zte, host=host, revision=revision, attendant=attendant,
            nonce=proposal["nonce"], confirmation="", risk_ack=True,
            original_post=original_post,
        )

    def apply(self, zte, *, host: str, revision: str,
              attendant: str, nonce: str,
              confirmation: str, risk_ack: bool, original_post) -> dict:
        if self._active == "full":
            self._active = None
            return self._full.apply(
                zte, host=host, revision=revision, attendant=attendant,
                nonce=nonce, confirmation=confirmation, risk_ack=risk_ack,
                original_post=original_post,
            )
        proposal = self._pending
        self.clear()  # one-shot, including rejected attempts
        if original_post is None:
            raise PermissionError("Transporte experimental indisponível.")
        if not proposal or not secrets.compare_digest(proposal.nonce, str(nonce)):
            raise PermissionError("Nonce inválido ou já consumido.")
        if (proposal.host != host or proposal.revision != revision or
                self._clock() - proposal.created > PREVIEW_TTL):
            raise PermissionError("Prévia expirada ou sessão alterada.")
        spec = STRATEGIES[proposal.tag]
        live = self._read(zte, proposal.tag, proposal.instance_id)
        if any(str(live.get(key)) != value
               for key, value in proposal.original.items()):
            raise RuntimeError("Configuração mudou desde a prévia; gere outra.")
        # Never let the request body come from the apply HTTP request.
        payload = build_captured_payload(
            proposal.tag, live, proposal.desired
        )
        # Refresh menuView right before POST. Preserve the session-wide
        # transport lock even if Check, network or XML verification fails.
        zte.get_view(CAPTURED_GET_VIEWS[proposal.tag], Menu3Location=0)
        blocked = zte.session.post
        old_writes = getattr(zte, "writes_enabled", False)
        try:
            zte.session.post = original_post
            zte.writes_enabled = True
            try:
                post_menu(zte, proposal.tag, payload,
                          **GET_PARAMS.get(proposal.tag, {}))
            except Exception:
                # Sending may have succeeded even if the reply timed out.
                return {"success": False, "uncertain": True,
                        "stage": "post_or_response", "tag": proposal.tag,
                        "detail": "Confira manualmente; POST não será repetido."}
        finally:
            zte.session.post = blocked
            zte.writes_enabled = old_writes
        for _ in range(3):
            try:
                observed = self._read(zte, proposal.tag, proposal.instance_id)
                if all(str(observed.get(key)) == value
                       for key, value in proposal.desired.items()
                       if proposal.original[key] != value):
                    return {"success": True, "verified": True,
                            "tag": proposal.tag,
                            "changed_fields": [
                                key for key in proposal.desired
                                if proposal.original[key] != proposal.desired[key]
                            ], "physical_validation": "pending"}
            except (OSError, RuntimeError, ET.ParseError):
                pass
            time.sleep(0.3)
        return {"success": False, "uncertain": True,
                "stage": "readback", "tag": proposal.tag,
                "detail": "Releitura não confirmou; inspecione a ONT antes de repetir."}

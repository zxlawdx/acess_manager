"""F6201B V9.3.10P7N7: adaptador experimental de alterações supervisionadas.

O mapeamento do proprietário documenta GETs, mas NÃO um POST Apply.
Reaproveitamos o read-modify-write SSID existente apenas sob opt-in
explícito do operador, com preflight/preview, nonce de uso único, verificação
de firmware, sem habilitar os demais endpoints de escrita da aplicação.

Se o menu ou o token diferirem, a operação é recusada ANTES do POST.
Não prometer rollback de Wi-Fi: mudanças podem derrubar o acesso remoto.
"""
from __future__ import annotations

import os
import re
import secrets
import time
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from typing import Any

from apps.zte_manager.model.zte_configuration import zte_wifi


EXACT_FIRMWARE = "V9.3.10P7N7"
OPT_IN_ENV = "ZTE_F6201B_EXPERIMENTAL_WRITES"
SAFE_FIELDS = frozenset({"ssid", "enabled", "broadcast"})
PREVIEW_TTL = 120


@dataclass
class Preview:
    nonce: str
    host: str
    ssid_id: str
    config: dict[str, Any]
    previous: dict[str, Any]
    created_at: float


class ExperimentalF6201BWrites:
    """Serviço transitório; zte_service mantém exclusão mútua por RLock."""

    def __init__(self):
        self._pending: Preview | None = None

    @staticmethod
    def opted_in() -> bool:
        return os.environ.get(OPT_IN_ENV, "").strip().lower() == "1"

    @staticmethod
    def capabilities(firmware: str | None = None) -> dict:
        eligible = firmware == EXACT_FIRMWARE
        return {
            "model": "F6201B",
            "firmware": firmware,
            "supported_firmware": eligible,
            "opted_in": ExperimentalF6201BWrites.opted_in(),
            "operations": [{
                "id": "ssid_basic",
                "label": "SSID: nome, ativação e visibilidade",
                "fields": sorted(SAFE_FIELDS),
                "experimental": True,
                "risk": "Alterar ou desligar SSID pode interromper sua conexão Wi-Fi.",
            }],
            "capture_evidence": "GET observado; POST Apply NÃO observado",
            "requires": [
                "confirmação específica após visualizar a diferença",
                "firmware exato e autenticação administrativa",
                "menuView e token temporário reais",
                "mapeamento atual de SSID/PSK confirmado no dispositivo",
                "liberação explícita via variável de ambiente",
            ],
            "note": (
                "Não habilita escrita geral, WAN, GPON, TR-069, DNS ou "
                "reboot. O primeiro Apply exige homologação física."
            ),
        }

    def clear(self):
        self._pending = None

    @staticmethod
    def _validate_config(config) -> dict:
        if not isinstance(config, dict) or not config:
            raise ValueError("Informe ao menos uma alteração.")
        extra = set(config) - SAFE_FIELDS
        if extra:
            raise ValueError("Campos não habilitados para F6201B: " +
                             ", ".join(sorted(map(str, extra))))
        normalized = {}
        for key, value in config.items():
            if key == "ssid":
                if not isinstance(value, str) or not 1 <= len(value) <= 32:
                    raise ValueError("O nome da rede precisa ter 1 a 32 caracteres.")
                if any(ord(char) < 32 for char in value):
                    raise ValueError("O SSID contém caracteres de controle.")
                normalized[key] = value
            else:
                if type(value) is not bool:
                    raise ValueError(key + " deve ser verdadeiro ou falso.")
                normalized[key] = value
        return normalized

    @staticmethod
    def _inspect_session(zte) -> tuple[list[dict], str]:
        """GET + validação do shape; nunca envia POST no preflight."""
        html = zte.get_view("wlanBasic", Menu3Location=0)
        # Não usar mero HTTP 200 como prova de menu compatível.
        if not isinstance(html, str) or (
            "wlan_wlansssidconf" not in html
            and "Btn_apply_WLANSSIDConf" not in html
        ):
            raise RuntimeError(
                "O formulário de escrita do firmware não foi identificado "
                "na menuView. Envie uma captura sanitizada do botão Aplicar."
            )
        if not getattr(zte, "session_tmp_token", None):
            raise RuntimeError("Não foi encontrado token temporário do menu.")
        if getattr(zte, "integrity_check", None) is True and not (
            getattr(zte, "public_key_pem", None)
        ):
            raise RuntimeError("Este firmware exige Check, mas falta chave pública.")
        raw = zte.get_menu("wlan_wlansssidconf_lua.lua")
        if not isinstance(raw, str) or not raw.strip().startswith("<"):
            raise RuntimeError("Resposta Wi-Fi não é XML.")
        root = ET.fromstring(raw)
        if root.tag != "ajax_response_xml_root":
            raise RuntimeError("A sessão devolveu outra página.")
        error_id = (root.findtext("IF_ERRORID") or "0").strip()
        if error_id != "0":
            raise RuntimeError("A ONT recusou a leitura do formulário.")
        aps = zte._parse_instances(raw).get("OBJ_WLANAP_ID", [])
        if not aps or any("_InstID" not in item for item in aps):
            raise RuntimeError("A ONT não retornou IDs de SSID verificáveis.")
        # PSK deve permanecer preservada no POST legado. Um firmware que
        # oculte as instâncias PSK precisa ter um adaptador específico.
        secure_ids = {item["_InstID"] for item in aps
                      if item.get("BeaconType") not in ("None", "", None)}
        if secure_ids:
            psks = zte._parse_instances(raw).get("OBJ_WLANPSK_ID", [])
            if not psks:
                raise RuntimeError(
                    "O firmware não forneceu metadados PSK. "
                    "Não arriscar limpar a segurança das redes."
                )
        return aps, raw

    def preview(self, zte, *, host: str, firmware: str,
                ssid_id: str, config: dict) -> dict:
        self.clear()
        if firmware != EXACT_FIRMWARE:
            raise PermissionError("Somente F6201B firmware V9.3.10P7N7.")
        if not self.opted_in():
            raise PermissionError(
                "Modo experimental bloqueado. Defina " + OPT_IN_ENV +
                "=1 apenas em laboratório/com acesso local."
            )
        if not isinstance(ssid_id, str) or not re.fullmatch(
            r"DEV\.WIFI\.AP\d+", ssid_id
        ):
            raise ValueError("ID de SSID inválido.")
        desired = self._validate_config(config)
        aps, _ = self._inspect_session(zte)
        current = next((ap for ap in aps if ap.get("_InstID") == ssid_id), None)
        if not current:
            raise ValueError("SSID não encontrado na leitura atual.")
        before = {
            "ssid": current.get("ESSID", ""),
            "enabled": current.get("Enable") == "1",
            "broadcast": current.get("ESSIDHideEnable") != "1",
        }
        changes = {key: {"before": before[key], "after": value}
                   for key, value in desired.items()
                   if value != before[key]}
        if not changes:
            raise ValueError("Nenhuma diferença encontrada.")
        # Não colocar credenciais em cache, logs ou preview.
        nonce = secrets.token_urlsafe(24)
        self._pending = Preview(
            nonce, host, ssid_id, desired, before, time.monotonic()
        )
        return {"operation": "ssid_basic", "model": "F6201B",
                "firmware": firmware, "ssid_id": ssid_id,
                "changes": changes,
                "nonce": nonce, "expires_in_seconds": PREVIEW_TTL,
                "warning": ("EXPERIMENTAL: POST Apply não foi observado "
                            "na captura. Mantenha acesso local à ONT.")}

    def apply(self, zte, *, host: str, firmware: str,
              nonce: str, confirmation: str, original_post) -> dict:
        proposal = self._pending
        # Consome inclusive tentativa inválida: evitar replay involuntário.
        self.clear()
        if not self.opted_in() or firmware != EXACT_FIRMWARE:
            raise PermissionError("Escrita experimental não autorizada.")
        if confirmation != "APLICAR F6201B":
            raise PermissionError("Confirmação explícita obrigatória.")
        if not proposal or not secrets.compare_digest(proposal.nonce, str(nonce)):
            raise PermissionError("Prévia ausente ou inválida.")
        if (proposal.host != host or
                time.monotonic() - proposal.created_at > PREVIEW_TTL):
            raise PermissionError("Sessão ou prévia expirou; refaça o diagnóstico.")
        if original_post is None:
            raise PermissionError("Transporte de escrita não foi preservado.")
        aps, _ = self._inspect_session(zte)
        current = next((ap for ap in aps
                        if ap.get("_InstID") == proposal.ssid_id), None)
        if current is None:
            raise RuntimeError("SSID não está mais disponível.")
        now = {"ssid": current.get("ESSID", ""),
               "enabled": current.get("Enable") == "1",
               "broadcast": current.get("ESSIDHideEnable") != "1"}
        if now != proposal.previous:
            raise RuntimeError("Estado da rede mudou após a prévia. Refaça.")
        # Lock pertence ao service principal. Nunca habilitar globalmente:
        # restaura o bloqueio do transport em bloco finally.
        blocked_post = zte.session.post
        prior_enabled = getattr(zte, "writes_enabled", False)
        try:
            zte.session.post = original_post
            zte.writes_enabled = True
            # Reuso da rotina atual: read-modify-write, RSA/Check quando
            # disponível, e releitura obrigatória dos campos alterados.
            result = zte_wifi.set_ssid_config(
                zte, proposal.ssid_id, proposal.config
            )
        finally:
            zte.writes_enabled = prior_enabled
            zte.session.post = blocked_post
        return {
            "success": bool(result.get("success")),
            "verified": bool(result.get("verified")),
            "ssid_id": proposal.ssid_id,
            "changed": sorted(proposal.config),
            "experimental": True,
        }

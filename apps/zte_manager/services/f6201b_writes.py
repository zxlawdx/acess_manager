"""F6201B captured SSID operations on a native authenticated router session.

The operator action starts one internal validation and captured Apply.
Only the identified firmware and its actual XML form permit a write.
Router auth, credentials preservation and readback remain mandatory.
"""

from __future__ import annotations

import re
import secrets
import hashlib
import time
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from typing import Any

from apps.zte_manager.model.zte_configuration import zte_wifi, zte_security


EXACT_FIRMWARE = "V9.3.10P7N7"
OPT_IN_ENV = "ZTE_F6201B_EXPERIMENTAL_WRITES"
SAFE_FIELDS = frozenset({"ssid", "enabled", "broadcast", "password", "isolation", "max_clients"})
PREVIEW_TTL = 120


@dataclass
class Preview:
    nonce: str
    host: str
    ssid_id: str
    config: dict[str, Any]
    previous: dict[str, Any]
    created_at: float
    psk_hash: str | None = None


class ExperimentalF6201BWrites:
    """Serviço transitório; zte_service mantém exclusão mútua por RLock."""

    def __init__(self):
        self._pending: Preview | None = None

    @staticmethod
    def opted_in() -> bool:
        # Deprecated compatibility field: the connected ONT, not an app-level
        # environment/employee gate, decides supported operations.
        return True

    @staticmethod
    def capabilities(firmware: str | None = None) -> dict:
        eligible = firmware == EXACT_FIRMWARE
        return {
            "model": "F6201B",
            "firmware": firmware,
            "supported_firmware": eligible,
            "operations": [{
                "id": "ssid_basic",
                "label": "SSID: nome, senha, ativação, isolamento e clientes",
                "fields": sorted(SAFE_FIELDS),
                "experimental": True,
                "risk": "Alterar ou desligar SSID pode interromper sua conexão Wi-Fi.",
            }],
            "capture_evidence": (
                "GET e POST Apply observados na segunda captura enviada; "
                "a compatibilidade do adaptador deve ser verificada em "
                "releitura do equipamento"
            ),
            "requires": [
                "firmware mapeado e sessão aceita pelo próprio equipamento",
                "menuView e token temporário reais",
                "mapeamento atual de SSID/PSK confirmado no dispositivo",
                "Apply reproduz a ordem dos campos da captura validada",
            ],
            "note": (
                "SSID possui seu editor próprio; demais formulários capturados "
                "usam estratégias específicas do gerenciamento avançado."
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
            elif key == "password":
                if not isinstance(value, str) or not 8 <= len(value) <= 63:
                    raise ValueError("A senha Wi-Fi deve ter 8 a 63 caracteres.")
                if not value.isascii() or any(ord(char) < 32 for char in value):
                    raise ValueError("A senha Wi-Fi contém caracteres inválidos.")
                normalized[key] = value
            elif key == "max_clients":
                if type(value) is not int or not 1 <= value <= 64:
                    raise ValueError("Número de clientes deve estar entre 1 e 64.")
                normalized[key] = value
            else:
                if type(value) is not bool:
                    raise ValueError(key + " deve ser verdadeiro ou falso.")
                normalized[key] = value
        return normalized

    @staticmethod
    def list_ssids(zte) -> list[dict]:
        # Leitura direta observada na captura; não executar POST, nem
        # retornar os objetos PSK, cookies ou quaisquer credenciais.
        # A captura mostra wlanBasic menuView ANTES de menuData.
        # Sem esse contexto, o equipamento devolve menu vazio mesmo
        # autenticado (também causava zero leituras no diagnóstico).
        zte.get_view("wlanBasic", Menu3Location=0)
        raw = zte.get_menu("wlan_wlansssidconf_lua.lua")
        if not isinstance(raw, str):
            raise RuntimeError("Resposta de SSID não está em XML.")
        root = ET.fromstring(raw)
        if (root.tag != "ajax_response_xml_root" or
                (root.findtext("IF_ERRORID") or "0").strip() != "0"):
            raise RuntimeError("Firmware recusou a listagem de SSIDs.")
        aps = zte._parse_instances(raw).get("OBJ_WLANAP_ID", [])
        return [
            {
                "id": ap.get("_InstID"),
                "ssid": ap.get("ESSID") or "",
                "enabled": ap.get("Enable") == "1",
                "broadcast": ap.get("ESSIDHideEnable") != "1",
                "isolation": ap.get("VapIsolationEnable") == "1",
                "max_clients": int(ap.get("MaxUserNum") or 32),
                "band": ap.get("WLANViewName") or "",
            }
            for ap in aps if ap.get("_InstID")
        ]

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
        return aps, raw

    @staticmethod
    def _ensure_psk_preservable(zte, ap: dict, raw: str):
        """Não tocar SSID protegido se o segredo atual não for legível.

        O método de escrita legado reconstrói o formulário incluindo a PSK,
        mesmo ao modificar apenas ESSID/Enable. Sem esta prova específica
        há risco de gravar string vazia ou ciphertext como nova senha.
        """
        if ap.get("BeaconType") in ("None", "", None):
            return
        psks = zte._parse_instances(raw).get("OBJ_WLANPSK_ID", [])
        psk = zte_wifi._map_psk_by_ap(psks).get(ap["_InstID"])
        if not psk or not psk.get("KeyPassphrase"):
            raise RuntimeError(
                "Senha atual indisponível; não alterar rede protegida."
            )
        # Para este caminho experimental, exigir o formato criptografado
        # conhecido do adaptador existente em vez de supor plaintext.
        if "KeyPassphrase" not in zte_wifi._get_encode_fields(raw):
            raise RuntimeError(
                "A resposta não confirmou o formato de criptografia da PSK. "
                "Capture somente o metadado encode e o fluxo Apply."
            )
        token = getattr(zte, "session_tmp_token", None)
        if not token:
            raise RuntimeError("Token de descriptografia não encontrado.")
        try:
            clear = zte_security.aes_decrypt_value(
                psk["KeyPassphrase"], token, token[::-1]
            )
            if (not isinstance(clear, str)
                    or not 8 <= len(clear) <= 63
                    or not clear.isascii()):
                raise ValueError("PSK inválida")
        except Exception as exc:
            raise RuntimeError(
                "Não foi possível confirmar a preservação da senha atual."
            ) from None
        # Não registrar, persistir nem retornar o valor descriptografado.
        del clear

    def preview(self, zte, *, host: str, firmware: str,
                ssid_id: str, config: dict) -> dict:
        self.clear()
        if firmware != EXACT_FIRMWARE:
            raise PermissionError("Somente F6201B firmware V9.3.10P7N7.")
        if not isinstance(ssid_id, str) or not re.fullmatch(
            r"DEV\.WIFI\.AP\d+", ssid_id
        ):
            raise ValueError("ID de SSID inválido.")
        desired = self._validate_config(config)
        aps, raw = self._inspect_session(zte)
        current = next((ap for ap in aps if ap.get("_InstID") == ssid_id), None)
        if not current:
            raise ValueError("SSID não encontrado na leitura atual.")
        self._ensure_psk_preservable(zte, current, raw)
        if "password" in desired and current.get("BeaconType") in ("None", "", None, "Basic"):
            raise ValueError(
                "Troca de senha exige SSID WPA/WPA2/WPA3 com PSK existente. "
                "Altere primeiro o modo de segurança na interface original."
            )
        before = {
            "ssid": current.get("ESSID", ""),
            "enabled": current.get("Enable") == "1",
            "broadcast": current.get("ESSIDHideEnable") != "1",
            "isolation": current.get("VapIsolationEnable") == "1",
            "max_clients": int(current.get("MaxUserNum") or 32),
        }
        changes = {
            key: ({"before": "********", "after": "********"}
                  if key == "password" else
                  {"before": before[key], "after": value})
            for key, value in desired.items()
            if key == "password" or value != before[key]
        }
        if not changes:
            raise ValueError("Nenhuma diferença encontrada.")
        # Não colocar credenciais em cache, logs ou preview.
        nonce = secrets.token_urlsafe(24)
        fingerprint = None
        if "password" in desired:
            psks = zte._parse_instances(raw).get("OBJ_WLANPSK_ID", [])
            psk = zte_wifi._map_psk_by_ap(psks).get(ssid_id)
            if not psk or not psk.get("KeyPassphrase"):
                raise RuntimeError("A rede não retornou PSK para troca de senha.")
            fingerprint = hashlib.sha256(
                psk["KeyPassphrase"].encode("utf-8")
            ).hexdigest()
        self._pending = Preview(
            nonce, host, ssid_id, desired, before, time.monotonic(), fingerprint
        )
        return {"operation": "ssid_basic", "model": "F6201B",
                "firmware": firmware, "ssid_id": ssid_id,
                "changes": changes,
                "nonce": nonce, "expires_in_seconds": PREVIEW_TTL,
                "warning": ("POST Apply de SSID foi documentado na captura, "
                            "mas ainda exige verificação física e acesso local.")}

    def apply_changes(self, zte, *, host: str, firmware: str,
                      ssid_id: str, config: dict, original_post) -> dict:
        """Single operator click, preserving captured preflight/PSK protection."""
        proposal = self.preview(
            zte, host=host, firmware=firmware,
            ssid_id=ssid_id, config=config
        )
        return self.apply(
            zte, host=host, firmware=firmware,
            nonce=proposal["nonce"], confirmation="",
            original_post=original_post,
        )

    def apply(self, zte, *, host: str, firmware: str,
              nonce: str, confirmation: str, original_post) -> dict:
        proposal = self._pending
        # Consome inclusive tentativa inválida: evitar replay involuntário.
        self.clear()
        if firmware != EXACT_FIRMWARE:
            raise PermissionError("Escrita experimental não autorizada.")
        if not proposal or not secrets.compare_digest(proposal.nonce, str(nonce)):
            raise PermissionError("Prévia ausente ou inválida.")
        if (proposal.host != host or
                time.monotonic() - proposal.created_at > PREVIEW_TTL):
            raise PermissionError("Sessão ou prévia expirou; refaça o diagnóstico.")
        if original_post is None:
            raise PermissionError("Transporte de escrita não foi preservado.")
        aps, raw = self._inspect_session(zte)
        current = next((ap for ap in aps
                        if ap.get("_InstID") == proposal.ssid_id), None)
        if current is None:
            raise RuntimeError("SSID não está mais disponível.")
        self._ensure_psk_preservable(zte, current, raw)
        now = {"ssid": current.get("ESSID", ""),
               "enabled": current.get("Enable") == "1",
               "broadcast": current.get("ESSIDHideEnable") != "1",
               "isolation": current.get("VapIsolationEnable") == "1",
               "max_clients": int(current.get("MaxUserNum") or 32)}
        if proposal.psk_hash:
            psks = zte._parse_instances(raw).get("OBJ_WLANPSK_ID", [])
            psk = zte_wifi._map_psk_by_ap(psks).get(proposal.ssid_id)
            fingerprint = hashlib.sha256(
                (psk or {}).get("KeyPassphrase", "").encode("utf-8")
            ).hexdigest()
            if not secrets.compare_digest(fingerprint, proposal.psk_hash):
                raise RuntimeError("A PSK foi alterada após a prévia.")
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
                zte, proposal.ssid_id, proposal.config,
                captured_f6201b=True
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

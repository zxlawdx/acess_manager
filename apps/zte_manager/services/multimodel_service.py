"""Descoberta conservadora e somente leitura para famílias ZTE.

Perfis inspirados na documentação pública do juacas/zte_tracker; esta é uma
implementação independente. O nome do modelo sugere candidatos, mas somente
uma resposta XML válida confirma o endpoint e nenhum POST é feito aqui.
A família Vue exige uma implementação de autenticação separada.
"""

from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class ReadEndpoint:
    view: str
    tag: str
    root: str
    params: tuple[tuple[str, str], ...] = ()


# Protocolos conhecidos por família, não garantias por firmware/operadora.
FAMILY: dict[str, dict[str, ReadEndpoint]] = {
    "f6640": {
        "wifi_clients": ReadEndpoint("localNetStatus", "wlan_client_stat_lua.lua", "OBJ_WLAN_AD_ID"),
        "lan_clients": ReadEndpoint("localNetStatus", "accessdev_landevs_lua.lua", "OBJ_ACCESSDEV_ID"),
        "wan": ReadEndpoint(
            "ethWanStatus", "wan_internetstatus_lua.lua", "ID_WAN_COMFIG",
            (("TypeUplink", "2"), ("pageType", "1")),
        ),
    },
    "h288a": {
        "wifi_clients": ReadEndpoint("localNetStatus", "accessdev_ssiddev_lua.lua", "OBJ_ACCESSDEV_ID"),
        "lan_clients": ReadEndpoint("localNetStatus", "accessdev_landevs_lua.lua", "OBJ_ACCESSDEV_ID"),
        "wan": ReadEndpoint(
            "ethWanStatus", "wan_internetstatus_lua.lua", "ID_WAN_COMFIG",
            (("TypeUplink", "2"), ("pageType", "1")),
        ),
    },
    "h388x": {
        "wifi_clients": ReadEndpoint("localNetStatus", "accessdev_ssiddev_lua.lua", "OBJ_ACCESSDEV_ID"),
        "lan_clients": ReadEndpoint("localNetStatus", "accessdev_landevs_lua.lua", "OBJ_ACCESSDEV_ID"),
        "wan": ReadEndpoint(
            "ethWanStatus", "wan_internet_lua.lua", "ID_WAN_COMFIG",
            (("TypeUplink", "2"), ("pageType", "1")),
        ),
    },
    "h2640": {
        "wifi_clients": ReadEndpoint("localNetStatus", "accessdev_ssiddev_lua.lua", "OBJ_ACCESSDEV_ID"),
        "lan_clients": ReadEndpoint("localNetStatus", "accessdev_landevs_lua.lua", "OBJ_ACCESSDEV_ID"),
        "dsl": ReadEndpoint("dslWanStatus", "dsl_interface_status_lua.lua", "OBJ_DSLINTERFACE_ID"),
    },
    "vue": {},  # Não enviar menus ThinkLua a um firmware Vue.
}

MODEL_FAMILY = {
    "F6640": "f6640", "F6645P": "f6640", "F680": "f6640",
    "F6600P": "f6640", "F8748": "f6640",
    "H169A": "h288a", "H288A": "h288a", "H3600P": "h288a",
    "H3640": "h288a", "H6645P": "h288a", "H6745": "h288a",
    "H388X": "h388x", "H2640": "h2640",
    "E2631": "vue", "SR7410": "vue",
}

# Não armazenar respostas XML nem campos de clientes no relatório estrutural.
SENSITIVE_NAME = re.compile(
    r"(password|passwd|secret|token|credential|key|serial|mac|ssid|"
    r"host|ipaddress|imei|username|name)", re.I
)


def normalize_model(value: str | None) -> str:
    return re.sub(r"[^A-Z0-9]", "", (value or "").upper())


def find_family(model: str | None) -> tuple[str | None, str | None]:
    candidate = normalize_model(model)
    # Mais específico primeiro: H6645P antes de outros nomes parciais.
    for key in sorted(MODEL_FAMILY, key=len, reverse=True):
        if key in candidate:
            return key, MODEL_FAMILY[key]
    return None, None


def catalog() -> dict[str, Any]:
    return {
        "models": [
            {
                "model": model,
                "family": family,
                "protocol": "vue" if family == "vue" else "thinklua",
                "discovery": (
                    "separate_auth_required" if family == "vue"
                    else "read_only_probe"
                ),
            }
            for model, family in MODEL_FAMILY.items()
        ],
        "notes": (
            "O catálogo mostra candidatos documentados pelo zte_tracker, "
            "não valida compatibilidade de cada firmware. Probe é somente leitura."
        ),
    }


def _shape(xml: str, expected_root: str) -> dict[str, Any]:
    if not xml or "SessionTimeout" in xml or "login_need_refresh" in xml:
        raise RuntimeError("Sessão expirada ou resposta vazia")

    root = ET.fromstring(xml)
    if root.tag != "ajax_response_xml_root":
        raise RuntimeError("Resposta não é XML ThinkLua")

    error = (root.findtext("IF_ERRORSTR") or "").strip()
    if error and error.upper() not in {"SUCC", "SUCCESS", "0"}:
        raise RuntimeError("Firmware não disponibilizou este menu")

    result = {}
    for node in root:
        if not (node.tag.startswith(("OBJ_", "ID_"))):
            continue
        instances = node.findall("Instance")
        fields = set()
        for instance in instances:
            children = list(instance)
            for i, child in enumerate(children[:-1]):
                if child.tag == "ParaName":
                    field = (child.text or "").strip()
                    if field and not SENSITIVE_NAME.search(field):
                        fields.add(field)
        result[node.tag] = {"records": len(instances), "fields": sorted(fields)}

    # Menus podem retornar 0 clientes: objeto vazio ainda é evidência de suporte.
    if expected_root not in result:
        raise RuntimeError("Objeto esperado não encontrado no firmware")

    return result


def probe(zte, model: str, *, max_endpoints: int = 4) -> dict[str, Any]:
    selected, family = find_family(model)
    if family is None:
        return {
            "model": model, "supported": False, "read_only": True,
            "reason": "Modelo sem perfil cadastrado; sem tentativa às cegas.",
            "endpoints": {},
        }

    if family == "vue":
        return {
            "model": selected, "family": family, "supported": False,
            "read_only": True, "reason": (
                "Este equipamento usa API Vue; a autenticação ThinkLua "
                "atual não é compatível. Nenhum menu foi consultado."
            ), "endpoints": {},
        }

    endpoints = {}
    for name, endpoint in list(FAMILY[family].items())[:max(1, min(max_endpoints, 4))]:
        try:
            zte.get_view(endpoint.view, Menu3Location=0)
            xml = zte.get_menu(endpoint.tag, **dict(endpoint.params))
            # Faz a validação local mesmo quando implementação de ZTE mudar.
            endpoints[name] = {
                "available": True,
                "structure": _shape(xml, endpoint.root),
                "tag": endpoint.tag,
            }
        except Exception as exc:
            # Não expor HTML, tokens ou payloads fornecidos pelo firmware.
            endpoints[name] = {
                "available": False,
                "error_type": type(exc).__name__,
                "tag": endpoint.tag,
            }

    return {
        "model": selected, "family": family, "read_only": True,
        "supported": any(x["available"] for x in endpoints.values()),
        "endpoints": endpoints,
        "notes": "Somente descoberta; escrita e backup requerem validação por firmware.",
    }

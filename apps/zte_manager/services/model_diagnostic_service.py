"""Diagnóstico seguro por família de firmware ZTE.

A sessão já deve estar autenticada. Apenas operações GET: não reutiliza
AutomaticDiagnosticService, que dispara ping/traceroute via POST no roteador.
Não equiparar DSL sincronizada a Internet, nem HTTP 200 a menu disponível.
"""

from __future__ import annotations

import xml.etree.ElementTree as ET
from typing import Any

from apps.zte_manager.services import multimodel_service as models


# Campos estritamente selecionados para não exportar IP, MAC ou credenciais.
WAN_FIELDS = {
    "ConnStatus": "status",
    "WANCName": "name",
    "TransType": "transport",
    "UpTime": "uptime_seconds",
    "RxBytes": "rx_bytes",
    "TxBytes": "tx_bytes",
    "RxPackets": "rx_packets",
    "TxPackets": "tx_packets",
    "RxError": "rx_errors",
    "TxError": "tx_errors",
}
DSL_FIELDS = {
    "Status": "line_status",
    "Upstream_current_rate": "upstream_kbps",
    "Downstream_current_rate": "downstream_kbps",
    "Upstream_noise_margin": "upstream_margin_db",
    "Downstream_noise_margin": "downstream_margin_db",
    "Upstream_attenuation": "upstream_attenuation_db",
    "Downstream_attenuation": "downstream_attenuation_db",
    "CurrentProfile": "dsl_profile",
}
HEALTH_FIELDS = {
    "ModelName": "model",
    "HardwareVer": "hardware",
    "SoftwareVer": "firmware",
    "PowerOnTime": "uptime_seconds",
    "CpuUsage1": "cpu",
    "MemUsage": "memory",
}
# Informações de fibra apenas em famílias documentadas com essa consulta.
PON_OPTICAL = models.ReadEndpoint(
    "ponopticalinfo", "optical_info_lua.lua",
    "OBJ_PON_OPTICALPARA_ID",
)


def _instances(raw: str, root_name: str) -> list[dict[str, str]]:
    models._shape(raw, root_name)  # valida XML, erro do firmware e raiz esperada
    root = ET.fromstring(raw)
    records: list[dict[str, str]] = []
    for entry in root.findall(f"{root_name}/Instance"):
        data: dict[str, str] = {}
        children = list(entry)
        for i in range(0, len(children) - 1, 2):
            if children[i].tag == "ParaName" and children[i + 1].tag == "ParaValue":
                key = (children[i].text or "").strip()
                if key:
                    data[key] = children[i + 1].text or ""
        records.append(data)
    return records


def _whitelist(raw: str, root: str, fields: dict[str, str], limit: int = 8):
    records = _instances(raw, root)
    return [
        {rename: item[field] for field, rename in fields.items() if field in item}
        for item in records[:limit]
    ]


def _read(zte, endpoint: models.ReadEndpoint, fields: dict[str, str], limit=8):
    raw = models._fetch(zte, endpoint)
    return _whitelist(raw, endpoint.root, fields, limit)


def _result(name: str, reader):
    try:
        return {"available": True, "data": reader()}
    except Exception as exc:
        # Não propagar texto da ONT: exceções HTTP podem conter credenciais.
        return {"available": False, "error_type": type(exc).__name__}


def diagnostic(zte, model: str, *, include_clients: bool = True) -> dict[str, Any]:
    selected, family = models.find_family(model)
    if family is None:
        return {
            "model": selected, "family": None, "read_only": True,
            "supported": False,
            "reason": "Perfil desconhecido: nenhum endpoint será consultado.",
            "sections": {},
        }
    endpoints = models.FAMILY[family]
    sections = {}

    # A ordem é intencional: o firmware depende de menu/contexto e
    # requisições consecutivas (não paralelas) dentro da sessão atual.
    if family != "vue":
        health = models.ReadEndpoint(
            "statusMgr", "devmgr_statusmgr_lua.lua", "OBJ_DEVINFO_ID",
        )
        sections["device"] = _result(
            "device",
            lambda: _read(zte, health, HEALTH_FIELDS, limit=1),
        )

    status_endpoint = endpoints.get("wan") or endpoints.get("dsl")
    if status_endpoint:
        section = "dsl" if family == "h2640" else "wan"
        fields = DSL_FIELDS if section == "dsl" else WAN_FIELDS
        sections[section] = _result(
            section,
            lambda: _read(zte, status_endpoint, fields),
        )

    if selected == "F6600P":
        sections["optical"] = _result(
            "optical",
            lambda: _read(
                zte, PON_OPTICAL,
                {"RxPower": "rx_power", "TxPower": "tx_power",
                 "Temp": "temperature"},
                limit=1,
            ),
        )

    if include_clients:
        for name in ("wifi_clients", "lan_clients"):
            endpoint = endpoints.get(name)
            if endpoint:
                # Para o relatório geral, apenas contagens de dispositivos:
                # hostname, SSID, IP e MAC permanecem na tela local Clientes.
                sections[name] = _result(
                    name,
                    lambda e=endpoint: {
                        "connected": len(
                            _instances(models._fetch(zte, e), e.root)
                        )
                    },
                )

    return {
        "model": selected, "family": family, "read_only": True,
        "supported": any(item["available"] for item in sections.values()),
        "sections": sections,
        "notes": (
            "Status DSL é sincronismo, não prova conectividade Internet. "
            "Resultado parcial por firmware; não executar escrita."
        ) if family == "h2640" else (
            "Leitura parcial por firmware; WAN/GPON podem variar por operadora."
        ),
    }

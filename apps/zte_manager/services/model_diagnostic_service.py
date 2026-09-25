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

# Campos efetivamente registrados no F6201B V9.3.10P7N7.
# Whitelist explícita: nunca ler senhas, ESSID, IP/MAC de clientes,
# ACS URL, usuários ou dados telefônicos no relatório do atendimento.
F6201B_FIELDS = {
    "wifi_radios": {"Band": "band", "RadioStatus": "radio_status"},
    "lan_ports": {"_InstID": "port", "Status": "status", "Speed": "speed",
                  "Duplex": "duplex", "InError": "rx_errors",
                  "OutError": "tx_errors"},
    "band_steering": {"BsEnable": "enabled"},
    "wps": {"Enable": "enabled", "WPSMode": "mode"},
    "mesh": {"Enable": "enabled", "Mode": "mode"},
    "dns": {"SerIPAddress1": "dns_ipv4_1", "SerIPAddress2": "dns_ipv4_2",
            "SerIPv6Address1": "dns_ipv6_1", "SerIPv6Address2": "dns_ipv6_2"},
    "dhcp": {"ServerEnable": "enabled", "LeaseTime": "lease_seconds",
             "DnsServerSource": "dns_origin"},
    "firewall": {"Enable": "enabled", "Level": "level"},
    "voip_status": {"IsOnline": "online", "VoIPRegStatus": "registration"},
    "tr069_status": {"PeriodicInformEnable": "inform_enabled",
                     "PeriodicInformInterval": "inform_interval"},
    "upnp": {"EnableUPnPIGD": "enabled"},
    "wifi_schedule": {"TimerEnable": "enabled"},
    "ping_history": {"DiagnosticsState": "state",
                     "AverageResponseTime": "average_ms",
                     "FailureCount": "failures", "SuccessCount": "successes"},
    "traceroute_history": {"DiagnosticsState": "state",
                           "NumberOfPRouteHops": "hops"},
}
F6201B_COUNTS_ONLY = {"dhcp_leases", "arp", "route_table"}

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
        data = reader()
        # Um HTTP 200 / XML válido sem instâncias não é evidência de que
        # o diagnóstico trouxe dados. Contagem 0 de clientes é legítima.
        if isinstance(data, list):
            populated = bool(data)
        elif isinstance(data, dict):
            populated = (
                "connected" in data
                or "ssid_total" in data
                or any(bool(value) for value in data.values())
            )
        else:
            populated = data is not None
        return {
            "available": populated,
            "data": data,
            "reason": None if populated else "no_data_from_firmware",
        }
    except Exception as exc:
        # Categorias seguras ajudam a distinguir falha de sessão, menu
        # incompatível e timeout. NUNCA enviar mensagem HTTP/XML da ONT:
        # ela pode conter sessão, senhas ou dados dos assinantes.
        kind = type(exc).__name__
        message = str(exc).lower()
        if "sessão expirada" in message or "sessiontimeout" in message:
            reason = "session_expired"
        elif "objeto esperado" in message:
            reason = "unexpected_xml_object"
        elif kind in {"Timeout", "ReadTimeout", "ConnectTimeout"}:
            reason = "network_timeout"
        elif kind == "ParseError" or "não é xml" in message:
            reason = "invalid_xml"
        else:
            reason = "read_failed"
        return {
            "available": False,
            "reason": reason,
            "error_type": kind,
        }


def device_resource_details(zte) -> dict[str, Any]:
    """Objetos separados, conforme devmgr_statusmgr_lua.lua no tracker."""
    raw = models._fetch(
        zte,
        models.ReadEndpoint(
            "statusMgr", "devmgr_statusmgr_lua.lua", "OBJ_DEVINFO_ID"
        ),
    )
    result = {
        "identity": _whitelist(
            raw, "OBJ_DEVINFO_ID", HEALTH_FIELDS, limit=1
        ),
        "resources": _whitelist(
            raw, "OBJ_CPUMEMUSAGE_ID",
            {"CpuUsage1": "cpu1", "CpuUsage2": "cpu2",
             "CpuUsage3": "cpu3", "CpuUsage4": "cpu4",
             "MemUsage": "memory_percent"},
            limit=1,
        ) if "OBJ_CPUMEMUSAGE_ID" in raw else [],
        "uptime": _whitelist(
            raw, "OBJ_POWERONTIME_ID",
            {"PowerOnTime": "seconds"}, limit=1,
        ) if "OBJ_POWERONTIME_ID" in raw else [],
    }
    return result


def optical_details(zte, endpoint=PON_OPTICAL) -> dict[str, Any]:
    """PON opt-in F6600P. Não supor unidade para campos desconhecidos."""
    raw = models._fetch(zte, endpoint)
    data = {
        "optical": _whitelist(
            raw, endpoint.root,
            {"RxPower": "rx_power_raw", "TxPower": "tx_power_raw",
             "Temp": "temperature_raw", "Volt": "voltage_raw",
             "Current": "current_raw"},
            limit=1,
        )
    }
    if "OBJ_LOS_INFO_ID" in raw:
        los = _instances(raw, "OBJ_LOS_INFO_ID")
        data["loss_of_signal"] = [
            item.get("LosInfo") != "0"
            for item in los if "LosInfo" in item
        ][:1]
    if "OBJ_GPONREGSTATUS_ID" in raw:
        reg = _instances(raw, "OBJ_GPONREGSTATUS_ID")
        data["registration"] = [
            {"state": item["RegStatus"]}
            for item in reg if "RegStatus" in item
        ][:1]
    return data


def wifi_ssid_summary(zte, endpoint: models.ReadEndpoint) -> dict[str, Any]:
    """Somente contagens das redes ativas por banda, sem ESSID/senhas."""
    raw = models._fetch(zte, endpoint)
    access_points = _instances(raw, "OBJ_WLANAP_ID")
    return {
        "ssid_total": len(access_points),
        "ssid_enabled": sum(item.get("Enable") == "1" for item in access_points),
    }


def diagnostic(
    zte, model: str, *, include_clients: bool = True,
    section: str | None = None,
) -> dict[str, Any]:
    """Consulta completa ou uma seção por requisição para UI progressiva."""
    supported_sections = {
        "device", "wan", "dsl", "optical", "wifi_ssids",
        "wifi_clients", "lan_clients",
        *F6201B_FIELDS, *F6201B_COUNTS_ONLY,
    }
    if section is not None and section not in supported_sections:
        raise ValueError("Seção de diagnóstico inválida")
    wants = lambda name: section is None or section == name
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
    if family != "vue" and wants("device"):
        sections["device"] = _result("device", lambda: device_resource_details(zte))

    status_endpoint = endpoints.get("wan") or endpoints.get("dsl")
    if status_endpoint:
        kind = "dsl" if family == "h2640" else "wan"
        fields = DSL_FIELDS if kind == "dsl" else WAN_FIELDS
        if wants(kind):
            sections[kind] = _result(
                kind,
                lambda: _read(zte, status_endpoint, fields),
            )

    if selected in {"F6600P", "F6201B"} and wants("optical"):
        sections["optical"] = _result(
            "optical",
            lambda: optical_details(zte, endpoints.get("pon_optical", PON_OPTICAL)),
        )

    if family in {"f6640", "f6201b_candidate"} and wants("wifi_ssids"):
        sections["wifi_ssids"] = _result(
            "wifi_ssids",
            lambda: wifi_ssid_summary(zte, endpoints["wifi_ssids"]),
        )

    if selected == "F6201B":
        # Campos reais do manifesto sanitizado. Sem captura em tempo real
        # aqui: status é confirmado novamente pelos GETs da sessão ativa.
        if wants("dhcp_leases"):
            endpoint = endpoints["dhcp_leases"]
            sections["dhcp_leases"] = _result(
                "dhcp_leases",
                lambda: {"leases": len(_instances(
                    models._fetch(zte, endpoint), endpoint.root))},
            )
        for name, fields in F6201B_FIELDS.items():
            if not wants(name):
                continue
            endpoint = endpoints[name]
            sections[name] = _result(
                name, lambda e=endpoint, f=fields: _read(zte, e, f, limit=16)
            )
        for name in F6201B_COUNTS_ONLY - {"dhcp_leases"}:
            if not wants(name):
                continue
            endpoint = endpoints[name]
            sections[name] = _result(
                name, lambda e=endpoint, k=name: {
                    "records": len(_instances(models._fetch(zte, e), e.root))
                }
            )

    if include_clients:
        for name in ("wifi_clients", "lan_clients"):
            # DHCP leases não significam dispositivos cabeados online.
            if selected == "F6201B" and name == "lan_clients":
                continue
            endpoint = endpoints.get(name)
            if endpoint and wants(name):
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
        "experimental": family == "f6201b_candidate",
        "supported": any(item["available"] for item in sections.values()),
        "sections": sections,
        "notes": (
            "Status DSL é sincronismo, não prova conectividade Internet. "
            "Resultado parcial por firmware; não executar escrita."
        ) if family == "h2640" else (
            "Leitura parcial por firmware; WAN/GPON podem variar por operadora."
        ),
    }

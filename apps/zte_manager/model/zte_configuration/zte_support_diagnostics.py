from __future__ import annotations

import re
import time
import xml.etree.ElementTree as ET
from typing import Any

from .zte_post import post_menu


def _number(value: Any) -> float | None:
    if value in (None, "", "NULL"):
        return None

    match = re.search(
        r"-?\d+(?:[.,]\d+)?",
        str(value),
    )

    if not match:
        return None

    return float(
        match.group(0).replace(",", ".")
    )


def _session_value(xml_text: str) -> str | None:
    """
    Alguns endpoints do dashboard AIS não usam OBJ_*/Instance para devolver o
    identificador do diagnóstico. Preservamos esse detalhe aqui, isolado do
    restante do domínio.
    """
    try:
        root = ET.fromstring(xml_text)
        node = root.find(".//SESSION_IDVALUE")

        if node is not None and node.text:
            return node.text.strip()
    except ET.ParseError:
        pass

    match = re.search(
        r"<SESSION_IDVALUE>(.*?)</SESSION_IDVALUE>",
        xml_text,
        re.DOTALL,
    )

    return (
        match.group(1).strip()
        if match
        else None
    )


def wifi_neighbor_scan(zte, band: str) -> dict[str, Any]:
    """
    Varre APs vizinhos usando o mesmo backend ThinkLua encontrado nas páginas
    Scan 2.4 GHz / Scan 5 GHz.

    O recurso varia por firmware. Tentamos as duas famílias de backend vistas
    em builds ZTE e falhamos de forma explícita para o DiagnosticEngine poder
    marcar somente esta coleta como indisponível.
    """
    normalized = str(band).lower()
    is_5g = "5" in normalized
    query_value = (
        "ScanAP5g"
        if is_5g
        else "ScanAP"
    )

    errors = []

    for view in (
        "wlanStaScanAP",
        "wlanBasic",
    ):
        try:
            zte.get_view(
                view,
                Menu3Location=0,
            )
        except Exception as error:
            errors.append(
                f"{view}: {error}"
            )
            continue

        for tag in (
            "tot_wlan_wlan_profile_lua.lua",
            "wlan_sta_wlan_profile_lua.lua",
            "wlan_wlan_profile_lua.lua",
        ):
            try:
                extras = {
                    "APGetFrom": query_value,
                }

                if zte.session_tmp_token:
                    extras["_sessionTOKEN"] = (
                        zte.session_tmp_token
                    )

                xml = zte.get_menu(
                    tag,
                    **extras,
                )

                zte._validar_resposta(xml)

                instances = (
                    zte._parse_instances(xml)
                    .get(
                        "OBJ_WLANGETNEBAP_ID",
                        [],
                    )
                )

                networks = []

                for item in instances:
                    signal = _number(
                        item.get("Signal")
                    )
                    noise = _number(
                        item.get("Noise")
                    )

                    networks.append({
                        "ssid": item.get("Essid") or "",
                        "bssid": item.get("MacAddr") or "",
                        "auth": item.get("AuthMode") or "",
                        "signal": signal,
                        "signal_raw": item.get("Signal"),
                        "noise": noise,
                        "noise_raw": item.get("Noise"),
                        "channel": _number(
                            item.get("Channel")
                        ),
                        "secondary_channel": _number(
                            item.get("ScndChannel")
                        ),
                        "dtim": item.get("DTIM"),
                        "beacon_interval": item.get(
                            "BeaconIntervel"
                        ),
                    })

                return {
                    "band": (
                        "5GHz"
                        if is_5g
                        else "2.4GHz"
                    ),
                    "available": True,
                    "backend": tag,
                    "networks": networks,
                }

            except Exception as error:
                errors.append(
                    f"{tag}: {error}"
                )

    raise RuntimeError(
        "Scan de redes vizinhas não disponível neste firmware/login. "
        + " | ".join(errors[-4:])
    )


def nslookup(
    zte,
    hostname: str,
    *,
    interface: str = "",
    server_ip: str = "",
    ip_version: str = "IPv4",
) -> dict[str, Any]:
    """Executa o NsLookup nativo do firmware e aguarda o resultado."""
    if not hostname:
        raise ValueError(
            "Informe um hostname para o DNS Lookup."
        )

    zte.get_view(
        "networkDiag",
        Menu3Location=0,
    )

    tag = "DiagnosisNsLookupReq_lua.lua"

    # A leitura inicial prepara os objetos e também confirma se este backend
    # existe no firmware antes de disparar o diagnóstico.
    initial = zte.get_menu(
        tag
    )

    zte._validar_resposta(
        initial
    )

    response = post_menu(
        zte,
        tag,
        [
            ("IF_ACTION", "NsLookupDiagnosis"),
            ("_InstID", "IGD.NSLOOKUP"),
            ("DiagnosticsState", "Requested"),
            ("Interface", interface),
            ("HostName", hostname),
            ("ServerIP", server_ip),
            ("Timeout", "1000"),
            ("NumberOfRepetitions", "1"),
            ("IPVersion", ip_version),
        ],
    )

    zte._validar_resposta(
        response
    )

    for attempt in range(4):
        xml = zte.get_menu(
            tag
        )

        zte._validar_resposta(
            xml
        )

        parsed = zte._parse_instances(
            xml
        )

        results = parsed.get(
            "OBJ_DEV_GETRESULT_NSLOOKUP_ID",
            [],
        )

        request = parsed.get(
            "OBJ_DEVNSLOOKUP_ID",
            [],
        )

        result = (
            results[0]
            if results
            else {}
        )

        addresses = str(
            result.get("IPAddresses")
            or ""
        ).strip()

        if addresses not in {
            "",
            "NULL",
        }:
            return {
                "success": True,
                "hostname": hostname,
                "hostname_returned": result.get(
                    "HostNameReturned"
                ),
                "addresses": addresses,
                "request": (
                    request[0]
                    if request
                    else {}
                ),
            }

        if attempt < 3:
            time.sleep(2)

    return {
        "success": False,
        "hostname": hostname,
        "addresses": "",
        "message": "O firmware concluiu o DNS Lookup sem endereço resolvido.",
    }


def native_speedtest_servers(zte) -> dict[str, Any]:
    """
    Descobre servidores do Speed Test nativo do dashboard AIS.

    Não presume que todo F670L possua esse dashboard. A ausência vira
    capability indisponível e permite fallback pelo computador do atendente.
    """
    zte.get_view(
        "homePage",
        Menu3Location=0,
    )

    tag = "home_ais_lua.lua"

    xml = zte.get_menu(
        tag,
        IF_ACTION="SetSpeedtestServer",
    )

    zte._validar_resposta(
        xml
    )

    session_id = _session_value(
        xml
    )

    if not session_id:
        raise RuntimeError(
            "O firmware não devolveu a sessão de descoberta do Speed Test."
        )

    for attempt in range(8):
        result_xml = zte.get_menu(
            tag,
            IF_ACTION="GetSpeedtestServer",
            sessionId=session_id,
        )

        zte._validar_resposta(
            result_xml
        )

        instances = (
            zte._parse_instances(result_xml)
            .get(
                "OBJ_SPEEDTEST_SERVERS_ID",
                [],
            )
        )

        if instances:
            data = instances[0]
            state = str(
                data.get("State")
                or ""
            )

            if state in {
                "1",
                "3",
            }:
                raise RuntimeError(
                    (
                        "O Speed Test nativo não alcançou o serviço de medição."
                        if state == "1"
                        else "O Speed Test nativo não encontrou rota para o serviço."
                    )
                )

            if state == "2":
                servers = []

                for index in range(15):
                    value = str(
                        data.get(
                            f"URL{index}"
                        )
                        or ""
                    ).strip()

                    if not value:
                        continue

                    name, separator, url = value.partition("@")

                    servers.append({
                        "name": (
                            name
                            if separator
                            else value
                        ),
                        "url": (
                            url
                            if separator
                            else value
                        ),
                    })

                if not servers:
                    raise RuntimeError(
                        "O firmware anunciou Speed Test, mas não retornou servidores."
                    )

                return {
                    "session_id": session_id,
                    "servers": servers,
                }

        if attempt < 7:
            time.sleep(2)

    raise TimeoutError(
        "A ONT não finalizou a descoberta de servidores do Speed Test."
    )


def native_speedtest(
    zte,
    *,
    server_url: str | None = None,
) -> dict[str, Any]:
    """Executa upload/download diretamente da ONT quando o firmware suporta."""
    discovery = native_speedtest_servers(
        zte
    )

    servers = discovery[
        "servers"
    ]

    selected = next((
        item
        for item in servers
        if (
            server_url
            and item["url"] == server_url
        )
    ), servers[0])

    tag = "home_ais_lua.lua"

    zte.get_view(
        "homePage",
        Menu3Location=0,
    )

    response = post_menu(
        zte,
        tag,
        [
            ("IF_ACTION", "SpeedtestDIAG"),
            ("Url", selected["url"]),
        ],
        IF_ACTION="SpeedtestDIAG",
        Url=selected["url"],
    )

    session_id = _session_value(
        response
    )

    if not session_id:
        raise RuntimeError(
            "A ONT iniciou o Speed Test sem devolver o identificador da execução."
        )

    latest = {}

    for attempt in range(120):
        xml = zte.get_menu(
            tag,
            IF_ACTION="SpeedtestGetDIAG",
            sessionId=session_id,
        )

        zte._validar_resposta(
            xml
        )

        instances = (
            zte._parse_instances(xml)
            .get(
                "OBJ_SPEEDTEST_DIAGNOSE_ID",
                [],
            )
        )

        if instances:
            latest = instances[0]
            state = str(
                latest.get("State")
                or "0"
            )

            if state != "0":
                return {
                    "success": True,
                    "source": "ont_native",
                    "server": selected,
                    "state": state,
                    "upload_mbps": _number(
                        latest.get("UpRate")
                    ),
                    "download_mbps": _number(
                        latest.get("DownRate")
                    ),
                    "progress": _number(
                        latest.get("Percntage")
                    ),
                    "raw": latest,
                }

        if attempt < 119:
            time.sleep(1)

    raise TimeoutError(
        "O Speed Test nativo não terminou em 120 segundos."
    )

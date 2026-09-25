"""Native F6201B ping/traceroute using only captured ThinkLua form fields."""
import ipaddress
import re
import time
import xml.etree.ElementTree as ET
from apps.zte_manager.model.zte_configuration.zte_post import post_menu
from apps.zte_manager.services.f6201b_evidence import OBSERVED_DIAGNOSTIC_ACTIONS

PING = "networkdiag_ping_lua.lua"
TRACE = "networkdiag_traceroute_lua.lua"
ROOTS = {PING: "OBJ_DEVPING_ID", TRACE: "OBJ_TRACERT_ID"}


def read(zte, tag, view=False):
    if view:
        zte.get_view("networkDiag", Menu3Location=0)
    xml = zte.get_menu(tag)
    root = ET.fromstring(xml)
    if root.tag != "ajax_response_xml_root" or root.findtext("IF_ERRORID") != "0":
        raise RuntimeError("A ONT não confirmou a leitura de diagnóstico.")
    if ROOTS[tag] not in xml:
        raise RuntimeError("O firmware não disponibiliza " + tag)
    return zte._parse_instances(xml).get(ROOTS[tag], [])


def host_name(value):
    value = str(value or "").strip()
    if not value or len(value) > 253 or any(c.isspace() for c in value):
        raise ValueError("Destino inválido.")
    try:
        ipaddress.ip_address(value)
    except ValueError:
        if not all(re.fullmatch(
            r"[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?", part
        ) for part in value.rstrip(".").split(".")):
            raise ValueError("Domínio inválido.")
    return value


def bounded(value, name, low, high):
    try:
        n = int(value)
    except (TypeError, ValueError):
        raise ValueError(name + " exige um inteiro.") from None
    if str(value).strip() != str(n) or not low <= n <= high:
        raise ValueError(name + " fora do intervalo permitido.")
    return str(n)


def post(zte, original_post, tag, fields):
    if original_post is None:
        raise RuntimeError("Transporte autenticado não encontrado.")
    schema = OBSERVED_DIAGNOSTIC_ACTIONS[tag]
    body = [(key, fields[key]) for key in schema if key != "_sessionTOKEN"]
    old_post = zte.session.post
    old_enabled = getattr(zte, "writes_enabled", False)
    try:
        zte.session.post = original_post
        zte.writes_enabled = True
        return post_menu(zte, tag, body)
    finally:
        zte.session.post = old_post
        zte.writes_enabled = old_enabled


def trace_hops(raw):
    hops = []
    for line in str(raw or "").splitlines():
        match = re.match(r"^\s*(\d+)\s+(.+)$", line)
        if not match:
            continue
        content = match.group(2)
        times = re.findall(r"(\d+(?:\.\d+)?)\s*ms\b", content, re.I)
        addr = re.search(r"(?:\d{1,3}\.){3}\d{1,3}", content)
        hops.append({"numero": int(match.group(1)),
                     "ip": addr.group() if addr else None,
                     "latencias_ms": [float(x) for x in times],
                     "timeout": "*" in content and not times,
                     "linha": line.strip()})
    return hops

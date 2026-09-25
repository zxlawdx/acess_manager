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


class F6201BDiagnostics:
    """Strategy for one captured diagnostic operation at a time."""

    def __init__(self, sleep=time.sleep, attempts=8):
        self.sleep = sleep
        self.attempts = attempts

    @staticmethod
    def _fields(tag, config, baseline):
        destination = host_name(config.get("host"))
        if config.get("interface"):
            raise ValueError(
                "A seleção de interface não foi exposta neste formulário."
            )
        if config.get("ip_version", "IPv4") != "IPv4":
            raise ValueError("A captura não confirmou IPVersion IPv6.")
        if tag == PING:
            row = baseline[0] if baseline else {}
            return {
                "IF_ACTION": "PingDiagnosis",
                "_InstID": "", "Host": destination, "Interface": "",
                "NumofRepeat": bounded(config.get("count", 4), "Pacotes", 1, 30),
                "DataBlockSize": bounded(
                    config.get("data_size", row.get("DataBlockSize") or 64),
                    "Tamanho", 1, 1400,
                ),
                "Timeout": bounded(config.get("timeout", 5000),
                                   "Timeout", 1000, 10000),
                "Btn_cancel_PingDiagnosis": "", "Btn_PingDiagnosis": "",
                "PingAck": "",
            }
        proto = config.get("protocol", "ICMP")
        if proto not in ("ICMP", "UDP"):
            raise ValueError("Protocolo inválido.")
        return {
            "IF_ACTION": "TraceRouteDiagnosis", "_InstID": "",
            "Control": "0", "Host": destination, "Interface": "",
            "MaxHopCount": bounded(config.get("max_hops", 30), "Saltos", 1, 64),
            "Timeout": bounded(config.get("timeout", 5000),
                               "Timeout", 2000, 10000),
            "Protocol": proto,
            "Btn_TraceRouteDiagnosis": "", "Result": "",
        }

    def execute(self, zte, original_post, tag, config):
        if tag not in ROOTS:
            raise ValueError("Diagnóstico não mapeado.")
        baseline = read(zte, tag, view=True)
        fields = self._fields(tag, config, baseline)
        keys = OBSERVED_DIAGNOSTIC_ACTIONS[tag]
        if set(fields) != set(keys) - {"_sessionTOKEN"}:
            raise RuntimeError("Formulário de diagnóstico incompleto.")
        before = dict(baseline[0]) if baseline else None
        post(zte, original_post, tag, fields)
        for attempt in range(self.attempts):
            current = read(zte, tag)
            if current:
                row = current[0]
                changed = before is None or any(
                    row.get(key) != before.get(key)
                    for key in ("PingAck", "SuccessCount", "FailureCount",
                                "MinimumResponseTime", "MaximumResponseTime",
                                "AverageResponseTime", "DiagnosticsState",
                                "Flag", "Result",
                                "NumberOfPRouteHops", "ResponseTime")
                )
                if tag == PING and changed and row.get("PingAck") not in (
                    None, "", "NULL"
                ):
                    try:
                        good = int(row.get("SuccessCount") or 0)
                        bad = int(row.get("FailureCount") or 0)
                    except ValueError:
                        good = bad = 0
                    return {
                        "host": fields["Host"], "resultado": row["PingAck"],
                        "minimo_ms": row.get("MinimumResponseTime"),
                        "medio_ms": row.get("AverageResponseTime"),
                        "maximo_ms": row.get("MaximumResponseTime"),
                        "sucesso": row.get("SuccessCount"),
                        "falha": row.get("FailureCount"),
                        "perda_percentual": round(100 * bad / (bad + good), 2)
                            if good + bad else None,
                        "verified": True, "fonte": "ONT",
                    }
                if tag == TRACE and changed and row.get("Flag") != "1":
                    result = row.get("Result")
                    if result and result != "NULL":
                        return {
                            "host": fields["Host"], "resultado": result,
                            "hops": trace_hops(result),
                            "salto_total": row.get("NumberOfPRouteHops"),
                            "response_time": row.get("ResponseTime"),
                            "verified": True, "fonte": "ONT",
                        }
            if attempt + 1 < self.attempts:
                self.sleep(1 if tag == PING else 3)
        raise TimeoutError(
            "A ONT recebeu o teste, mas não confirmou novo resultado. "
            "Não reenviar automaticamente."
        )

from __future__ import annotations

from typing import Any

from apps.zte_manager.model.telemetry import OpticalTelemetry
from apps.zte_manager.services.huawei_captured_features import parse_huawei_js_records


OPTICAL_AMP_PAGE = "/html/amp/opticinfo/opticinfo.asp"
OPTICAL_STATUS_PAGE = "/html/status/opticinfo.asp"
OPTICAL_ENDPOINTS = (OPTICAL_AMP_PAGE, OPTICAL_STATUS_PAGE)


def _number(value: object) -> float | None:
    text = str(value or "").strip()
    if not text or text in {"--", "-", "N/A", "n/a"}:
        return None
    for suffix in ("dBmV", "dBm", "mV", "mA", "°C", "℃", "C"):
        if text.endswith(suffix):
            text = text[: -len(suffix)].strip()
            break
    try:
        return float(text)
    except (TypeError, ValueError):
        return None


def _text(value: object) -> str | None:
    text = str(value or "").strip()
    return text or None


def _value(record: dict[str, Any], *names: str) -> object | None:
    wanted = {name.casefold() for name in names}
    for key, value in record.items():
        if str(key).casefold() in wanted and value not in (None, ""):
            return value
    return None


def parse_huawei_optical_response(
    source: str,
    *,
    endpoint: str,
) -> OpticalTelemetry:
    """Parse only characterized ``stOpticInfo`` signatures.

    Huawei firmware exposes multiple positional constructors with the same
    name. Positional fallbacks are therefore gated by the observed argument
    count instead of assuming every model/firmware uses the same layout.
    """

    records = [
        record
        for record in parse_huawei_js_records(source or "")
        if str(record.get("_constructor") or "").casefold() == "stopticinfo"
    ]
    if not records:
        raise RuntimeError("Resposta óptica Huawei sem stOpticInfo reconhecível.")

    record = records[0]
    args = list(record.get("_args") or [])
    argc = len(args)

    # Named fields are preferred when the page's function definition maps
    # properties correctly. The positional maps below are only for signatures
    # independently observed in firmware/reference captures.
    link_status = _value(record, "LinkStatus", "linkStatus", "Status")
    tx = _value(record, "transOpticPower", "TxPower", "TXPower")
    rx = _value(record, "revOpticPower", "RxPower", "RXPower")
    voltage = _value(record, "voltage", "Voltage")
    temperature = _value(record, "temperature", "Temperature")
    bias = _value(record, "bias", "Bias", "BiasCurrent", "TxCurrent")
    rf_rx = _value(record, "rfRxPower", "RfRxPower")
    rf_output = _value(record, "rfOutputPower", "RfOutputPower")

    signature: str
    if argc == 6:
        # Older status page: domain, tx, rx, voltage, temperature, bias.
        signature = "stOpticInfo/6"
        tx = tx if tx is not None else args[1]
        rx = rx if rx is not None else args[2]
        voltage = voltage if voltage is not None else args[3]
        temperature = temperature if temperature is not None else args[4]
        bias = bias if bias is not None else args[5]
    elif argc == 8:
        # AMP firmware variant adds RF receive/output power.
        signature = "stOpticInfo/8"
        tx = tx if tx is not None else args[1]
        rx = rx if rx is not None else args[2]
        voltage = voltage if voltage is not None else args[3]
        temperature = temperature if temperature is not None else args[4]
        bias = bias if bias is not None else args[5]
        rf_rx = rf_rx if rf_rx is not None else args[6]
        rf_output = rf_output if rf_output is not None else args[7]
    elif argc == 16:
        # Extended AMP shape: domain, link, tx, rx, voltage, temperature,
        # bias, RF rx/out, vendor metadata, wavelengths/range and LOS state.
        signature = "stOpticInfo/16"
        link_status = link_status if link_status is not None else args[1]
        tx = tx if tx is not None else args[2]
        rx = rx if rx is not None else args[3]
        voltage = voltage if voltage is not None else args[4]
        temperature = temperature if temperature is not None else args[5]
        bias = bias if bias is not None else args[6]
        rf_rx = rf_rx if rf_rx is not None else args[7]
        rf_output = rf_output if rf_output is not None else args[8]
    else:
        raise RuntimeError(
            f"Assinatura stOpticInfo não caracterizada: {argc} argumentos."
        )

    telemetry = OpticalTelemetry(
        link_status=_text(link_status),
        tx_power_dbm=_number(tx),
        rx_power_dbm=_number(rx),
        voltage_mv=_number(voltage),
        temperature_c=_number(temperature),
        bias_ma=_number(bias),
        rf_rx_power_dbm=_number(rf_rx),
        rf_output_power_dbmv=_number(rf_output),
        source_transport="webui",
        source_endpoint=endpoint,
        signature=signature,
    )
    if telemetry.tx_power_dbm is None and telemetry.rx_power_dbm is None:
        raise RuntimeError("Resposta óptica Huawei sem potência TX/RX parseável.")
    return telemetry


class HuaweiOpticalTelemetryReader:
    """Read optical telemetry by safely probing characterized WebUI variants."""

    def __init__(self, client) -> None:
        self.client = client

    def read(self) -> OpticalTelemetry:
        failures: list[str] = []
        for endpoint in OPTICAL_ENDPOINTS:
            try:
                source = self.client.get_page(endpoint)
                return parse_huawei_optical_response(source, endpoint=endpoint)
            except Exception as exc:
                failures.append(f"{endpoint}:{type(exc).__name__}")
        raise RuntimeError(
            "Nenhuma variante óptica Huawei reconhecida respondeu com sucesso: "
            + ", ".join(failures)
        )

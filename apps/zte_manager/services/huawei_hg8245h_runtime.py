from __future__ import annotations

import json
import re
import xml.etree.ElementTree as ET
from typing import Any

from apps.zte_manager.infrastructure.huawei.family_client import API_DEVICE_INFO_PATH
from apps.zte_manager.infrastructure.huawei.protocol import (
    HuaweiAuthFlow,
    HuaweiProtocolFamily,
)


_SOURCE = "bogomolov/huawei_HG8245H_remote"


def _compact(value: object) -> str:
    return re.sub(r"[^A-Z0-9]+", "", str(value or "").upper())


def _flatten_json(value: object, output: dict[str, Any]) -> None:
    if isinstance(value, dict):
        for key, item in value.items():
            if isinstance(item, (dict, list)):
                _flatten_json(item, output)
            elif item not in (None, ""):
                output.setdefault(str(key).casefold(), item)
    elif isinstance(value, list):
        for item in value:
            _flatten_json(item, output)


def _parse_api_fields(source: object) -> dict[str, Any]:
    text = str(source or "").strip()
    if not text:
        raise RuntimeError("HG8245H API deviceinfo vazio.")

    fields: dict[str, Any] = {}
    try:
        data = json.loads(text)
    except (TypeError, ValueError, json.JSONDecodeError):
        data = None
    if data is not None:
        _flatten_json(data, fields)
        return fields

    try:
        root = ET.fromstring(text)
    except ET.ParseError as exc:
        raise RuntimeError("HG8245H API deviceinfo não é JSON/XML reconhecível.") from exc

    for node in root.iter():
        if len(list(node)):
            continue
        value = str(node.text or "").strip()
        if not value:
            continue
        local = str(node.tag).split("}")[-1].casefold()
        fields.setdefault(local, value)
    return fields


def _value(fields: dict[str, Any], *names: str, default: object = "") -> object:
    for name in names:
        value = fields.get(str(name).casefold())
        if value not in (None, ""):
            return value
    return default


def _number(value: object) -> float | None:
    if value in (None, ""):
        return None
    match = re.search(r"-?\d+(?:\.\d+)?", str(value))
    return float(match.group(0)) if match else None


class HuaweiHG8245HApiRuntime:
    """Read-only HG8245H runtime for the modern SesTokenInfo /api/ family."""

    SOURCE = _SOURCE
    MODEL = "HG8245H"
    DEVICE_INFO_PATH = API_DEVICE_INFO_PATH

    def __init__(self, client) -> None:
        self.client = client

    def _source(self, *, refresh: bool = False) -> str:
        if not refresh:
            snapshot = getattr(self.client, "authenticated_identity_source", None)
            if callable(snapshot):
                item = snapshot()
                if item and item[0] == self.DEVICE_INFO_PATH and item[1]:
                    return str(item[1])
        getter = getattr(self.client, "get_api_page", None)
        if not callable(getter):
            raise RuntimeError("Cliente Huawei não expõe leitura segura /api/.")
        return str(getter(self.DEVICE_INFO_PATH) or "")

    def device_status(self, *, refresh: bool = False) -> dict[str, Any]:
        source = self._source(refresh=refresh)
        fields = _parse_api_fields(source)
        detected_model = str(_value(
            fields,
            "DeviceName",
            "ProductName",
            "ProductClass",
            "ModelName",
            "Model",
            "DeviceType",
        ) or "").strip()
        serial = str(_value(fields, "SerialNumber", "SerialNo", "SN") or "")
        firmware = str(_value(
            fields,
            "SoftwareVersion",
            "SoftwareVer",
            "FirmwareVersion",
            "MainSoftwareVersion",
        ) or "")
        hardware = str(_value(fields, "HardwareVersion", "HardwareVer") or "")
        uptime = _number(_value(fields, "UpTime", "Uptime", "DeviceUpTime"))

        return {
            "fabricante": "Huawei",
            "modelo": detected_model or self.MODEL,
            "detected_model": detected_model,
            "serial": serial,
            "firmware": firmware,
            "hardware": hardware,
            "uptime": int(uptime) if uptime is not None else "",
            "source": self.DEVICE_INFO_PATH,
            "evidence": "reference_endpoint+runtime_parser",
        }

    def source_signature(self) -> dict[str, Any]:
        auth_flow = getattr(self.client, "auth_flow", None)
        protocol_family = getattr(self.client, "protocol_family", None)
        auth_ok = auth_flow in {HuaweiAuthFlow.API_SES_TOKEN, HuaweiAuthFlow.API_SES_TOKEN.value}
        family_ok = protocol_family in {
            HuaweiProtocolFamily.API_SESTOKEN,
            HuaweiProtocolFamily.API_SESTOKEN.value,
        }
        if not auth_ok or not family_ok:
            return {
                "compatible": False,
                "strong_fingerprint": False,
                "model": None,
                "evidence": [],
                "endpoints": {"device_info": self.DEVICE_INFO_PATH},
            }

        device = self.device_status(refresh=False)
        detected = str(device.get("detected_model") or "")
        model_ok = _compact(detected) == self.MODEL
        evidence = [
            "auth:api_ses_token",
            "protocol:api_sestoken",
            f"deviceinfo:{self.DEVICE_INFO_PATH}",
        ]
        evidence.append(
            "device-model:HG8245H" if model_ok else "device-model:mismatch-or-missing"
        )
        return {
            "compatible": bool(auth_ok and family_ok and model_ok),
            "strong_fingerprint": bool(auth_ok and family_ok and model_ok),
            "model": detected or None,
            "source": self.SOURCE,
            "evidence": evidence,
            "endpoints": {"device_info": self.DEVICE_INFO_PATH},
            "physical_validation": False,
        }

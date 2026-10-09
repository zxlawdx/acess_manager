from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from apps.zte_manager.infrastructure.huawei.js_parser import HuaweiJsConstructorParser
from apps.zte_manager.infrastructure.huawei.protocol import HuaweiAuthFlow
from apps.zte_manager.model.telemetry import DeviceResourceTelemetry
from apps.zte_manager.services.huawei_telemetry import parse_huawei_optical_response


@dataclass(frozen=True)
class HuaweiReadEndpoint:
    path: str
    method: str = "GET"
    referer: str = "/index.asp"

    def read(self, client) -> str:
        if self.method.upper() == "POST":
            return client.post_read(self.path, {}, referer=self.referer)
        return client.get_page(self.path)


@dataclass(frozen=True)
class HuaweiEG8145FamilyProfile:
    key: str
    canonical_model: str
    aliases: tuple[str, ...]
    parser_family: str
    device_info: HuaweiReadEndpoint
    client_endpoints: tuple[HuaweiReadEndpoint, ...]
    optical: HuaweiReadEndpoint | None = None
    source: str = ""

    @property
    def model_compacts(self) -> frozenset[str]:
        return frozenset(
            _compact_model(value)
            for value in (self.canonical_model, *self.aliases)
            if value
        )


DEVICE_INFO_ENDPOINT = HuaweiReadEndpoint(
    "/html/ssmp/deviceinfo/deviceinfo.asp",
    "GET",
    "/index.asp",
)
COMMON_CLIENT_ENDPOINT = HuaweiReadEndpoint(
    "/html/bbsp/common/GetLanUserDevInfo.asp",
    "POST",
    "/html/bbsp/userdevinfo/userdevinfo.asp",
)
EG8145V5_CLIENT_FALLBACK = HuaweiReadEndpoint(
    "/html/bbsp/userdevinfo/getuserdevinfo.asp",
    "GET",
    "/html/bbsp/userdevinfo/userdevinfo.asp",
)
HN8010TS_OPTICAL_ENDPOINT = HuaweiReadEndpoint(
    "/html/amp/opticinfo/opticinfo.asp",
    "GET",
    "/index.asp",
)


EG8145V5_PROFILE = HuaweiEG8145FamilyProfile(
    key="eg8145v5",
    canonical_model="EG8145V5",
    aliases=("Huawei EG8145V5",),
    parser_family="eg8145v5",
    device_info=DEVICE_INFO_ENDPOINT,
    client_endpoints=(COMMON_CLIENT_ENDPOINT, EG8145V5_CLIENT_FALLBACK),
    source="chickenzord/go-huawei-client + undefjs/huawei-eg8145v5-hacs",
)
HN8010TS_PROFILE = HuaweiEG8145FamilyProfile(
    key="hn8010ts",
    canonical_model="HN8010TS",
    aliases=("Huawei HN8010TS",),
    parser_family="hn8010ts",
    device_info=DEVICE_INFO_ENDPOINT,
    client_endpoints=(COMMON_CLIENT_ENDPOINT,),
    optical=HN8010TS_OPTICAL_ENDPOINT,
    source="chickenzord/go-huawei-client PR #2",
)
PHASE2_PROFILES = (EG8145V5_PROFILE, HN8010TS_PROFILE)


# Source-scoped positional schemas. Constructor definitions embedded in a live
# page remain authoritative; these maps cover the shapes independently exposed
# by the two Phase-2 references when a response omits the function definition.
_PHASE2_SCHEMAS = {
    ("eg8145v5", "stDeviceInfo"): (
        "Domain",
        "SerialNumber",
        "HardwareVersion",
        "SoftwareVersion",
        "ModelName",
        "VendorID",
        "ReleaseTime",
        "Mac",
        "Description",
        "ManufactureInfo",
        "DeviceAlias",
    ),
    ("hn8010ts", "stDeviceInfo"): (
        "Domain",
        "SerialNumber",
        "HardwareVersion",
        "SoftwareVersion",
        "ModelName",
        "VendorID",
        "ReleaseTime",
        "Mac",
        "Description",
        "ManufactureInfo",
        "DeviceAlias",
    ),
    ("eg8145v5", "stUserDevInfo"): (
        "Domain",
        "IpAddr",
        "MacAddr",
        "Port",
        "PortID",
        "DevStatus",
        "IpType",
        "Time",
        "HostName",
        "IPv4Enabled",
        "IPv6Enabled",
        "DeviceType",
        "UserDevAlias",
        "UserSpecifiedDeviceType",
        "LeaseTimeRemaining",
    ),
    ("hn8010ts", "stUserDevInfo"): (
        "Domain",
        "IpAddr",
        "MacAddr",
        "Port",
        "PortID",
        "DevStatus",
        "IpType",
        "Time",
        "HostName",
        "IPv4Enabled",
        "IPv6Enabled",
        "DeviceType",
        "UserDevAlias",
        "UserSpecifiedDeviceType",
        "LeaseTimeRemaining",
    ),
    ("eg8145v5", "stUserDevInfoPTVDF"): (
        "HostName",
        "DeviceType",
        "IpAddr",
        "MacAddr",
        "RealMac",
        "DevStatus",
        "Port",
        "ConnectedTime",
        "ActiveTime",
        "Domain",
    ),
}


def _compact_model(value: object) -> str:
    text = re.sub(r"\bHUAWEI\b", " ", str(value or "").upper())
    return re.sub(r"[^A-Z0-9]+", "", text)


def _record_value(record: dict[str, Any], *names: str, default: object = "") -> object:
    wanted = {name.casefold() for name in names}
    for key, value in record.items():
        if str(key).casefold() in wanted and value not in (None, ""):
            return value
    return default


def _source_scalar(source: str, *names: str, default: object = "") -> object:
    text = str(source or "")
    for name in names:
        escaped = re.escape(name)
        for pattern in (
            rf"(?:var\s+)?{escaped}\s*=\s*['\"]([^'\"]*)['\"]",
            rf"(?:var\s+)?{escaped}\s*=\s*(-?\d+(?:\.\d+)?)",
        ):
            match = re.search(pattern, text, re.I)
            if match:
                return match.group(1)
    return default


def _number(value: object) -> float | None:
    if value in (None, ""):
        return None
    match = re.search(r"-?\d+(?:\.\d+)?", str(value))
    return float(match.group(0)) if match else None


def _normalize_mac(value: object) -> str:
    compact = re.sub(r"[^0-9A-Fa-f]", "", str(value or ""))
    if len(compact) != 12:
        return ""
    return ":".join(compact[index:index + 2] for index in range(0, 12, 2)).upper()


def _ipv4(value: object) -> str:
    text = str(value or "").strip()
    if not re.fullmatch(r"(?:\d{1,3}\.){3}\d{1,3}", text):
        return ""
    try:
        if any(int(part) > 255 for part in text.split(".")):
            return ""
    except ValueError:
        return ""
    return text


def _connection_type(port: object) -> str:
    value = str(port or "").strip().casefold()
    if any(marker in value for marker in ("ssid", "wlan", "wi-fi", "wifi")):
        return "wifi"
    if any(marker in value for marker in ("lan", "eth", "ethernet")):
        return "lan"
    return "unknown"


class HuaweiEG8145V5FamilyRuntime:
    """Read-only Phase-2 adapter sharing the existing RandCount session.

    This class owns only model/firmware endpoint schemas and normalization. It
    never authenticates, retries credentials, mutates Wi-Fi or opens a second
    HTTP session. The connected HuaweiFamilyAwareWebClient remains the sole
    owner of transport, cookies and reauthentication.
    """

    def __init__(self, client, profile: HuaweiEG8145FamilyProfile) -> None:
        self.client = client
        self.profile = profile
        self.parser = HuaweiJsConstructorParser(_PHASE2_SCHEMAS)
        self._last_client_endpoint: str | None = None
        self._last_client_recognized = False

    def _records(self, source: str) -> list[dict[str, Any]]:
        return self.parser.parse(
            source,
            protocol_family=self.profile.parser_family,
        )

    def _device_source_and_record(self) -> tuple[str, dict[str, Any]]:
        source = self.profile.device_info.read(self.client)
        records = self._records(source)
        record = next(
            (
                item for item in records
                if str(item.get("_constructor") or "").casefold() == "stdeviceinfo"
            ),
            {},
        )
        return source, record

    def device_status(self) -> dict[str, Any]:
        source, record = self._device_source_and_record()
        detected_model = str(
            _record_value(record, "ModelName", "ProductName", "ProductClass")
            or _source_scalar(source, "ModelName", "ProductName", "ProductClass")
            or ""
        )
        serial = _record_value(record, "SerialNumber", "SerialNo", "SN")
        firmware = _record_value(record, "SoftwareVersion", "SoftwareVer")
        hardware = _record_value(record, "HardwareVersion", "HardwareVer")
        mac = _normalize_mac(_record_value(record, "Mac", "MAC", "MACAddress"))
        cpu = _number(_source_scalar(source, "cpuUsed", "CPUUsage"))
        memory = _number(_source_scalar(source, "memUsed", "MemoryUsage"))
        uptime = _number(_source_scalar(source, "dev_uptime", "UpTime", "Uptime"))

        if not detected_model and not record:
            raise RuntimeError("DeviceInfo EG8145/HN8010 sem estrutura reconhecível.")

        return {
            "fabricante": "Huawei",
            "modelo": detected_model or self.profile.canonical_model,
            # This field is deliberately not backfilled from the selected
            # profile. Runtime fingerprinting consumes it as evidence.
            "detected_model": detected_model,
            "serial": str(serial or ""),
            "firmware": str(firmware or ""),
            "hardware": str(hardware or ""),
            "mac": mac,
            "uptime": int(uptime) if uptime is not None else "",
            "cpu_percent": cpu,
            "cpu": ({"used_percent": cpu} if cpu is not None else {}),
            "memoria_percent": memory,
            "source": self.profile.device_info.path,
            "evidence": "reference_endpoint+runtime_parser",
        }

    @staticmethod
    def _client_constructor(record: dict[str, Any]) -> bool:
        name = str(record.get("_constructor") or "").casefold()
        return name.startswith("stuserdev") or name in {"userdevice", "stlandevice"}

    def _read_client_records(self) -> tuple[list[dict[str, Any]], str, bool]:
        last_error: BaseException | None = None
        for endpoint in self.profile.client_endpoints:
            try:
                source = endpoint.read(self.client)
            except Exception as exc:
                last_error = exc
                continue
            records = [item for item in self._records(source) if self._client_constructor(item)]
            recognized = bool(records) or bool(
                re.search(r"(?:stUserDev|GetUserDevInfoList)", source or "", re.I)
            )
            if recognized:
                self._last_client_endpoint = endpoint.path
                self._last_client_recognized = True
                return records, endpoint.path, True
        self._last_client_endpoint = None
        self._last_client_recognized = False
        if last_error is not None:
            raise RuntimeError(
                "Nenhum endpoint de clientes Phase-2 respondeu com schema reconhecido."
            ) from last_error
        raise RuntimeError(
            "Nenhum endpoint de clientes Phase-2 respondeu com schema reconhecido."
        )

    def clients(self) -> list[dict[str, Any]]:
        records, endpoint, _recognized = self._read_client_records()
        rows: list[dict[str, Any]] = []
        seen: set[str] = set()
        for item in records:
            mac = _normalize_mac(
                _record_value(item, "MacAddr", "MacAddress", "MACAddress", "RealMac")
            )
            if not mac or mac in seen:
                continue
            seen.add(mac)
            port = str(_record_value(item, "Port", "PortID", "Interface") or "")
            status = str(_record_value(item, "DevStatus", "Status") or "")
            rows.append({
                "hostname": str(_record_value(item, "HostName", "Hostname", "Name") or ""),
                "ip": _ipv4(_record_value(item, "IpAddr", "IPAddress", "IPv4Address")),
                "mac": mac,
                "interface": port,
                "connection_type": _connection_type(port),
                "online": status,
                "status": status,
                "lease": str(_record_value(item, "LeaseTimeRemaining", "LeaseTime") or ""),
                "device_type": str(_record_value(item, "DeviceType", "DevType") or ""),
                "connected_time": str(_record_value(item, "ConnectedTime", "Time") or ""),
                "active_time": str(_record_value(item, "ActiveTime") or ""),
                "rssi": None,
                "noise": None,
                "snr": None,
                "rx_rate": None,
                "tx_rate": None,
                "source": endpoint,
            })
        return rows

    def resource_telemetry(self) -> dict[str, Any]:
        device = self.device_status()
        telemetry = DeviceResourceTelemetry(
            cpu_used_percent=_number(device.get("cpu_percent")),
            memory_used_percent=_number(device.get("memoria_percent")),
            uptime_seconds=(
                int(device["uptime"])
                if device.get("uptime") not in (None, "")
                else None
            ),
            source_transport="webui",
        )
        data = telemetry.as_dict()
        if all(
            data.get(key) is None
            for key in ("cpu_used_percent", "memory_used_percent", "uptime_seconds")
        ):
            raise RuntimeError("DeviceInfo Phase-2 sem CPU, memória ou uptime parseável.")
        data["source_endpoint"] = self.profile.device_info.path
        return data

    def optical_telemetry(self) -> dict[str, Any]:
        endpoint = self.profile.optical
        if endpoint is None:
            raise RuntimeError(
                "Óptica não foi promovida para este profile Phase-2 sem evidência específica."
            )
        source = endpoint.read(self.client)
        return parse_huawei_optical_response(source, endpoint=endpoint.path).as_dict()

    def optical_status(self) -> dict[str, Any]:
        telemetry = self.optical_telemetry()
        return {
            "rx_power_dbm": telemetry.get("rx_power_dbm"),
            "tx_power_dbm": telemetry.get("tx_power_dbm"),
            "temperature_c": telemetry.get("temperature_c"),
            "voltage": telemetry.get("voltage_mv"),
            "current_ma": telemetry.get("bias_ma"),
            "registration_status": telemetry.get("link_status") or "",
            "source": telemetry.get("source_endpoint") or self.profile.optical.path,
            "signature": telemetry.get("signature"),
            "evidence": "reference_endpoint+runtime_parser",
        }

    def source_signature(self) -> dict[str, Any]:
        evidence: list[str] = []
        endpoints: dict[str, object] = {
            "device_info": self.profile.device_info.path,
            "clients": [endpoint.path for endpoint in self.profile.client_endpoints],
            "optical": self.profile.optical.path if self.profile.optical else None,
        }

        auth_flow = getattr(self.client, "auth_flow", None)
        auth_ok = auth_flow in (
            None,
            HuaweiAuthFlow.RAND_COUNT,
            HuaweiAuthFlow.RAND_COUNT.value,
        )
        if auth_flow is not None:
            evidence.append(f"auth:{getattr(auth_flow, 'value', auth_flow)}")
        if not auth_ok:
            return {
                "compatible": False,
                "strong_fingerprint": False,
                "profile": self.profile.key,
                "model": None,
                "evidence": evidence,
                "endpoints": endpoints,
            }

        try:
            device = self.device_status()
        except Exception:
            return {
                "compatible": False,
                "strong_fingerprint": False,
                "profile": self.profile.key,
                "model": None,
                "evidence": evidence,
                "endpoints": endpoints,
            }

        actual_model = str(device.get("detected_model") or "")
        model_match = bool(actual_model) and (
            _compact_model(actual_model) in self.profile.model_compacts
        )
        if model_match:
            evidence.append(f"device-model:{self.profile.canonical_model}")
        else:
            evidence.append(
                "device-model:missing" if not actual_model else "device-model:mismatch"
            )
            return {
                "compatible": False,
                "strong_fingerprint": False,
                "profile": self.profile.key,
                "model": actual_model or None,
                "evidence": evidence,
                "endpoints": endpoints,
            }

        try:
            _records, endpoint, recognized = self._read_client_records()
        except Exception:
            recognized = False
            endpoint = None
        if recognized:
            evidence.append(f"clients:{endpoint}")

        optics_ok = self.profile.optical is None
        if self.profile.optical is not None:
            try:
                optical = self.optical_telemetry()
                optics_ok = bool(
                    optical.get("tx_power_dbm") is not None
                    or optical.get("rx_power_dbm") is not None
                )
            except Exception:
                optics_ok = False
            if optics_ok:
                evidence.append(f"optical:{self.profile.optical.path}")

        compatible = bool(model_match and recognized and optics_ok)
        return {
            "compatible": compatible,
            "strong_fingerprint": compatible,
            "profile": self.profile.key,
            "model": actual_model,
            "evidence": evidence,
            "endpoints": endpoints,
            "source": self.profile.source,
            "physical_validation": False,
        }


def ordered_phase2_profiles(
    model_hint: object = None,
) -> tuple[HuaweiEG8145FamilyProfile, ...]:
    compact = _compact_model(model_hint)
    return tuple(
        sorted(
            PHASE2_PROFILES,
            key=lambda profile: 0 if compact in profile.model_compacts else 1,
        )
    )

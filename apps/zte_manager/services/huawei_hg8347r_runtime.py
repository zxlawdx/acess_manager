from __future__ import annotations

import json
import re
from copy import deepcopy
from typing import Any

from apps.zte_manager.infrastructure.huawei.codec import decode_huawei_js_string
from apps.zte_manager.infrastructure.huawei.protocol import HuaweiAuthFlow


class HuaweiHG8347RRuntime:
    """Clean-room read runtime for the HG8347R AMP/BBSP/AJAX family.

    The public reference for this model has no explicit license, so this class
    is implemented independently from factual protocol observations only:
    legacy RandCount auth, a page-scoped ``hwonttoken`` and the read-only
    ``getajax.cgi`` user-device query. It does not copy source structure or
    expose any write/reboot operation not evidenced for this model.
    """

    MODEL = "HG8347R"
    SOURCE = "clean-room:CutJiuCai/hg8347r"
    USER_DEVICE_PAGE = "/html/bbsp/userdevinfo/userdevinfolan.asp"
    USER_DEVICE_AJAX = (
        "/getajax.cgi?"
        "x=InternetGatewayDevice.LANDevice.1.X_HW_UserDev.{i}&"
        "RequestFile=html/bbsp/userdevinfo/userdevinfolan.asp"
    )
    LOGOUT_PATH = "/logout.cgi?RequestFile=html/logout.html"

    _TOKEN_PATTERNS = (
        re.compile(
            r"<input\b[^>]*\bid=[\"']hwonttoken[\"'][^>]*\bvalue=[\"']([A-Za-z0-9]{16,128})[\"']",
            re.I | re.S,
        ),
        re.compile(
            r"<input\b[^>]*\bvalue=[\"']([A-Za-z0-9]{16,128})[\"'][^>]*\bid=[\"']hwonttoken[\"']",
            re.I | re.S,
        ),
        re.compile(
            r"<input\b[^>]*\bname=[\"']onttoken[\"'][^>]*\bvalue=[\"']([A-Za-z0-9]{16,128})[\"']",
            re.I | re.S,
        ),
    )

    _AJAX_FIELDS = (
        "HostName",
        "IpAddr",
        "MacAddr",
        "PortType",
        "PortID",
        "TrafficSend",
        "TrafficRecv",
        "DevStatus",
        "time",
        "IpType",
    )

    def __init__(self, client) -> None:
        self.client = client
        self._cached_signature: dict[str, Any] | None = None
        self._cached_clients: list[dict[str, Any]] | None = None

    @staticmethod
    def _auth_is_rand_count(client) -> bool:
        value = getattr(client, "auth_flow", None)
        return value in {HuaweiAuthFlow.RAND_COUNT, HuaweiAuthFlow.RAND_COUNT.value}

    @classmethod
    def extract_page_token(cls, source: object) -> str:
        text = str(source or "")
        for pattern in cls._TOKEN_PATTERNS:
            match = pattern.search(text)
            if match:
                return match.group(1)
        raise ValueError("HG8347R hwonttoken não encontrado na página de dispositivos.")

    @staticmethod
    def _decoded_json(source: object) -> Any:
        text = decode_huawei_js_string(str(source or "")).lstrip("\ufeff").strip()
        if not text:
            raise ValueError("HG8347R getajax retornou corpo vazio.")
        try:
            return json.loads(text)
        except json.JSONDecodeError as exc:
            raise ValueError("HG8347R getajax não retornou JSON reconhecível.") from exc

    @classmethod
    def parse_clients(cls, source: object) -> tuple[list[dict[str, Any]], bool]:
        value = cls._decoded_json(source)
        if not isinstance(value, list):
            raise ValueError("HG8347R getajax não retornou uma lista JSON.")

        success_marker = False
        devices: list[dict[str, Any]] = []
        for item in value:
            if not isinstance(item, dict):
                continue
            if "result" in item:
                marker = item.get("result")
                success_marker = str(marker).strip() in {"0", "0.0"}
                continue
            if any(key in item for key in ("MacAddr", "IpAddr", "HostName", "PortType")):
                devices.append(dict(item))
        return devices, success_marker

    @staticmethod
    def _connection_type(port_type: object) -> str:
        value = str(port_type or "").strip().casefold()
        if any(marker in value for marker in ("wifi", "wlan", "ssid")):
            return "wifi"
        if any(marker in value for marker in ("eth", "lan")):
            return "lan"
        return "unknown"

    @classmethod
    def normalize_client(cls, item: dict[str, Any]) -> dict[str, Any]:
        port_type = item.get("PortType")
        status = str(item.get("DevStatus") or "").strip()
        online = status.casefold() in {"1", "online", "up", "active", "connected"}
        return {
            "hostname": item.get("HostName") or "",
            "ip": item.get("IpAddr") or "",
            "mac": item.get("MacAddr") or "",
            "interface": item.get("PortID") or port_type or "",
            "connection_type": cls._connection_type(port_type),
            "online": online,
            "status": status,
            "ip_type": item.get("IpType") or "",
            "uptime": item.get("Time") or item.get("time") or "",
            "traffic_send": item.get("TrafficSend") or "",
            "traffic_recv": item.get("TrafficRecv") or "",
            "domain": item.get("Domain") or "",
            "source": "hg8347r:getajax:userdev",
        }

    def _read_raw_clients(self) -> tuple[list[dict[str, Any]], dict[str, Any]]:
        page = self.client.get_page(self.USER_DEVICE_PAGE)
        token = self.extract_page_token(page)
        payload = {field: "" for field in self._AJAX_FIELDS}
        payload["x.X_HW_Token"] = token
        body = self.client.post_read(
            self.USER_DEVICE_AJAX,
            payload,
            referer=self.USER_DEVICE_PAGE,
        )
        devices, success_marker = self.parse_clients(body)
        if not success_marker:
            raise ValueError("HG8347R getajax não confirmou result=0.")
        signature = {
            "compatible": True,
            "strong_fingerprint": True,
            "source": self.SOURCE,
            "model": self.MODEL,
            "auth_flow": "rand_count",
            "evidence": [
                "page:hwonttoken",
                "ajax:X_HW_UserDev",
                "ajax:result=0",
            ],
            "endpoints": {
                "page": self.USER_DEVICE_PAGE,
                "clients": self.USER_DEVICE_AJAX,
                "logout": self.LOGOUT_PATH,
            },
        }
        return devices, signature

    def source_signature(self, *, refresh: bool = False) -> dict[str, Any]:
        if self._cached_signature is not None and not refresh:
            return deepcopy(self._cached_signature)
        if not self._auth_is_rand_count(self.client):
            return {
                "compatible": False,
                "strong_fingerprint": False,
                "source": self.SOURCE,
                "model": None,
                "auth_flow": str(getattr(self.client, "auth_flow", "unknown")),
                "evidence": ["auth:not-rand-count"],
                "endpoints": {},
            }
        devices, signature = self._read_raw_clients()
        self._cached_clients = [self.normalize_client(item) for item in devices]
        self._cached_signature = deepcopy(signature)
        return deepcopy(signature)

    def clients(self, *, refresh: bool = False) -> list[dict[str, Any]]:
        if self._cached_clients is not None and not refresh:
            return deepcopy(self._cached_clients)
        devices, signature = self._read_raw_clients()
        self._cached_clients = [self.normalize_client(item) for item in devices]
        self._cached_signature = deepcopy(signature)
        return deepcopy(self._cached_clients)

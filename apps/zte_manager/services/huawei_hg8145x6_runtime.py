from __future__ import annotations

import re
from typing import Any

from apps.zte_manager.services.huawei_captured_features import (
    DEVICE_INFO_PAGE,
    WAN_CACHE_PAGE,
    WLAN_LIST_PAGE,
    HuaweiCapturedFeatureService,
    _record_domain,
    parse_huawei_js_records,
)


HG8145X6_WLAN_INFO_PAGE = "/html/amp/wlaninfo/wlaninfo.asp"
HG8145X6_ASSOCIATED_DEVICES_PAGE = (
    "/html/amp/wlaninfo/getassociateddeviceinfo.asp"
)


class HuaweiHG8145X6CapturedFeatureService(HuaweiCapturedFeatureService):
    """Read-only WebUI adapter derived from the user-supplied ONTWatch client.

    ONTWatch documents these endpoints against an HG8145X6-10 V5R022C00
    firmware build. Access Manager keeps the adapter read-only and promotes a
    capability only after the authenticated endpoint can be read at runtime.
    No EG8041 mutation contract is inherited as evidence for this model.
    """

    SOURCE = "ONTWatch/HG8145X6-10"

    @staticmethod
    def _rows(source: str, constructor: str) -> list[dict[str, Any]]:
        wanted = str(constructor or "").casefold()
        return [
            row
            for row in parse_huawei_js_records(source or "")
            if str(row.get("_constructor") or "").casefold() == wanted
        ]

    @staticmethod
    def _arg(row: dict[str, Any], index: int, default: Any = "") -> Any:
        args = list(row.get("_args") or [])
        return args[index] if 0 <= index < len(args) else default

    @classmethod
    def _int_arg(
        cls,
        row: dict[str, Any],
        index: int,
        default: int = 0,
    ) -> int:
        try:
            return int(cls._arg(row, index, default))
        except (TypeError, ValueError):
            return default

    @staticmethod
    def _wlan_index(value: object) -> int | None:
        match = re.search(r"WLANConfiguration\.(\d+)", str(value or ""))
        return int(match.group(1)) if match else None

    @staticmethod
    def _band(value: object) -> str:
        raw = str(value or "").strip()
        folded = raw.casefold()
        if "5" in folded:
            return "5GHz"
        if any(token in folded for token in ("2.4", "2g", "2 ghz")):
            return "2.4GHz"
        return raw

    def source_signature(self) -> dict[str, Any]:
        """Read the documented ONTWatch endpoints without mutating the ONT."""
        probes = (
            ("wan", WAN_CACHE_PAGE, ("WanPPP",)),
            ("ssids", WLAN_LIST_PAGE, ("stWlanInfo",)),
            ("traffic", HG8145X6_WLAN_INFO_PAGE, ("stPacketInfo",)),
            (
                "clients",
                HG8145X6_ASSOCIATED_DEVICES_PAGE,
                ("stAssociatedDevice",),
            ),
            (
                "device",
                DEVICE_INFO_PAGE,
                ("dev_uptime", "cpuUsed", "memUsed"),
            ),
        )
        endpoints: dict[str, dict[str, Any]] = {}
        evidence: list[str] = []
        for key, path, markers in probes:
            try:
                source = self._page(path)
            except Exception as exc:
                endpoints[key] = {
                    "path": path,
                    "readable": False,
                    "marker": False,
                    "error": type(exc).__name__,
                }
                continue
            marker = any(item in source for item in markers)
            endpoints[key] = {
                "path": path,
                "readable": True,
                "marker": marker,
            }
            evidence.append(f"endpoint:{path}")
            if marker:
                evidence.append(f"marker:{key}")

        core = ("wan", "ssids", "device")
        compatible = all(
            endpoints.get(key, {}).get("readable")
            for key in core
        ) and sum(
            1 for key in core if endpoints.get(key, {}).get("marker")
        ) >= 2
        return {
            "compatible": bool(compatible),
            "source": self.SOURCE,
            "endpoints": endpoints,
            "evidence": evidence,
        }

    def _ssid_inventory(self) -> dict[int, dict[str, Any]]:
        source = self._page(WLAN_LIST_PAGE)
        inventory: dict[int, dict[str, Any]] = {}
        for row in self._rows(source, "stWlanInfo"):
            object_path = str(self._arg(row, 0, ""))
            index = self._wlan_index(object_path)
            if index is None:
                continue
            raw_band = self._arg(row, 5, "")
            inventory[index] = {
                "id": object_path,
                "wlan_index": index,
                "ssid": str(self._arg(row, 2, "")),
                "band": self._band(raw_band),
                "band_raw": str(raw_band or ""),
            }
        return inventory

    def wifi_networks(self, reveal_password: bool = False) -> list[dict[str, Any]]:
        """Return SSID identity even when WlanBasic parsing is unavailable."""
        inventory = self._ssid_inventory()
        try:
            base_rows = super().wifi_networks(reveal_password=False)
        except Exception:
            base_rows = []

        by_index: dict[int, dict[str, Any]] = {}
        for row in base_rows or []:
            index = self._wlan_index(row.get("id"))
            if index is not None:
                by_index[index] = dict(row)

        rows: list[dict[str, Any]] = []
        for index in sorted(inventory):
            observed = inventory[index]
            current = by_index.get(index, {})
            rows.append({
                "id": current.get("id") or observed["id"],
                "ssid": observed.get("ssid") or current.get("ssid") or "",
                "banda": observed.get("band") or current.get("banda") or "",
                "ativo": current.get("ativo"),
                "seguranca": current.get("seguranca") or "",
                "max_clientes": current.get("max_clientes"),
                "broadcast": current.get("broadcast"),
                "isolamento": current.get("isolamento"),
                "wps_enabled": current.get("wps_enabled"),
                "wps_method": current.get("wps_method") or "",
                "authentication_mode": current.get("authentication_mode") or "",
                "encryption_mode": current.get("encryption_mode") or "",
                "group_rekey": current.get("group_rekey"),
                "password": "",
                "password_hidden": True,
                "password_readable": False,
                "wlan_index": index,
                "band_raw": observed.get("band_raw") or "",
                "source": self.SOURCE,
            })
        return rows

    def wan_status(self) -> list[dict[str, Any]]:
        source = self._page(WAN_CACHE_PAGE)
        rows: list[dict[str, Any]] = []
        for record in self._rows(source, "WanPPP"):
            # Positional layout is the one used by ONTWatch's verified
            # HG8145X6-10 parser. Guard every index so firmware drift degrades
            # to missing values rather than returning shifted credentials.
            if len(record.get("_args") or []) < 44:
                continue
            domain = _record_domain(record) or str(self._arg(record, 0, ""))
            dns_raw = str(self._arg(record, 18, "") or "")
            dns = [item.strip() for item in dns_raw.split(",") if item.strip()]
            name = str(self._arg(record, 8, "") or domain)
            rows.append({
                "id": domain,
                "nome": name,
                "name": name,
                "status": str(self._arg(record, 5, "")),
                "connection_status": str(self._arg(record, 12, "")),
                "mode": str(self._arg(record, 13, "")),
                "ip": str(self._arg(record, 14, "")),
                "gateway": str(self._arg(record, 15, "")),
                "nat": str(self._arg(record, 16, "")),
                "dns1": dns[0] if dns else "",
                "dns2": dns[1] if len(dns) > 1 else "",
                "dns": dns,
                "username": str(self._arg(record, 19, "")),
                "dial_mode": str(self._arg(record, 21, "")),
                "vlan": self._int_arg(record, 23),
                "mtu": self._int_arg(record, 37),
                "bras": str(self._arg(record, 38, "")),
                "uptime": self._int_arg(record, 40),
                "session_id": str(self._arg(record, 43, "")),
                "mac": str(self._arg(record, 4, "")).upper(),
                "last_error": str(self._arg(record, 6, "")),
                "ipv6": "",
                "wan_type": "PPPoE",
                "services": "",
                "source": self.SOURCE,
            })
        if rows:
            return rows
        return super().wan_status()

    def pppoe_status(self, reveal_password: bool = False) -> list[dict[str, Any]]:
        return [
            {
                "id": row.get("id") or "",
                "nome": row.get("nome") or "",
                "username": row.get("username") or "",
                "password": "",
                "password_hidden": True,
                "auth_type": "",
                "vlan": row.get("vlan"),
                "mtu": row.get("mtu"),
                "session_id": row.get("session_id") or "",
                "bras": row.get("bras") or "",
                "dial_mode": row.get("dial_mode") or "",
                "uptime": row.get("uptime"),
            }
            for row in self.wan_status()
            if str(row.get("wan_type") or "").casefold() == "pppoe"
        ]

    def wifi_traffic(self) -> list[dict[str, Any]]:
        source = self._page(HG8145X6_WLAN_INFO_PAGE)
        ssids = self._ssid_inventory()
        rows: list[dict[str, Any]] = []
        for record in self._rows(source, "stPacketInfo"):
            if len(record.get("_args") or []) < 5:
                continue
            object_path = str(self._arg(record, 0, ""))
            index = self._wlan_index(object_path)
            if index is None:
                continue
            ssid = ssids.get(index, {})
            sent_bytes = self._int_arg(record, 1)
            sent_packets = self._int_arg(record, 2)
            recv_bytes = self._int_arg(record, 3)
            recv_packets = self._int_arg(record, 4)
            rows.append({
                "id": object_path,
                "wlan_index": index,
                "ssid": ssid.get("ssid") or f"SSID{index}",
                "band": ssid.get("band") or "",
                "sent_bytes": sent_bytes,
                "sent_packets": sent_packets,
                "recv_bytes": recv_bytes,
                "recv_packets": recv_packets,
                # Access Manager aliases: counters are cumulative and LAN-side.
                "tx_bytes": sent_bytes,
                "tx_packets": sent_packets,
                "rx_bytes": recv_bytes,
                "rx_packets": recv_packets,
                "counter_type": "cumulative",
                "scope": "wlan_lan_side",
                "source": self.SOURCE,
            })
        return rows

    def wifi_clients(self) -> list[dict[str, Any]]:
        source = self._page(HG8145X6_ASSOCIATED_DEVICES_PAGE)
        ssids = self._ssid_inventory()
        clients: list[dict[str, Any]] = []
        for record in self._rows(source, "stAssociatedDevice"):
            if len(record.get("_args") or []) < 16:
                continue
            object_path = str(self._arg(record, 0, ""))
            index = self._wlan_index(object_path)
            if index is None:
                continue
            ssid = ssids.get(index, {})
            clients.append({
                "wlan_index": index,
                "mac": str(self._arg(record, 1, "")).upper(),
                "uptime": self._int_arg(record, 2),
                "tempo_conectado": self._int_arg(record, 2),
                "rx_rate": self._int_arg(record, 3),
                "tx_rate": self._int_arg(record, 4),
                "rssi": self._int_arg(record, 5),
                "noise": self._int_arg(record, 6),
                "snr": self._int_arg(record, 7),
                "signal_quality": self._int_arg(record, 8),
                "mode": str(self._arg(record, 9, "")),
                "ip": str(self._arg(record, 13, "")),
                "hostname": str(self._arg(record, 14, "")),
                "antenna": str(self._arg(record, 15, "")),
                "ssid": ssid.get("ssid") or "",
                "band": ssid.get("band") or "",
                "radio": ssid.get("ssid") or f"WLAN{index}",
                "interface": f"WLAN{index}",
                "connection_type": "wifi",
                "status": "Online",
                "address_source": "",
                "ipv6": "",
                "lease": "",
                "vendor": "",
                "os": "",
                "source": self.SOURCE,
            })
        return clients

    def device_status(self) -> dict[str, Any]:
        source = self._page(DEVICE_INFO_PAGE)
        try:
            result = super().device_status()
        except Exception:
            result = {
                "fabricante": "Huawei",
                "modelo": self.model,
            }

        uptime = re.search(r"var\s+dev_uptime\s*=\s*['\"](\d+)['\"]", source)
        cpu = re.search(r"var\s+cpuUsed\s*=\s*['\"]([^'\"]*)['\"]", source)
        memory = re.search(r"var\s+memUsed\s*=\s*['\"]([^'\"]*)['\"]", source)
        if uptime:
            result["uptime"] = int(uptime.group(1))
        if cpu:
            result["cpu_percent"] = cpu.group(1)
            result["cpu"] = {"used_percent": cpu.group(1)}
        if memory:
            result["memoria_percent"] = memory.group(1)
            result["memory"] = {"used_percent": memory.group(1)}
        result["resource_source"] = DEVICE_INFO_PAGE
        result["source"] = self.SOURCE
        return result

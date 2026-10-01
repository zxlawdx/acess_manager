from __future__ import annotations

import re
import time
from typing import Any, Callable, Iterable

from apps.zte_manager.infrastructure.huawei import (
    HuaweiMutationTransport,
    HuaweiWebClient,
    decode_huawei_js_string,
)


DHCP_PAGE = "/html/bbsp/dhcp/dhcp.asp"
DHCP_SERVER_PAGE = "/html/bbsp/dhcpservercfg/dhcp2.asp"
DHCP_STATIC_PAGE = "/html/bbsp/dhcpstatic/dhcpstatic.asp"
DHCP_INFO_PAGE = "/html/bbsp/common/dhcpinfo.asp"
LAYER3_PAGE = "/html/bbsp/layer3/layer3.asp"
LAN_ADDRESS_PAGE = "/html/bbsp/lanaddress/lanaddress.asp"

DNS_PAGE = "/html/bbsp/dnsconfiguration/dnsconfigcommon.asp"
DNS_HOSTS_PAGE = "/html/bbsp/common/dnshostslist.asp"

DMZ_PAGE = "/html/bbsp/dmz/dmz.asp"
FIREWALL_PAGE = "/html/bbsp/firewalllevel/firewalllevel.asp"
DOS_PAGE = "/html/bbsp/Dos/Dos.asp"
IPV6_FIREWALL_PAGE = "/html/bbsp/ipv6firewall/firewall.asp"
INTERNET_CONTROL_PAGE = "/html/bbsp/internetcontrol/internetcontrol.asp"
ALG_PAGE = "/html/bbsp/alg/alg.asp"
IGMP_PAGE = "/html/bbsp/igmp/igmp.asp"

TR069_PAGE = "/html/ssmp/tr069/tr069.asp"
OPTICAL_PAGE = "/html/amp/opticinfo/opticinfo.asp"
WAN_INFO_PAGE = "/html/bbsp/common/wan_list_info.asp"
WAN_CACHE_PAGE = "/html/bbsp/common/wan_list_cache_wan.asp"

WLAN_BASIC_PAGE = "/html/amp/wlanbasic/WlanBasic.asp"
WLAN_ADV_PAGE = "/html/amp/wlanadv/WlanAdvance.asp"

WAN_DMZ_DOMAIN = (
    "InternetGatewayDevice.WANDevice.1.WANConnectionDevice.1."
    "WANPPPConnection.1.X_HW_DMZ"
)


def _matching_delimiter(source: str, start: int, opening: str, closing: str) -> int:
    depth = 0
    quote: str | None = None
    escaped = False
    for index in range(start, len(source)):
        char = source[index]
        if quote:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == quote:
                quote = None
            continue
        if char in {"'", '"'}:
            quote = char
            continue
        if char == opening:
            depth += 1
        elif char == closing:
            depth -= 1
            if depth == 0:
                return index
    return -1


def _split_js_arguments(raw: str) -> list[str]:
    items: list[str] = []
    current: list[str] = []
    quote: str | None = None
    escaped = False
    depth = 0
    for char in raw:
        if quote:
            current.append(char)
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == quote:
                quote = None
            continue
        if char in {"'", '"'}:
            quote = char
            current.append(char)
            continue
        if char in "([{":
            depth += 1
            current.append(char)
            continue
        if char in ")]}":
            depth = max(0, depth - 1)
            current.append(char)
            continue
        if char == "," and depth == 0:
            items.append("".join(current).strip())
            current = []
            continue
        current.append(char)
    if current or raw.strip():
        items.append("".join(current).strip())
    return items


def _js_literal(raw: str) -> Any:
    value = raw.strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
        return decode_huawei_js_string(value[1:-1])
    low = value.lower()
    if low in {"null", "undefined"}:
        return ""
    if low == "true":
        return True
    if low == "false":
        return False
    if re.fullmatch(r"-?[0-9]+", value):
        try:
            return int(value)
        except ValueError:
            pass
    if re.fullmatch(r"-?(?:[0-9]+\.[0-9]*|[0-9]*\.[0-9]+)", value):
        try:
            return float(value)
        except ValueError:
            pass
    return decode_huawei_js_string(value)


def _constructor_definitions(html: str) -> dict[str, tuple[list[str], dict[str, str]]]:
    definitions: dict[str, tuple[list[str], dict[str, str]]] = {}
    pattern = re.compile(r"function\s+([A-Za-z_$][\w$]*)\s*\(")
    for match in pattern.finditer(html or ""):
        open_paren = match.end() - 1
        close_paren = _matching_delimiter(html, open_paren, "(", ")")
        if close_paren < 0:
            continue
        body_start = html.find("{", close_paren)
        if body_start < 0:
            continue
        body_end = _matching_delimiter(html, body_start, "{", "}")
        if body_end < 0:
            continue
        params = [
            item.strip()
            for item in html[open_paren + 1:close_paren].split(",")
            if item.strip()
        ]
        body = html[body_start + 1:body_end]
        assignments: dict[str, str] = {}
        for prop, param in re.findall(
            r"this\s*\.\s*([A-Za-z_$][\w$]*)\s*=\s*([A-Za-z_$][\w$]*)",
            body,
        ):
            assignments[prop] = param
        for prop, param in re.findall(
            r"this\s*\[\s*['\"]([^'\"]+)['\"]\s*\]\s*=\s*([A-Za-z_$][\w$]*)",
            body,
        ):
            assignments[prop] = param
        definitions[match.group(1)] = (params, assignments)
    return definitions


def parse_huawei_js_records(html: str) -> list[dict[str, Any]]:
    """Parse Huawei's generated JS constructor records without model-specific positions."""
    definitions = _constructor_definitions(html or "")
    records: list[dict[str, Any]] = []
    pattern = re.compile(r"new\s+([A-Za-z_$][\w$]*)\s*\(")
    for match in pattern.finditer(html or ""):
        name = match.group(1)
        open_paren = match.end() - 1
        close_paren = _matching_delimiter(html, open_paren, "(", ")")
        if close_paren < 0:
            continue
        values = [
            _js_literal(item)
            for item in _split_js_arguments(html[open_paren + 1:close_paren])
        ]
        params, assignments = definitions.get(name, ([], {}))
        record: dict[str, Any] = {
            "_constructor": name,
            "_args": values,
        }
        for index, param in enumerate(params):
            if index < len(values):
                record[param] = values[index]
        param_index = {param: index for index, param in enumerate(params)}
        for prop, param in assignments.items():
            index = param_index.get(param)
            if index is not None and index < len(values):
                record[prop] = values[index]
        records.append(record)
    return records


def _record_value(records: Iterable[dict[str, Any]], *keys: str, default=None):
    wanted = {str(key).lower() for key in keys}
    for record in records:
        for key, value in record.items():
            if str(key).lower() in wanted and value not in (None, ""):
                return value
    return default


def _record_domain(record: dict[str, Any]) -> str:
    for key in ("domain", "Domain", "_InstID", "InstID", "id"):
        value = record.get(key)
        if isinstance(value, str) and "InternetGatewayDevice." in value:
            return value
    for value in record.values():
        if isinstance(value, str) and value.startswith("InternetGatewayDevice."):
            return value
    return ""


def _as01(value: Any, default: str = "0") -> str:
    if value in (True, 1, "1", "true", "True", "on", "ON"):
        return "1"
    if value in (False, 0, "0", "false", "False", "off", "OFF"):
        return "0"
    return default


def _enabled(value: Any) -> bool:
    return _as01(value) == "1"


def _band_details(band: str) -> tuple[str, str, str]:
    normalized = str(band or "").lower()
    if "5" in normalized:
        return "5GHz", "5", "5G"
    return "2.4GHz", "1", "2G"


class HuaweiCapturedFeatureService:
    """Features physically exercised on the EG8041X7-10 WebUI capture.

    A mutation is always submitted at most once. Success is established through
    a fresh read whenever the corresponding page exposes enough state.
    """

    def __init__(
        self,
        client: HuaweiWebClient,
        *,
        model: str | None = None,
        sleep: Callable[[float], None] = time.sleep,
        readback_tries: int = 6,
    ) -> None:
        self.client = client
        self.model = model or ""
        self.sleep = sleep
        self.readback_tries = max(1, int(readback_tries))

    def _page(self, path: str) -> str:
        return self.client.get_page(path)

    def _records(self, *pages: str) -> tuple[str, list[dict[str, Any]]]:
        chunks: list[str] = []
        for page in pages:
            try:
                chunks.append(self._page(page))
            except Exception:
                if len(pages) == 1:
                    raise
        html = "\n".join(chunks)
        return html, parse_huawei_js_records(html)

    def _post_verified(
        self,
        *,
        path: str,
        request_file: str,
        payload: dict[str, str],
        verifier: Callable[[], Any] | None,
    ) -> dict[str, Any]:
        page = self._page(request_file)
        token = self.client.extract_token(page)
        body = {**payload, "x.X_HW_Token": token}
        transport: HuaweiMutationTransport = self.client.post_form(
            path,
            body,
            referer=request_file,
        )
        verified = None
        if verifier is not None:
            for delay in (0.35, 0.55, 0.8, 1.0, 1.4, 1.8)[: self.readback_tries]:
                self.sleep(delay)
                try:
                    verified = verifier()
                except Exception:
                    verified = None
                if verified:
                    break
        success = bool(verified) if verifier is not None else (
            transport.http_status is not None
            and 200 <= transport.http_status < 400
        )
        return {
            "success": success,
            "verified": bool(verified),
            "uncertain": (
                not success
                and (
                    transport.timed_out
                    or transport.connection_uncertain
                    or transport.http_status is not None
                )
            ),
            "http_status": transport.http_status,
        }

    # ----------------------------- WAN / device reads

    def optical_status(self) -> dict[str, Any]:
        _html, records = self._records(OPTICAL_PAGE)
        return {
            "rx_power_dbm": _record_value(records, "RxPower", "RXPower", "RxOpticalPower", "ReceivePower"),
            "tx_power_dbm": _record_value(records, "TxPower", "TXPower", "TxOpticalPower", "TransmitPower"),
            "temperature_c": _record_value(records, "Temperature", "TemperatureC", "ChipTemperature"),
            "voltage": _record_value(records, "Voltage", "SupplyVoltage"),
            "current_ma": _record_value(records, "Current", "BiasCurrent", "TxBias"),
            "registration_status": _record_value(records, "Status", "ONTState", "RegisterStatus", default="Huawei GPON"),
            "onu_id": _record_value(records, "OnuId", "ONUId", "ONTID", default="-"),
            "los": _record_value(records, "LOS", "LosStatus", default="-"),
            "pon_uptime": _record_value(records, "Uptime", "PONUptime"),
        }

    def _wan_records(self) -> list[dict[str, Any]]:
        # wan_list_info.asp defines WanIP/WanPPP constructors while
        # wan_list_cache_wan.asp returns the live new WanPPP/new WanIP
        # instances. Parsing the concatenated sources lets the generic
        # constructor mapper attach the live arguments to their properties.
        _html, records = self._records(
            WAN_INFO_PAGE,
            WAN_CACHE_PAGE,
        )
        return [
            item
            for item in records
            if (
                item.get("_constructor") in {"WanIP", "WanPPP"}
                or "WANIPConnection" in _record_domain(item)
                or "WANPPPConnection" in _record_domain(item)
            )
        ]

    def wan_status(self) -> list[dict[str, Any]]:
        result: list[dict[str, Any]] = []
        for item in self._wan_records():
            domain = _record_domain(item)
            name = (
                item.get("NewName")
                or item.get("Name")
                or item.get("name")
                or domain
            )
            dns_raw = str(
                item.get("dnsstr")
                or item.get("DNSServers")
                or ""
            )
            dns_parts = [
                value.strip()
                for value in dns_raw.split(",")
                if value.strip()
            ]
            dns1 = (
                item.get("IPv4PrimaryDNS")
                or item.get("PrimaryDNS")
                or item.get("DNS1")
                or (dns_parts[0] if dns_parts else "")
            )
            dns2 = (
                item.get("IPv4SecondaryDNS")
                or item.get("SecondaryDNS")
                or item.get("DNS2")
                or (dns_parts[1] if len(dns_parts) > 1 else "")
            )
            result.append({
                "id": domain,
                "nome": name,
                "status": (
                    item.get("ConnectionStatus")
                    or item.get("Status")
                    or ""
                ),
                "ip": (
                    item.get("IPv4IPAddress")
                    or item.get("IPAddress")
                    or item.get("ExternalIPAddress")
                    or ""
                ),
                "gateway": (
                    item.get("IPv4Gateway")
                    or item.get("Gateway")
                    or item.get("DefaultGateway")
                    or ""
                ),
                "vlan": item.get("VlanId") or item.get("VLANID") or "",
                "mtu": (
                    item.get("IPv4MXU")
                    or item.get("MTU")
                    or item.get("MaxMRUSize")
                    or ""
                ),
                "dns1": dns1,
                "dns2": dns2,
                "nat": (
                    item.get("IPv4NATEnable")
                    or item.get("NATEnable")
                    or ""
                ),
                "uptime": item.get("Uptime") or "",
                "ipv6": item.get("IPv6IPAddress") or item.get("IPv6Address") or "",
                "wan_type": (
                    "PPPoE"
                    if "WANPPPConnection" in domain
                    or item.get("_constructor") == "WanPPP"
                    else "IP"
                ),
                "services": item.get("ServiceList") or item.get("ServList") or "",
            })
        return result

    def pppoe_status(self, reveal_password: bool = False) -> list[dict[str, Any]]:
        rows = []
        for item in self._wan_records():
            domain = _record_domain(item)
            if (
                "WANPPPConnection" not in domain
                and item.get("_constructor") != "WanPPP"
            ):
                continue
            password = ""
            if reveal_password:
                password = str(
                    item.get("Password")
                    or item.get("PPPPassword")
                    or ""
                )
            rows.append({
                "id": domain,
                "nome": item.get("NewName") or item.get("Name") or domain,
                "username": item.get("Username") or item.get("UserName") or "",
                "password": password,
                "password_hidden": not reveal_password,
                "auth_type": item.get("PPPAuthenticationProtocol") or item.get("AuthMode") or "",
                "vlan": item.get("VlanId") or item.get("VLANID") or "",
                "mtu": item.get("MTU") or item.get("MaxMRUSize") or "",
            })
        return rows

    def lan_clients(self) -> list[dict[str, Any]]:
        try:
            _html, records = self._records(DHCP_INFO_PAGE)
        except Exception:
            return []
        clients: list[dict[str, Any]] = []
        for item in records:
            ip = (
                item.get("IPAddr")
                or item.get("IPAddress")
                or item.get("Yiaddr")
            )
            mac = (
                item.get("MACAddr")
                or item.get("MACAddress")
                or item.get("Chaddr")
            )
            if not ip or not mac:
                continue
            clients.append({
                "hostname": item.get("HostName") or item.get("hostname") or "",
                "ip": ip,
                "mac": mac,
            })
        return clients

    def wifi_clients(self) -> list[dict[str, Any]]:
        # The capture proved DHCP clients, not an association table with RSSI.
        return []

    def lan_ports(self) -> list[dict[str, Any]]:
        # Link counters/speed were not semantically captured. Expose no fake state.
        return []

    # ----------------------------- LAN / Layer3

    def layer3_status(self) -> dict[str, Any]:
        _html, records = self._records(LAYER3_PAGE)
        ports: list[dict[str, Any]] = []
        prefix = (
            "InternetGatewayDevice.LANDevice.1."
            "LANEthernetInterfaceConfig."
        )
        for instance in ("1", "2", "3", "4"):
            domain = prefix + instance
            record = next(
                (
                    item for item in records
                    if _record_domain(item) == domain
                ),
                {},
            )
            value = (
                record.get("X_HW_L3Enable")
                or record.get("L3Enable")
                or ""
            )
            ports.append({
                "port": int(instance),
                "domain": domain,
                "enabled": _enabled(value),
                "raw": str(value),
            })
        return {
            "ports": ports,
        }

    def set_layer3_ports(
        self,
        config: dict[str, Any],
    ) -> dict[str, Any]:
        current = self.layer3_status()
        current_by_port = {
            str(item["port"]): item
            for item in current.get("ports") or []
        }
        values: dict[str, str] = {}
        for instance in ("1", "2", "3", "4"):
            source = (
                config.get(f"LAN{instance}")
                if f"LAN{instance}" in config
                else config.get(instance)
            )
            if source is None:
                source = (
                    current_by_port.get(instance, {})
                    .get("enabled", True)
                )
            values[f"LAN{instance}.X_HW_L3Enable"] = _as01(source)

        query = "&".join(
            f"LAN{i}=InternetGatewayDevice.LANDevice.1."
            f"LANEthernetInterfaceConfig.{i}"
            for i in ("1", "2", "3", "4")
        )
        path = (
            "/html/bbsp/layer3/set.cgi?"
            + query
            + "&RequestFile=html/bbsp/layer3/layer3.asp"
        )

        def verify():
            actual = self.layer3_status()
            for item in actual.get("ports") or []:
                expected = values.get(
                    f"LAN{item['port']}.X_HW_L3Enable"
                )
                if expected is None:
                    continue
                if item.get("raw") not in ("", expected):
                    return None
            return actual

        return self._post_verified(
            path=path,
            request_file=LAYER3_PAGE,
            payload=values,
            verifier=verify,
        )

    def lan_ipv4_status(self) -> dict[str, Any]:
        _html, records = self._records(DHCP_PAGE)
        interfaces = []
        prefix = (
            "InternetGatewayDevice.LANDevice.1."
            "LANHostConfigManagement.IPInterface."
        )
        for instance in ("1", "2"):
            domain = prefix + instance
            record = next(
                (
                    item for item in records
                    if _record_domain(item) == domain
                ),
                {},
            )
            interfaces.append({
                "domain": domain,
                "instance": int(instance),
                "enabled": _enabled(
                    record.get("Enable", "1")
                ),
                "ip": (
                    record.get("IPInterfaceIPAddress")
                    or record.get("IPAddress")
                    or ""
                ),
                "subnet_mask": (
                    record.get("IPInterfaceSubnetMask")
                    or record.get("SubnetMask")
                    or ""
                ),
            })
        return {"interfaces": interfaces}

    def set_lan_ipv4(
        self,
        config: dict[str, Any],
    ) -> dict[str, Any]:
        current = self.lan_ipv4_status()
        by_instance = {
            str(item["instance"]): item
            for item in current.get("interfaces") or []
        }
        primary = by_instance.get("1") or {}
        secondary = by_instance.get("2") or {}

        primary_ip = str(
            config.get("primary_ip", primary.get("ip") or "")
        )
        primary_mask = str(
            config.get(
                "primary_subnet_mask",
                primary.get("subnet_mask") or "",
            )
        )
        secondary_enabled = bool(
            config.get(
                "secondary_enabled",
                secondary.get("enabled", True),
            )
        )
        secondary_ip = str(
            config.get("secondary_ip", secondary.get("ip") or "")
        )
        secondary_mask = str(
            config.get(
                "secondary_subnet_mask",
                secondary.get("subnet_mask") or "",
            )
        )
        if not primary_ip or not primary_mask:
            raise ValueError(
                "IPv4/máscara primários da LAN são obrigatórios."
            )

        path = (
            "/html/bbsp/dhcp/set.cgi"
            "?x=InternetGatewayDevice.LANDevice.1."
            "LANHostConfigManagement.IPInterface.1"
            "&z=InternetGatewayDevice.LANDevice.1."
            "LANHostConfigManagement.IPInterface.2"
            "&RequestFile=html/bbsp/dhcp/dhcp.asp"
        )
        payload = {
            "x.IPInterfaceIPAddress": primary_ip,
            "x.IPInterfaceSubnetMask": primary_mask,
            "z.Enable": _as01(secondary_enabled),
            "z.IPInterfaceIPAddress": secondary_ip,
            "z.IPInterfaceSubnetMask": secondary_mask,
        }

        # Changing the primary LAN address can intentionally break this HTTP
        # path. In that case _post_verified returns uncertain instead of
        # repeating the mutation.
        def verify():
            actual = self.lan_ipv4_status()
            rows = {
                str(item["instance"]): item
                for item in actual.get("interfaces") or []
            }
            one = rows.get("1") or {}
            two = rows.get("2") or {}
            if str(one.get("ip") or "") != primary_ip:
                return None
            if str(one.get("subnet_mask") or "") != primary_mask:
                return None
            if secondary_ip and str(two.get("ip") or "") != secondary_ip:
                return None
            return actual

        return self._post_verified(
            path=path,
            request_file=DHCP_PAGE,
            payload=payload,
            verifier=verify,
        )

    def ipv6_lan_status(self) -> dict[str, Any]:
        _html, records = self._records(LAN_ADDRESS_PAGE)
        keys = (
            "IPv6Address", "Prefix", "PreferredLifeTime",
            "ValidLifeTime", "Mode", "ParentPrefix",
            "ChildPrefixMask", "MTU", "LanInterface",
            "mode", "Enable", "IPv6DNSConfigType",
            "IPv6DNSWANConnection", "IPv6DNSServers",
            "ULAmode", "IAPDAddLength",
        )
        return {
            key: _record_value(records, key, default="")
            for key in keys
        }

    def set_ipv6_lan(
        self,
        config: dict[str, Any],
    ) -> dict[str, Any]:
        current = self.ipv6_lan_status()
        aliases = {
            "ipv6_address": "IPv6Address",
            "prefix": "Prefix",
            "preferred_lifetime": "PreferredLifeTime",
            "valid_lifetime": "ValidLifeTime",
            "prefix_mode": "Mode",
            "parent_prefix": "ParentPrefix",
            "child_prefix_mask": "ChildPrefixMask",
            "mtu": "MTU",
            "lan_interface": "LanInterface",
            "ra_mode": "mode",
            "ra_enable": "Enable",
            "dns_config_type": "IPv6DNSConfigType",
            "dns_wan_connection": "IPv6DNSWANConnection",
            "dns_servers": "IPv6DNSServers",
            "ula_mode": "ULAmode",
            "iapd_add_length": "IAPDAddLength",
        }
        normalized = dict(current)
        for key, value in config.items():
            target = aliases.get(key, key)
            if target not in current:
                raise ValueError(
                    f"Parâmetro IPv6 LAN Huawei não mapeado: {key}."
                )
            normalized[target] = value

        path = (
            "/html/bbsp/lanaddress/set.cgi"
            "?x=InternetGatewayDevice.LANDevice.1."
            "LANHostConfigManagement.X_HW_IPv6Interface.1.IPv6Address.1"
            "&y=InternetGatewayDevice.LANDevice.1."
            "LANHostConfigManagement.X_HW_IPv6Interface.1.IPv6Prefix.1"
            "&z=InternetGatewayDevice.LANDevice.1."
            "LANHostConfigManagement.X_HW_IPv6Interface.1"
            "&p=InternetGatewayDevice.LANDevice.1.X_HW_IPv6Config"
            "&m=InternetGatewayDevice.LANDevice.1.X_HW_RouterAdvertisement"
            "&r=InternetGatewayDevice.LANDevice.1.X_HW_DHCPv6.Server"
            "&n=InternetGatewayDevice.LANDevice.1."
            "LANHostConfigManagement.X_HW_IPv6Interface.1.ULAIPv6Prefix"
            "&t=InternetGatewayDevice.LANDevice.1.X_HW_DHCPv6.Server.Pool.1"
            "&RequestFile=html/bbsp/lanaddress/lanaddress.asp"
        )
        payload = {
            "x.IPv6Address": str(normalized.get("IPv6Address") or ""),
            "y.Prefix": str(normalized.get("Prefix") or ""),
            "y.PreferredLifeTime": str(normalized.get("PreferredLifeTime") or ""),
            "y.ValidLifeTime": str(normalized.get("ValidLifeTime") or ""),
            "y.Mode": str(normalized.get("Mode") or ""),
            "y.ParentPrefix": str(normalized.get("ParentPrefix") or ""),
            "y.ChildPrefixMask": str(normalized.get("ChildPrefixMask") or ""),
            "m.MTU": str(normalized.get("MTU") or ""),
            "z.LanInterface": str(normalized.get("LanInterface") or ""),
            "m.mode": str(normalized.get("mode") or ""),
            "m.Enable": _as01(normalized.get("Enable")),
            "r.Enable": _as01(normalized.get("Enable")),
            "p.IPv6DNSConfigType": str(normalized.get("IPv6DNSConfigType") or ""),
            "p.IPv6DNSWANConnection": str(normalized.get("IPv6DNSWANConnection") or ""),
            "p.IPv6DNSServers": str(normalized.get("IPv6DNSServers") or ""),
            "n.ULAmode": str(normalized.get("ULAmode") or ""),
            "t.IAPDAddLength": str(normalized.get("IAPDAddLength") or ""),
        }

        def verify():
            actual = self.ipv6_lan_status()
            expected = {
                "IPv6Address": payload["x.IPv6Address"],
                "Prefix": payload["y.Prefix"],
                "MTU": payload["m.MTU"],
                "IPv6DNSConfigType": payload["p.IPv6DNSConfigType"],
            }
            for key, value in expected.items():
                if value and str(actual.get(key) or "") != str(value):
                    return None
            return actual

        return self._post_verified(
            path=path,
            request_file=LAN_ADDRESS_PAGE,
            payload=payload,
            verifier=verify,
        )

    # ----------------------------- DHCP

    def dhcp_status(self) -> dict[str, Any]:
        html, records = self._records(
            DHCP_PAGE,
            DHCP_SERVER_PAGE,
            DHCP_STATIC_PAGE,
            DHCP_INFO_PAGE,
        )
        dns_list = str(
            _record_value(records, "X_HW_DNSList", "DNSList", default="")
            or ""
        )
        dns = [item.strip() for item in dns_list.split(",") if item.strip()]
        server_enable = _record_value(
            records,
            "DHCPServerEnable",
            "ServerEnable",
            default="",
        )
        basic = {
            "_InstID": (
                _record_value(records, "_InstID", "Domain", "domain", default="")
                or "InternetGatewayDevice.LANDevice.1.LANHostConfigManagement"
            ),
            "ServerEnable": _as01(server_enable) if server_enable != "" else "",
            "MinAddress": _record_value(records, "MinAddress", default=""),
            "MaxAddress": _record_value(records, "MaxAddress", default=""),
            "LeaseTime": _record_value(records, "DHCPLeaseTime", "LeaseTime", default=""),
            "DNSServer1": dns[0] if dns else "",
            "DNSServer2": dns[1] if len(dns) > 1 else "",
            "IPAddr": _record_value(records, "IPInterfaceIPAddress", "IPAddr", default=""),
            "SubnetMask": _record_value(records, "IPInterfaceSubnetMask", "SubnetMask", default=""),
        }
        reservations: list[dict[str, Any]] = []
        leases: list[dict[str, Any]] = []
        for item in records:
            domain = _record_domain(item)
            ip = item.get("Yiaddr") or item.get("IPAddr") or item.get("IPAddress")
            mac = item.get("Chaddr") or item.get("MACAddr") or item.get("MACAddress")
            if "DHCPStaticAddress" in domain or (item.get("Yiaddr") and item.get("Chaddr")):
                reservations.append({
                    "_InstID": domain,
                    "Name": item.get("Name") or "",
                    "IPAddr": ip or "",
                    "MACAddr": mac or "",
                })
            elif ip and mac:
                leases.append({
                    "HostName": item.get("HostName") or item.get("hostname") or "",
                    "IPAddr": ip,
                    "MACAddr": mac,
                    "RemainingLeaseTime": (
                        item.get("RemainingLeaseTime")
                        or item.get("LeaseTime")
                        or ""
                    ),
                })
        write_ready = all(
            basic.get(key) not in (None, "")
            for key in ("MinAddress", "MaxAddress", "LeaseTime")
        )
        return {
            "basic": basic,
            "leases": leases,
            "reservations": reservations,
            "ipv6": [],
            "write_safe": True,
            "capabilities": {
                "server_write": write_ready,
                "gateway_write": False,
                "lease_read": True,
                "reservation_write": False,
                "reservation_update": True,
                "reservation_delete": False,
                "ipv6_read": False,
                "ipv6_write": False,
            },
            "warnings": (
                []
                if write_ready
                else ["A página DHCP respondeu, mas nem todos os campos do formulário foram identificados."]
            ),
        }

    def set_dhcp_basic(self, config: dict[str, Any]) -> dict[str, Any]:
        allowed = {
            "enabled", "min_address", "max_address", "dns1", "dns2", "lease_time"
        }
        unsupported = [
            key
            for key, value in config.items()
            if key not in allowed and value not in (None, "", False, [])
        ]
        if unsupported:
            raise ValueError(
                "Campos DHCP Huawei ainda não mapeados: " + ", ".join(unsupported)
            )

        current = self.dhcp_status()["basic"]
        html, records = self._records(DHCP_SERVER_PAGE)

        enabled = (
            config["enabled"]
            if "enabled" in config
            else _enabled(current.get("ServerEnable"))
        )
        min_address = str(config.get("min_address", current.get("MinAddress") or ""))
        max_address = str(config.get("max_address", current.get("MaxAddress") or ""))
        lease = str(config.get("lease_time", current.get("LeaseTime") or ""))

        dns1 = str(config.get("dns1", current.get("DNSServer1") or "") or "")
        dns2 = str(config.get("dns2", current.get("DNSServer2") or "") or "")
        dns_list = ",".join(item for item in (dns1, dns2) if item)

        payload = {
            "z.DHCPServerEnable": _as01(enabled),
            "z.X_HW_DNSList": dns_list,
            "z.MinAddress": min_address,
            "z.MaxAddress": max_address,
            "z.DHCPLeaseTime": lease,
        }
        preservation = {
            "y.DHCPEnable": _record_value(records, "DHCPEnable", default=None),
            "z.X_HW_DHCPL2RelayEnable": _record_value(records, "X_HW_DHCPL2RelayEnable", default=None),
            "z.X_HW_Option125Enable": _record_value(records, "X_HW_Option125Enable", default=None),
        }
        payload.update({
            key: str(value)
            for key, value in preservation.items()
            if value is not None
        })

        path = (
            "/html/bbsp/dhcpservercfg/set.cgi"
            "?x=InternetGatewayDevice.LANDevice.1.LANHostConfigManagement.IPInterface.2"
            "&y=InternetGatewayDevice.X_HW_DHCPSLVSERVER"
            "&z=InternetGatewayDevice.LANDevice.1.LANHostConfigManagement"
            "&RequestFile=html/bbsp/dhcpservercfg/dhcp2.asp"
        )

        def verify():
            actual = self.dhcp_status()["basic"]
            expected = {
                "ServerEnable": _as01(enabled),
                "MinAddress": min_address,
                "MaxAddress": max_address,
                "LeaseTime": lease,
                "DNSServer1": dns1,
                "DNSServer2": dns2,
            }
            for key, value in expected.items():
                if str(actual.get(key) or "") != str(value or ""):
                    return None
            return actual

        result = self._post_verified(
            path=path,
            request_file=DHCP_SERVER_PAGE,
            payload=payload,
            verifier=verify,
        )
        result["basic"] = verify() if result["verified"] else None
        return result

    def update_dhcp_reservation(
        self,
        instance_or_domain: str,
        *,
        ip: str,
        mac: str,
    ) -> dict[str, Any]:
        raw = str(instance_or_domain or "").strip()
        prefix = (
            "InternetGatewayDevice.LANDevice.1."
            "LANHostConfigManagement.DHCPStaticAddress."
        )
        if raw.isdigit():
            domain = prefix + raw
        elif raw.startswith(prefix) and raw[len(prefix):].isdigit():
            domain = raw
        else:
            raise ValueError(
                "Instância DHCP Static Huawei inválida."
            )

        path = (
            "/html/bbsp/dhcpstatic/set.cgi"
            f"?x={domain}"
            "&RequestFile=html/bbsp/dhcpstatic/dhcpstatic.asp"
        )

        def verify():
            actual = self.dhcp_status()
            for item in actual.get("reservations") or []:
                if (
                    item.get("_InstID") == domain
                    and str(item.get("IPAddr") or "") == str(ip)
                    and str(item.get("MACAddr") or "").upper()
                    == str(mac).upper()
                ):
                    return item
            return None

        return self._post_verified(
            path=path,
            request_file=DHCP_STATIC_PAGE,
            payload={
                "x.Yiaddr": str(ip),
                "x.Chaddr": str(mac),
            },
            verifier=verify,
        )

    # ----------------------------- DNS

    def dns_status(self) -> dict[str, Any]:
        _html, records = self._records(DNS_PAGE, DNS_HOSTS_PAGE)
        search_rows = [
            item
            for item in records
            if (
                "SearList" in _record_domain(item)
                or (
                    item.get("DNSServer") not in (None, "")
                    and item.get("Interface") not in (None, "")
                )
            )
        ]
        host_rows = [
            item
            for item in records
            if (
                "X_HW_DNS.HOSTS" in _record_domain(item)
                or (
                    item.get("IPAddress") not in (None, "")
                    and item.get("DomainName") not in (None, "")
                    and item not in search_rows
                )
            )
        ]
        ipv4 = [
            str(item.get("DNSServer") or "")
            for item in search_rows
            if item.get("DNSServer")
        ]
        domain = ""
        if search_rows:
            domain = str(search_rows[0].get("DomainName") or "")
        elif host_rows:
            domain = str(host_rows[0].get("DomainName") or "")
        return {
            "domain_name": domain,
            "ipv4_1": ipv4[0] if ipv4 else "",
            "ipv4_2": ipv4[1] if len(ipv4) > 1 else "",
            "ipv6_1": "",
            "ipv6_2": "",
            "hosts": [
                {
                    "id": _record_domain(item),
                    "nome": item.get("DomainName") or "",
                    "ip": item.get("IPAddress") or "",
                }
                for item in host_rows
            ],
            "_search_rows": search_rows,
        }

    def set_dns(self, config: dict[str, Any]) -> dict[str, Any]:
        if config.get("ipv6_1") or config.get("ipv6_2"):
            raise ValueError("DNS IPv6 Huawei ainda não foi validado neste profile.")
        if config.get("hosts"):
            raise ValueError(
                "Criação/remoção de hosts DNS Huawei não foi capturada; somente a lista DNS validada pode ser alterada."
            )

        current = self.dns_status()
        rows = current.pop("_search_rows", [])
        row = rows[0] if rows else {}
        interface = str(row.get("Interface") or "")
        if not interface:
            raise RuntimeError(
                "A interface WAN vinculada ao DNS não foi identificada; nenhuma alteração foi enviada."
            )
        domain_obj = _record_domain(row) or "InternetGatewayDevice.X_HW_DNS.SearList.1"
        dns1 = str(config.get("ipv4_1", current.get("ipv4_1") or "") or "")
        domain_name = str(config.get("domain_name", current.get("domain_name") or "") or "")
        if not dns1:
            raise ValueError("Informe o DNS IPv4 principal.")

        path = (
            "/html/bbsp/dnsconfiguration/set.cgi"
            f"?x={domain_obj}"
            "&RequestFile=html/bbsp/dnsconfiguration/dnsconfigcommon.asp"
        )
        payload = {
            "x.DNSServer": dns1,
            "x.DomainName": domain_name,
            "x.Interface": interface,
        }

        def verify():
            actual = self.dns_status()
            if str(actual.get("ipv4_1") or "") != dns1:
                return None
            if domain_name and str(actual.get("domain_name") or "") != domain_name:
                return None
            return actual

        return self._post_verified(
            path=path,
            request_file=DNS_PAGE,
            payload=payload,
            verifier=verify,
        )

    def update_dns_host(
        self,
        instance_or_domain: str,
        *,
        ip: str,
        domain_name: str,
    ) -> dict[str, Any]:
        raw = str(instance_or_domain or "").strip()
        prefix = "InternetGatewayDevice.X_HW_DNS.HOSTS."
        if raw.isdigit():
            domain = prefix + raw
        elif raw.startswith(prefix) and raw[len(prefix):].isdigit():
            domain = raw
        else:
            raise ValueError(
                "Instância DNS HOSTS Huawei inválida."
            )

        path = (
            "/html/bbsp/dnsconfiguration/set.cgi"
            f"?x={domain}"
            "&RequestFile=html/bbsp/dnsconfiguration/dnsconfigcommon.asp"
        )

        def verify():
            actual = self.dns_status()
            for item in actual.get("hosts") or []:
                if (
                    item.get("id") == domain
                    and str(item.get("ip") or "") == str(ip)
                    and str(item.get("nome") or "") == str(domain_name)
                ):
                    return item
            return None

        return self._post_verified(
            path=path,
            request_file=DNS_PAGE,
            payload={
                "x.IPAddress": str(ip),
                "x.DomainName": str(domain_name),
            },
            verifier=verify,
        )

    # ----------------------------- DMZ

    def dmz_status(self) -> dict[str, Any]:
        _html, records = self._records(DMZ_PAGE)
        record = next(
            (
                item for item in records
                if "X_HW_DMZ" in _record_domain(item)
                or "DMZEnable" in item
            ),
            {},
        )
        return {
            "available": bool(record),
            "id": _record_domain(record) or WAN_DMZ_DOMAIN,
            "enabled": _enabled(record.get("DMZEnable")),
            "internal_client": str(record.get("DMZHostIPAddress") or ""),
            "wan": "",
        }

    def set_dmz(self, config: dict[str, Any]) -> dict[str, Any]:
        current = self.dmz_status()
        domain = current.get("id") or WAN_DMZ_DOMAIN
        enabled = bool(config.get("enabled", current.get("enabled", False)))
        host = str(config.get("internal_client", current.get("internal_client") or "") or "")
        path = (
            "/html/bbsp/dmz/set.cgi"
            f"?x={domain}"
            "&RequestFile=html/bbsp/dmz/dmz.asp"
        )

        def verify():
            actual = self.dmz_status()
            if bool(actual.get("enabled")) != enabled:
                return None
            if str(actual.get("internal_client") or "") != host:
                return None
            return actual

        return self._post_verified(
            path=path,
            request_file=DMZ_PAGE,
            payload={
                "x.DMZEnable": _as01(enabled),
                "x.DMZHostIPAddress": host,
            },
            verifier=verify,
        )

    # ----------------------------- Wi-Fi

    def _wifi_pages(self, band: str) -> tuple[str, str, str, str]:
        display, instance, query_band = _band_details(band)
        return (
            display,
            instance,
            f"{WLAN_BASIC_PAGE}?{query_band}",
            f"{WLAN_ADV_PAGE}?{query_band}",
        )

    def _wifi_basic_record(self, band: str) -> tuple[dict[str, Any], list[dict[str, Any]]]:
        _display, instance, page, _adv = self._wifi_pages(band)
        _html, records = self._records(page)
        domain_suffix = f"WLANConfiguration.{instance}"
        candidates = [
            item
            for item in records
            if (
                item.get("SSID") not in (None, "")
                and (
                    domain_suffix in _record_domain(item)
                    or str(item.get("SsidInst") or "") == instance
                )
            )
        ]
        if not candidates:
            candidates = [
                item
                for item in records
                if item.get("SSID") not in (None, "")
            ]
        merged: dict[str, Any] = {}
        for item in candidates:
            merged.update({
                key: value
                for key, value in item.items()
                if value not in (None, "")
            })
        return merged, records

    def wifi_networks(self, reveal_password: bool = False) -> list[dict[str, Any]]:
        networks = []
        for band in ("2.4GHz", "5GHz"):
            display, instance, _page, _adv = self._wifi_pages(band)
            record, records = self._wifi_basic_record(band)
            if not record:
                continue
            domain = _record_domain(record)
            if not domain or "WLANConfiguration" not in domain:
                domain = f"InternetGatewayDevice.LANDevice.1.WLANConfiguration.{instance}"
            networks.append({
                "id": domain,
                "ssid": record.get("SSID") or _record_value(records, "SSID", default=""),
                "banda": display,
                "ativo": _enabled(record.get("Enable", _record_value(records, "Enable", default="1"))),
                "seguranca": record.get("BeaconType") or _record_value(records, "BeaconType", default=""),
                "max_clientes": (
                    record.get("X_HW_AssociateNum")
                    or record.get("MaxAssociateNum")
                    or _record_value(records, "X_HW_AssociateNum", "MaxAssociateNum", default=64)
                ),
                "broadcast": _enabled(
                    record.get(
                        "SSIDAdvertisementEnabled",
                        _record_value(records, "SSIDAdvertisementEnabled", default="1"),
                    )
                ),
                "isolamento": False,
                "password": "",
                "password_hidden": True,
            })
        return networks

    def _band_from_ssid_id(self, ssid_id: str) -> str:
        raw = str(ssid_id or "")
        if raw.endswith(".5") or raw == "5" or "5GHz" in raw:
            return "5GHz"
        if raw.endswith(".1") or raw == "1" or "2.4" in raw:
            return "2.4GHz"
        raise ValueError("SSID Huawei deve identificar WLANConfiguration.1 ou .5.")

    def set_ssid_config(self, ssid_id: str, config: dict[str, Any]) -> dict[str, Any]:
        band = self._band_from_ssid_id(ssid_id)
        display, instance, basic_page, _adv_page = self._wifi_pages(band)
        current = next(
            (item for item in self.wifi_networks(False) if item["banda"] == display),
            None,
        )
        if current is None:
            raise RuntimeError("A configuração Wi-Fi Huawei não pôde ser relida.")

        if config.get("password"):
            raise ValueError(
                "A alteração de senha Wi-Fi não foi capturada no formulário Huawei; nenhuma alteração foi enviada."
            )
        if config.get("isolation") not in (None, False):
            raise ValueError(
                "Isolamento SSID Huawei ainda não foi validado neste profile."
            )

        encryption = config.get("encryption")
        if encryption not in (None, "", current.get("seguranca")):
            raise ValueError(
                "Alteração do modo de segurança Wi-Fi ainda não foi validada para esta captura."
            )

        ssid = str(config.get("ssid", current.get("ssid") or ""))
        enabled = bool(config.get("enabled", current.get("ativo", True)))
        broadcast = bool(config.get("broadcast", current.get("broadcast", True)))
        max_clients = str(config.get("max_clients", current.get("max_clientes") or 64))

        y = f"InternetGatewayDevice.LANDevice.1.WLANConfiguration.{instance}"
        z = f"{y}.WPS"
        w = "InternetGatewayDevice.X_HW_DEBUG.AMP.WifiCoverSetWlanBasic"
        c = "InternetGatewayDevice.X_HW_DEBUG.WLANConfigAction"
        path = (
            "/html/amp/wlanbasic/set.cgi"
            f"?c1={c}&w={w}&y={y}&z={z}&k={y}.PreSharedKey.1&c2={c}"
            "&RequestFile=html/amp/wlanbasic/WlanBasic.asp"
        )
        record, records = self._wifi_basic_record(band)
        beacon_type = str(
            record.get("BeaconType")
            or _record_value(records, "BeaconType", default="")
            or current.get("seguranca")
            or ""
        )
        if not beacon_type:
            raise RuntimeError(
                "O modo de segurança Wi-Fi atual não foi identificado; "
                "nenhum POST foi enviado."
            )

        # WlanBasic.asp submits a complete form. Preserve every captured
        # non-secret field instead of sending a partial POST that could reset
        # security/WPS defaults. The capture contained no PSK field.
        def preserved(name: str, default: str) -> str:
            value = (
                record.get(name)
                or _record_value(records, name, default="")
            )
            return str(value if value not in (None, "") else default)

        auth_default = (
            "PSKandSAEAuthentication"
            if beacon_type == "WPA2/WPA3"
            else ""
        )
        if beacon_type != "WPA2/WPA3" and not preserved(
            "X_HW_WPAand11iAuthenticationMode",
            "",
        ):
            raise RuntimeError(
                "O formulário Huawei não expôs os campos necessários para "
                "preservar a segurança atual do SSID."
            )

        payload = {
            "y.Enable": _as01(enabled),
            "y.SSIDAdvertisementEnabled": _as01(broadcast),
            "y.SSID": ssid,
            "y.X_HW_AssociateNum": max_clients,
            "y.BeaconType": beacon_type,
            "y.X_HW_WPAand11iAuthenticationMode": preserved(
                "X_HW_WPAand11iAuthenticationMode",
                auth_default,
            ),
            "y.X_HW_WPAand11iEncryptionModes": preserved(
                "X_HW_WPAand11iEncryptionModes",
                "AESEncryption",
            ),
            "y.X_HW_GroupRekey": preserved(
                "X_HW_GroupRekey",
                "3600",
            ),
            "z.Enable": preserved("WPSEnable", "1"),
            "z.X_HW_ConfigMethod": preserved(
                "X_HW_ConfigMethod",
                "PushButton",
            ),
            "w.SsidInst": instance,
            "w.SSID": ssid,
            "w.Enable": _as01(enabled),
            "w.Standard": preserved("Standard", "11ax"),
            "w.BasicAuthenticationMode": preserved(
                "BasicAuthenticationMode",
                "None",
            ),
            "w.BasicEncryptionModes": preserved(
                "BasicEncryptionModes",
                "AESEncryption",
            ),
            "w.WPAAuthenticationMode": preserved(
                "WPAAuthenticationMode",
                "EAPAuthentication",
            ),
            "w.WPAEncryptionModes": preserved(
                "WPAEncryptionModes",
                "AESEncryption",
            ),
            "w.IEEE11iAuthenticationMode": preserved(
                "IEEE11iAuthenticationMode",
                "EAPAuthentication",
            ),
            "w.IEEE11iEncryptionModes": preserved(
                "IEEE11iEncryptionModes",
                "AESEncryption",
            ),
            "w.MixAuthenticationMode": preserved(
                "MixAuthenticationMode",
                auth_default or "PSKandSAEAuthentication",
            ),
            "w.MixEncryptionModes": preserved(
                "MixEncryptionModes",
                "AESEncryption",
            ),
            "w.SSIDAdvertisementEnabled": _as01(broadcast),
            "w.WMMEnable": preserved("WMMEnable", "1"),
            "w.MaxAssociateNum": max_clients,
            "w.BeaconType": beacon_type,
            "w.WEPEncryptionLevel": preserved(
                "WEPEncryptionLevel",
                "104-bit",
            ),
            "w.WEPKeyIndex": preserved("WEPKeyIndex", "1"),
            "c1.ActionType": "0",
            "c2.ActionType": "1",
            "c2.SSIDList": instance,
        }

        def verify():
            actual = next(
                (item for item in self.wifi_networks(False) if item["banda"] == display),
                None,
            )
            if not actual:
                return None
            if str(actual.get("ssid") or "") != ssid:
                return None
            if bool(actual.get("ativo")) != enabled:
                return None
            if bool(actual.get("broadcast")) != broadcast:
                return None
            if str(actual.get("max_clientes") or "") != max_clients:
                return None
            return actual

        return self._post_verified(
            path=path,
            request_file=basic_page,
            payload=payload,
            verifier=verify,
        )

    @staticmethod
    def _standard_for_ui(raw: Any, band: str) -> str:
        value = str(raw or "")
        if value == "11ax":
            return "a,n,ac,ax" if band == "5GHz" else "b,g,n,ax"
        return value

    @staticmethod
    def _power_for_ui(raw: Any) -> str:
        value = str(raw or "")
        if value and not value.endswith("%"):
            return value + "%"
        return value or "100%"

    def wifi_radios(self) -> list[dict[str, Any]]:
        radios = []
        for band in ("2.4GHz", "5GHz"):
            display, instance, _basic, adv_page = self._wifi_pages(band)
            _html, records = self._records(adv_page)
            domain_suffix = f"WLANConfiguration.{instance}"
            relevant = [
                item
                for item in records
                if domain_suffix in _record_domain(item)
            ]
            if not relevant:
                relevant = records
            channel = _record_value(relevant, "Channel", default="0")
            auto = _enabled(_record_value(relevant, "AutoChannelEnable", default="1"))
            raw_standard = _record_value(relevant, "X_HW_Standard", "Standard", default="11ax")
            raw_bw = str(_record_value(relevant, "X_HW_HT20", default=""))
            # Only values observed in this physical capture are mapped.
            bandwidth = (
                "Auto"
                if display == "2.4GHz" and raw_bw == "0"
                else "80MHz"
                if display == "5GHz" and raw_bw == "4"
                else "Auto"
            )
            basic = next(
                (row for row in self.wifi_networks(False) if row["banda"] == display),
                {},
            )
            radios.append({
                "id": f"InternetGatewayDevice.LANDevice.1.WLANConfiguration.{instance}",
                "banda": display,
                "canal": str(channel),
                "canal_automatico": auto or str(channel) == "0",
                "largura": bandwidth,
                "padrao": self._standard_for_ui(raw_standard, display),
                "pais": _record_value(relevant, "RegulatoryDomain", default="BR"),
                "potencia": self._power_for_ui(
                    _record_value(relevant, "TransmitPower", default="100")
                ),
                "beacon_interval": _record_value(relevant, "BeaconPeriod", default=100),
                "sgi": False,
                "mu_mimo": False,
                "downlink_ofdma": False,
                "twt": False,
                "radio_ativo": bool(basic.get("ativo", True)),
                "_raw_ht20": raw_bw,
                "_raw_standard": str(raw_standard),
                "_raw_dtim": str(
                    _record_value(relevant, "DtimPeriod", default="1")
                ),
                "_raw_rts": str(
                    _record_value(relevant, "RTSThreshold", default="2346")
                ),
                "_raw_frag": str(
                    _record_value(relevant, "FragThreshold", default="2346")
                ),
                "_raw_band_steering": str(
                    _record_value(relevant, "BandSteeringPolicy", default="1")
                ),
                "_raw_airtime": str(
                    _record_value(relevant, "X_HW_AirtimeFairness", default="0")
                ),
                "_raw_auto_scope": str(
                    _record_value(relevant, "X_HW_AutoChannelScope", default="0")
                ),
            })
        return radios

    def wifi_channels(
        self,
        band: str | None = None,
        bandwidth: str | None = None,
        country: str = "BRI",
    ) -> list[dict[str, Any]]:
        normalized = "5GHz" if "5" in str(band or "") else "2.4GHz"
        channels = (
            [36, 40, 44, 48, 52, 56, 60, 64, 100, 104, 108, 112,
             116, 120, 124, 128, 132, 136, 140, 144, 149, 153, 157, 161, 165]
            if normalized == "5GHz"
            else list(range(1, 12))
        )
        return [{
            "banda": normalized,
            "largura": bandwidth or "Auto",
            "pais": country,
            "canais": channels,
        }]

    def set_wifi_radio(self, band: str, config: dict[str, Any]) -> dict[str, Any]:
        display, instance, _basic, adv_page = self._wifi_pages(band)
        current = next(
            (row for row in self.wifi_radios() if row["banda"] == display),
            None,
        )
        if current is None:
            raise RuntimeError("O rádio Huawei não pôde ser relido.")

        for key, label in (
            ("bandwidth", "largura de canal"),
            ("standard", "padrão Wi-Fi"),
            ("sgi", "SGI"),
        ):
            if key in config and config[key] not in (None, current.get(
                {"bandwidth": "largura", "standard": "padrao", "sgi": "sgi"}[key]
            )):
                raise ValueError(
                    f"Alteração de {label} Huawei ainda não foi validada nesta captura."
                )

        auto = bool(config.get("auto_channel", current.get("canal_automatico", True)))
        channel = "0" if auto else str(config.get("channel") or current.get("canal") or "0")
        country = str(config.get("country", current.get("pais") or "BR") or "BR")
        power = str(config.get("tx_power", current.get("potencia") or "100%") or "100%").rstrip("%")
        beacon = str(config.get("beacon_interval", current.get("beacon_interval") or 100))

        y = f"InternetGatewayDevice.LANDevice.1.WLANConfiguration.{instance}"
        radio = "1" if instance == "1" else "2"
        x = f"{y}.X_HW_AdvanceConf"
        v = f"{y}.X_HW_AttachConf"
        c = "InternetGatewayDevice.X_HW_DEBUG.WLANConfigAction"
        query = (
            f"?c1={c}&x={x}&v={v}&y={y}&r=InternetGatewayDevice.LANDevice.1.WiFi.Radio.{radio}"
        )
        if instance == "5":
            query += "&z=InternetGatewayDevice.LANDevice.1.WiFi.X_HW_GlobalConfig"
        query += f"&c2={c}&RequestFile=html/amp/wlanadv/WlanAdvance.asp"
        path = "/html/amp/wlanadv/set.cgi" + query

        payload = {
            "y.Channel": channel,
            "y.AutoChannelEnable": _as01(auto),
            "y.RegulatoryDomain": country,
            "y.TransmitPower": power,
            "y.X_HW_HT20": str(
                current.get("_raw_ht20")
                or ("4" if instance == "5" else "0")
            ),
            "y.X_HW_Standard": str(
                current.get("_raw_standard")
                or "11ax"
            ),
            "x.DtimPeriod": str(
                current.get("_raw_dtim")
                or "1"
            ),
            "x.BeaconPeriod": beacon,
            "x.RTSThreshold": str(
                current.get("_raw_rts")
                or "2346"
            ),
            "x.FragThreshold": str(
                current.get("_raw_frag")
                or "2346"
            ),
            "z.BandSteeringPolicy": str(
                current.get("_raw_band_steering")
                or "1"
            ),
            "v.X_HW_AirtimeFairness": str(
                current.get("_raw_airtime")
                or "0"
            ),
            "c1.ActionType": "0",
            "c2.ActionType": "1",
            "c2.SSIDList": instance,
        }
        if instance == "5":
            payload["y.X_HW_AutoChannelScope"] = str(
                current.get("_raw_auto_scope")
                or "0"
            )

        def verify():
            actual = next(
                (row for row in self.wifi_radios() if row["banda"] == display),
                None,
            )
            if not actual:
                return None
            if bool(actual.get("canal_automatico")) != auto:
                return None
            if not auto and str(actual.get("canal") or "") != channel:
                return None
            if str(actual.get("pais") or "") != country:
                return None
            if str(actual.get("potencia") or "").rstrip("%") != power:
                return None
            if str(actual.get("beacon_interval") or "") != beacon:
                return None
            return actual

        return self._post_verified(
            path=path,
            request_file=adv_page,
            payload=payload,
            verifier=verify,
        )

    def radio_power_status(self) -> list[dict[str, Any]]:
        return [
            {"band": item["banda"], "enabled": item["ativo"]}
            for item in self.wifi_networks(False)
        ]

    def set_radio_power(self, band: str, enabled: bool) -> dict[str, Any]:
        network = next(
            (
                item for item in self.wifi_networks(False)
                if item["banda"] == _band_details(band)[0]
            ),
            None,
        )
        if not network:
            raise RuntimeError("SSID principal Huawei não encontrado.")
        return self.set_ssid_config(
            network["id"],
            {
                "enabled": bool(enabled),
                "ssid": network["ssid"],
                "broadcast": network["broadcast"],
                "max_clients": network["max_clientes"],
                "encryption": network["seguranca"],
            },
        )

    # ----------------------------- TR-069

    def tr069_management_status(self) -> dict[str, Any]:
        _html, records = self._records(TR069_PAGE)
        record = next(
            (
                item for item in records
                if "ManagementServer" in _record_domain(item)
                or "URL" in item
            ),
            {},
        )
        server = {
            "URL": record.get("URL") or _record_value(records, "URL", default=""),
            "UserName": record.get("UserName") or record.get("Username") or "",
            "PeriodicInformEnable": record.get("PeriodicInformEnable") or "",
            "PeriodicInformInterval": record.get("PeriodicInformInterval") or "",
            "DefaultWan": record.get("DefaultWan") or "",
            "ConnectionRequestUsername": record.get("ConnectionRequestUsername") or "",
        }
        return {
            "available": bool(records),
            "server": server,
        }

    def tr069_setup(self) -> dict[str, Any]:
        status = self.tr069_management_status()
        server = status.get("server") or {}
        return {
            "available": status.get("available") is True,
            "acs_secret_exists": True,
            "request_secret_exists": True,
            "wan_candidates": [
                {
                    "name": item.get("nome") or item.get("id"),
                    "services": item.get("services") or "",
                }
                for item in self.wan_status()
                if "TR069" in str(item.get("services") or "").upper()
            ],
            "current": {
                key: server.get(key)
                for key in (
                    "URL", "UserName", "PeriodicInformEnable",
                    "PeriodicInformInterval", "DefaultWan",
                    "ConnectionRequestUsername",
                )
            },
            "limited": True,
            "note": "Captura Huawei validou alteração da URL ACS; credenciais TR-069 não são alteradas por este profile.",
        }

    def set_management_tr069(
        self,
        config: dict[str, Any],
        *,
        confirm: bool = True,
    ) -> dict[str, Any]:
        url = str(config.get("url") or config.get("URL") or "")
        extras = {
            key: value
            for key, value in config.items()
            if key not in {"url", "URL", "confirm"}
            and value not in (None, "", False, [])
        }
        if extras:
            raise ValueError(
                "A captura Huawei validou somente a URL ACS; os demais parâmetros TR-069 não serão enviados."
            )
        if not url:
            raise ValueError("Informe a URL ACS.")

        path = (
            "/html/ssmp/tr069/set.cgi"
            "?x=InternetGatewayDevice.ManagementServer"
            "&RequestFile=html/ssmp/tr069/tr069.asp"
        )

        def verify():
            actual = self.tr069_management_status()
            if str((actual.get("server") or {}).get("URL") or "") != url:
                return None
            return actual

        return self._post_verified(
            path=path,
            request_file=TR069_PAGE,
            payload={"x.URL": url},
            verifier=verify,
        )

    # ----------------------------- Security / misc captured toggles

    def firewall_management_status(self) -> dict[str, Any]:
        pages = (
            FIREWALL_PAGE, DOS_PAGE, IPV6_FIREWALL_PAGE,
            INTERNET_CONTROL_PAGE, ALG_PAGE, IGMP_PAGE,
        )
        _html, records = self._records(*pages)
        return {
            "available": bool(records),
            "firewall": {
                "Enable": _record_value(records, "Enable", default=""),
                "AdvancedLevel": _record_value(records, "AdvancedLevel", default=""),
            },
            "dos": {
                key: _record_value(records, key, default="")
                for key in (
                    "SynFloodEn", "IcmpEchoReplyEn", "IcmpRedirectEn",
                    "LandEn", "SmurfEn", "WinnukeEn", "PingSweepEn",
                )
            },
            "ipv6_firewall": _record_value(
                records, "X_HW_IPv6FWDFireWallEnable", default=""
            ),
            "alg": {
                key: _record_value(records, key, default="")
                for key in (
                    "FtpEnable", "TftpEnable", "H323Enable", "SipEnable",
                    "RTSPEnable", "PptpEnable", "L2TPForward",
                    "IPSecForward", "RTCPEnable", "RTCPPort",
                )
            },
            "igmp": _record_value(records, "IGMPEnable", default=""),
        }

    def alg_status(self) -> dict[str, Any]:
        _html, records = self._records(ALG_PAGE)
        return {
            key: _record_value(records, key, default="")
            for key in (
                "FtpEnable", "TftpEnable", "H323Enable", "SipEnable",
                "RTSPEnable", "PptpEnable", "L2TPForward",
                "IPSecForward", "RTCPEnable", "RTCPPort",
            )
        }

    def set_alg(self, config: dict[str, Any]) -> dict[str, Any]:
        current = self.alg_status()
        keys = (
            "FtpEnable", "TftpEnable", "H323Enable", "SipEnable",
            "RTSPEnable", "PptpEnable", "L2TPForward",
            "IPSecForward", "RTCPEnable", "RTCPPort",
        )
        aliases = {
            "ftp": "FtpEnable",
            "tftp": "TftpEnable",
            "h323": "H323Enable",
            "sip": "SipEnable",
            "rtsp": "RTSPEnable",
            "pptp": "PptpEnable",
            "l2tp": "L2TPForward",
            "ipsec": "IPSecForward",
            "rtcp": "RTCPEnable",
            "rtcp_port": "RTCPPort",
        }
        normalized = dict(current)
        for key, value in config.items():
            target = aliases.get(key, key)
            if target not in keys:
                raise ValueError(
                    f"Parâmetro ALG Huawei não mapeado: {key}."
                )
            normalized[target] = value

        payload = {
            f"x.{key}": (
                str(value)
                if key == "RTCPPort"
                else _as01(value)
            )
            for key, value in normalized.items()
            if key in keys
        }
        path = (
            "/html/bbsp/alg/set.cgi"
            "?x=InternetGatewayDevice.X_HW_ALG"
            "&RequestFile=html/bbsp/alg/alg.asp"
        )

        def verify():
            actual = self.alg_status()
            for key in keys:
                expected = payload.get(f"x.{key}")
                if expected is None:
                    continue
                if str(actual.get(key) or "") != str(expected):
                    return None
            return actual

        return self._post_verified(
            path=path,
            request_file=ALG_PAGE,
            payload=payload,
            verifier=verify,
        )

    def igmp_status(self) -> dict[str, Any]:
        _html, records = self._records(IGMP_PAGE)
        raw = _record_value(records, "IGMPEnable", default="")
        return {
            "IGMPEnable": raw,
            "enabled": _enabled(raw),
        }

    def set_igmp(self, config: dict[str, Any]) -> dict[str, Any]:
        enabled = config.get(
            "enabled",
            config.get(
                "IGMPEnable",
                self.igmp_status().get("IGMPEnable"),
            ),
        )
        expected = _as01(enabled)
        path = (
            "/html/bbsp/igmp/set.cgi"
            "?x=InternetGatewayDevice.Services.X_HW_IPTV"
            "&RequestFile=html/bbsp/igmp/igmp.asp"
        )

        def verify():
            actual = self.igmp_status()
            return actual if str(actual.get("IGMPEnable") or "") == expected else None

        return self._post_verified(
            path=path,
            request_file=IGMP_PAGE,
            payload={"x.IGMPEnable": expected},
            verifier=verify,
        )

    def dos_status(self) -> dict[str, Any]:
        _html, records = self._records(DOS_PAGE)
        return {
            key: _record_value(records, key, default="")
            for key in (
                "SynFloodEn", "IcmpEchoReplyEn", "IcmpRedirectEn",
                "LandEn", "SmurfEn", "WinnukeEn", "PingSweepEn",
            )
        }

    def set_dos(self, config: dict[str, Any]) -> dict[str, Any]:
        keys = (
            "SynFloodEn", "IcmpEchoReplyEn", "IcmpRedirectEn",
            "LandEn", "SmurfEn", "WinnukeEn", "PingSweepEn",
        )
        current = self.dos_status()
        normalized = dict(current)
        for key, value in config.items():
            if key not in keys:
                raise ValueError(
                    f"Parâmetro DoS Huawei não mapeado: {key}."
                )
            normalized[key] = value

        payload = {
            f"x.{key}": _as01(normalized.get(key))
            for key in keys
        }
        path = (
            "/html/bbsp/Dos/set.cgi"
            "?x=InternetGatewayDevice.X_HW_Security.Dosfilter"
            "&RequestFile=html/bbsp/Dos/Dos.asp"
        )

        def verify():
            actual = self.dos_status()
            for key in keys:
                if str(actual.get(key) or "") != payload[f"x.{key}"]:
                    return None
            return actual

        return self._post_verified(
            path=path,
            request_file=DOS_PAGE,
            payload=payload,
            verifier=verify,
        )

    def ipv6_firewall_status(self) -> dict[str, Any]:
        _html, records = self._records(IPV6_FIREWALL_PAGE)
        raw = _record_value(
            records,
            "X_HW_IPv6FWDFireWallEnable",
            default="",
        )
        return {
            "X_HW_IPv6FWDFireWallEnable": raw,
            "enabled": _enabled(raw),
        }

    def set_ipv6_firewall(self, config: dict[str, Any]) -> dict[str, Any]:
        enabled = config.get(
            "enabled",
            config.get(
                "X_HW_IPv6FWDFireWallEnable",
                self.ipv6_firewall_status().get(
                    "X_HW_IPv6FWDFireWallEnable"
                ),
            ),
        )
        expected = _as01(enabled)
        path = (
            "/html/bbsp/ipv6firewall/set.cgi"
            "?x=InternetGatewayDevice.X_HW_Security"
            "&RequestFile=html/bbsp/ipv6firewall/firewall.asp"
        )

        def verify():
            actual = self.ipv6_firewall_status()
            return (
                actual
                if str(
                    actual.get("X_HW_IPv6FWDFireWallEnable")
                    or ""
                ) == expected
                else None
            )

        return self._post_verified(
            path=path,
            request_file=IPV6_FIREWALL_PAGE,
            payload={
                "x.X_HW_IPv6FWDFireWallEnable": expected
            },
            verifier=verify,
        )

    def internet_control_status(self) -> dict[str, Any]:
        _html, records = self._records(INTERNET_CONTROL_PAGE)
        raw = _record_value(records, "Enable", default="")
        return {
            "Enable": raw,
            "enabled": _enabled(raw),
        }

    def set_internet_control(self, config: dict[str, Any]) -> dict[str, Any]:
        enabled = config.get(
            "enabled",
            config.get(
                "Enable",
                self.internet_control_status().get("Enable"),
            ),
        )
        expected = _as01(enabled)
        path = (
            "/html/bbsp/internetcontrol/set.cgi"
            "?x=InternetGatewayDevice.X_HW_Security.X_HW_InternetOffCtrl"
            "&RequestFile=html/bbsp/internetcontrol/internetcontrol.asp"
        )

        def verify():
            actual = self.internet_control_status()
            return actual if str(actual.get("Enable") or "") == expected else None

        return self._post_verified(
            path=path,
            request_file=INTERNET_CONTROL_PAGE,
            payload={"x.Enable": expected},
            verifier=verify,
        )

    def set_management_firewall(
        self,
        config: dict[str, Any],
        *,
        confirm: bool = False,
    ) -> dict[str, Any]:
        allowed = {
            "enabled", "Enable",
            "level", "advanced_level", "AdvancedLevel",
        }
        extras = [
            key for key, value in config.items()
            if key not in allowed and value not in (None, "", False, [])
        ]
        if extras:
            raise ValueError(
                "Este formulário Huawei aceita apenas nível/estado global do firewall; use as capabilities específicas para outros filtros."
            )
        current = self.firewall_management_status()["firewall"]
        enabled = config.get("enabled", config.get("Enable", current.get("Enable")))
        level = str(
            config.get(
                "level",
                config.get(
                    "advanced_level",
                    config.get(
                        "AdvancedLevel",
                        current.get("AdvancedLevel") or "",
                    ),
                ),
            )
        )
        path = (
            "/html/bbsp/firewalllevel/set.cgi"
            "?x=InternetGatewayDevice.X_HW_Security.Firewall"
            "&RequestFile=html/bbsp/firewalllevel/firewalllevel.asp"
        )

        def verify():
            actual = self.firewall_management_status()["firewall"]
            if str(actual.get("Enable") or "") != _as01(enabled):
                return None
            if level and str(actual.get("AdvancedLevel") or "") != level:
                return None
            return actual

        return self._post_verified(
            path=path,
            request_file=FIREWALL_PAGE,
            payload={
                "x.Enable": _as01(enabled),
                "x.AdvancedLevel": level,
            },
            verifier=verify,
        )

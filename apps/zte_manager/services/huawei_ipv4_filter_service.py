from __future__ import annotations

import re
import time
from dataclasses import asdict, dataclass
from typing import Callable, Iterable

from apps.zte_manager.infrastructure.huawei import (
    HuaweiMutationTransport,
    HuaweiWebClient,
    decode_huawei_js_string,
)
from apps.zte_manager.model.device_adapters.huawei import (
    HuaweiIPv4FilterCapability,
    huawei_ipv4_filter_capability,
)


PAGE = "/html/bbsp/ipincoming/ipincoming.asp"
DIR = "/html/bbsp/ipincoming"
DOMAIN_PREFIX = (
    "InternetGatewayDevice.X_HW_Security.IpFilterIn."
)


@dataclass(frozen=True)
class HuaweiIPv4FilterRule:
    domain: str
    name: str = ""
    protocol: str = ""
    direction: str = ""
    lan_start_ip: str = ""
    lan_end_ip: str = ""
    wan_start_ip: str = ""
    wan_end_ip: str = ""
    lan_tcp_port: str = ""
    lan_udp_port: str = ""
    wan_tcp_port: str = ""
    wan_udp_port: str = ""
    source_interface: str = ""
    vlan_id: str = ""
    priority: str = ""
    action: str = ""

    def as_dict(self) -> dict[str, str]:
        return asdict(self)


_MUTABLE_FIELDS = (
    "name",
    "protocol",
    "direction",
    "lan_start_ip",
    "lan_end_ip",
    "wan_start_ip",
    "wan_end_ip",
    "lan_tcp_port",
    "lan_udp_port",
    "wan_tcp_port",
    "wan_udp_port",
)


def parse_st_filter_in(
    html: str,
) -> list[HuaweiIPv4FilterRule]:
    rules: list[HuaweiIPv4FilterRule] = []

    for match in re.finditer(
        r"new\s+stFilterIn\s*\((.*?)\)",
        html or "",
        re.I | re.S,
    ):
        values = re.findall(
            r'"((?:\\.|[^"\\])*)"',
            match.group(1),
        )

        if len(values) < 16:
            continue

        values = [
            decode_huawei_js_string(value)
            for value in values[:16]
        ]

        rules.append(
            HuaweiIPv4FilterRule(
                domain=values[0],
                priority=values[1],
                protocol=values[2],
                direction=values[3],
                lan_start_ip=values[4],
                lan_end_ip=values[5],
                wan_start_ip=values[6],
                wan_end_ip=values[7],
                action=values[8],
                lan_tcp_port=values[9],
                lan_udp_port=values[10],
                wan_tcp_port=values[11],
                wan_udp_port=values[12],
                name=values[13],
                source_interface=values[14],
                vlan_id=values[15],
            )
        )

    return rules


def resolve_ipv4_filter_domain(
    instance_or_domain: str | int,
) -> str:
    raw = str(instance_or_domain).strip()
    match = re.fullmatch(
        (
            r"(?:InternetGatewayDevice\.X_HW_Security\."
            r"IpFilterIn\.)?([1-9][0-9]*)"
        ),
        raw,
    )

    if not match:
        raise ValueError(
            "Instância IPv4 Filtering inválida."
        )

    return DOMAIN_PREFIX + match.group(1)


def build_create_payload(
    rule: HuaweiIPv4FilterRule,
    token: str,
) -> dict[str, str]:
    return _build_mutation_payload(rule, token)


def build_update_payload(
    rule: HuaweiIPv4FilterRule,
    token: str,
) -> dict[str, str]:
    return _build_mutation_payload(rule, token)


def build_delete_payload(
    instance_or_domain: str | int,
    token: str,
) -> dict[str, str]:
    return {
        resolve_ipv4_filter_domain(
            instance_or_domain
        ): "",
        "x.X_HW_Token": token,
    }


def _build_mutation_payload(
    rule: HuaweiIPv4FilterRule,
    token: str,
) -> dict[str, str]:
    return {
        "x.Protocol": rule.protocol,
        "x.Direction": rule.direction,
        "x.Name": rule.name,
        "x.SourceIPStart": rule.lan_start_ip,
        "x.SourceIPEnd": rule.lan_end_ip,
        "x.DestIPStart": rule.wan_start_ip,
        "x.DestIPEnd": rule.wan_end_ip,
        "x.LanSideTcpPort": rule.lan_tcp_port,
        "x.LanSideUdpPort": rule.lan_udp_port,
        "x.WanSideTcpPort": rule.wan_tcp_port,
        "x.WanSideUdpPort": rule.wan_udp_port,
        "x.X_HW_Token": token,
    }


def semantic_rule_matches(
    actual: HuaweiIPv4FilterRule,
    expected: HuaweiIPv4FilterRule,
) -> bool:
    return all(
        getattr(actual, field)
        == getattr(expected, field)
        for field in _MUTABLE_FIELDS
    )


class HuaweiIPv4FilterService:
    def __init__(
        self,
        client: HuaweiWebClient,
        *,
        model: str | None = None,
        sleep: Callable[[float], None] = time.sleep,
        readback_tries: int = 8,
    ) -> None:
        self.client = client
        self.model = model
        self.sleep = sleep
        self.readback_tries = max(
            1,
            int(readback_tries),
        )

    def capability(
        self,
        *,
        probe_read: bool = False,
    ) -> dict[str, bool]:
        profile = huawei_ipv4_filter_capability(
            self.model
        )
        read_available = profile.read

        if probe_read and not read_available:
            try:
                self._state()
                read_available = True
            except Exception:
                read_available = False

        return {
            **profile.as_dict(),
            "read": read_available,
        }

    def list_ipv4_filters(self) -> dict:
        _html, rules = self._state()

        return {
            "rules": [
                rule.as_dict()
                for rule in rules
            ],
            "capability": {
                **self.capability(
                    probe_read=False
                ),
                "read": True,
            },
        }

    def create_ipv4_filter(
        self,
        rule: HuaweiIPv4FilterRule,
    ) -> dict:
        self._require(
            "create"
        )

        page, _rules = self._state()
        token = self.client.extract_token(
            page
        )

        path = (
            f"{DIR}/add.cgi"
            "?x=InternetGatewayDevice.X_HW_Security.IpFilterIn"
            "&RequestFile=html/bbsp/ipincoming/ipincoming.asp"
        )

        transport = self.client.post_form(
            path,
            build_create_payload(
                rule,
                token,
            ),
            referer=PAGE,
        )

        verified = self._wait_for(
            lambda rules: next(
                (
                    item
                    for item in rules
                    if item.name == rule.name
                    and semantic_rule_matches(
                        item,
                        rule,
                    )
                ),
                None,
            )
        )

        return self._mutation_response(
            "create",
            transport,
            verified,
        )

    def update_ipv4_filter(
        self,
        instance_or_domain: str | int,
        rule: HuaweiIPv4FilterRule,
    ) -> dict:
        self._require(
            "update"
        )

        domain = resolve_ipv4_filter_domain(
            instance_or_domain
        )
        page, _rules = self._state()
        token = self.client.extract_token(
            page
        )

        path = (
            f"{DIR}/set.cgi"
            f"?x={domain}"
            "&RequestFile=html/bbsp/ipincoming/ipincoming.asp"
        )

        transport = self.client.post_form(
            path,
            build_update_payload(
                rule,
                token,
            ),
            referer=PAGE,
        )

        verified = self._wait_for(
            lambda rules: next(
                (
                    item
                    for item in rules
                    if item.domain == domain
                    and semantic_rule_matches(
                        item,
                        rule,
                    )
                ),
                None,
            )
        )

        return self._mutation_response(
            "update",
            transport,
            verified,
        )

    def delete_ipv4_filter(
        self,
        instance_or_domain: str | int,
    ) -> dict:
        self._require(
            "delete"
        )

        domain = resolve_ipv4_filter_domain(
            instance_or_domain
        )
        page, rules_before = self._state()
        previous = next(
            (
                rule
                for rule in rules_before
                if rule.domain == domain
            ),
            None,
        )
        token = self.client.extract_token(
            page
        )

        path = (
            f"{DIR}/del.cgi"
            "?RequestFile=html/bbsp/ipincoming/ipincoming.asp"
        )

        transport = self.client.post_form(
            path,
            build_delete_payload(
                domain,
                token,
            ),
            referer=PAGE,
        )

        verified = self._wait_for(
            lambda rules: (
                True
                if not any(
                    item.domain == domain
                    for item in rules
                )
                else None
            )
        )

        result = self._mutation_response(
            "delete",
            transport,
            verified,
        )
        result["deleted_domain"] = domain

        if previous:
            result[
                "previous"
            ] = previous.as_dict()

        return result

    def _require(
        self,
        operation: str,
    ) -> None:
        capability: HuaweiIPv4FilterCapability = (
            huawei_ipv4_filter_capability(
                self.model
            )
        )

        if not getattr(
            capability,
            operation,
            False,
        ):
            raise PermissionError(
                "Escrita de IPv4 Filtering ainda não "
                "foi validada para este modelo Huawei."
            )

    def _state(
        self,
    ) -> tuple[
        str,
        list[HuaweiIPv4FilterRule],
    ]:
        html = self.client.get_page(
            PAGE
        )

        return (
            html,
            parse_st_filter_in(
                html
            ),
        )

    def _wait_for(
        self,
        predicate: Callable[
            [Iterable[HuaweiIPv4FilterRule]],
            object,
        ],
    ) -> object | None:
        delays = (
            0.35,
            0.55,
            0.8,
            1.0,
            1.2,
            1.5,
            1.8,
            2.0,
        )

        for attempt in range(
            self.readback_tries
        ):
            self.sleep(
                delays[
                    min(
                        attempt,
                        len(delays) - 1,
                    )
                ]
            )

            try:
                _html, rules = self._state()
            except Exception:
                continue

            found = predicate(
                rules
            )

            if found:
                return found

        return None

    @staticmethod
    def _mutation_response(
        operation: str,
        transport: HuaweiMutationTransport,
        verified: object | None,
    ) -> dict:
        if verified:
            rule = (
                verified.as_dict()
                if isinstance(
                    verified,
                    HuaweiIPv4FilterRule,
                )
                else None
            )

            return {
                "success": True,
                "verified": True,
                "uncertain": False,
                "operation": operation,
                "rule": rule,
                "transport": {
                    "http_status": (
                        transport.http_status
                    ),
                    "timed_out": (
                        transport.timed_out
                    ),
                    "connection_uncertain": (
                        transport.connection_uncertain
                    ),
                },
            }

        uncertain = bool(
            transport.timed_out
            or transport.connection_uncertain
            or (
                transport.http_status
                is not None
                and 200
                <= transport.http_status
                < 400
            )
        )

        return {
            "success": False,
            "verified": False,
            "uncertain": uncertain,
            "operation": operation,
            "error": (
                "A ONT recebeu a tentativa, mas a "
                "alteração não foi confirmada na releitura."
                if uncertain
                else
                "A alteração de IPv4 Filtering "
                "não foi aplicada pela ONT."
            ),
            "transport": {
                "http_status": (
                    transport.http_status
                ),
                "timed_out": (
                    transport.timed_out
                ),
                "connection_uncertain": (
                    transport.connection_uncertain
                ),
            },
        }

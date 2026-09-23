from __future__ import annotations

import hashlib
import os
import random
import string
from pathlib import Path
from typing import Any

from . import zte_security
from . import zte_wan_config
from .zte_network_management import (
    CrudSpec,
    ThinkLuaCrudGateway,
)
from .zte_post import post_menu


QOS_QUEUE_SPEC = CrudSpec(
    view="qosQueue",
    tag="qos_queue_lua.lua",
    object_key="OBJ_QOSQQ_ID",
    fields=(
        "Alias",
        "Enable",
        "TrafficClasses",
        "QueueInterface",
        "DefaultQueue",
        "NeedStats",
        "SchedulerAlgorithm",
        "Weight",
        "QueueNum",
        "ShapingRate",
    ),
)

QOS_SHAPER_SPEC = CrudSpec(
    view="qosShaper",
    tag="qos_shaper_lua.lua",
    object_key="OBJ_QOSSHAPER_CONF_ID",
    fields=(
        "Enable",
        "Interface",
        "ShapingRate",
        "Alias",
    ),
)

QOS_POLICER_SPEC = CrudSpec(
    view="qosSpeed",
    tag="qos_speed_lua.lua",
    object_key="OBJ_QOSQP_ID",
    fields=(
        "Enable",
        "Alias",
        "CommittedRate",
        "CommittedBurstSize",
        "ExcessBurstSize",
        "PeakRate",
        "PeakBurstSize",
        "MeterType",
        "ConformingAction",
        "PartialConformingAction",
        "NonConformingAction",
    ),
)

IP_FILTER_SPEC = CrudSpec(
    view="filterCriteria",
    tag="firewall_ipfilter_lua.lua",
    object_key="OBJ_FWIP_ID",
    fields=(
        "ViewName",
        "Enable",
        "Protocol",
        "Name",
        "INCViewName",
        "OUTCViewName",
        "IPVersion",
        "SourceIP",
        "SourceIPMask",
        "DestIP",
        "DestIPMask",
        "MinSrcPort",
        "MaxSrcPort",
        "MinDstPort",
        "MaxDstPort",
        "FilterTarget",
        "FilterIndex",
        "DSCP",
    ),
)

MAC_FILTER_SPEC = CrudSpec(
    view="filterCriteria",
    tag="firewall_macfilterv3_lua.lua",
    object_key="OBJ_MACFILTER_ID",
    fields=(
        "Name",
        "Type",
        "Protocol",
        "SrcMacAddr",
        "DstMacAddr",
    ),
)

FILTER_GLOBAL_SPEC = CrudSpec(
    view="filterCriteria",
    tag="firewall_filterglobal_lua.lua",
    object_key="OBJ_FWBASE_ID",
    fields=(
        "MacFilterTarget",
        "MacFilterEnable",
        "UrlFilterTarget",
        "UrlFilterEnable",
    ),
)

SNTP_SPEC = CrudSpec(
    view="sntp",
    tag="sntp_lua.lua",
    object_key="OBJ_SNTP_ID",
    fields=(
        "NtpServer1",
        "NtpServer2",
        "NtpServer3",
        "NtpServer4",
        "NtpServer5",
        "CurrentLocalTime",
        "DaylightSavingsUsed",
        "PollTimeInterval",
        "Dscp",
        "ZoneIndex",
        "AutoSetTzname",
        "NtpConfigPermission",
        "SntpBindWanName",
        "Enable",
    ),
)


def _wire_bool(value):
    if isinstance(
        value,
        bool,
    ):
        return "1" if value else "0"

    return value


def qos_status(zte) -> dict[str, Any]:
    gateway = ThinkLuaCrudGateway(
        zte
    )

    result = {}

    for name, spec in (
        ("queues", QOS_QUEUE_SPEC),
        ("shapers", QOS_SHAPER_SPEC),
        ("policers", QOS_POLICER_SPEC),
    ):
        try:
            result[
                name
            ] = gateway.read(
                spec
            )
        except Exception as error:
            result[
                name
            ] = {
                "error": str(error),
                "items": [],
            }

    return result


def save_qos(
    zte,
    kind: str,
    config: dict[str, Any],
) -> dict[str, Any]:
    specs = {
        "queue": QOS_QUEUE_SPEC,
        "shaper": QOS_SHAPER_SPEC,
        "policer": QOS_POLICER_SPEC,
    }

    spec = specs.get(
        str(
            kind
        ).lower()
    )

    if spec is None:
        raise ValueError(
            "Tipo QoS inválido."
        )

    values = {}

    for field in spec.fields:
        if field in config:
            values[
                field
            ] = _wire_bool(
                config[
                    field
                ]
            )

    return ThinkLuaCrudGateway(
        zte
    ).save(
        spec,
        values=values,
        instance_id=config.get(
            "id"
        ),
    )


def delete_qos(
    zte,
    kind: str,
    instance_id: str,
) -> dict[str, Any]:
    specs = {
        "queue": QOS_QUEUE_SPEC,
        "shaper": QOS_SHAPER_SPEC,
        "policer": QOS_POLICER_SPEC,
    }

    spec = specs.get(
        str(
            kind
        ).lower()
    )

    if spec is None:
        raise ValueError(
            "Tipo QoS inválido."
        )

    return ThinkLuaCrudGateway(
        zte
    ).delete(
        spec,
        instance_id,
    )


def firewall_status(zte) -> dict[str, Any]:
    zte.get_view(
        "firewall",
        Menu3Location=0,
    )

    xml = zte.get_menu(
        "firewall_config_lua.lua"
    )

    zte._validar_resposta(
        xml
    )

    objects = zte._parse_instances(
        xml
    )

    level = (
        objects.get(
            "OBJ_FWLEVEL_ID",
            [{}],
        )[0]
        if objects.get(
            "OBJ_FWLEVEL_ID"
        )
        else {}
    )

    spi = (
        objects.get(
            "OBJ_FWSPI_ID",
            [{}],
        )[0]
        if objects.get(
            "OBJ_FWSPI_ID"
        )
        else {}
    )

    return {
        "available": bool(
            level
            or spi
        ),
        "id": level.get(
            "_InstID"
        ),
        "enabled": level.get(
            "Enable"
        ) == "1",
        "level": level.get(
            "Level"
        ),
        "spi": spi,
        "raw": {
            "level": level,
            "spi": spi,
        },
    }


def firewall_rules(zte) -> dict[str, Any]:
    gateway = ThinkLuaCrudGateway(
        zte
    )

    result = {}

    for name, spec in (
        ("ip", IP_FILTER_SPEC),
        ("mac", MAC_FILTER_SPEC),
        ("global", FILTER_GLOBAL_SPEC),
    ):
        try:
            result[name] = gateway.read(
                spec
            )
        except Exception as error:
            result[name] = {
                "error": str(error),
                "items": [],
            }

    return result


def save_firewall_rule(
    zte,
    kind: str,
    config: dict[str, Any],
) -> dict[str, Any]:
    specs = {
        "ip": IP_FILTER_SPEC,
        "mac": MAC_FILTER_SPEC,
    }

    spec = specs.get(
        str(kind).lower()
    )

    if spec is None:
        raise ValueError(
            "Filtro deve ser ip ou mac."
        )

    values = {}

    for field in spec.fields:
        if field in config:
            values[field] = _wire_bool(
                config[field]
            )

    return ThinkLuaCrudGateway(
        zte
    ).save(
        spec,
        values=values,
        instance_id=config.get(
            "id"
        ),
    )


def delete_firewall_rule(
    zte,
    kind: str,
    instance_id: str,
) -> dict[str, Any]:
    specs = {
        "ip": IP_FILTER_SPEC,
        "mac": MAC_FILTER_SPEC,
    }

    spec = specs.get(
        str(kind).lower()
    )

    if spec is None:
        raise ValueError(
            "Filtro deve ser ip ou mac."
        )

    return ThinkLuaCrudGateway(
        zte
    ).delete(
        spec,
        instance_id,
    )


def set_filter_global(
    zte,
    config: dict[str, Any],
) -> dict[str, Any]:
    current = ThinkLuaCrudGateway(
        zte
    ).read(
        FILTER_GLOBAL_SPEC
    )

    instance = (
        current[0]
        if current
        else {}
    )

    mapping = {
        "mac_enabled": "MacFilterEnable",
        "mac_target": "MacFilterTarget",
        "url_enabled": "UrlFilterEnable",
        "url_target": "UrlFilterTarget",
    }

    values = {}

    for source, target in mapping.items():
        if source in config:
            values[target] = _wire_bool(
                config[source]
            )

    return ThinkLuaCrudGateway(
        zte
    ).save(
        FILTER_GLOBAL_SPEC,
        values=values,
        instance_id=instance.get(
            "_InstID"
        ),
    )


def set_firewall(
    zte,
    config: dict[str, Any],
) -> dict[str, Any]:
    current = firewall_status(
        zte
    )

    if not current.get(
        "available"
    ):
        raise RuntimeError(
            "Firewall não disponível neste firmware/login."
        )

    level = (
        config.get(
            "level"
        )
        or current.get(
            "level"
        )
        or "Middle"
    )

    if level not in {
        "Low",
        "Middle",
        "High",
    }:
        raise ValueError(
            "Firewall deve usar nível Low, Middle ou High."
        )

    enabled = config.get(
        "enabled",
        current.get(
            "enabled",
            True,
        ),
    )

    zte.get_view(
        "firewall",
        Menu3Location=0,
    )

    response = post_menu(
        zte,
        "firewall_config_lua.lua",
        [
            ("IF_ACTION", "Apply"),
            (
                "_InstID",
                current.get("id") or "IGD",
            ),
            (
                "Enable",
                "1" if enabled else "0",
            ),
            ("Level", level),
            ("Btn_cancel_FirewallConf", ""),
            ("Btn_apply_FirewallConf", ""),
        ],
    )

    zte._validar_resposta(
        response
    )

    return {
        "success": True,
        "before": current,
        "after": firewall_status(
            zte
        ),
    }


def sntp_status(zte) -> list[dict[str, Any]]:
    return ThinkLuaCrudGateway(
        zte
    ).read(
        SNTP_SPEC
    )


def set_sntp(
    zte,
    config: dict[str, Any],
) -> dict[str, Any]:
    current = sntp_status(
        zte
    )

    instance_id = (
        config.get("id")
        or (
            current[0].get(
                "_InstID"
            )
            if current
            else None
        )
    )

    mapping = {
        "enabled": "Enable",
        "server1": "NtpServer1",
        "server2": "NtpServer2",
        "server3": "NtpServer3",
        "server4": "NtpServer4",
        "server5": "NtpServer5",
        "interval": "PollTimeInterval",
        "zone": "ZoneIndex",
        "bind_wan": "SntpBindWanName",
        "dscp": "Dscp",
    }

    values = {}

    for source, target in mapping.items():
        if source not in config:
            continue

        values[
            target
        ] = _wire_bool(
            config[source]
        )

    return ThinkLuaCrudGateway(
        zte
    ).save(
        SNTP_SPEC,
        values=values,
        instance_id=instance_id,
    )


def tr069_status(zte) -> dict[str, Any]:
    zte.get_view(
        "remoteMgr",
        Menu3Location=0,
    )

    xml = zte.get_menu(
        "tr069_remotemgr_lua.lua"
    )

    zte._validar_resposta(
        xml
    )

    objects = zte._parse_instances(
        xml
    )

    server = (
        objects.get(
            "OBJ_MANAGESERVER_ID",
            [{}],
        )[0]
        if objects.get(
            "OBJ_MANAGESERVER_ID"
        )
        else {}
    )

    queue = (
        objects.get(
            "OBJ_TR069QUEUECONF_ID",
            [{}],
        )[0]
        if objects.get(
            "OBJ_TR069QUEUECONF_ID"
        )
        else {}
    )

    sanitized = dict(
        server
    )

    for key in (
        "UserPassword",
        "ConnectionRequestPassword",
    ):
        if key in sanitized:
            sanitized[
                key
            ] = (
                "••••••••"
                if sanitized[
                    key
                ]
                else ""
            )

    return {
        "available": bool(
            server
        ),
        "server": sanitized,
        "queue": queue,
    }


def set_tr069(
    zte,
    config: dict[str, Any],
) -> dict[str, Any]:
    before = tr069_status(
        zte
    )

    if not before.get(
        "available"
    ):
        raise RuntimeError(
            "TR-069 não está disponível neste firmware/login."
        )

    current = dict(
        before.get(
            "server"
        )
        or {}
    )

    mapping = {
        "url": "URL",
        "username": "UserName",
        "periodic_inform_enabled": "PeriodicInformEnable",
        "periodic_inform_interval": "PeriodicInformInterval",
        "connection_request_username": "ConnectionRequestUsername",
        "default_wan": "DefaultWan",
        "support_cert_auth": "SupportCertAuth",
        "cert_id": "CertID",
        "remote_upgrade_cert_auth": "RemoteUpgradeCertAuth",
    }

    for source, target in mapping.items():
        if source in config:
            current[target] = _wire_bool(
                config[source]
            )

    secret_changes = {
        "UserPassword": config.get(
            "password"
        ),
        "ConnectionRequestPassword": config.get(
            "connection_request_password"
        ),
    }

    changed_secret_names = [
        name
        for name, value in secret_changes.items()
        if value is not None
    ]

    crypto_key = None
    crypto_iv = None
    encode = None

    if changed_secret_names:
        crypto_key = "".join(
            random.choices(
                string.digits,
                k=16,
            )
        )
        crypto_iv = "".join(
            random.choices(
                string.digits,
                k=16,
            )
        )

        encode = zte_security.rsa_encrypt_text(
            f"{crypto_key}+{crypto_iv}",
            getattr(
                zte,
                "public_key_pem",
                None,
            ),
        )

    def secret_value(name):
        value = secret_changes[
            name
        ]

        if value is None:
            # Sentinel usado pela interface para preservar a senha atual.
            return "\t" * 6

        return zte_security.aes_encrypt_value(
            value,
            crypto_key,
            crypto_iv,
        )

    fields = [
        ("IF_ACTION", "Apply"),
        ("_InstID", ""),
        ("URL", current.get("URL") or ""),
        ("UserName", current.get("UserName") or ""),
        ("UserPassword", secret_value("UserPassword")),
        (
            "PeriodicInformEnable",
            current.get("PeriodicInformEnable")
            or "1",
        ),
        (
            "PeriodicInformInterval",
            current.get("PeriodicInformInterval")
            or "3600",
        ),
        (
            "ConnectionRequestURL",
            current.get("ConnectionRequestURL")
            or "",
        ),
        (
            "ConnectionRequestUsername",
            current.get("ConnectionRequestUsername")
            or "",
        ),
        (
            "ConnectionRequestPassword",
            secret_value(
                "ConnectionRequestPassword"
            ),
        ),
        (
            "DefaultWan",
            current.get("DefaultWan")
            or "",
        ),
        (
            "SupportCertAuth",
            current.get("SupportCertAuth")
            or "0",
        ),
        (
            "CertID",
            current.get("CertID")
            or "",
        ),
        (
            "CertList",
            current.get("CertList")
            or "",
        ),
        (
            "RemoteUpgradeCertAuth",
            current.get("RemoteUpgradeCertAuth")
            or "0",
        ),
        (
            "DSCPRemark",
            (
                before.get(
                    "queue",
                    {},
                ).get(
                    "DSCPRemark"
                )
                or ""
            ),
        ),
        (
            "VLanPrioRemark",
            (
                before.get(
                    "queue",
                    {},
                ).get(
                    "VLanPrioRemark"
                )
                or ""
            ),
        ),
        ("Btn_cancel_TR069BasicConf", ""),
        ("Btn_apply_TR069BasicConf", ""),
    ]

    if encode:
        fields.append((
            "encode",
            encode,
        ))

    zte.get_view(
        "remoteMgr",
        Menu3Location=0,
    )

    response = post_menu(
        zte,
        "tr069_remotemgr_lua.lua",
        fields,
    )

    zte._validar_resposta(
        response
    )

    return {
        "success": True,
        "before": before,
        "after": tr069_status(
            zte
        ),
    }


def _wan_instances(
    zte,
) -> tuple[
    list[dict[str, Any]],
    set[str],
]:
    xml = zte_wan_config.wan_config_raw(
        zte
    )

    zte._validar_resposta(
        xml
    )

    objects = zte._parse_instances(
        xml
    )

    instances = (
        objects.get(
            "ID_WAN_COMFIG"
        )
        or objects.get(
            "OBJ_WAN_CONFIG_ID"
        )
        or []
    )

    encode_fields = (
        zte_wan_config._get_encode_fields(
            xml
        )
    )

    return (
        instances,
        encode_fields,
    )


def wan_configurations(
    zte,
) -> list[dict[str, Any]]:
    instances, encode_fields = (
        _wan_instances(
            zte
        )
    )

    token = getattr(
        zte,
        "session_tmp_token",
        None,
    )

    result = []

    for item in instances:
        row = dict(
            item
        )

        if (
            token
            and "UserName" in encode_fields
            and row.get(
                "UserName"
            )
        ):
            row[
                "UserName"
            ] = zte_security.aes_decrypt_value(
                row["UserName"],
                token,
                token[::-1],
            )

        if "Password" in row:
            row[
                "Password"
            ] = (
                "••••••••"
                if row[
                    "Password"
                ]
                else ""
            )

        result.append(
            row
        )

    return result


_WAN_API_MAP = {
    "enabled": "Enable",
    "name": "WANCName",
    "mode": "mode",
    "link_mode": "linkMode",
    "lan_binding": "LANDViewName",
    "service_list": "StrServList",
    "service_code": "ServList",
    "nat": "IsNAT",
    "default_gateway": "IsDefGW",
    "forward": "IsForward",
    "vlan_id": "VLANID",
    "priority": "Priority",
    "vlan_enabled": "VlanEnable",
    "mtu": "MTU",
    "ip_mode": "IpMode",
    "username": "UserName",
    "password": "Password",
    "auth_type": "AuthType",
    "trigger": "ConnTrigger",
    "pppoe_service_name": "PPPoeServiceName",
}


def update_wan(
    zte,
    instance_id: str,
    config: dict[str, Any],
) -> dict[str, Any]:
    instances, encode_fields = (
        _wan_instances(
            zte
        )
    )

    target = next((
        item
        for item in instances
        if item.get(
            "_InstID"
        ) == instance_id
    ), None)

    if target is None:
        raise ValueError(
            "WAN não encontrada."
        )

    merged = dict(
        target
    )

    for source, target_name in (
        _WAN_API_MAP.items()
    ):
        if source not in config:
            continue

        value = _wire_bool(
            config[source]
        )

        merged[
            target_name
        ] = value

    token = getattr(
        zte,
        "session_tmp_token",
        None,
    )

    if "username" in config:
        if (
            "UserName" in encode_fields
            and token
        ):
            merged[
                "UserName"
            ] = zte_security.aes_encrypt_value(
                config.get(
                    "username"
                ),
                token,
                token[::-1],
            )

    if "password" in config:
        if (
            "Password" in encode_fields
            and token
        ):
            merged[
                "Password"
            ] = zte_security.aes_encrypt_value(
                config.get(
                    "password"
                ),
                token,
                token[::-1],
            )

    mode = str(
        merged.get(
            "mode"
        )
        or "route"
    )

    link_mode = str(
        merged.get(
            "linkMode"
        )
        or (
            "PPP"
            if str(
                merged.get(
                    "wantype"
                )
            ).lower() == "pppoe"
            else "IP"
        )
    )

    fields = [
        ("IF_ACTION", "Apply"),
        (
            "_InstID",
            instance_id,
        ),
        (
            "xdslMode",
            merged.get(
                "xdslMode"
            )
            or merged.get(
                "XMODE"
            )
            or "NULL",
        ),
        ("TypeFlag", "0"),
        ("mode", mode),
        (
            "linkMode",
            link_mode,
        ),
    ]

    ordered = (
        "Enable",
        "WANCName",
        "ConnType",
        "LANDViewName",
        "StrServList",
        "ServList",
        "IsNAT",
        "IsDefGW",
        "IsForward",
        "VLANID",
        "Priority",
        "VlanEnable",
        "IPAddress",
        "SubnetMask",
        "GateWay",
        "DNS1",
        "DNS2",
        "DNS3",
        "WorkIFMac",
        "UserName",
        "Password",
        "MRU",
        "MTU",
        "IpMode",
        "ConnTrigger",
        "TransType",
        "AuthType",
        "IdleTime",
        "PPPoeServiceName",
        "DSCP",
        "EnablePassThrough",
        "IPv6AcquireMode",
        "DnsSrc",
        "Dns1v6",
        "Dns2v6",
        "Dns3v6",
        "Gateway6Src",
        "Gateway6",
        "IsPd",
        "IsSLAAC",
        "IsGUA",
        "IsPD",
        "WBDMode",
    )

    for name in ordered:
        if name in merged:
            fields.append((
                name,
                merged.get(
                    name
                )
                or "",
            ))

    zte.get_view(
        "ethWanConfig",
        Menu3Location=0,
    )

    response = post_menu(
        zte,
        "wan_internet_lua.lua",
        fields,
        TypeUplink=2,
        pageType=0,
    )

    zte._validar_resposta(
        response
    )

    return {
        "success": True,
        "before": target,
        "items": wan_configurations(
            zte
        ),
    }


def wan_action(
    zte,
    instance_id: str,
    action: str,
) -> dict[str, Any]:
    action_map = {
        "connect": "PPPCONNECT",
        "disconnect": "PPPDISCONNECT",
        "dhcp_renew": "DHCPRENEW",
        "dhcp_release": "DHCPRELEASE",
    }

    firmware_action = action_map.get(
        str(
            action
        ).lower()
    )

    if firmware_action is None:
        raise ValueError(
            "Ação WAN inválida."
        )

    instances, _ = _wan_instances(
        zte
    )

    target = next((
        item
        for item in instances
        if item.get(
            "_InstID"
        ) == instance_id
    ), None)

    if target is None:
        raise ValueError(
            "WAN não encontrada."
        )

    zte.get_view(
        "ethWanConfig",
        Menu3Location=0,
    )

    response = post_menu(
        zte,
        "wan_internet_lua.lua",
        [
            (
                "IF_ACTION",
                firmware_action,
            ),
            (
                "_InstID",
                instance_id,
            ),
            (
                "xdslMode",
                target.get(
                    "xdslMode"
                )
                or target.get(
                    "XMODE"
                )
                or "NULL",
            ),
            ("TypeFlag", "0"),
            (
                "mode",
                target.get(
                    "mode"
                )
                or "route",
            ),
            (
                "linkMode",
                target.get(
                    "linkMode"
                )
                or "PPP",
            ),
        ],
        TypeUplink=2,
        pageType=0,
    )

    zte._validar_resposta(
        response
    )

    return {
        "success": True,
        "action": action,
        "items": wan_configurations(
            zte
        ),
    }


def bridge_assistant(
    zte,
    instance_id: str,
    config: dict[str, Any],
) -> dict[str, Any]:
    instances, _ = _wan_instances(
        zte
    )

    before = next((
        dict(item)
        for item in instances
        if item.get(
            "_InstID"
        ) == instance_id
    ), None)

    if before is None:
        raise ValueError(
            "WAN não encontrada."
        )

    requested = {
        "mode": "bridge",
    }

    for key in (
        "lan_binding",
        "vlan_id",
        "priority",
        "vlan_enabled",
        "name",
        "enabled",
    ):
        if key in config:
            requested[
                key
            ] = config[
                key
            ]

    result = update_wan(
        zte,
        instance_id,
        requested,
    )

    after = next((
        item
        for item in result.get(
            "items",
            []
        )
        if item.get(
            "_InstID"
        ) == instance_id
    ), {})

    if str(
        after.get(
            "mode"
        )
        or ""
    ).lower() != "bridge":
        # Rollback best-effort. O registro original contém todos os campos
        # devolvidos pelo firmware e é reaplicado sem reescrever credenciais.
        restore = {
            source: before.get(
                target
            )
            for source, target in (
                _WAN_API_MAP.items()
            )
            if target in before
            and source not in {
                "username",
                "password",
            }
        }

        try:
            update_wan(
                zte,
                instance_id,
                restore,
            )
        except Exception:
            pass

        raise RuntimeError(
            "A ONT respondeu ao Bridge Mode, mas a validação não confirmou modo bridge; rollback foi tentado."
        )

    return {
        "success": True,
        "before": before,
        "after": after,
    }


def firmware_status(zte) -> dict[str, Any]:
    zte.get_view(
        "firmwareUpgr",
        Menu3Location=0,
    )

    xml = zte.get_menu(
        "upgrade_firmware_query_lua.lua"
    )

    zte._validar_resposta(
        xml
    )

    return {
        "objects": zte._parse_instances(
            xml
        ),
        "raw_status": xml[:2000],
    }


def _allow_upload(
    zte,
):
    zte.get_view(
        "usrCfgMgr",
        Menu3Location=0,
    )

    permission = post_menu(
        zte,
        "updownload_prevent_ctl.lua",
        [
            ("IF_ACTION", "updownload"),
            (
                "sessToken",
                zte.session_token or "",
            ),
        ],
    )

    zte._validar_resposta(
        permission
    )


def restore_configuration(
    zte,
    file_path: str,
) -> dict[str, Any]:
    path = Path(
        file_path
    ).expanduser()

    if not path.is_file():
        raise ValueError(
            "Arquivo de configuração não encontrado."
        )

    _allow_upload(
        zte
    )

    with path.open(
        "rb"
    ) as handle:
        response = zte.session.post(
            zte.base_url + "/",
            params={
                "_type": "menuData",
                "_tag": "do_restore_usrcfg.lua",
                "_sessionTOKEN": (
                    zte.session_token
                    or ""
                ),
            },
            files={
                "ConfigUpload": (
                    path.name,
                    handle,
                    "application/octet-stream",
                )
            },
            timeout=120,
        )

    response.raise_for_status()

    if response.text:
        zte._validar_resposta(
            response.text
        )

    return {
        "success": True,
        "file": str(
            path
        ),
        "size": path.stat().st_size,
        "message": (
            "Arquivo enviado. A ONT pode reiniciar durante a restauração."
        ),
    }


def upload_firmware(
    zte,
    file_path: str,
) -> dict[str, Any]:
    path = Path(
        file_path
    ).expanduser()

    if not path.is_file():
        raise ValueError(
            "Arquivo de firmware não encontrado."
        )

    zte.get_view(
        "firmwareUpgr",
        Menu3Location=0,
    )

    permission = post_menu(
        zte,
        "updownload_prevent_ctl.lua",
        [
            ("IF_ACTION", "updownload"),
            (
                "sessToken",
                zte.session_token or "",
            ),
        ],
    )

    zte._validar_resposta(
        permission
    )

    digest = hashlib.sha256(
        path.read_bytes()
    ).hexdigest()

    with path.open(
        "rb"
    ) as handle:
        response = zte.session.post(
            zte.base_url + "/",
            params={
                "_type": "menuData",
                "_tag": "do_firmware_upgrade.lua",
            },
            files={
                "VersionUpload": (
                    path.name,
                    handle,
                    "application/octet-stream",
                )
            },
            timeout=180,
        )

    response.raise_for_status()

    if response.text:
        zte._validar_resposta(
            response.text
        )

    return {
        "success": True,
        "file": str(
            path
        ),
        "sha256": digest,
        "size": path.stat().st_size,
        "message": (
            "Firmware enviado. Não desligue a ONT; acompanhe o status de upgrade."
        ),
    }

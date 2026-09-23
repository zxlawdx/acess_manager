from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable

from .zte_post import post_menu


@dataclass(frozen=True)
class CrudSpec:
    view: str
    tag: str
    object_key: str
    fields: tuple[str, ...]
    root_identity: str = "IGD"


class ThinkLuaCrudGateway:
    """
    Template Method para recursos ManagerOBJ.

    Centraliza o fluxo stateful da ZTE e evita duplicar leitura, merge, POST e
    releitura em DHCP reservation, port-forwarding e DMZ.
    """

    def __init__(self, zte):
        self.zte = zte

    def read(self, spec: CrudSpec) -> list[dict[str, Any]]:
        self.zte.get_view(
            spec.view,
            Menu3Location=0,
        )

        xml = self.zte.get_menu(
            spec.tag
        )

        self.zte._validar_resposta(xml)

        return (
            self.zte._parse_instances(xml)
            .get(spec.object_key, [])
        )

    def save(
        self,
        spec: CrudSpec,
        *,
        values: dict[str, Any],
        instance_id: str | None = None,
    ) -> dict[str, Any]:
        current = self.read(spec)
        target = self._find(
            current,
            instance_id,
        )

        merged = dict(target or {})
        merged.update(
            {
                key: value
                for key, value in values.items()
                if value is not None
            }
        )

        identity = (
            instance_id
            or merged.get("_InstID")
            or "-1"
        )

        fields = [
            ("IF_ACTION", "Apply"),
            ("_InstID", identity),
        ]

        for name in spec.fields:
            value = merged.get(name)

            if value is None:
                value = ""

            fields.append((
                name,
                self._wire(value),
            ))

        self.zte.get_view(
            spec.view,
            Menu3Location=0,
        )

        response = post_menu(
            self.zte,
            spec.tag,
            fields,
        )

        self.zte._validar_resposta(
            response
        )

        updated = self.read(spec)

        return {
            "success": True,
            "before": target,
            "items": updated,
        }

    def delete(
        self,
        spec: CrudSpec,
        instance_id: str,
    ) -> dict[str, Any]:
        if not instance_id:
            raise ValueError(
                "Informe a identidade da regra."
            )

        current = self.read(spec)
        target = self._find(
            current,
            instance_id,
        )

        if target is None:
            raise ValueError(
                "A regra solicitada não foi encontrada."
            )

        self.zte.get_view(
            spec.view,
            Menu3Location=0,
        )

        response = post_menu(
            self.zte,
            spec.tag,
            [
                ("IF_ACTION", "Delete"),
                ("_InstID", instance_id),
            ],
        )

        self.zte._validar_resposta(
            response
        )

        updated = self.read(spec)

        return {
            "success": True,
            "before": target,
            "items": updated,
        }

    @staticmethod
    def _find(
        items: Iterable[dict[str, Any]],
        instance_id: str | None,
    ) -> dict[str, Any] | None:
        if not instance_id:
            return None

        return next(
            (
                item
                for item in items
                if item.get("_InstID") == instance_id
            ),
            None,
        )

    @staticmethod
    def _wire(value: Any) -> str:
        if isinstance(value, bool):
            return "1" if value else "0"

        return str(value)


DHCP_RESERVATION_SPEC = CrudSpec(
    view="lanMgrIpv4",
    tag="Localnet_LanMgrIpv4_DHCPStaticRule_lua.lua",
    object_key="OBJ_DHCPBIND_ID",
    fields=(
        "Name",
        "IPAddr",
        "MACAddr",
    ),
)

PORT_FORWARD_SPEC = CrudSpec(
    view="portForwarding",
    tag="firewall_portforwarding_lua.lua",
    object_key="OBJ_FWPM_ID",
    root_identity="DEV",
    fields=(
        "Interface",
        "AllInterface",
        "Enable",
        "Protocol",
        "Alias",
        "ExternalPort",
        "ExternalPortEndRange",
        "InternalClient",
        "InternalPort",
        "InternalPortEndRange",
        "RemoteHost",
        "RemoteHostEndRange",
        "Description",
    ),
)

DMZ_SPEC = CrudSpec(
    view="dmz",
    tag="firewall_dmz_lua.lua",
    object_key="OBJ_FWDMZ_ID",
    fields=(
        "Enable",
        "InternalClient",
        "WANCViewName",
    ),
)


def dhcp_status(zte) -> dict[str, Any]:
    gateway = ThinkLuaCrudGateway(zte)

    zte.get_view(
        "lanMgrIpv4",
        Menu3Location=0,
    )

    basic_xml = zte.get_menu(
        "Localnet_LanMgrIpv4_DHCPBasicCfg_lua.lua"
    )
    zte._validar_resposta(basic_xml)
    basic_objects = zte._parse_instances(
        basic_xml
    )

    zte.get_view(
        "lanMgrIpv4",
        Menu3Location=0,
    )
    lease_xml = zte.get_menu(
        "Localnet_LanMgrIpv4_DHCPHostInfo_lua.lua"
    )
    zte._validar_resposta(lease_xml)
    lease_objects = zte._parse_instances(
        lease_xml
    )

    reservations = gateway.read(
        DHCP_RESERVATION_SPEC
    )

    basic = (
        basic_objects
        .get("OBJ_Br0AndDhcpsHosCfg_ID", [{}])[0]
        if basic_objects.get("OBJ_Br0AndDhcpsHosCfg_ID")
        else {}
    )

    lan_dns = (
        basic_objects
        .get("OBJ_LANDNS_ID", [{}])[0]
        if basic_objects.get("OBJ_LANDNS_ID")
        else {}
    )

    return {
        "basic": basic,
        "lan_dns": lan_dns,
        "leases": lease_objects.get(
            "OBJ_DHCPHOSTINFO_ID",
            [],
        ),
        "reservations": reservations,
    }


def set_dhcp_basic(
    zte,
    config: dict[str, Any],
) -> dict[str, Any]:
    """
    Altera apenas o servidor/pool/DNS/lease.

    O IP/submask LAN é preservado de propósito: mudar o endereço nesta console
    derruba a sessão e pode retirar o equipamento do caminho de gerenciamento.
    """
    current = dhcp_status(zte)
    basic = dict(
        current.get("basic") or {}
    )
    lan_dns = dict(
        current.get("lan_dns") or {}
    )

    mapping = {
        "enabled": "ServerEnable",
        "min_address": "MinAddress",
        "max_address": "MaxAddress",
        "dns_source": "DnsServerSource",
        "dns1": "DNSServer1",
        "dns2": "DNSServer2",
        "lease_time": "LeaseTime",
    }

    for source, target in mapping.items():
        if source in config:
            value = config[source]

            if source == "enabled":
                value = "1" if value else "0"

            basic[target] = str(value)

    if "ipv4_dns_origin" in config:
        lan_dns["Ipv4DnsOrigin"] = str(
            config["ipv4_dns_origin"]
        )

    fields = [
        ("IF_ACTION", "Apply"),
        (
            "_InstID",
            basic.get("_InstID") or "",
        ),
        (
            "IF_URL_HOST",
            basic.get("IPAddr") or "",
        ),
    ]

    ordered = (
        "IPAddr",
        "SubMask",
        "ServerEnable",
        "SubnetMask",
        "MinAddress",
        "MaxAddress",
        "DnsServerSource",
        "DNSServer1",
        "DNSServer2",
        "LeaseTime",
    )

    for name in ordered:
        fields.append((
            name,
            basic.get(name) or "",
        ))

    for name in (
        "Ipv4DnsOrigin",
        "Ipv6DnsOrigin",
        "IPv4AssignLANIP",
        "IPv6AssignLANIP",
    ):
        if name in lan_dns:
            fields.append((
                name,
                lan_dns.get(name) or "",
            ))

    fields.extend([
        ("Btn_cancel_DHCPBasicCfg", ""),
        ("Btn_apply_DHCPBasicCfg", ""),
    ])

    zte.get_view(
        "lanMgrIpv4",
        Menu3Location=0,
    )

    response = post_menu(
        zte,
        "Localnet_LanMgrIpv4_DHCPBasicCfg_lua.lua",
        fields,
    )

    zte._validar_resposta(
        response
    )

    return {
        "success": True,
        "before": current,
        "after": dhcp_status(zte),
    }


def save_dhcp_reservation(
    zte,
    config: dict[str, Any],
) -> dict[str, Any]:
    return ThinkLuaCrudGateway(zte).save(
        DHCP_RESERVATION_SPEC,
        values={
            "Name": config.get("name"),
            "IPAddr": config.get("ip"),
            "MACAddr": config.get("mac"),
        },
        instance_id=config.get("id"),
    )


def delete_dhcp_reservation(
    zte,
    instance_id: str,
) -> dict[str, Any]:
    return ThinkLuaCrudGateway(zte).delete(
        DHCP_RESERVATION_SPEC,
        instance_id,
    )


def port_forwarding_status(zte) -> list[dict[str, Any]]:
    return ThinkLuaCrudGateway(zte).read(
        PORT_FORWARD_SPEC
    )


def save_port_forward(
    zte,
    config: dict[str, Any],
) -> dict[str, Any]:
    external_end = (
        config.get("external_port_end")
        or config.get("external_port")
        or ""
    )
    internal_end = (
        config.get("internal_port_end")
        or config.get("internal_port")
        or ""
    )

    return ThinkLuaCrudGateway(zte).save(
        PORT_FORWARD_SPEC,
        values={
            "Interface": config.get("interface") or "",
            "AllInterface": "1" if config.get("all_interfaces", True) else "0",
            "Enable": "1" if config.get("enabled", True) else "0",
            "Protocol": config.get("protocol") or "TCP",
            "Alias": config.get("name") or "",
            "ExternalPort": config.get("external_port"),
            "ExternalPortEndRange": external_end,
            "InternalClient": config.get("internal_client"),
            "InternalPort": config.get("internal_port"),
            "InternalPortEndRange": internal_end,
            "RemoteHost": config.get("remote_host") or "",
            "RemoteHostEndRange": config.get("remote_host_end") or "",
            "Description": config.get("description") or "",
        },
        instance_id=config.get("id"),
    )


def delete_port_forward(
    zte,
    instance_id: str,
) -> dict[str, Any]:
    return ThinkLuaCrudGateway(zte).delete(
        PORT_FORWARD_SPEC,
        instance_id,
    )


def dmz_status(zte) -> list[dict[str, Any]]:
    return ThinkLuaCrudGateway(zte).read(
        DMZ_SPEC
    )


def set_dmz(
    zte,
    config: dict[str, Any],
) -> dict[str, Any]:
    return ThinkLuaCrudGateway(zte).save(
        DMZ_SPEC,
        values={
            "Enable": "1" if config.get("enabled", False) else "0",
            "InternalClient": config.get("internal_client") or "",
            "WANCViewName": config.get("wan") or "",
        },
        instance_id=config.get("id"),
    )

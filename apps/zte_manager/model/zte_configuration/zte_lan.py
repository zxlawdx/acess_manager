# =========================================================
# LAN PORT STATUS
# =========================================================


_SPEED_MAP = {
    "0": "Auto",
    "1": "10 Mbps",
    "2": "100 Mbps",
    "3": "1000 Mbps",
    "4": "2500 Mbps",
    "5": "5000 Mbps",
    "6": "10000 Mbps",
}


def _normalize_speed(value):
    """
    Alguns firmwares retornam a velocidade como enum (0..6), enquanto outros
    já devolvem "100 Mbps"/"1000 Mbps". Normalizar aqui evita o diagnóstico
    interpretar enum 2 como 2 Mbps.
    """
    text = str(
        value or ""
    ).strip()

    return _SPEED_MAP.get(
        text,
        value
    )


def lan_ports_raw(zte):
    zte.get_view(
        "localNetStatus",
        Menu3Location=0
    )

    return zte.get_menu(
        "status_lan_info_lua.lua"
    )


def lan_ports(zte):
    xml = lan_ports_raw(
        zte
    )

    zte._validar_resposta(
        xml
    )

    portas = (
        zte._parse_instances(xml)
        .get(
            "OBJ_PON_PORT_BASIC_STATUS_ID",
            []
        )
    )

    resultado = []

    for index, porta in enumerate(
        portas,
        start=1
    ):
        resultado.append({
            "id": porta.get("_InstID"),
            "port": index,
            "status": porta.get("Status"),
            "interface": porta.get("IFName"),
            "speed": _normalize_speed(
                porta.get("Speed")
            ),
            "speed_raw": porta.get("Speed"),
            "duplex": porta.get("Duplex"),
            "rx_bytes": porta.get("InBytes"),
            "tx_bytes": porta.get("OutBytes"),
            "rx_packets": porta.get("InPkts"),
            "tx_packets": porta.get("OutPkts"),
            "rx_errors": porta.get("InError"),
            "tx_errors": porta.get("OutError"),
            "rx_discard": porta.get("InDiscard"),
            "tx_discard": porta.get("OutDiscard"),
        })

    return resultado

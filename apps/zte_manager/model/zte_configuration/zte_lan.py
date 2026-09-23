# =========================================================
# LAN PORT STATUS
# =========================================================


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
            "speed": porta.get("Speed"),
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

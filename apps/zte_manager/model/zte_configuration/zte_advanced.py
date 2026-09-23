from .zte_post import post_menu


# =========================================================
# RÁDIOS - ON/OFF
# =========================================================


def radio_power_status(zte):
    """
    Lê o formulário wlan_wlanbasiconoff_lua.lua.

    O firmware separa o liga/desliga do rádio da configuração avançada.
    Mantemos essa leitura própria para não misturar TimerEnable com
    wlan_wlanbasicadconf_lua.lua.
    """

    zte.get_view(
        "wlanBasic",
        Menu3Location=0
    )

    xml = zte.get_menu(
        "wlan_wlanbasiconoff_lua.lua"
    )

    zte._validar_resposta(
        xml
    )

    dados = zte._parse_instances(
        xml
    )

    timer_cfg = _first(
        dados,
        "OBJ_WLANTIMECFG_ID"
    )

    timer = _first(
        dados,
        "OBJ_WLANTIME_ID"
    )

    radios = dados.get(
        "OBJ_WLANSETTING_ID",
        []
    )

    return {
        "timer_enabled": timer_cfg.get("TimerEnable") == "1",
        "timer_id": timer_cfg.get("_InstID"),
        "schedule": {
            "start_hour": timer.get("TimeStartHour"),
            "start_minute": timer.get("TimeStartMin"),
            "end_hour": timer.get("TimeEndHour"),
            "end_minute": timer.get("TimeEndMin"),
        },
        "radios": [
            {
                "id": radio.get("_InstID"),
                "band": radio.get("Band"),
                "enabled": radio.get("RadioStatus") == "1",
            }
            for radio in radios
        ],
    }


def set_radio_power(
    zte,
    band,
    enabled
):
    """
    Liga/desliga um rádio preservando o estado do outro.

    O backend original percorre _InstID_0, _InstID_1... e aplica
    RadioStatus_N. Quando o modo manual é usado TimerEnable precisa ser 0.
    """

    status = radio_power_status(
        zte
    )

    radios = status.get(
        "radios",
        []
    )

    alvo = next((
        radio
        for radio in radios
        if radio.get("band") == band
    ), None)

    if alvo is None:
        raise ValueError(
            f"Rádio {band} não encontrado."
        )

    for radio in radios:
        if radio.get("band") == band:
            radio["enabled"] = bool(
                enabled
            )

    schedule = status.get(
        "schedule",
        {}
    )

    campos = [
        ("IF_ACTION", "Apply"),
        (
            "_InstID",
            status.get("timer_id") or "IGD"
        ),
        ("TimerEnable", "0"),
    ]

    for index, radio in enumerate(
        radios
    ):
        campos.extend([
            (
                f"_InstID_{index}",
                radio.get("id") or ""
            ),
            (
                f"Band_{index}",
                radio.get("band") or ""
            ),
            (
                f"RadioStatus_{index}",
                "1" if radio.get("enabled") else "0"
            ),
        ])

    # O formulário mantém esses campos no DOM mesmo quando o agendamento
    # está desabilitado. Preservamos os valores atuais para reproduzir o
    # comportamento do browser sem apagar uma programação existente.
    campos.extend([
        (
            "TimeStartHour",
            schedule.get("start_hour") or "0"
        ),
        (
            "TimeStartMin",
            schedule.get("start_minute") or "0"
        ),
        (
            "TimeEndHour",
            schedule.get("end_hour") or "0"
        ),
        (
            "TimeEndMin",
            schedule.get("end_minute") or "0"
        ),
        ("Btn_cancel_WlanBasicAdConf", ""),
        ("Btn_apply_WlanBasicAdConf", ""),
    ])

    zte.get_view(
        "wlanBasic",
        Menu3Location=0
    )

    resposta = post_menu(
        zte,
        "wlan_wlanbasiconoff_lua.lua",
        campos
    )

    zte._validar_resposta(
        resposta
    )

    verificado = radio_power_status(
        zte
    )

    atual = next((
        radio
        for radio in verificado.get("radios", [])
        if radio.get("band") == band
    ), None)

    if (
        atual is None
        or atual.get("enabled") != bool(enabled)
    ):
        raise RuntimeError(
            "A ONT respondeu SUCC, mas o estado do rádio não foi confirmado."
        )

    return {
        "success": True,
        "band": band,
        "enabled": bool(enabled),
        "timer_disabled": True,
    }


# =========================================================
# WPS
# =========================================================


def wps_status(zte):
    """
    Lê o WPS por rádio.

    No ThinkLua, OBJ_WPS_ID e OBJ_WLANSETTING_ID são retornados juntos.
    O JavaScript original cria uma instância visual por rádio na mesma ordem.
    """

    zte.get_view(
        "wps",
        Menu3Location=0
    )

    xml = zte.get_menu(
        "wlan_wps_lua.lua"
    )

    zte._validar_resposta(
        xml
    )

    dados = zte._parse_instances(
        xml
    )

    wps_list = dados.get(
        "OBJ_WPS_ID",
        []
    )

    radios = dados.get(
        "OBJ_WLANSETTING_ID",
        []
    )

    resultado = []

    quantidade = max(
        len(wps_list),
        len(radios)
    )

    for index in range(
        quantidade
    ):
        wps = (
            wps_list[index]
            if index < len(wps_list)
            else {}
        )

        radio = (
            radios[index]
            if index < len(radios)
            else {}
        )

        enabled = wps.get(
            "Enable"
        ) == "1"

        wps_mode = wps.get(
            "WPSMode"
        )

        mode = "Disabled"

        if enabled:
            mode = (
                "PBC"
                if wps_mode == "0"
                else "PIN"
            )

        resultado.append({
            "id": wps.get("_InstID"),
            "band": radio.get("Band"),
            "radio_id": radio.get("_InstID"),
            "radio_enabled": radio.get("RadioStatus") == "1",
            "enabled": enabled,
            "mode": mode,
            "pin_available": bool(
                wps.get("WpsPINShow")
            ),
        })

    return resultado


def set_wps(
    zte,
    band,
    mode
):
    """
    Configura somente os modos seguros de automatizar pela console:
    Disabled ou PBC. PIN fica apenas em leitura porque variantes do firmware
    adicionam campos diferentes ao formulário.
    """

    mode = str(
        mode or ""
    ).strip()

    if mode not in (
        "Disabled",
        "PBC",
    ):
        raise ValueError(
            "WPS mode deve ser Disabled ou PBC."
        )

    atuais = wps_status(
        zte
    )

    alvo = next((
        item
        for item in atuais
        if item.get("band") == band
    ), None)

    if alvo is None:
        raise ValueError(
            f"WPS para {band} não encontrado."
        )

    ssid_inst_id = alvo.get(
        "id"
    )

    if not ssid_inst_id:
        raise RuntimeError(
            "A ONT não retornou a identidade usada pelo WPS."
        )

    enabled = mode != "Disabled"

    campos = [
        ("IF_ACTION", "Apply"),
        ("_InstID", "-1"),
        ("SSID_InstID", ssid_inst_id),
        ("Enable", "1" if enabled else "0"),
        ("WPSMode", "0"),
        ("WPSChoose", mode),
        ("Btn_apply_WPS", ""),
    ]

    zte.get_view(
        "wps",
        Menu3Location=0
    )

    resposta = post_menu(
        zte,
        "wlan_wps_lua.lua",
        campos
    )

    zte._validar_resposta(
        resposta
    )

    return {
        "success": True,
        "band": band,
        "mode": mode,
    }


# =========================================================
# UPNP
# =========================================================


def upnp_status(zte):
    zte.get_view(
        "upnp",
        Menu3Location=0
    )

    xml = zte.get_menu(
        "upnp_upnp_lua.lua"
    )

    zte._validar_resposta(
        xml
    )

    dados = zte._parse_instances(
        xml
    )

    config = _first(
        dados,
        "OBJ_UPNPCONFIG_ID"
    )

    if not config:
        return {
            "available": False,
        }

    return {
        "available": True,
        "id": config.get("_InstID"),
        "enabled": config.get("EnableUPnPIGD") == "1",
        "wan": config.get("WanName"),
        "wan_ipv6": config.get("Wanv6Name"),
        "advertisement_period": _int_or_value(
            config.get("ADPeriod")
        ),
        "ttl": _int_or_value(
            config.get("TTL")
        ),
    }


def set_upnp(
    zte,
    config
):
    atual = upnp_status(
        zte
    )

    if not atual.get(
        "available"
    ):
        raise RuntimeError(
            "UPnP não está disponível para esta conta/firmware."
        )

    novo = {
        "enabled": config.get(
            "enabled",
            atual.get("enabled", False)
        ),
        "wan": config.get(
            "wan",
            atual.get("wan") or ""
        ),
        "wan_ipv6": config.get(
            "wan_ipv6",
            atual.get("wan_ipv6") or ""
        ),
        "advertisement_period": int(
            config.get(
                "advertisement_period",
                atual.get("advertisement_period") or 30
            )
        ),
        "ttl": int(
            config.get(
                "ttl",
                atual.get("ttl") or 4
            )
        ),
    }

    if not 4 <= novo["advertisement_period"] <= 1440:
        raise ValueError(
            "ADPeriod do UPnP deve ficar entre 4 e 1440 segundos."
        )

    if not 1 <= novo["ttl"] <= 255:
        raise ValueError(
            "TTL do UPnP deve ficar entre 1 e 255."
        )

    zte.get_view(
        "upnp",
        Menu3Location=0
    )

    resposta = post_menu(
        zte,
        "upnp_upnp_lua.lua",
        [
            ("IF_ACTION", "Apply"),
            ("_InstID", atual.get("id") or "IGD"),
            (
                "EnableUPnPIGD",
                "1" if novo["enabled"] else "0"
            ),
            ("WanName", novo["wan"]),
            ("ADPeriod", novo["advertisement_period"]),
            ("TTL", novo["ttl"]),
            ("Wanv6Name", novo["wan_ipv6"]),
            ("Btn_cancel_LocalUPnP", ""),
            ("Btn_apply_LocalUPnP", ""),
        ]
    )

    zte._validar_resposta(
        resposta
    )

    return {
        "success": True,
        **novo,
    }


# =========================================================
# HELPERS
# =========================================================


def _first(
    dados,
    key
):
    values = dados.get(
        key,
        []
    )

    return (
        values[0]
        if values
        else {}
    )


def _int_or_value(
    value
):
    if value in (
        None,
        "",
    ):
        return value

    try:
        return int(
            value
        )
    except (
        TypeError,
        ValueError,
    ):
        return value


# =========================================================
# BAND STEERING / SMART CONNECT
# =========================================================


def band_steering_status(zte):
    """
    Lê o recurso de Band Steering exposto pelo firmware ThinkLua.

    Em algumas variantes essa página só existe para perfis com direito 3.
    Quando o menu não estiver disponível a camada de API devolve o erro do
    próprio equipamento em vez de fingir suporte.
    """

    zte.get_view(
        "smBandSteer",
        Menu3Location=0
    )

    xml = zte.get_menu(
        "mgts_bandsteer_lua.lua"
    )

    zte._validar_resposta(
        xml
    )

    dados = zte._parse_instances(
        xml
    )

    enabled = _first(
        dados,
        "OBJ_BANDSTEER_ENABLE_ID"
    )

    params = _first(
        dados,
        "OBJ_MGTS_BANDSTEER_ID"
    )

    if not enabled and not params:
        return {
            "available": False,
        }

    return {
        "available": True,
        "id": enabled.get("_InstID") or "IGD",
        "enabled": enabled.get("EnBandSteer") == "1",
        "parameters": {
            "rssi_limit_24g": _int_or_value(
                params.get("BsRssiLmt24G")
            ),
            "rssi_limit_5g": _int_or_value(
                params.get("BsRssiLmt5G")
            ),
            "idle_rate_limit_24g": _int_or_value(
                params.get("BsStaIdleRateLmt24G")
            ),
            "idle_rate_limit_5g": _int_or_value(
                params.get("BsStaIdleRateLmt5G")
            ),
            "bandwidth_util_24g": _int_or_value(
                params.get("BsBwUtil24G")
            ),
            "bandwidth_util_5g": _int_or_value(
                params.get("BsBwUtil5G")
            ),
            "accept_rssi_24g": _int_or_value(
                params.get("BsAcceptRssi24G")
            ),
            "accept_rssi_5g": _int_or_value(
                params.get("BsAcceptRssi5G")
            ),
        },
    }


def set_band_steering(
    zte,
    enabled
):
    """
    Liga/desliga somente o seletor global EnBandSteer.

    O JavaScript original usa IF_ACTION=SET_ENABLES para essa ação; os
    parâmetros avançados de RSSI/airtime permanecem intocados.
    """

    atual = band_steering_status(
        zte
    )

    if not atual.get(
        "available"
    ):
        raise RuntimeError(
            "Band Steering não está disponível para esta conta/firmware."
        )

    zte.get_view(
        "smBandSteer",
        Menu3Location=0
    )

    resposta = post_menu(
        zte,
        "mgts_bandsteer_lua.lua",
        [
            ("IF_ACTION", "SET_ENABLES"),
            (
                "EnBandSteer",
                "1" if enabled else "0"
            ),
            (
                "_InstID",
                atual.get("id") or "IGD"
            ),
        ]
    )

    zte._validar_resposta(
        resposta
    )

    verificado = band_steering_status(
        zte
    )

    if verificado.get("enabled") != bool(enabled):
        raise RuntimeError(
            "A ONT respondeu SUCC, mas o Band Steering não foi confirmado."
        )

    return {
        "success": True,
        "enabled": bool(enabled),
    }

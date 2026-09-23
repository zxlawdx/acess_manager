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
# AGENDAMENTO DO WI-FI
# =========================================================


def wifi_schedule_status(zte):
    """Reaproveita a mesma página de power/timer sem duplicar parser."""
    status = radio_power_status(
        zte
    )

    return {
        "available": True,
        "enabled": status.get("timer_enabled", False),
        "schedule": status.get("schedule", {}),
        "radios": status.get("radios", []),
    }


def set_wifi_schedule(
    zte,
    config
):
    """
    Configura o timer global exposto pelo ThinkLua.

    Neste firmware o timer não é por banda: quando TimerEnable=1 o período
    vale para o Wi-Fi como um todo. Ao desativar, reenviamos o estado atual dos
    rádios para reproduzir o formulário oficial e não desligá-los por acidente.
    """
    current = radio_power_status(
        zte
    )

    enabled = bool(
        config.get("enabled", False)
    )
    schedule = current.get(
        "schedule",
        {}
    )

    values = {
        "start_hour": int(
            config.get(
                "start_hour",
                schedule.get("start_hour") or 0
            )
        ),
        "start_minute": int(
            config.get(
                "start_minute",
                schedule.get("start_minute") or 0
            )
        ),
        "end_hour": int(
            config.get(
                "end_hour",
                schedule.get("end_hour") or 0
            )
        ),
        "end_minute": int(
            config.get(
                "end_minute",
                schedule.get("end_minute") or 0
            )
        ),
    }

    if not 0 <= values["start_hour"] <= 23:
        raise ValueError("Hora inicial deve ficar entre 0 e 23.")

    if not 0 <= values["end_hour"] <= 23:
        raise ValueError("Hora final deve ficar entre 0 e 23.")

    if not 0 <= values["start_minute"] <= 59:
        raise ValueError("Minuto inicial deve ficar entre 0 e 59.")

    if not 0 <= values["end_minute"] <= 59:
        raise ValueError("Minuto final deve ficar entre 0 e 59.")

    fields = [
        ("IF_ACTION", "Apply"),
        (
            "_InstID",
            current.get("timer_id") or "IGD"
        ),
        (
            "TimerEnable",
            "1" if enabled else "0"
        ),
    ]

    # Quando TimerEnable=0 o backend entra em setWlanRadio(). Esses campos
    # garantem que a transição do modo agendado para manual preserve os rádios.
    for index, radio in enumerate(
        current.get("radios", [])
    ):
        fields.extend([
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

    fields.extend([
        (
            "TimeStartHour",
            str(values["start_hour"])
        ),
        (
            "TimeStartMin",
            str(values["start_minute"])
        ),
        (
            "TimeEndHour",
            str(values["end_hour"])
        ),
        (
            "TimeEndMin",
            str(values["end_minute"])
        ),
        ("Btn_cancel_WlanBasicAdConf", ""),
        ("Btn_apply_WlanBasicAdConf", ""),
    ])

    zte.get_view(
        "wlanBasic",
        Menu3Location=0
    )

    response = post_menu(
        zte,
        "wlan_wlanbasiconoff_lua.lua",
        fields
    )

    zte._validar_resposta(
        response
    )

    verified = wifi_schedule_status(
        zte
    )

    if verified.get("enabled") != enabled:
        raise RuntimeError(
            "A ONT respondeu SUCC, mas o estado do agendamento não foi confirmado."
        )

    return {
        "success": True,
        **verified,
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


BAND_STEERING_FIELDS = (
    "Enable",
    "BsRssiLmt24G",
    "BsRssiLmt5G",
    "BsVhtChk24G",
    "BsVhtChk5G",
    "BsActiveStaChk24G",
    "BsActiveStaChk5G",
    "BsStaIdleRateLmt24G",
    "BsStaIdleRateLmt5G",
    "BsBwUtil24G",
    "BsBwUtil5G",
    "BsAcceptBwUtil24G",
    "BsAcceptBwUtil5G",
    "BsAcceptRssi24G",
    "BsAcceptRssi5G",
    "BsAcceptVhtCheck24G",
    "BsAcceptVhtCheck5G",
    "BsBounceDetectTimeLmt",
    "BsBounceCountsLmt",
    "BsBounceDwellTimeLmt",
)


BAND_STEERING_API_MAP = {
    "rssi_limit_24g": "BsRssiLmt24G",
    "rssi_limit_5g": "BsRssiLmt5G",
    "vht_check_24g": "BsVhtChk24G",
    "vht_check_5g": "BsVhtChk5G",
    "active_sta_check_24g": "BsActiveStaChk24G",
    "active_sta_check_5g": "BsActiveStaChk5G",
    "idle_rate_limit_24g": "BsStaIdleRateLmt24G",
    "idle_rate_limit_5g": "BsStaIdleRateLmt5G",
    "bandwidth_util_24g": "BsBwUtil24G",
    "bandwidth_util_5g": "BsBwUtil5G",
    "accept_bandwidth_util_24g": "BsAcceptBwUtil24G",
    "accept_bandwidth_util_5g": "BsAcceptBwUtil5G",
    "accept_rssi_24g": "BsAcceptRssi24G",
    "accept_rssi_5g": "BsAcceptRssi5G",
    "accept_vht_check_24g": "BsAcceptVhtCheck24G",
    "accept_vht_check_5g": "BsAcceptVhtCheck5G",
    "bounce_detect_time": "BsBounceDetectTimeLmt",
    "bounce_count": "BsBounceCountsLmt",
    "bounce_dwell_time": "BsBounceDwellTimeLmt",
}


def _band_steering_read(zte):
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

    data = zte._parse_instances(
        xml
    )

    return (
        _first(
            data,
            "OBJ_BANDSTEER_ENABLE_ID"
        ),
        _first(
            data,
            "OBJ_MGTS_BANDSTEER_ID"
        ),
    )


def band_steering_status(zte):
    enabled, params = _band_steering_read(
        zte
    )

    if not enabled and not params:
        return {
            "available": False,
        }

    parameters = {}

    for api_name, firmware_name in (
        BAND_STEERING_API_MAP.items()
    ):
        parameters[api_name] = _int_or_value(
            params.get(firmware_name)
        )

    return {
        "available": True,
        "id": enabled.get("_InstID") or "IGD",
        "parameter_id": (
            params.get("_InstID")
            or "IGD.WiFi.RD1.BS"
        ),
        "enabled": enabled.get("EnBandSteer") == "1",
        "parameters": parameters,
    }


def set_band_steering(
    zte,
    enabled
):
    """Liga/desliga o seletor global sem tocar nos thresholds."""
    current = band_steering_status(
        zte
    )

    if not current.get("available"):
        raise RuntimeError(
            "Band Steering não está disponível para esta conta/firmware."
        )

    zte.get_view(
        "smBandSteer",
        Menu3Location=0
    )

    response = post_menu(
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
                current.get("id") or "IGD"
            ),
        ]
    )

    zte._validar_resposta(
        response
    )

    verified = band_steering_status(
        zte
    )

    if verified.get("enabled") != bool(enabled):
        raise RuntimeError(
            "A ONT respondeu SUCC, mas o Band Steering não foi confirmado."
        )

    return {
        "success": True,
        **verified,
    }


def configure_band_steering(
    zte,
    config
):
    """
    Ajusta os thresholds preservando todos os parâmetros que a UI não enviou.

    IF_ACTION=Apply afeta apenas OBJ_MGTS_BANDSTEER_ID; o enable global
    continua sendo tratado por set_band_steering().
    """
    current = band_steering_status(
        zte
    )

    if not current.get("available"):
        raise RuntimeError(
            "Band Steering não está disponível para esta conta/firmware."
        )

    _, raw = _band_steering_read(
        zte
    )

    merged = dict(
        raw
    )

    for api_name, firmware_name in (
        BAND_STEERING_API_MAP.items()
    ):
        if api_name not in config:
            continue

        value = config[api_name]

        if value is None:
            continue

        value = int(
            value
        )

        if (
            "Rssi" in firmware_name
            and not -120 <= value <= 0
        ):
            raise ValueError(
                f"{api_name} deve ficar entre -120 e 0 dBm."
            )

        if (
            "BwUtil" in firmware_name
            and not 0 <= value <= 100
        ):
            raise ValueError(
                f"{api_name} deve ficar entre 0 e 100."
            )

        if value < -120:
            raise ValueError(
                f"{api_name} possui valor inválido."
            )

        merged[firmware_name] = str(
            value
        )

    fields = [
        ("IF_ACTION", "Apply"),
        (
            "_InstID",
            current.get("parameter_id")
            or "IGD.WiFi.RD1.BS"
        ),
    ]

    for name in BAND_STEERING_FIELDS:
        if name in merged:
            fields.append((
                name,
                merged.get(name) or ""
            ))

    zte.get_view(
        "smBandSteer",
        Menu3Location=0
    )

    response = post_menu(
        zte,
        "mgts_bandsteer_lua.lua",
        fields
    )

    zte._validar_resposta(
        response
    )

    verified = band_steering_status(
        zte
    )

    return {
        "success": True,
        **verified,
    }

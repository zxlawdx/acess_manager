from .zte_post import post_menu


# =========================================================
# REGRAS DO FORMULÁRIO ORIGINAL
# =========================================================


STANDARD_PARAMETERS = {
    "b": {
        "BasicDataRates": "1,2",
        "OpDataRates": "1,2,5.5,11",
        "11nMode": "0",
        "GreenField": "0",
    },
    "g": {
        "BasicDataRates": "1,2,5.5,11,6,9,12,18,24",
        "OpDataRates": "1,2,5.5,11,6,9,12,18,24,36,48,54",
        "11nMode": "0",
        "GreenField": "0",
    },
    "b,g": {
        "BasicDataRates": "1,2,5.5,11",
        "OpDataRates": "1,2,5.5,11,6,9,12,18,24,36,48,54",
        "11nMode": "0",
        "GreenField": "0",
    },
    "2.4n": {
        "BasicDataRates": "1,2,5.5,11",
        "OpDataRates": "1,2,5.5,11,6,9,12,18,24,36,48,54",
        "11nMode": "1",
        "GreenField": "1",
    },
    "5n": {
        "BasicDataRates": "6,9,12,18,24,36,48,54",
        "OpDataRates": "6,9,12,18,24,36,48,54",
        "11nMode": "1",
        "GreenField": "1",
    },
    "g,n": {
        "BasicDataRates": "1,2,5.5,11,6,9,12,18,24",
        "OpDataRates": "1,2,5.5,11,6,9,12,18,24,36,48,54",
        "11nMode": "1",
        "GreenField": "0",
    },
    "b,g,n": {
        "BasicDataRates": "1,2,5.5,11",
        "OpDataRates": "1,2,5.5,11,6,9,12,18,24,36,48,54",
        "11nMode": "1",
        "GreenField": "0",
    },
    "b,g,n,ax": {
        "BasicDataRates": "1,2,5.5,11",
        "OpDataRates": "1,2,5.5,11,6,9,12,18,24,36,48,54",
        "11nMode": "1",
        "GreenField": "0",
    },
    "a": {
        "BasicDataRates": "6,9,12,18,24,36,48,54",
        "OpDataRates": "6,9,12,18,24,36,48,54",
        "11nMode": "0",
        "GreenField": "0",
    },
    "a,n": {
        "BasicDataRates": "6,9,12,18,24,36,48,54",
        "OpDataRates": "6,9,12,18,24,36,48,54",
        "11nMode": "1",
        "GreenField": "0",
    },
    "a,n,ac": {
        "BasicDataRates": "6,9,12,18,24,36,48,54",
        "OpDataRates": "6,9,12,18,24,36,48,54",
        "11nMode": "1",
        "GreenField": "0",
    },
    "a,n,ac,ax": {
        "BasicDataRates": "6,9,12,18,24,36,48,54",
        "OpDataRates": "6,9,12,18,24,36,48,54",
        "11nMode": "1",
        "GreenField": "0",
    },
    "ac": {
        "BasicDataRates": "6,9,12,18,24,36,48,54",
        "OpDataRates": "6,9,12,18,24,36,48,54",
        "11nMode": "1",
        "GreenField": "0",
    },
}


# Ordem observada no formulário wlan_wlanbasicadconf_t.lp.
# Os controles UI_* e os botões têm PostIgnore no firmware e não entram aqui.
RADIO_FIELDS = [
    "BasicDataRates",
    "OpDataRates",
    "11nMode",
    "GreenField",
    "AutoChannelEnabled",
    "Band",
    "Channel",
    "SideBand",
    "Standard",
    "BandWidth",
    "AutoChRange",
    "BandBEnabled",
    "MUMIMOEnable",
    "SSIDIsolationEnable",
    "CountryCode",
    "SGIEnabled",
    "BeaconInterval",
    "TxPower",
    "QosType",
    "WorkMode",
    "RtsCts",
    "DTIM",
    "DownLinkMUMIMO",
    "UPLinkMUMIMO",
    "UPLinkOFDMA",
    "DownLinkOFDMA",
    "TWTSupport",
    "SpatialReuse",
    "PreambleType",
]


# =========================================================
# GET
# =========================================================


def get_channel(zte):
    zte.get_view(
        "wlanBasic",
        Menu3Location=0
    )

    return zte.get_menu(
        "wlan_wlanbasicadconf_lua.lua"
    )


# =========================================================
# POST
# =========================================================


def set_radio_config(
    zte,
    band,
    config
):
    """
    Aplica a configuração avançada de um rádio.

    Fluxo:
        1. abre wlanBasic;
        2. lê configuração atual + tabela de canais;
        3. preserva parâmetros que o perfil não altera;
        4. reproduz hiddenValueChangeByCustom do JS original;
        5. post_menu adiciona _sessionTOKEN e calcula Check.
    """

    xml = get_channel(
        zte
    )

    zte._validar_resposta(
        xml
    )

    dados = zte._parse_instances(
        xml
    )

    radios = dados.get(
        "OBJ_WLANSETTING_ID",
        []
    )

    radio = next((
        item
        for item in radios
        if item.get("Band") == band
    ), None)

    if radio is None:
        raise ValueError(
            f"Rádio {band} não encontrado."
        )

    novo = dict(
        radio
    )

    _apply_standard(
        novo,
        band,
        config
    )

    _apply_channel(
        dados,
        novo,
        band,
        config
    )

    _apply_advanced(
        novo,
        config
    )

    campos = [
        ("IF_ACTION", "Apply"),
        ("_InstID", radio.get("_InstID")),
    ]

    for nome in RADIO_FIELDS:
        if nome not in novo:
            continue

        valor = novo.get(
            nome
        )

        if valor is None:
            continue

        campos.append((
            nome,
            valor
        ))

    # Os botões são inputs do formulário original. Mesmo sendo type=button,
    # InitialPostData() os serializa com valor vazio no final do body.
    campos.extend([
        ("Btn_cancel_WlanBasicAdConf", ""),
        ("Btn_apply_WlanBasicAdConf", ""),
    ])

    resposta = post_menu(
        zte,
        "wlan_wlanbasicadconf_lua.lua",
        campos
    )

    if "<IF_ERRORSTR>SUCC</IF_ERRORSTR>" not in resposta:
        raise RuntimeError(
            "A ZTE recusou a configuração WLAN. "
            + resposta[:400]
        )

    return {
        "success": True,
        "band": band,
        "config": config,
    }


# =========================================================
# BUILDER HELPERS
# =========================================================


def _apply_standard(
    novo,
    band,
    config
):
    standard = config.get(
        "standard"
    )

    if standard:
        novo["Standard"] = standard

        key = standard

        if standard == "n":
            key = (
                "5n"
                if band == "5GHz"
                else "2.4n"
            )

        novo.update(
            STANDARD_PARAMETERS.get(
                key,
                {}
            )
        )

    if config.get("bandwidth"):
        novo["BandWidth"] = config[
            "bandwidth"
        ]

    if config.get("country"):
        novo["CountryCode"] = config[
            "country"
        ]


def _apply_channel(
    dados,
    novo,
    band,
    config
):
    if not (
        "auto_channel" in config
        or "channel" in config
    ):
        return

    auto_channel = config.get(
        "auto_channel"
    )

    channel = config.get(
        "channel"
    )

    if (
        auto_channel is True
        or channel in (
            None,
            "",
            "Auto",
        )
    ):
        novo["AutoChannelEnabled"] = "1"
        novo["Channel"] = "NULL"
        return

    _validate_channel(
        dados,
        band=band,
        country=novo.get("CountryCode"),
        bandwidth=novo.get("BandWidth"),
        channel=channel,
    )

    novo["AutoChannelEnabled"] = "0"
    novo["Channel"] = str(
        channel
    )

    if config.get("sideband"):
        novo["SideBand"] = config[
            "sideband"
        ]


def _apply_advanced(
    novo,
    config
):
    """
    Aplica somente overrides recebidos.

    Campos ausentes permanecem exatamente como vieram da ONT. Esse padrão é
    importante entre F6600P/F670L porque nem todo firmware expõe todos os
    controles de 802.11ax.
    """
    boolean_fields = {
        "sgi": "SGIEnabled",
        "mu_mimo": "MUMIMOEnable",
        "uplink_mu_mimo": "UPLinkMUMIMO",
        "downlink_mu_mimo": "DownLinkMUMIMO",
        "uplink_ofdma": "UPLinkOFDMA",
        "downlink_ofdma": "DownLinkOFDMA",
        "twt": "TWTSupport",
        "spatial_reuse": "SpatialReuse",
        "ssid_isolation": "SSIDIsolationEnable",
    }

    for source, target in boolean_fields.items():
        if source in config:
            novo[target] = (
                "1"
                if config[source]
                else "0"
            )

    if config.get("beacon_interval") is not None:
        beacon = int(
            config["beacon_interval"]
        )

        if not 100 <= beacon <= 1000:
            raise ValueError(
                "BeaconInterval deve ficar entre 100 e 1000."
            )

        novo["BeaconInterval"] = str(
            beacon
        )

    if config.get("rts_cts") is not None:
        rts_cts = int(
            config["rts_cts"]
        )

        if not 0 <= rts_cts <= 2347:
            raise ValueError(
                "RTS/CTS deve ficar entre 0 e 2347."
            )

        novo["RtsCts"] = str(
            rts_cts
        )

    if config.get("dtim") is not None:
        dtim = int(
            config["dtim"]
        )

        if not 1 <= dtim <= 5:
            raise ValueError(
                "DTIM deve ficar entre 1 e 5."
            )

        novo["DTIM"] = str(
            dtim
        )

    direct_fields = {
        "tx_power": "TxPower",
        "qos_type": "QosType",
        "work_mode": "WorkMode",
        "preamble_type": "PreambleType",
    }

    for source, target in direct_fields.items():
        value = config.get(source)

        if value is not None and value != "":
            novo[target] = str(
                value
            )


def _validate_channel(
    dados,
    band,
    country,
    bandwidth,
    channel,
):
    channel = str(
        channel
    )

    configuracoes = dados.get(
        "OBJ_CHANNEL_ID",
        []
    )

    compativeis = [
        item
        for item in configuracoes
        if item.get("CountryCode") == country
        and item.get("Band") == band
        and item.get("BandWidth") == bandwidth
    ]

    # Se o firmware não informou esta combinação, não criamos uma tabela local.
    # O próprio equipamento ainda fará a validação no POST.
    if not compativeis:
        return

    canais = set()

    for item in compativeis:
        canais.update(
            valor.strip()
            for valor in item.get(
                "ChannelList",
                ""
            ).split(",")
            if valor.strip()
        )

    if channel not in canais:
        raise ValueError(
            f"Canal {channel} não é válido para "
            f"{band} / {bandwidth} / {country}."
        )

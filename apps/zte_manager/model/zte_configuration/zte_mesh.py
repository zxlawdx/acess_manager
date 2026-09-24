from __future__ import annotations

from typing import Any

from .zte_post import post_menu


MESH_SOURCES = (
    {
        "view": "smNetSphereMAP",
        "tag": "braziloi_Localnet_NetSphere_Mode_lua.lua",
        "kind": "localnet_netsphere",
        "profile": "f670l_v9_braziloi",
        "prefer_cookie_only": True,
    },
    {
        "view": "smNetSphereMAP",
        "tag": "wlan_NetSphere_Mode_lua.lua",
        "kind": "wlan_netsphere",
    },
    {
        "view": "smNetSphereMAP",
        "tag": "Localnet_NetSphere_Mode_lua.lua",
        "kind": "localnet_netsphere",
    },
    {
        "view": "BandSteerMesh",
        "tag": "NetSphere_Mode_lua.lua",
        "kind": "netsphere",
    },
    {
        "view": "wlanBasic",
        "tag": "NetSphere_Mode_lua.lua",
        "kind": "netsphere",
    },
    {
        "view": "wlanBasic",
        "tag": "Localnet_NetSphere_Mode_lua.lua",
        "kind": "localnet_netsphere",
    },
)


def _first(
    parsed: dict[str, list[dict[str, Any]]],
    key: str,
) -> dict[str, Any]:
    items = parsed.get(
        key,
        [],
    )

    return (
        dict(items[0])
        if items
        else {}
    )


def _as_bool(
    value,
) -> bool | None:
    if value in (
        "1",
        1,
        True,
        "true",
        "True",
        "on",
        "On",
    ):
        return True

    if value in (
        "0",
        0,
        False,
        "false",
        "False",
        "off",
        "Off",
    ):
        return False

    return None


def _as_int(
    value,
) -> int | None:
    if value in (
        None,
        "",
    ):
        return None

    try:
        return int(
            str(value).strip()
        )
    except (
        TypeError,
        ValueError,
    ):
        return None


def _menu_extras(
    zte,
) -> dict[str, Any]:
    """
    Alguns firmwares exigem o token temporário também no GET menuData.

    A UI original costuma carregar esse valor a partir da menuView. Em menus
    ocultos a view pode não existir para a role atual, então reaproveitamos o
    token de uma view conhecida antes de concluir que o backend não existe.
    """
    token = getattr(
        zte,
        "session_tmp_token",
        None,
    )

    if not token:
        return {}

    return {
        "_sessionTOKEN": token,
    }


def _mesh_payload_from_xml(
    zte,
    xml,
    source,
    context_view,
) -> dict[str, Any]:
    zte._validar_resposta(
        xml
    )

    parsed = zte._parse_instances(
        xml
    )

    mesh = _first(
        parsed,
        "OBJ_NETSPHERE_MAP_ID",
    )

    if not mesh:
        raise RuntimeError(
            "O backend respondeu, mas OBJ_NETSPHERE_MAP_ID não foi retornado."
        )

    resolved_source = dict(
        source
    )
    resolved_source[
        "context_view"
    ] = context_view
    # O método de autenticação usado no menuData é preenchido
    # pelo caller com base na tentativa que realmente respondeu.
    resolved_source.setdefault(
        "used_session_token",
        False,
    )
    resolved_source.setdefault(
        "menu_auth",
        "cookie_only",
    )

    return {
        "source": resolved_source,
        "mesh": mesh,
        "map_master": _first(
            parsed,
            "OBJ_MAP_MASTER_ID",
        ),
        "domain_band_steering": _first(
            parsed,
            "OBJ_TEMP_DOMAIN_BS",
        ),
        "netsphere_band_steering": _first(
            parsed,
            "OBJ_NETSPHERE_BANDSTEER_ID",
        ),
        "roaming": _first(
            parsed,
            "OBJ_MULTIAP_ROAM_ID",
        ),
        "map_domain": _first(
            parsed,
            "OBJ_MAP_DOMAIN_ID",
        ),
        "raw_objects": parsed,
    }


def _source_payload(
    zte,
    source,
) -> dict[str, Any]:
    """
    Tenta o backend Mesh usando primeiro sua view canônica e depois views
    conhecidas que conseguem renovar o _sessionTmpToken.

    SessionTimeout no menuData nem sempre significa logout: em vários ZTE ele
    também significa que a tag foi chamada sem o contexto de menu correto.
    """
    attempts = []

    context_views = []

    for view in (
        source["view"],
        "wlanBasic",
        "wps",
        "homePage",
    ):
        if view not in context_views:
            context_views.append(
                view
            )

    for context_view in context_views:
        try:
            html = zte.get_view(
                context_view,
                Menu3Location=0,
            )

            if "SessionTimeout" in str(
                html
            ):
                raise RuntimeError(
                    f"menuView {context_view} devolveu SessionTimeout."
                )

            token_extras = _menu_extras(
                zte
            )

            menu_attempts = [
                (
                    "cookie_only",
                    {},
                ),
            ]

            if token_extras:
                token_attempt = (
                    "session_token",
                    token_extras,
                )

                if source.get(
                    "prefer_cookie_only",
                    False,
                ):
                    menu_attempts.append(
                        token_attempt
                    )
                else:
                    menu_attempts = [
                        token_attempt,
                        *menu_attempts,
                    ]

            menu_errors = []

            for (
                auth_mode,
                extras,
            ) in menu_attempts:
                try:
                    xml = zte.get_menu(
                        source["tag"],
                        **extras,
                    )

                    resolved_source = dict(
                        source
                    )
                    resolved_source[
                        "used_session_token"
                    ] = bool(
                        extras
                    )
                    resolved_source[
                        "menu_auth"
                    ] = auth_mode

                    return _mesh_payload_from_xml(
                        zte,
                        xml,
                        resolved_source,
                        context_view,
                    )

                except Exception as error:
                    menu_errors.append(
                        f"{auth_mode}: {error}"
                    )

            raise RuntimeError(
                " | ".join(
                    menu_errors
                )
            )

        except Exception as error:
            attempts.append(
                f"{context_view}: {error}"
            )

    raise RuntimeError(
        "nenhum contexto de view aceitou este backend: "
        + " | ".join(
            attempts
        )
    )


def _read_mesh(
    zte,
) -> dict[str, Any]:
    errors = []

    for source in MESH_SOURCES:
        try:
            return _source_payload(
                zte,
                source,
            )
        except Exception as error:
            errors.append({
                "view": source["view"],
                "tag": source["tag"],
                "error": str(error),
            })

    raise RuntimeError(
        "EasyMesh/NetSphere não respondeu nos backends conhecidos. "
        + " | ".join(
            (
                f"{item['tag']}: {item['error']}"
            )
            for item in errors
        )
    )


def mesh_status(
    zte,
) -> dict[str, Any]:
    """
    Lê o EasyMesh/NetSphere mesmo quando o menu está oculto pela interface.

    Variantes de firmware ZTE expõem o mesmo OBJ_NETSPHERE_MAP_ID em tags
    diferentes. O probe tenta as variantes conhecidas sem alterar a ONT.
    """
    try:
        payload = _read_mesh(
            zte
        )
    except Exception as error:
        return {
            "available": False,
            "enabled": False,
            "error": str(error),
            "probe": {
                "sources": [
                    {
                        "view": item["view"],
                        "tag": item["tag"],
                    }
                    for item in MESH_SOURCES
                ]
            },
        }

    mesh = payload[
        "mesh"
    ]

    map_master = payload[
        "map_master"
    ]

    domain_bs = payload[
        "domain_band_steering"
    ]

    netsphere_bs = payload[
        "netsphere_band_steering"
    ]

    roaming = payload[
        "roaming"
    ]

    band_steering = (
        _as_bool(
            map_master.get(
                "EnBandSteer"
            )
        )
        if map_master
        else _as_bool(
            netsphere_bs.get(
                "BandSteerEnable"
            )
        )
        if netsphere_bs
        else None
    )

    rssi_24 = (
        _as_int(
            domain_bs.get(
                "BsRssiLmt24G"
            )
        )
        if domain_bs
        else _as_int(
            roaming.get(
                "RoamRssiLmt24G"
            )
        )
        if roaming
        else None
    )

    rssi_5 = (
        _as_int(
            domain_bs.get(
                "BsRssiLmt5G"
            )
        )
        if domain_bs
        else _as_int(
            roaming.get(
                "RoamRssiLmt5G"
            )
        )
        if roaming
        else None
    )

    legacy_roaming = (
        _as_bool(
            roaming.get(
                "EnLegacyStaRoam"
            )
        )
        if roaming
        else None
    )

    return {
        "available": True,
        "enabled": (
            _as_bool(
                mesh.get(
                    "Enable"
                )
            )
            is True
        ),
        "id": (
            mesh.get(
                "_InstID"
            )
            or "DEV.MULTIAPCFG"
        ),
        "mode_raw": mesh.get(
            "Mode"
        ),
        "role": "controller_when_enabled",
        "role_note": (
            "Na F670L, habilitar EasyMesh/NetSphere faz a ONT atuar como "
            "Controller; o equipamento secundário precisa operar como Agent."
        ),
        "band_steering": band_steering,
        "rssi_limit_24g": rssi_24,
        "rssi_limit_5g": rssi_5,
        "legacy_station_roaming": legacy_roaming,
        "backend": payload[
            "source"
        ],
        "wps_pairing_supported": True,
        "raw": {
            "mesh": mesh,
            "map_master": map_master,
            "domain_band_steering": domain_bs,
            "netsphere_band_steering": netsphere_bs,
            "roaming": roaming,
            "map_domain": payload[
                "map_domain"
            ],
        },
    }


def _rssi(
    value,
    name,
):
    if value is None:
        return None

    number = int(
        value
    )

    if not -110 <= number <= -40:
        raise ValueError(
            f"{name} deve ficar entre -110 e -40 dBm."
        )

    return number


def configure_mesh(
    zte,
    config: dict[str, Any],
) -> dict[str, Any]:
    """
    Configura o EasyMesh preservando o Mode devolvido pelo firmware.

    Não tentamos converter a F670L em Agent: documentação/firmware dessa ONT
    usa Mesh Enable para assumir o papel de Controller. O papel do segundo
    equipamento deve ser configurado nele próprio.
    """
    current = mesh_status(
        zte
    )

    if not current.get(
        "available"
    ):
        raise RuntimeError(
            current.get(
                "error"
            )
            or "EasyMesh não está disponível nesta ONT."
        )

    enabled = bool(
        config.get(
            "enabled",
            current.get(
                "enabled",
                False,
            ),
        )
    )

    band_steering = config.get(
        "band_steering",
        current.get(
            "band_steering"
        ),
    )

    rssi_24 = _rssi(
        config.get(
            "rssi_limit_24g",
            current.get(
                "rssi_limit_24g"
            ),
        ),
        "RSSI 2.4 GHz",
    )

    rssi_5 = _rssi(
        config.get(
            "rssi_limit_5g",
            current.get(
                "rssi_limit_5g"
            ),
        ),
        "RSSI 5 GHz",
    )

    source = current[
        "backend"
    ]

    fields = [
        (
            "IF_ACTION",
            "Apply",
        ),
        (
            "_InstID",
            current.get(
                "id"
            )
            or "DEV.MULTIAPCFG",
        ),
        (
            "Enable",
            "1" if enabled else "0",
        ),
    ]

    # Algumas variantes carregam Mode mesmo sem mostrar Role no HTML.
    # Preservamos o valor atual para não trocar Controller/Agent por acidente.
    if current.get(
        "mode_raw"
    ) not in (
        None,
        "",
    ):
        fields.append((
            "Mode",
            str(
                current[
                    "mode_raw"
                ]
            ),
        ))

    kind = source.get(
        "kind"
    )

    raw = current.get(
        "raw",
        {},
    )

    if kind == "wlan_netsphere":
        if (
            raw.get(
                "map_master"
            )
            and band_steering is not None
        ):
            fields.append((
                "EnBandSteer",
                "1"
                if bool(
                    band_steering
                )
                else "0",
            ))

        if raw.get(
            "domain_band_steering"
        ):
            if rssi_24 is not None:
                fields.append((
                    "BsRssiLmt24G",
                    str(
                        rssi_24
                    ),
                ))

            if rssi_5 is not None:
                fields.append((
                    "BsRssiLmt5G",
                    str(
                        rssi_5
                    ),
                ))

    elif kind == "netsphere":
        if (
            raw.get(
                "netsphere_band_steering"
            )
            and band_steering is not None
        ):
            fields.append((
                "BandSteerEnable",
                "1"
                if bool(
                    band_steering
                )
                else "0",
            ))

    elif (
        kind == "localnet_netsphere"
        and raw.get(
            "roaming"
        )
    ):
        if config.get(
            "legacy_station_roaming"
        ) is not None:
            fields.append((
                "EnLegacyStaRoam",
                "1"
                if bool(
                    config[
                        "legacy_station_roaming"
                    ]
                )
                else "0",
            ))
        elif current.get(
            "legacy_station_roaming"
        ) is not None:
            fields.append((
                "EnLegacyStaRoam",
                "1"
                if current[
                    "legacy_station_roaming"
                ]
                else "0",
            ))

        if rssi_24 is not None:
            fields.append((
                "RoamRssiLmt24G",
                str(
                    rssi_24
                ),
            ))

        if rssi_5 is not None:
            fields.append((
                "RoamRssiLmt5G",
                str(
                    rssi_5
                ),
            ))

    zte.get_view(
        source[
            "view"
        ],
        Menu3Location=0,
    )

    response = post_menu(
        zte,
        source[
            "tag"
        ],
        fields,
    )

    zte._validar_resposta(
        response
    )

    verified = mesh_status(
        zte
    )

    if (
        verified.get(
            "available"
        )
        and verified.get(
            "enabled"
        ) != enabled
    ):
        raise RuntimeError(
            "A ONT respondeu SUCC, mas o estado EasyMesh não foi confirmado."
        )

    return {
        "success": True,
        "before": current,
        "after": verified,
        "reboot_may_occur": (
            current.get(
                "mode_raw"
            )
            != verified.get(
                "mode_raw"
            )
        ),
    }


def start_mesh_pairing(
    zte,
) -> dict[str, Any]:
    """
    Equivale ao botão físico WPS usado pelo fluxo EasyMesh da ZTE.

    O Controller entra em janela de pareamento. O usuário ainda precisa acionar
    WPS/EasyMesh no equipamento Agent.
    """
    current = mesh_status(
        zte
    )

    if not current.get(
        "available"
    ):
        raise RuntimeError(
            "EasyMesh não está disponível nesta ONT."
        )

    if not current.get(
        "enabled"
    ):
        raise RuntimeError(
            "Ative o EasyMesh antes de iniciar o pareamento."
        )

    # A página do firmware usa wlan_wps_btn_lua.lua -> dev_action cmd_wpsbtn.
    # Abrimos a view WPS antes do POST para manter o contexto ThinkLua.
    zte.get_view(
        "wps",
        Menu3Location=0,
    )

    response = post_menu(
        zte,
        "wlan_wps_btn_lua.lua",
        [
            (
                "IF_ACTION",
                "WPSBTN",
            ),
        ],
    )

    zte._validar_resposta(
        response
    )

    return {
        "success": True,
        "mesh_enabled": True,
        "action": "wps_pairing",
        "message": (
            "Janela WPS/EasyMesh iniciada no Controller. "
            "Agora acione WPS/EasyMesh no ZTE que será o Agent."
        ),
    }

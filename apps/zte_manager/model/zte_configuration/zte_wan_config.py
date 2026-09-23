import xml.etree.ElementTree as ET

from . import zte_security


# =========================================================
# WAN / PPPOE
# =========================================================


def wan_config_raw(zte):
    """
    A tela de configuração WAN é diferente da tela de status.

    No firmware ZTE ThinkLua de referência:
        menuView = ethWanConfig
        menuData = wan_internet_lua.lua
        TypeUplink = 2
        pageType = 0

    Este menu é o que expõe UserName/Password e informa em <encode> quais
    campos vieram criptografados.
    """

    zte.get_view(
        "ethWanConfig",
        Menu3Location=0
    )

    return zte.get_menu(
        "wan_internet_lua.lua",
        TypeUplink=2,
        pageType=0,
    )


def pppoe_status(
    zte,
    reveal_password=False
):
    xml = wan_config_raw(
        zte
    )

    zte._validar_resposta(
        xml
    )

    dados = zte._parse_instances(
        xml
    )

    conexoes = (
        dados.get("ID_WAN_COMFIG")
        or dados.get("OBJ_WAN_CONFIG_ID")
        or dados.get("OBJ_WAN_COMFIG")
        or []
    )

    encode_fields = _get_encode_fields(
        xml
    )

    token = getattr(
        zte,
        "session_tmp_token",
        None
    )

    resultado = []

    for wan in conexoes:
        if not _is_pppoe(wan):
            continue

        username = wan.get(
            "UserName",
            ""
        )

        password = wan.get(
            "Password",
            ""
        )

        # A interface oficial usa o token temporário como chave e o token
        # invertido como IV para exibir os campos marcados em <encode>.
        if token:
            if "UserName" in encode_fields:
                username = zte_security.aes_decrypt_value(
                    username,
                    token,
                    token[::-1]
                )

            if "Password" in encode_fields:
                password = zte_security.aes_decrypt_value(
                    password,
                    token,
                    token[::-1]
                )

        resultado.append({
            "id": wan.get("_InstID"),
            "nome": wan.get("WANCName"),
            "modo": wan.get("mode"),
            "tipo": wan.get("TransType"),
            "wan_type": wan.get("wantype"),
            "username": username,
            "password": (
                password
                if reveal_password
                else _mask_password(password)
            ),
            "password_hidden": not reveal_password,
            "auth_type": wan.get("AuthType"),
            "trigger": wan.get("ConnTrigger"),
            "vlan": wan.get("VLANID"),
            "mtu": wan.get("MTU"),
            "ip_mode": wan.get("IpMode"),
        })

    return resultado


def _is_pppoe(wan):
    valores = {
        str(wan.get("TransType", "")).lower(),
        str(wan.get("wantype", "")).lower(),
        str(wan.get("linkMode", "")).lower(),
    }

    if (
        wan.get("UserName")
        or wan.get("Password")
        or wan.get("PPPoEUserName")
    ):
        return True

    return any(
        "ppp" in valor
        for valor in valores
    )


def _get_encode_fields(xml):
    try:
        root = ET.fromstring(
            xml
        )
    except ET.ParseError:
        return set()

    encode = root.findtext(
        "encode"
    ) or ""

    return {
        item.strip()
        for item in encode.split(",")
        if item.strip()
    }


def _mask_password(password):
    if not password:
        return ""

    return "•" * min(
        max(len(password), 8),
        24
    )

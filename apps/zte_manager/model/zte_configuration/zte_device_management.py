import random
import string
import xml.etree.ElementTree as ET

from .zte_post import post_menu
from . import zte_security


# =========================================================
# PON / OPTICAL
# =========================================================


def optical_raw(zte):
    """
    Endpoint confirmado no perfil F6600P do zte_tracker e presente no
    dmenu ThinkLua: ponopticalinfo -> optical_info_lua.lua.
    """

    zte.get_view(
        "ponopticalinfo",
        Menu3Location=0
    )

    return zte.get_menu(
        "optical_info_lua.lua"
    )


def optical_status(zte):
    xml = optical_raw(
        zte
    )

    zte._validar_resposta(
        xml
    )

    dados = zte._parse_instances(
        xml
    )

    optical = _first(
        dados,
        "OBJ_PON_OPTICALPARA_ID"
    )

    los = _first(
        dados,
        "OBJ_LOS_INFO_ID"
    )

    onu = _first(
        dados,
        "OBJ_PONONUID_ID"
    )

    reg = _first(
        dados,
        "OBJ_GPONREGSTATUS_ID"
    )

    catv = _first(
        dados,
        "OBJ_PON_CATV_ID"
    )

    uptime = _first(
        dados,
        "OBJ_PON_POWERONTIME_ID"
    )

    return {
        "rx_power_dbm": _number_or_value(
            optical.get("RxPower")
        ),
        "tx_power_dbm": _number_or_value(
            optical.get("TxPower")
        ),
        "temperature_c": _number_or_value(
            optical.get("Temp")
        ),
        "voltage": _number_or_value(
            optical.get("Volt")
        ),
        "current_ma": _number_or_value(
            optical.get("Current")
        ),
        "rf_tx_power": _number_or_value(
            optical.get("RFTxPower")
        ),
        "video_rx_power": _number_or_value(
            optical.get("VideoRxPower")
        ),
        "los": los.get("LosInfo"),
        "onu_id": onu.get("OnuId"),
        "registration_status": reg.get("RegStatus"),
        "catv_enabled": catv.get("CatvEnable") == "1",
        "pon_uptime": _int_or_value(
            uptime.get("PONOnTime")
        ),
    }


# =========================================================
# REBOOT
# =========================================================


def reboot(zte):
    """
    Reproduz o fluxo documentado em zte_tracker/routers/Reboot.md.
    A sessão naturalmente deixa de responder depois que a ONT reinicia.
    """

    zte.get_view(
        "rebootAndReset",
        Menu3Location=0
    )

    resposta = post_menu(
        zte,
        "devmgr_restartmgr_lua.lua",
        [
            ("IF_ACTION", "Restart"),
            ("Btn_restart", ""),
        ]
    )

    return {
        "success": True,
        "message": "Comando de reinicialização enviado à ONT.",
        "response": resposta[:300],
    }


# =========================================================
# CONTA ADMINISTRATIVA
# =========================================================


def account_status(zte):
    """
    Lê as contas que o firmware permite ao usuário autenticado visualizar.
    Senhas nunca são devolvidas por esta função.
    """

    zte.get_view(
        "accountMgr",
        Menu3Location=0
    )

    xml = zte.get_menu(
        "devauth_accountmgr_lua.lua"
    )

    zte._validar_resposta(
        xml
    )

    contas = (
        zte._parse_instances(xml)
        .get(
            "OBJ_USERINFO_ID",
            []
        )
    )

    return [
        {
            "id": conta.get("_InstID"),
            "username": conta.get("Username"),
            "right": conta.get("Right"),
            "enabled": conta.get("Enable") == "1",
            "current": conta.get("Username") == zte.username,
        }
        for conta in contas
    ]


def change_admin_password(
    zte,
    new_password
):
    """
    Troca a senha da conta atualmente usada pelo app.

    O backend devauth_accountmgr_lua.lua declara Password e NewPassword como
    campos criptografados. Portanto usamos AES com chave/IV aleatórios e o
    parâmetro encode=RSA(key+iv), exatamente como o browser.
    """

    new_password = str(
        new_password or ""
    )

    if len(new_password) < 1:
        raise ValueError(
            "A nova senha não pode ficar vazia."
        )

    try:
        new_password.encode(
            "ascii"
        )
    except UnicodeEncodeError as erro:
        raise ValueError(
            "A senha administrativa deve usar caracteres ASCII."
        ) from erro

    zte.get_view(
        "accountMgr",
        Menu3Location=0
    )

    xml = zte.get_menu(
        "devauth_accountmgr_lua.lua"
    )

    zte._validar_resposta(
        xml
    )

    contas = (
        zte._parse_instances(xml)
        .get(
            "OBJ_USERINFO_ID",
            []
        )
    )

    conta = next((
        item
        for item in contas
        if item.get("Username") == zte.username
    ), None)

    if conta is None:
        raise RuntimeError(
            "A conta autenticada não apareceu em accountMgr; "
            "o firmware pode não permitir troca de senha para este perfil."
        )

    crypto_key = "".join(
        random.choices(
            string.digits,
            k=16
        )
    )

    crypto_iv = "".join(
        random.choices(
            string.digits,
            k=16
        )
    )

    current_encrypted = zte_security.aes_encrypt_value(
        zte.password,
        crypto_key,
        crypto_iv
    )

    new_encrypted = zte_security.aes_encrypt_value(
        new_password,
        crypto_key,
        crypto_iv
    )

    public_key = getattr(
        zte,
        "public_key_pem",
        None
    )

    encode = zte_security.rsa_encrypt_text(
        f"{crypto_key}+{crypto_iv}",
        public_key
    )

    # O token pertence à menuView; reabrimos imediatamente antes do POST.
    zte.get_view(
        "accountMgr",
        Menu3Location=0
    )

    resposta = post_menu(
        zte,
        "devauth_accountmgr_lua.lua",
        [
            ("IF_ACTION", "Apply"),
            ("_InstID", conta.get("_InstID", "")),
            ("Right", conta.get("Right", "")),
            ("Enable", conta.get("Enable", "1")),
            ("Username", conta.get("Username", zte.username)),
            ("Password", current_encrypted),
            ("NewPassword", new_encrypted),
            ("Keyword", conta.get("Keyword", "")),
            ("Btn_cancel_AccountManag", ""),
            ("Btn_apply_AccountManag", ""),
            ("encode", encode),
        ]
    )

    zte._validar_resposta(
        resposta
    )

    # O firmware atualiza o hash da sessão ativa quando a conta alterada é a
    # mesma do login. Mantemos também a credencial local sincronizada para
    # futuros relogins automáticos/manuais.
    zte.password = new_password

    return {
        "success": True,
        "username": zte.username,
        "message": "Senha administrativa alterada.",
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


def _number_or_value(value):
    if value in (
        None,
        ""
    ):
        return value

    try:
        return float(
            value
        )
    except (
        TypeError,
        ValueError,
    ):
        return value


def _int_or_value(value):
    if value in (
        None,
        ""
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

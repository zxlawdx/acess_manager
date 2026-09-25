import random
import re
import string
import xml.etree.ElementTree as ET

from .zte_post import post_menu
from . import zte_security


# =========================================================
# SEGURANÇA / MODOS DO FORMULÁRIO ORIGINAL
# =========================================================


ENCRYPTION_TYPE_MAP = {
    "No Security": {
        "BeaconType": "None",
    },
    "WEP-OpenSystem": {
        "BeaconType": "Basic",
        "WEPAuthMode": "None",
    },
    "WEP-ShareKey": {
        "BeaconType": "Basic",
        "WEPAuthMode": "SharedAuthentication",
    },
    "WPA-PSK-TKIP": {
        "BeaconType": "WPA",
        "WPAAuthMode": "PSKAuthentication",
        "WPAEncryptType": "TKIPEncryption",
    },
    "WPA-PSK-AES": {
        "BeaconType": "WPA",
        "WPAAuthMode": "PSKAuthentication",
        "WPAEncryptType": "AESEncryption",
    },
    "WPA-PSK-TKIP/AES": {
        "BeaconType": "WPA",
        "WPAAuthMode": "PSKAuthentication",
        "WPAEncryptType": "TKIPandAESEncryption",
    },
    "WPA2-PSK-AES": {
        "BeaconType": "11i",
        "11iAuthMode": "PSKAuthentication",
        "11iEncryptType": "AESEncryption",
    },
    "WPA2-PSK-TKIP": {
        "BeaconType": "11i",
        "11iAuthMode": "PSKAuthentication",
        "11iEncryptType": "TKIPEncryption",
    },
    "WPA2-PSK-TKIP/AES": {
        "BeaconType": "11i",
        "11iAuthMode": "PSKAuthentication",
        "11iEncryptType": "TKIPandAESEncryption",
    },
    "WPA/WPA2-PSK-TKIP": {
        "BeaconType": "WPAand11i",
        "WPAAuthMode": "PSKAuthentication",
        "11iAuthMode": "PSKAuthentication",
        "WPAEncryptType": "TKIPEncryption",
        "11iEncryptType": "TKIPEncryption",
    },
    "WPA/WPA2-PSK-AES": {
        "BeaconType": "WPAand11i",
        "WPAAuthMode": "PSKAuthentication",
        "11iAuthMode": "PSKAuthentication",
        "WPAEncryptType": "AESEncryption",
        "11iEncryptType": "AESEncryption",
    },
    "WPA/WPA2-PSK-TKIP/AES": {
        "BeaconType": "WPAand11i",
        "WPAAuthMode": "PSKAuthentication",
        "11iAuthMode": "PSKAuthentication",
        "WPAEncryptType": "TKIPandAESEncryption",
        "11iEncryptType": "TKIPandAESEncryption",
    },
    "WPA2-EAP-AES": {
        "BeaconType": "11i",
        "11iAuthMode": "EAPAuthentication",
        "11iEncryptType": "AESEncryption",
    },
    "WPA/WPA2-EAP-TKIP/AES": {
        "BeaconType": "WPAand11i",
        "WPAAuthMode": "EAPAuthentication",
        "11iAuthMode": "EAPAuthentication",
        "WPAEncryptType": "TKIPandAESEncryption",
        "11iEncryptType": "TKIPandAESEncryption",
    },
    "WPA3-OWE": {
        "BeaconType": "WPA3",
        "WPA3AuthMode": "OWEAuthentication",
        "WPA3EncryptType": "AESEncryption",
    },
    "WPA3-SAE": {
        "BeaconType": "WPA3",
        "WPA3AuthMode": "SAEAuthentication",
        "WPA3EncryptType": "AESEncryption",
    },
    "WPA/WPA2/WPA3-PSK/SAE": {
        "BeaconType": "WPAand11iandWPA3",
        "WPAAuthMode": "PSKAuthentication",
        "11iAuthMode": "PSKAuthentication",
        "WPA3AuthMode": "SAEAuthentication",
        "WPAEncryptType": "TKIPandAESEncryption",
        "11iEncryptType": "TKIPandAESEncryption",
        "WPA3EncryptType": "AESEncryption",
    },
    "WPA2/WPA3-SAE": {
        "BeaconType": "11iandWPA3",
        "11iAuthMode": "PSKAuthentication",
        "WPA3AuthMode": "SAEAuthentication",
        "11iEncryptType": "TKIPandAESEncryption",
        "WPA3EncryptType": "AESEncryption",
    },
    "WPA2-PSK-AES/WPA3-SAE-AES": {
        "BeaconType": "11iandWPA3",
        "11iAuthMode": "PSKAuthentication",
        "WPA3AuthMode": "SAEAuthentication",
        "11iEncryptType": "AESEncryption",
        "WPA3EncryptType": "AESEncryption",
    },
    "WPA-EAP-TKIP": {
        "BeaconType": "WPA",
        "WPAAuthMode": "EAPAuthentication",
        "WPAEncryptType": "TKIPEncryption",
    },
}


# =========================================================
# GET
# =========================================================


def wifi_status(zte):
    # O firmware exige que a view seja aberta na mesma sessão antes do menuData.
    zte.get_view(
        "wlanBasic",
        Menu3Location=0
    )

    return zte.get_menu(
        "wlan_wlansssidconf_lua.lua"
    )


def wifi_networks(
    zte,
    reveal_password=False
):
    """
    Retorna os SSIDs com os campos que realmente existem no firmware.

    A senha é mascarada por padrão. Quando reveal_password=True, o valor de
    KeyPassphrase é decodificado usando o _sessionTmpToken da mesma menuView.
    """

    xml = wifi_status(
        zte
    )

    zte._validar_resposta(
        xml
    )

    dados = zte._parse_instances(
        xml
    )

    aps = dados.get(
        "OBJ_WLANAP_ID",
        []
    )

    psks = dados.get(
        "OBJ_WLANPSK_ID",
        []
    )

    encode_fields = _get_encode_fields(
        xml
    )

    psk_by_ap = _map_psk_by_ap(
        psks
    )

    token = getattr(
        zte,
        "session_tmp_token",
        None
    )

    resultado = []

    for ap in aps:
        ap_id = ap.get(
            "_InstID",
            ""
        )

        radio = ap.get(
            "WLANViewName"
        )

        banda = {
            "DEV.WIFI.RD1": "2.4GHz",
            "DEV.WIFI.RD2": "5GHz",
        }.get(
            radio,
            radio
        )

        psk = psk_by_ap.get(
            ap_id,
            {}
        )

        password = psk.get(
            "KeyPassphrase",
            ""
        )

        if (
            password
            and token
            and "KeyPassphrase" in encode_fields
        ):
            password = zte_security.aes_decrypt_value(
                password,
                token,
                token[::-1]
            )

        resultado.append({
            "id": ap_id,
            "ssid": ap.get("ESSID"),
            "alias": ap.get("Alias"),
            "banda": banda,
            "radio": radio,
            "ativo": ap.get("Enable") == "1",
            "oculto": ap.get("ESSIDHideEnable") == "1",
            "broadcast": ap.get("ESSIDHideEnable") != "1",
            "max_clientes": _int_or_value(
                ap.get("MaxUserNum")
            ),
            "isolamento": ap.get("VapIsolationEnable") == "1",
            "seguranca": _resolve_encryption_type(
                ap
            ),
            "password": (
                password
                if reveal_password
                else _mask_password(password)
            ),
            "password_hidden": not reveal_password,
            "beacon_type": ap.get("BeaconType"),
            "wpa_auth": ap.get("WPAAuthMode"),
            "wpa2_auth": ap.get("11iAuthMode"),
            "wpa3_auth": ap.get("WPA3AuthMode"),
            "raw": {
                "psk_id": psk.get("_InstID"),
                "pmf": ap.get("PMFEnable"),
                "wpa_group_rekey": ap.get("WPAGroupRekey"),
            },
        })

    return resultado


# =========================================================
# WRITE - SSID
# =========================================================


def set_ssid_config(
    zte,
    ssid_id,
    config,
    *,
    captured_f6201b=False,
):
    """
    Atualiza um único SSID preservando o restante da configuração atual.

    Strategy usada aqui: read-modify-write.
    Em vez de inventar os campos de segurança, lemos AP/PSK/WEP do próprio
    equipamento, alteramos apenas o que foi solicitado e reproduzimos a ordem
    do formulário wlan_wlansssidconf_t.lp.
    """

    if not ssid_id:
        raise ValueError(
            "Informe o ID do SSID."
        )

    xml = wifi_status(
        zte
    )

    zte._validar_resposta(
        xml
    )

    dados = zte._parse_instances(
        xml
    )

    aps = dados.get(
        "OBJ_WLANAP_ID",
        []
    )

    ap = next((
        item
        for item in aps
        if item.get("_InstID") == ssid_id
    ), None)

    if ap is None:
        raise ValueError(
            f"SSID {ssid_id} não encontrado."
        )

    psks = dados.get(
        "OBJ_WLANPSK_ID",
        []
    )

    weps = dados.get(
        "OBJ_WLANWEPKEY_ID",
        []
    )

    psk = _map_psk_by_ap(
        psks
    ).get(
        ssid_id,
        {}
    )

    wep_list = _weps_for_ap(
        weps,
        ssid_id
    )

    token = getattr(
        zte,
        "session_tmp_token",
        None
    )

    if not token:
        raise RuntimeError(
            "Não encontrei _sessionTmpToken para configurar o SSID."
        )

    encode_fields = _get_encode_fields(
        xml
    )

    atual = dict(
        ap
    )

    # ---------------------------------------------------------
    # Aplica somente os overrides pedidos pela API.
    # ---------------------------------------------------------

    if "enabled" in config:
        atual["Enable"] = (
            "1"
            if config["enabled"]
            else "0"
        )

    if "ssid" in config:
        ssid = str(
            config["ssid"]
        ).strip()

        _validate_ssid_name(
            ssid
        )

        atual["ESSID"] = ssid

    if "broadcast" in config:
        atual["ESSIDHideEnable"] = (
            "0"
            if config["broadcast"]
            else "1"
        )

    if "hidden" in config:
        atual["ESSIDHideEnable"] = (
            "1"
            if config["hidden"]
            else "0"
        )

    if "isolation" in config:
        atual["VapIsolationEnable"] = (
            "1"
            if config["isolation"]
            else "0"
        )

    if "max_clients" in config:
        max_clients = int(
            config["max_clients"]
        )

        if not 1 <= max_clients <= 64:
            raise ValueError(
                "max_clients deve ficar entre 1 e 64."
            )

        atual["MaxUserNum"] = str(
            max_clients
        )

    if config.get("encryption"):
        encryption = str(
            config["encryption"]
        )

        if encryption not in ENCRYPTION_TYPE_MAP:
            raise ValueError(
                f"Modo de segurança não suportado: {encryption}"
            )

        atual.update(
            ENCRYPTION_TYPE_MAP[
                encryption
            ]
        )

    current_password = psk.get(
        "KeyPassphrase",
        ""
    )

    if (
        current_password
        and "KeyPassphrase" in encode_fields
    ):
        current_password = zte_security.aes_decrypt_value(
            current_password,
            token,
            token[::-1]
        )

    new_password = config.get(
        "password",
        current_password
    )

    encryption_type = _resolve_encryption_type(
        atual
    )

    is_psk = _uses_psk(
        atual
    )

    is_wep = atual.get(
        "BeaconType"
    ) == "Basic"

    if is_psk:
        _validate_wifi_password(
            new_password
        )

    # ---------------------------------------------------------
    # Campos secretos são AES. A chave+IV do POST vai no campo
    # encode, criptografado pela chave RSA da própria ONT.
    # ---------------------------------------------------------

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

    encrypted_password = (
        zte_security.aes_encrypt_value(
            new_password,
            crypto_key,
            crypto_iv
        )
        if is_psk and new_password
        else ""
    )

    encrypted_weps = []

    for wep in wep_list[:4]:
        value = wep.get(
            "WEPKey",
            ""
        )

        if (
            value
            and "WEPKey" in encode_fields
        ):
            value = zte_security.aes_decrypt_value(
                value,
                token,
                token[::-1]
            )

        encrypted_weps.append(
            zte_security.aes_encrypt_value(
                value,
                crypto_key,
                crypto_iv
            )
            if value
            else ""
        )

    while len(encrypted_weps) < 4:
        encrypted_weps.append(
            ""
        )

    psk_id = (
        psk.get("_InstID")
        or f"{ssid_id}.PSK1"
    )

    wep_ids = [
        item.get(
            "_InstID",
            f"{ssid_id}.WEP{index + 1}"
        )
        for index, item in enumerate(
            wep_list[:4]
        )
    ]

    while len(wep_ids) < 4:
        wep_ids.append(
            f"{ssid_id}.WEP{len(wep_ids) + 1}"
        )

    campos = [
        ("IF_ACTION", "Apply"),
        ("_InstID", ssid_id),
        ("_WEPCONIG", "Y" if is_wep else "N"),
        ("_PSKCONIG", "Y" if is_psk else "N"),
        ("BeaconType", atual.get("BeaconType", "")),
        ("WEPAuthMode", atual.get("WEPAuthMode", "")),
        ("WPAAuthMode", atual.get("WPAAuthMode", "")),
        ("11iAuthMode", atual.get("11iAuthMode", "")),
        ("WPAEncryptType", atual.get("WPAEncryptType", "")),
        ("11iEncryptType", atual.get("11iEncryptType", "")),
        ("WPA3AuthMode", atual.get("WPA3AuthMode", "")),
        ("WPA3EncryptType", atual.get("WPA3EncryptType", "")),
        ("_InstID_WEP0", wep_ids[0]),
        ("_InstID_WEP1", wep_ids[1]),
        ("_InstID_WEP2", wep_ids[2]),
        ("_InstID_WEP3", wep_ids[3]),
        ("_InstID_PSK", psk_id),
        ("MasterAuthServerIp", atual.get("MasterAuthServerIp", "")),
        ("_InstID_GUEST", atual.get("_InstID_GUEST", "")),
        ("_GUEST", atual.get("_GUEST", "N")),
        ("GuestWifi", atual.get("GuestWifi", "")),
        ("Enable", atual.get("Enable", "1")),
        ("ESSID", atual.get("ESSID", "")),
        ("ESSIDHideEnable", atual.get("ESSIDHideEnable", "0")),
        ("PMFEnable", atual.get("PMFEnable", "0")),
        ("EncryptionType", encryption_type),
        ("KeyPassphrase", encrypted_password),
        ("WEPKeyIndex", atual.get("WEPKeyIndex", "1")),
        ("ShowWEPKey", ""),
        ("WEPKey00", encrypted_weps[0]),
        ("WEPKey01", encrypted_weps[1]),
        ("WEPKey02", encrypted_weps[2]),
        ("WEPKey03", encrypted_weps[3]),
        ("VapIsolationEnable", atual.get("VapIsolationEnable", "0")),
        ("MaxUserNum", atual.get("MaxUserNum", "32")),
        ("Btn_cancel_WLANSSIDConf", ""),
        ("Btn_apply_WLANSSIDConf", ""),
    ]

    if (
        encrypted_password
        or any(encrypted_weps)
    ):
        public_key = getattr(
            zte,
            "public_key_pem",
            None
        )

        campos.append((
            "encode",
            zte_security.rsa_encrypt_text(
                f"{crypto_key}+{crypto_iv}",
                public_key
            )
        ))

    if captured_f6201b:
        # Corpo reproduzido do Apply real (F6201B V9.3.10P7N7).
        # Campos extras do F6600P poderiam alterar funções não solicitadas.
        # Falha fechada se os campos do manifesto não puderem ser montados.
        from apps.zte_manager.services.f6201b_evidence import SSID_APPLY_FIELDS
        fields = dict(campos)
        fields["BackupAuthServerIp"] = atual.get("BackupAuthServerIp", "")
        fields["MasterAcctServerIp"] = atual.get("MasterAcctServerIp", "")
        fields["BackupAcctServerIp"] = atual.get("BackupAcctServerIp", "")
        fields["_InstID_GUEST"] = atual.get("_InstID_GUEST", "")
        campos = [(name, fields[name]) for name in SSID_APPLY_FIELDS
                  if name != "_sessionTOKEN"]
        if len(campos) != len(SSID_APPLY_FIELDS) - 1:
            raise RuntimeError("O payload de SSID não corresponde à captura.")

    # Reabre a view imediatamente antes do POST. O GET acima é útil para
    # montar o payload, mas outras chamadas não podem trocar o contexto.
    zte.get_view(
        "wlanBasic",
        Menu3Location=0
    )

    resposta = post_menu(
        zte,
        "wlan_wlansssidconf_lua.lua",
        campos
    )

    zte._validar_resposta(
        resposta
    )

    # Verificação pós-write: se o equipamento disser SUCC mas não refletir a
    # alteração, a API não devolve um falso positivo.
    verificado = _verify_ssid(
        zte,
        ssid_id,
        config
    )

    return {
        "success": True,
        "id": ssid_id,
        "verified": verificado,
    }


# =========================================================
# HELPERS
# =========================================================


def _get_encode_fields(xml_text):
    try:
        root = ET.fromstring(
            xml_text
        )
    except ET.ParseError:
        return set()

    # F6201B retorna <encode> separado para AP, WEP e PSK.
    # Ler somente o primeiro perde KeyPassphrase e impede preservar a senha.
    return {
        item.strip()
        for node in root.findall("encode")
        for item in (node.text or "").split(",")
        if item.strip()
    }


def _map_psk_by_ap(psks):
    resultado = {}

    for psk in psks:
        inst_id = psk.get(
            "_InstID",
            ""
        )

        match = re.search(
            r"^(DEV\.WIFI\.AP\d+)\.PSK",
            inst_id
        )

        if match:
            resultado[
                match.group(1)
            ] = psk

    return resultado


def _weps_for_ap(
    weps,
    ap_id
):
    prefix = f"{ap_id}.WEP"

    return sorted(
        [
            item
            for item in weps
            if item.get(
                "_InstID",
                ""
            ).startswith(prefix)
        ],
        key=lambda item: item.get(
            "_InstID",
            ""
        )
    )


def _uses_psk(ap):
    for campo in (
        "WPAAuthMode",
        "11iAuthMode",
        "WPA3AuthMode",
    ):
        valor = ap.get(
            campo,
            ""
        )

        if (
            "PSK" in valor
            or "SAE" in valor
        ):
            return True

    return False


def _resolve_encryption_type(ap):
    for nome, campos in ENCRYPTION_TYPE_MAP.items():
        if all(
            ap.get(campo) == valor
            for campo, valor in campos.items()
        ):
            return nome

    if str(
        ap.get("BeaconType", "")
    ).lower() == "none":
        return "No Security"

    return "WPA2-PSK-AES"


def _mask_password(password):
    if not password:
        return ""

    return "•" * min(
        max(len(password), 8),
        24
    )


def _validate_ssid_name(ssid):
    if not 1 <= len(ssid) <= 32:
        raise ValueError(
            "O nome da rede deve ter entre 1 e 32 caracteres."
        )

    try:
        ssid.encode(
            "ascii"
        )
    except UnicodeEncodeError as erro:
        raise ValueError(
            "O firmware atual exige SSID em caracteres ASCII."
        ) from erro


def _validate_wifi_password(password):
    if password is None:
        raise ValueError(
            "A rede usa PSK/SAE e precisa de senha."
        )

    password = str(
        password
    )

    if not 8 <= len(password) <= 63:
        raise ValueError(
            "A senha Wi-Fi deve ter entre 8 e 63 caracteres."
        )

    try:
        password.encode(
            "ascii"
        )
    except UnicodeEncodeError as erro:
        raise ValueError(
            "A senha Wi-Fi deve usar caracteres ASCII."
        ) from erro


def _verify_ssid(
    zte,
    ssid_id,
    config
):
    redes = wifi_networks(
        zte,
        reveal_password=(
            "password" in config
        )
    )

    atual = next((
        item
        for item in redes
        if item.get("id") == ssid_id
    ), None)

    if atual is None:
        raise RuntimeError(
            "A ONT aceitou o POST, mas o SSID não apareceu na releitura."
        )

    checks = {
        "enabled": "ativo",
        "ssid": "ssid",
        "broadcast": "broadcast",
        "isolation": "isolamento",
        "max_clients": "max_clientes",
        "encryption": "seguranca",
        "password": "password",
    }

    for pedido, retorno in checks.items():
        if pedido not in config:
            continue

        esperado = config[pedido]
        obtido = atual.get(
            retorno
        )

        if pedido == "max_clients":
            esperado = int(
                esperado
            )

        if obtido != esperado:
            if pedido == "password":
                # Nunca devolver PSK antiga/nova em exceções, logs ou toast.
                raise RuntimeError(
                    "A ONT respondeu SUCC, mas a alteração da senha Wi-Fi "
                    "não foi confirmada pela releitura segura."
                )
            raise RuntimeError(
                f"A ONT respondeu SUCC, mas {pedido} não foi confirmado "
                f"na releitura ({obtido!r} != {esperado!r})."
            )

    return True


def _int_or_value(valor):
    if valor in (
        None,
        ""
    ):
        return valor

    try:
        return int(
            valor
        )
    except (
        TypeError,
        ValueError,
    ):
        return valor

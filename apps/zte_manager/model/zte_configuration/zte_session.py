import hashlib
import time
import xml.etree.ElementTree as ET

from . import zte_security


def login(zte):
    print("[1] Obtendo session token...")

    url = f"{zte.base_url}/?_type=loginData&_tag=login_entry"
    resposta = zte.session.get(url, timeout=10)
    print("HTTP:", resposta.status_code)
    resposta.raise_for_status()

    try:
        dados = resposta.json()
    except ValueError:
        print("\nResposta inesperada:")
        print(resposta.text[:1000])
        return False

    zte.session_token = dados.get("sess_token")

    if not zte.session_token:
        print("Não encontrei sess_token.")
        print(dados)
        return False

    print("Session token recebido.")
    print("\n[2] Obtendo challenge de login...")

    url = (
        f"{zte.base_url}/?_type=loginData"
        f"&_tag=login_token"
        f"&_={int(time.time() * 1000)}"
    )

    resposta = zte.session.get(url, timeout=10)
    print("HTTP:", resposta.status_code)
    resposta.raise_for_status()

    try:
        root = ET.fromstring(resposta.text)
        login_token = (root.text or "").strip()
    except ET.ParseError:
        print("Não consegui interpretar login_token.")
        print(resposta.text[:1000])
        return False

    if not login_token:
        print("Challenge vazio.")
        return False

    print("Challenge recebido.")
    print("\n[3] Calculando hash da senha...")

    senha_hash = hashlib.sha256(
        (zte.password + login_token).encode("utf-8")
    ).hexdigest()

    print("Hash calculado.")
    print("\n[4] Fazendo login...")

    url = f"{zte.base_url}/?_type=loginData&_tag=login_entry"
    payload = {
        "action": "login",
        "Username": zte.username,
        "Password": senha_hash,
        "_sessionTOKEN": zte.session_token,
    }

    resposta = zte.session.post(url, data=payload, timeout=10)
    print("HTTP:", resposta.status_code)
    resposta.raise_for_status()

    try:
        resultado = resposta.json()
    except ValueError:
        print("Resposta não é JSON:")
        print(resposta.text[:1000])
        return False

    novo_token = resultado.get("sess_token")
    if novo_token:
        zte.session_token = novo_token
    if resultado.get("login_need_refresh"):
        print("\n[5] Atualizando sessão após login...")

        resposta_refresh = zte.session.get(
            zte.base_url + "/",
            timeout=10,
        )

        print(
            "Refresh HTTP:",
            resposta_refresh.status_code
        )

        resposta_refresh.raise_for_status()

        # O Check dos POSTs não nasce no menuData. Ele é implementado pelo
        # JavaScript comum carregado na página principal após o login.
        #
        # Antes esta resposta era descartada e, no P6N34, isso fazia a API
        # chegar ao POST sem saber que IntegCheck estava ativo ou sem a chave
        # RSA usada por asyEncode(). Resultado: o equipamento aceitava GET,
        # mas devolvia HTTP 400 para qualquer POST de configuração.
        contexto = zte_security.update_page_security(
            zte,
            resposta_refresh.text,
            source="login-root"
        )

        print(
            "Segurança POST:",
            {
                "integrity_check": contexto["integrity_check"],
                "public_key_found": contexto["public_key_found"],
                "session_tmp_token_found": bool(
                    contexto["session_tmp_token"]
                ),
            }
        )

    # Jamais registrar token/cookie/credenciais em logs compartilhados.
    print("\nResposta do login:")
    print({
        "login_need_refresh": bool(resultado.get("login_need_refresh")),
        "lockingTime": resultado.get("lockingTime"),
        "loginErrMsg": resultado.get("loginErrMsg") or "",
        "session_token_received": bool(zte.session_token),
    })

    if resultado.get("loginErrMsg"):
        print("\nErro de login:")
        print(resultado["loginErrMsg"])
        return False

    print("\n[OK] Login aparentemente realizado.")
    return True


def logout(zte):
    if not zte.session_token:
        return

    url = f"{zte.base_url}/?_type=loginData&_tag=logout_entry"

    try:
        resposta = zte.session.post(
            url,
            data={
                "IF_LogOff": "1",
                "_sessionTOKEN": zte.session_token,
            },
            timeout=5,
        )
        print("\nLogout HTTP:", resposta.status_code)
    except Exception as erro:
        print("Erro no logout:", erro)
    finally:
        zte.session.close()

from . import zte_security


# =========================================================
# POST SEGURO DO FIRMWARE ZTE
# =========================================================


def post_menu(
    zte,
    tag,
    campos,
    **extras
):
    """
    Replica o dataPost() usado pela interface original.

    Regras importantes:
    - a ordem dos campos é preservada;
    - _sessionTOKEN entra por último;
    - o Check é calculado em cima exatamente do body que será enviado;
    - enviamos a string pronta para requests não reserializar o formulário.
    """

    token = getattr(
        zte,
        "session_tmp_token",
        None
    )

    if not token:
        raise RuntimeError(
            "Não encontrei _sessionTmpToken. Abra a menuView antes do POST."
        )

    campos_finais = list(
        campos
    )

    campos_finais.append((
        "_sessionTOKEN",
        token
    ))

    body = zte_security.build_form_body(
        campos_finais
    )

    headers = {
        "Content-Type": (
            "application/x-www-form-urlencoded; charset=UTF-8"
        )
    }

    public_key = getattr(
        zte,
        "public_key_pem",
        None
    )

    integrity_check = getattr(
        zte,
        "integrity_check",
        None
    )

    # Quando IntegCheck está ativo o browser cria:
    # SHA256(body) -> RSA PKCS#1 v1.5 -> Base64.
    #
    # No F6600P P6N34 a configuração pode continuar respondendo aos GETs mesmo
    # quando um POST sem Check será rejeitado com HTTP 400. Por isso não
    # fazemos fallback silencioso para um POST sem assinatura.
    if integrity_check is True:
        if not public_key:
            raise RuntimeError(
                "IntegCheck está ativo, mas a chave RSA de asyEncode() "
                "não foi encontrada na página principal do firmware."
            )

        headers["Check"] = (
            zte_security.compute_check_header(
                body,
                public_key
            )
        )

    elif public_key:
        # Alguns builds não expõem IntegCheck de forma simples no HTML, mas
        # expõem a chave de asyEncode(). Nesse caso assinamos do mesmo jeito.
        headers["Check"] = (
            zte_security.compute_check_header(
                body,
                public_key
            )
        )

    params = {
        "_type": "menuData",
        "_tag": tag,
    }

    params.update(
        extras
    )

    print(f"\nPOST -> {tag}")

    resposta = zte.session.post(
        zte.base_url + "/",
        params=params,
        data=body,
        headers=headers,
        timeout=60,
    )

    print("URL:", resposta.url)
    print("HTTP:", resposta.status_code)
    print(
        "POST security:",
        {
            "tmp_token": bool(token),
            "check": "Check" in headers,
            "rsa": bool(public_key),
            "integ_check": integrity_check,
            "security_source": getattr(
                zte,
                "security_source",
                None
            ),
        }
    )

    if resposta.status_code >= 400:
        resposta_curta = (
            resposta.text
            or resposta.reason
            or "sem corpo de resposta"
        )[:1200]

        print(
            "Resposta de erro da ONT:",
            resposta_curta
        )

        raise RuntimeError(
            f"A ONT recusou o POST {tag} com HTTP "
            f"{resposta.status_code}: {resposta_curta}"
        )

    zte._validar_resposta(
        resposta.text
    )

    return resposta.text

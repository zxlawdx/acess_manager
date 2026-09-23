import time

from . import zte_security


def get_view(zte, tag, **extras):
    params = {
        "_type": "menuView",
        "_tag": tag,
        "_": int(time.time() * 1000),
    }

    params.update(extras)

    print(f"\nVIEW -> {tag}")

    resposta = zte.session.get(
        zte.base_url + "/",
        params=params,
        timeout=10,
    )

    print("URL:", resposta.url)
    print("HTTP:", resposta.status_code)

    resposta.raise_for_status()

    # O mesmo HTML que prepara o contexto da página contém o token temporário
    # usado pelo POST e, em vários firmwares, a chave pública do header Check.
    contexto = zte_security.update_page_security(
        zte,
        resposta.text,
        source=f"menuView:{tag}"
    )

    print(
        "Security:",
        {
            "tmp_token": bool(
                contexto["session_tmp_token"]
            ),
            "rsa": contexto["public_key_found"],
            "integ_check": contexto["integrity_check"],
        }
    )

    return resposta.text


def get_menu(zte, tag, **extras):
    params = {
        "_type": "menuData",
        "_tag": tag,
        "_": int(time.time() * 1000),
    }

    params.update(extras)

    print(f"\nGET -> {tag}")

    resposta = zte.session.get(
        zte.base_url + "/",
        params=params,
        timeout=10,
    )

    print("URL:", resposta.url)
    print("HTTP:", resposta.status_code)

    resposta.raise_for_status()

    return resposta.text

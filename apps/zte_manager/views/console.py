from vela.template_engine.engine import render_template


def console_view(params: dict) -> str:
    """
    Renderiza a SPA do ZTE Automatic dentro do shell do Vela.

    A navegação entre Dashboard/Wi-Fi/WAN/etc continua no JavaScript da
    própria aplicação. O Vela fica responsável pela janela, pelo shell,
    estáticos e API local.
    """
    return render_template(
        "apps/zte_manager/templates/index.html",
        context={
            "app_name": "ZTE Automatic",
        },
        router=params["router"],
    )

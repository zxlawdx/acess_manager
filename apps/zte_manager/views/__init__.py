from apps.zte_manager.views.console import console_view


def register_routes(router):
    router.add(
        "/",
        console_view,
        name="zte_console",
        title="ZTE Automatic",
        icon="",
        layout="blank",
        show_in_sidebar=False,
    )

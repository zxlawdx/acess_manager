"""
Boot da aplicação Vela.
"""

from vela.core.app import VelaApp

from apps.zte_manager.bridge import ZTEBridge


INSTALLED_APPS = [
    "apps.zte_manager",
]


def run():
    app = VelaApp(
        settings_module="config.settings",
        bridge_class=ZTEBridge,
    )

    for app_name in INSTALLED_APPS:
        app.register_app(
            app_name
        )

    app.run()

"""
Configuração do ZTE Automatic no Vela Framework.
"""

APP_TITLE = "ZTE Automatic"
ENTRY_ROUTE = "/"

WINDOW_WIDTH = 1480
WINDOW_HEIGHT = 920

# A interface já possui sidebar/topbar próprios. Usamos o shell Vela apenas
# como host da janela, bridge, roteamento e servidor HTTP local.
LAYOUT = {
    "sidebar": False,
    "topbar": False,
    "theme": "dark",
}

# Em produção deixamos DevTools fechado. Para desenvolvimento basta trocar
# para True e executar `python manage.py runapp` novamente.
DEBUG = False

API = {
    "enabled": True,
    "host": "127.0.0.1",
    "port": 8765,
    "auto_port": True
}

SHELL_MODE = "http"
STATIC_ROOT = "staticfiles"

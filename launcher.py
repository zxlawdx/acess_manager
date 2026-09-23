"""
ZTE Automatic - Launcher do executável.

No desenvolvimento:
    python manage.py runapp

No executável:
    launcher.py -> config.wsgi.run()
"""

import os
import sys
from pathlib import Path


# ---------------------------------------------------------
# Diretório da aplicação
# ---------------------------------------------------------
#
# O Vela resolve templates/staticfiles a partir do diretório
# de trabalho. Em um bundle PyInstaller --onedir, os arquivos
# adicionados com --add-data ficam em sys._MEIPASS/_internal.
# Por isso o executável precisa trabalhar a partir dali.

if getattr(sys, "frozen", False):
    BASE_DIR = Path(
        getattr(
            sys,
            "_MEIPASS",
            Path(sys.executable).parent,
        )
    ).resolve()

    os.chdir(
        BASE_DIR
    )

else:
    BASE_DIR = Path(
        __file__
    ).resolve().parent


sys.path.insert(
    0,
    str(BASE_DIR)
)


# ---------------------------------------------------------
# Backend gráfico
# ---------------------------------------------------------
#
# Windows:
#   usa PyQt6/QtWebEngine via qtpy. O engine mais novo oferece
#   melhor compatibilidade com CSS/JavaScript moderno.
#
# Linux:
#   deixa o pywebview selecionar GTK/WebKit, aproveitando as
#   bibliotecas do sistema instaladas pelo workflow.

if sys.platform == "win32":

    os.environ.setdefault(
        "PYWEBVIEW_GUI",
        "qt"
    )

    # qtpy/pywebview suportam Qt 6. Forçamos PyQt6 para evitar que
    # uma instalação residual de PyQt5 seja escolhida por engano.
    os.environ.setdefault(
        "QT_API",
        "pyqt6"
    )

    try:
        import webview

        _original_start = webview.start


        def start_qt(
            *args,
            **kwargs
        ):
            kwargs.pop(
                "gui",
                None
            )

            kwargs["debug"] = False

            return _original_start(
                *args,
                gui="qt",
                **kwargs
            )


        webview.start = start_qt

    except Exception as exc:
        print(
            "[ZTE Automatic] "
            f"Não foi possível configurar Qt: {exc}",
            file=sys.stderr,
        )


# ---------------------------------------------------------
# Smoke test do bundle
# ---------------------------------------------------------
#
# O GitHub Actions executa o binário com --self-test depois do
# PyInstaller. Isso detecta dependências ausentes no bundle antes
# de publicar a Release, sem abrir a interface gráfica.

def _bundle_self_test():
    import platformdirs  # noqa: F401
    import pydantic  # noqa: F401
    import pydantic_core  # noqa: F401
    import cryptography  # noqa: F401
    import vela  # noqa: F401
    import apps.zte_manager.api  # noqa: F401

    print(
        "ZTEAutomatic bundle self-test: OK"
    )


if (
    __name__ == "__main__"
    and "--self-test" in sys.argv
):
    _bundle_self_test()
    raise SystemExit(0)


# ---------------------------------------------------------
# Imports explícitos
# ---------------------------------------------------------
#
# O Vela registra apps e APIs com importlib. Esses imports
# explícitos ajudam o PyInstaller a identificar o bootstrap
# principal, enquanto o build também usa --collect-submodules
# para os módulos dinâmicos.

import config.settings  # noqa: F401
import config.wsgi      # noqa: F401

from config.wsgi import run


if __name__ == "__main__":
    run()

"""
Launcher Windows para o build do ZTE Automatic.

Força Qt/QtWebEngine no executável, seguindo o padrão recomendado pelo Vela.
"""

import os
import sys
from pathlib import Path


os.environ["PYWEBVIEW_GUI"] = "qt"

from PyQt5.QtWidgets import QApplication  # noqa: F401
from PyQt5.QtWebEngineWidgets import QWebEngineView  # noqa: F401

import webview
import webview.platforms.qt  # noqa: F401


webview.settings["OPEN_DEVTOOLS_IN_DEBUG"] = False

_original_start = webview.start


def start_qt(*args, **kwargs):
    kwargs["debug"] = False
    kwargs.pop(
        "gui",
        None
    )

    return _original_start(
        *args,
        gui="qt",
        **kwargs
    )


webview.start = start_qt

BASE_DIR = Path(
    __file__
).resolve().parent

sys.path.insert(
    0,
    str(BASE_DIR)
)

from config.wsgi import run


if __name__ == "__main__":
    run()

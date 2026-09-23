import os
import sys
from pathlib import Path


def project_root() -> Path:
    """Raiz do projeto durante desenvolvimento."""
    return Path(
        __file__
    ).resolve().parents[2]


def data_dir() -> Path:
    """
    Diretório persistente da aplicação.

    Desenvolvimento:
        <repo>/data

    Executável Windows:
        %LOCALAPPDATA%/ZTEAutomatic

    O caminho pode ser sobrescrito com ZTE_AUTOMATIC_DATA_DIR, útil para uma
    instalação portátil em laboratório ou em testes automatizados.
    """
    custom = os.getenv(
        "ZTE_AUTOMATIC_DATA_DIR"
    )

    if custom:
        path = Path(
            custom
        ).expanduser()

    elif getattr(
        sys,
        "frozen",
        False
    ):
        if sys.platform == "win32":
            base = Path(
                os.getenv(
                    "LOCALAPPDATA",
                    Path.home()
                )
            )

            path = base / "ZTEAutomatic"

        else:
            path = (
                Path.home()
                / ".local"
                / "share"
                / "zte-automatic"
            )

    else:
        path = project_root() / "data"

    path.mkdir(
        parents=True,
        exist_ok=True
    )

    return path

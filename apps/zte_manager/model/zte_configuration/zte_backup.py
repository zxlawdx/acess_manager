from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path

from apps.zte_manager.runtime import data_dir

from .zte_post import post_menu


def export_user_configuration(
    zte,
    *,
    device: dict | None = None,
) -> dict:
    """
    Exporta a configuração usando o mesmo fluxo usrCfgMgr da UI oficial.

    A restauração não é automatizada: importar um arquivo de outro firmware
    pode inutilizar WAN/ACS. O backup fica local para auditoria/rollback manual.
    """
    zte.get_view(
        "usrCfgMgr",
        Menu3Location=0,
    )

    # A interface primeiro pede permissão ao gate de upload/download.
    permission = post_menu(
        zte,
        "updownload_prevent_ctl.lua",
        [
            ("IF_ACTION", "updownload"),
            (
                "sessToken",
                zte.session_token or ""
            ),
        ],
    )

    zte._validar_resposta(
        permission
    )

    response = zte.session.post(
        zte.base_url + "/",
        params={
            "_type": "menuData",
            "_tag": "do_download_usercfg.lua",
        },
        data={
            "config": "",
            "TOKEN_DOWNLOAD": (
                zte.session_token or ""
            ),
        },
        timeout=60,
    )

    response.raise_for_status()

    if not response.content:
        raise RuntimeError(
            "A ONT respondeu ao backup sem conteúdo."
        )

    # Alguns firmwares devolvem HTTP 200 com a página de login quando o
    # download token expira. Nunca salvar esse HTML como backup válido.
    head = response.content[:1024].lstrip().lower()
    content_type = response.headers.get("Content-Type", "").lower()

    if (
        head.startswith((b"<!doctype html", b"<html"))
        or (
            "text/html" in content_type
            and (
                b"<html" in head
                or b"<form" in head
                or b"login" in head
            )
        )
    ):
        raise RuntimeError(
            "A ONT retornou uma página HTML no lugar do backup. "
            "A sessão pode ter expirado ou o firmware F670L "
            "pode exigir um fluxo de download diferente. "
            "Reconecte e verifique o endpoint antes de tentar novamente."
        )

    info = device or {}
    identity = (
        info.get("serial")
        or info.get("modelo")
        or "zte"
    )

    safe_identity = re.sub(
        r"[^A-Za-z0-9_.-]+",
        "_",
        str(identity),
    ).strip("_") or "zte"

    backup_dir = (
        data_dir()
        / "backups"
    )
    backup_dir.mkdir(
        parents=True,
        exist_ok=True,
    )

    suffix = ".bin"
    disposition = response.headers.get(
        "Content-Disposition",
        "",
    )

    match = re.search(
        r'filename="?([^";]+)',
        disposition,
        flags=re.IGNORECASE,
    )

    if match:
        original = Path(
            match.group(1)
        ).name
        suffix = (
            Path(original).suffix
            or suffix
        )

    filename = (
        f"{safe_identity}-"
        f"{datetime.now().strftime('%Y%m%d-%H%M%S')}"
        f"{suffix}"
    )

    path = backup_dir / filename
    path.write_bytes(
        response.content
    )

    return {
        "success": True,
        "path": str(path),
        "filename": filename,
        "size": len(response.content),
        "content_type": response.headers.get(
            "Content-Type"
        ),
    }

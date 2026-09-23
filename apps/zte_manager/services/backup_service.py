from __future__ import annotations

import hashlib
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any

from apps.zte_manager.repositories.management_repository import (
    ManagementRepository,
    management_repository,
)


_SECRET_MARKERS = (
    "password",
    "passwd",
    "passphrase",
    "secret",
    "psk",
    "wepkey",
    "privatekey",
    "credential",
)


def _is_secret(path: str) -> bool:
    lower = path.lower()

    return any(
        marker in lower
        for marker in _SECRET_MARKERS
    )


def _hash(data: bytes) -> str:
    return hashlib.sha256(
        data
    ).hexdigest()


def _flatten_xml(
    node: ET.Element,
    path: str = "",
    result: dict[str, str] | None = None,
) -> dict[str, str]:
    result = result or {}

    current = (
        f"{path}.{node.tag}"
        if path
        else node.tag
    )

    if node.attrib:
        for key, value in sorted(
            node.attrib.items()
        ):
            attr_path = (
                f"{current}[@{key}]"
            )
            result[
                attr_path
            ] = (
                "••••••••"
                if _is_secret(
                    attr_path
                )
                else value
            )

    children = list(
        node
    )

    text = (
        node.text
        or ""
    ).strip()

    if text and not children:
        result[current] = (
            "••••••••"
            if _is_secret(
                current
            )
            else text
        )

    counts: dict[str, int] = {}

    for child in children:
        index = counts.get(
            child.tag,
            0,
        )
        counts[
            child.tag
        ] = index + 1

        _flatten_xml(
            child,
            (
                f"{current}[{index}]"
            ),
            result,
        )

    return result


class BackupCompareService:
    def __init__(
        self,
        repository: ManagementRepository = management_repository,
    ):
        self.repository = repository

    def compare(
        self,
        left_id: int,
        right_id: int,
    ) -> dict[str, Any]:
        backups = (
            self.repository
            .list_backups()
        )

        left = next((
            item
            for item in backups
            if int(
                item["id"]
            ) == int(
                left_id
            )
        ), None)

        right = next((
            item
            for item in backups
            if int(
                item["id"]
            ) == int(
                right_id
            )
        ), None)

        if left is None or right is None:
            raise ValueError(
                "Um dos backups não foi encontrado."
            )

        left_path = Path(
            left[
                "path"
            ]
        )
        right_path = Path(
            right[
                "path"
            ]
        )

        if not left_path.is_file():
            raise RuntimeError(
                f"Arquivo do backup #{left_id} não existe mais."
            )

        if not right_path.is_file():
            raise RuntimeError(
                f"Arquivo do backup #{right_id} não existe mais."
            )

        left_data = left_path.read_bytes()
        right_data = right_path.read_bytes()

        left_hash = _hash(
            left_data
        )
        right_hash = _hash(
            right_data
        )

        base = {
            "left": {
                **left,
                "size": len(
                    left_data
                ),
                "sha256": left_hash,
            },
            "right": {
                **right,
                "size": len(
                    right_data
                ),
                "sha256": right_hash,
            },
            "identical": (
                left_hash
                == right_hash
            ),
        }

        if base[
            "identical"
        ]:
            return {
                **base,
                "format": "binary",
                "changes": [],
                "message": (
                    "Os backups são byte a byte idênticos."
                ),
            }

        xml_left = self._xml(
            left_data
        )
        xml_right = self._xml(
            right_data
        )

        if (
            xml_left is None
            or xml_right is None
        ):
            return {
                **base,
                "format": "binary",
                "changes": [],
                "message": (
                    "Os arquivos são diferentes, mas o conteúdo não é XML legível; "
                    "a comparação foi limitada a SHA-256 e tamanho."
                ),
            }

        fields = sorted(
            set(
                xml_left
            )
            | set(
                xml_right
            )
        )

        changes = []

        for key in fields:
            before = xml_left.get(
                key
            )
            after = xml_right.get(
                key
            )

            if before == after:
                continue

            changes.append({
                "path": key,
                "before": before,
                "after": after,
                "secret": _is_secret(
                    key
                ),
            })

        return {
            **base,
            "format": "xml",
            "changes": changes[:2000],
            "change_count": len(
                changes
            ),
            "truncated": len(
                changes
            ) > 2000,
            "message": (
                f"{len(changes)} campo(s) diferente(s)."
            ),
        }

    @staticmethod
    def _xml(
        data: bytes,
    ) -> dict[str, str] | None:
        try:
            root = ET.fromstring(
                data
            )
        except (
            ET.ParseError,
            UnicodeDecodeError,
        ):
            return None

        return _flatten_xml(
            root
        )


backup_compare_service = BackupCompareService()

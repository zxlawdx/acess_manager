"""Recursively redact secret-bearing mapping fields BEFORE SQLite serialization."""
from __future__ import annotations

from collections.abc import Mapping
from typing import Any

_SECRET_TOKENS = (
    "password", "passwd", "passphrase", "secret", "token", "credential",
    "authorization", "cookie", "private_key", "public_key", "keypassphrase",
    "psk", "chave", "senha",
)


def _is_secret(key: object) -> bool:
    label = str(key).casefold().replace("-", "_")
    return any(token in label for token in _SECRET_TOKENS)


def redact_sensitive(value: Any, *, _depth: int = 0) -> Any:
    """Preserve normal snapshot shapes while never serializing secret fields."""
    if _depth > 24:
        return "[nested-data-omitted]"
    if isinstance(value, Mapping):
        return {
            str(key): (
                "[REDACTED]" if _is_secret(key)
                else redact_sensitive(item, _depth=_depth + 1)
            )
            for key, item in value.items()
        }
    if isinstance(value, (list, tuple)):
        return [redact_sensitive(item, _depth=_depth + 1) for item in value]
    return value

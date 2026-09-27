"""Locally stored non-secret ACS provider templates (no router credentials).

An operator must supply ACS and connection-request passwords at apply time;
neither the repository, browser localStorage nor profile JSON stores secrets.
"""
from __future__ import annotations

import json
import os
import re
import tempfile
from pathlib import Path
from threading import RLock
from urllib.parse import urlsplit

from apps.zte_manager.runtime import data_dir

PROVIDER_DEFAULT = {
    "name": "Brasil Digital",
    # Company's own URL is configured locally rather than published in git.
    "url": "",
    "username": "admin",
    "connection_request_username": "IXCSoft",
    "periodic_inform_enabled": True,
    "periodic_inform_interval": 1200,
}
_ALLOWED = frozenset(PROVIDER_DEFAULT)


def validate_provider(raw: dict) -> dict:
    if not isinstance(raw, dict):
        raise ValueError("O perfil ACS precisa ser um objeto.")
    if any(key in raw for key in (
        "password", "connection_request_password",
        "UserPassword", "ConnectionRequestPassword",
    )):
        raise ValueError("Senhas não podem ser salvas em perfis locais.")
    name = str(raw.get("name") or "").strip()
    if not 1 <= len(name) <= 60 or not re.fullmatch(r"[\w .-]+", name):
        raise ValueError("Nome do provedor inválido.")
    url = str(raw.get("url") or "").strip()
    if url:
        parts = urlsplit(url)
        if parts.scheme not in {"http", "https"} or not parts.hostname or (
            parts.username is not None or parts.password is not None
        ):
            raise ValueError("A URL ACS precisa ser HTTP(S), sem credenciais.")
    result = {key: raw.get(key, PROVIDER_DEFAULT[key]) for key in _ALLOWED}
    result.update(name=name, url=url)
    for key in ("username", "connection_request_username"):
        value = str(result[key] or "").strip()
        if len(value) > 120 or any(ord(c) < 32 for c in value):
            raise ValueError("Usuário ACS inválido.")
        result[key] = value
    interval = int(result["periodic_inform_interval"])
    if not 60 <= interval <= 86400:
        raise ValueError("Intervalo TR-069 fora da faixa permitida.")
    result["periodic_inform_interval"] = interval
    result["periodic_inform_enabled"] = (
        result["periodic_inform_enabled"] is True
    )
    return result


class TR069ProviderProfiles:
    def __init__(self, path: Path | None = None) -> None:
        self.path = Path(path) if path else data_dir() / "tr069_providers.json"
        self._lock = RLock()

    def _read(self) -> dict:
        if not self.path.exists():
            return {}
        try:
            payload = json.loads(self.path.read_text(encoding="utf-8"))
            if not isinstance(payload, dict):
                return {}
            return {
                name: validate_provider(item)
                for name, item in payload.items() if isinstance(item, dict)
            }
        except (ValueError, OSError, TypeError):
            # Corrupt config must not silently replace an existing file.
            raise ValueError("O arquivo de perfis ACS está inválido.") from None

    def list(self) -> list[dict]:
        with self._lock:
            providers = self._read()
            if "Brasil Digital" not in providers:
                providers["Brasil Digital"] = dict(PROVIDER_DEFAULT)
            return sorted(providers.values(), key=lambda item: item["name"].lower())

    def save(self, raw: dict) -> dict:
        provider = validate_provider(raw)
        with self._lock:
            providers = self._read()
            providers[provider["name"]] = provider
            self.path.parent.mkdir(parents=True, exist_ok=True)
            temporary = None
            try:
                with tempfile.NamedTemporaryFile(
                    mode="w", encoding="utf-8", delete=False,
                    dir=self.path.parent, prefix=".tr069-", suffix=".tmp",
                ) as stream:
                    temporary = Path(stream.name)
                    if os.name != "nt":
                        os.chmod(temporary, 0o600)
                    json.dump(providers, stream, ensure_ascii=False, indent=2)
                os.replace(temporary, self.path)
            finally:
                if temporary is not None and temporary.exists():
                    temporary.unlink()
        return provider

    def delete(self, name: str) -> bool:
        # Built-in template can be edited, but not accidentally deleted.
        if name == "Brasil Digital":
            raise ValueError("O perfil base não pode ser excluído.")
        with self._lock:
            providers = self._read()
            if name not in providers:
                return False
            del providers[name]
            self.path.parent.mkdir(parents=True, exist_ok=True)
            temporary = None
            try:
                with tempfile.NamedTemporaryFile(
                    mode="w", encoding="utf-8", delete=False,
                    dir=self.path.parent, prefix=".tr069-", suffix=".tmp",
                ) as stream:
                    temporary = Path(stream.name)
                    if os.name != "nt":
                        os.chmod(temporary, 0o600)
                    json.dump(providers, stream, ensure_ascii=False, indent=2)
                os.replace(temporary, self.path)
            finally:
                if temporary is not None and temporary.exists():
                    temporary.unlink()
        return True


tr069_provider_profiles = TR069ProviderProfiles()

"""Multiple Wi-Fi/DNS presets per technician; original primary preset is unchanged."""
from __future__ import annotations

import re
from threading import RLock

from apps.zte_manager.repositories.profile_repository import ProfileRepository
from apps.zte_manager.runtime import data_dir
from apps.zte_manager.services.profile_service import (
    ApplyProfileCommand, _normalize_profile, profile_service,
)

PRIMARY = "Configuração principal"
_SAFE_NAME = re.compile(r"^[\wÀ-ÿ .()-]{1,60}$", flags=re.UNICODE)


def safe_name(name: str) -> str:
    clean = str(name or "").strip()
    if not _SAFE_NAME.fullmatch(clean) or "::" in clean:
        raise ValueError("Informe um nome de configuração com até 60 caracteres.")
    return clean


class NamedPresetService:
    def __init__(self, repository: ProfileRepository | None = None):
        self.repository = repository or ProfileRepository(
            data_dir() / "named_attendant_profiles.json"
        )
        self._lock = RLock()

    def list(self, attendant: str) -> list[str]:
        prefix = str(attendant).strip() + "::"
        with self._lock:
            return [PRIMARY] + [
                key[len(prefix):] for key in self.repository.list()
                if key.startswith(prefix)
            ]

    def get(self, attendant: str, name: str) -> dict:
        clean = safe_name(name)
        with self._lock:
            if clean == PRIMARY:
                return profile_service.get_profile(attendant)
            saved = self.repository.get(str(attendant).strip() + "::" + clean)
            if saved is None:
                raise ValueError("Configuração não encontrada.")
            return _normalize_profile(saved)

    def save(self, attendant: str, name: str, config: dict) -> dict:
        clean = safe_name(name)
        normalized = _normalize_profile(config)
        with self._lock:
            if clean == PRIMARY:
                return profile_service.save_profile(attendant, normalized)
            return self.repository.save(
                str(attendant).strip() + "::" + clean, normalized
            )

    def delete(self, attendant: str, name: str) -> bool:
        clean = safe_name(name)
        if clean == PRIMARY:
            raise ValueError("A configuração principal não pode ser excluída.")
        with self._lock:
            return self.repository.delete(
                str(attendant).strip() + "::" + clean
            )

    def apply(self, zte, attendant: str, name: str) -> dict:
        profile = self.get(attendant, name)
        return ApplyProfileCommand(profile).execute(zte)


named_preset_service = NamedPresetService()

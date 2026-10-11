from __future__ import annotations

from typing import Any


class ZTEWorkspace:
    """ZTE-owned runtime boundary around the existing ZTEService.

    ThinkLua, F6201B, adapters and token/session logic remain in the validated
    ZTE runtime. Generic orchestration reaches them only through this facade.
    """

    vendor = "zte"

    def __init__(self, provider: Any) -> None:
        self._provider = provider

    @property
    def provider(self) -> Any:
        return self._provider

    @property
    def connected(self) -> bool:
        return bool(getattr(self._provider, "connected", False))

    @property
    def capabilities(self) -> dict:
        value = getattr(self._provider, "capabilities", None)
        if value is None:
            value = getattr(self._provider, "_capabilities", None)
        return dict(value or {})

    @property
    def writes_enabled(self) -> bool:
        backend = getattr(self._provider, "_zte", None)
        return bool(getattr(backend, "writes_enabled", False))

    def connect(self, *args, **kwargs):
        return self._provider.connect(*args, **kwargs)

    def disconnect(self) -> None:
        self._provider.disconnect()

    def __getattr__(self, name: str):
        if name.startswith("_"):
            raise AttributeError(name)
        return getattr(self._provider, name)

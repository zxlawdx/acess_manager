from __future__ import annotations

from typing import Any


class HuaweiWorkspace:
    """Huawei-owned runtime boundary.

    The workspace deliberately wraps the already validated Huawei provider
    instead of reimplementing protocol code. HTTP/AMP/BBSP/auth/readback logic
    remains inside the existing Huawei runtime while generic orchestration sees
    only this vendor-owned facade.
    """

    vendor = "huawei"

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
        return dict(value or {})

    @property
    def writes_enabled(self) -> bool:
        return bool(getattr(self._provider, "writes_enabled", False))

    def connect(self, *args, **kwargs):
        return self._provider.connect(*args, **kwargs)

    def disconnect(self) -> None:
        self._provider.disconnect()

    def __getattr__(self, name: str):
        if name.startswith("_"):
            raise AttributeError(name)
        return getattr(self._provider, name)

"""Vela API composition root for Access Manager.

Vela discovers this module. Importing the domain controller modules registers
all routes against the same ``vela.api.api`` singleton. Reexports preserve the
historical ``apps.zte_manager.api.<handler>`` import surface while controllers
live under ``presentation/api``.
"""

from __future__ import annotations

import functools
import sys

from apps.zte_manager.presentation.api.common import *  # noqa: F401,F403
from apps.zte_manager.presentation.api.system import *  # noqa: F401,F403
from apps.zte_manager.presentation.api.devices import *  # noqa: F401,F403
from apps.zte_manager.presentation.api.wan import *  # noqa: F401,F403
from apps.zte_manager.presentation.api.wifi import *  # noqa: F401,F403
from apps.zte_manager.presentation.api.network import *  # noqa: F401,F403
from apps.zte_manager.presentation.api.diagnostics import *  # noqa: F401,F403
from apps.zte_manager.presentation.api.capabilities import *  # noqa: F401,F403
from apps.zte_manager.presentation.api.f6201b import *  # noqa: F401,F403
from apps.zte_manager.presentation.api.profiles import *  # noqa: F401,F403
from apps.zte_manager.presentation.api.management_core import *  # noqa: F401,F403
from apps.zte_manager.presentation.api.management_network import *  # noqa: F401,F403
from apps.zte_manager.presentation.api.management_artifacts import *  # noqa: F401,F403


def _legacy_reexport(handler):
    """Preserve tests/internal callers that inject services on this module.

    Vela already registered the original domain handler. This wrapper affects
    only direct calls through ``apps.zte_manager.api`` and can be removed once
    consumers patch/inject the presentation facade rather than this old module.
    """
    @functools.wraps(handler)
    def wrapped(*args, **kwargs):
        # Helpers such as _call_device/_call_device_read live in common.py and
        # resolve their globals there, not in each controller module. Keep the
        # legacy injection surface coherent across both layers.
        common = sys.modules.get("apps.zte_manager.presentation.api.common")
        if common is not None:
            common.device_service = globals()["device_service"]
            common.zte_service = globals()["zte_service"]

        owner = sys.modules.get(handler.__module__)
        if owner is not None:
            if hasattr(owner, "device_service"):
                owner.device_service = globals()["device_service"]
            if hasattr(owner, "zte_service"):
                owner.zte_service = globals()["zte_service"]
        return handler(*args, **kwargs)
    return wrapped


for _name, _value in list(globals().items()):
    _module = getattr(_value, "__module__", "")
    if (
        callable(_value)
        and _module.startswith("apps.zte_manager.presentation.api.")
        and not _module.endswith(".common")
    ):
        globals()[_name] = _legacy_reexport(_value)

del _name, _value, _module

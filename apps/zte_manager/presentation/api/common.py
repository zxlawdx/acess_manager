from __future__ import annotations

import logging
import re
import traceback
from pathlib import Path
from typing import Any, Callable
from uuid import uuid4

from pydantic import ValidationError
from vela.api import api

from apps.zte_manager.schemas import (
    ACSConfigRequest,
    ACSParameterRequest,
    AdminPasswordRequest,
    AgentRequest,
    AttendantRequest,
    AttendanceReportRequest,
    AutomaticDiagnosticRequest,
    BackupCompareRequest,
    BandSteeringConfigRequest,
    BandSteeringRequest,
    BatchManagementRequest,
    BridgeModeRequest,
    BufferbloatRequest,
    CapabilityProbeRequest,
    ConnectRequest,
    DhcpBasicRequest,
    DhcpReservationRequest,
    DiagnosticRemediationRequest,
    DmzRequest,
    DnsRequest,
    DriftRequest,
    FilterGlobalManagementRequest,
    FirewallManagementRequest,
    FirewallRuleManagementRequest,
    FirmwareRegisterRequest,
    FirmwareUpgradeRequest,
    GatewayCommandRequest,
    HuaweiFeatureUpdateRequest,
    HuaweiIPv4FilterDeleteRequest,
    HuaweiIPv4FilterRuleRequest,
    InventorySyncRequest,
    InventoryUpdateRequest,
    ManagementBackupRequest,
    ManagementProfileRequest,
    MeshConfigRequest,
    MeshPairRequest,
    MonitorStartRequest,
    NamedPresetRequest,
    NamedPresetSaveRequest,
    NumericIdRequest,
    PingRequest,
    PortForwardRequest,
    ProfileRequest,
    QoSManagementRequest,
    RadioPowerRequest,
    RemoteAccessRequest,
    ResourceIdRequest,
    RestoreBackupRequest,
    SNTPManagementRequest,
    SpeedTestRequest,
    SupportDiagnosticRequest,
    TR069ManagementRequest,
    TR069ProviderApplyRequest,
    TR069ProviderDeleteRequest,
    TR069ProviderSaveRequest,
    TracerouteRequest,
    UpnpRequest,
    WANActionRequest,
    WANCreateRequest,
    WANDeleteRequest,
    WANManagementRequest,
    WifiRadioRequest,
    WifiSSIDRequest,
    WifiScheduleRequest,
    WpsRequest,
    ZeroTouchRequest,
)
from apps.zte_manager.services.cpe_management_service import cpe_management_service
from apps.zte_manager.services.desktop_capabilities import get_desktop_capabilities
from apps.zte_manager.services.desktop_clipboard import copy_text as copy_desktop_text
from apps.zte_manager.services.device_service import device_service
from apps.zte_manager.services.error_policy import PublicFailure, classify
from apps.zte_manager.services.tr069_profile_service import tr069_provider_profiles
from apps.zte_manager.services.zte_service import zte_service


logger = logging.getLogger(__name__)


def _safe_action_code(value: object) -> str:
    """Return a log-safe code identifier, never raw protocol/user data."""
    safe = re.sub(r"[^a-zA-Z0-9_]", "_", str(value or "unknown"))[:64]
    return safe or "unknown"


def _sanitized_traceback(exc: BaseException) -> str:
    """Return frame names/line numbers without exception text or code lines."""
    frames = traceback.extract_tb(exc.__traceback__, limit=8)
    return ";".join(
        f"{_safe_action_code(Path(frame.filename).stem)}."
        f"{_safe_action_code(frame.name)}:{frame.lineno}"
        for frame in frames
    )


def _json(context: dict | None) -> dict:
    if not context:
        return {}
    data = context.get("json") or {}
    return data if isinstance(data, dict) else {}


def _query(context: dict | None) -> dict:
    if not context:
        return {}
    data = context.get("query") or {}
    return data if isinstance(data, dict) else {}


def _bool(value: object, default: bool = False) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"1", "true", "yes", "on", "sim"}


def _validated(model, context):
    """Keep Pydantic validation at the HTTP boundary."""
    return model.model_validate(_json(context))


def _safe_call(func: Callable[..., Any], *args: Any, **kwargs: Any) -> Any:
    """Vela error boundary with stable public envelopes and redacted logs."""
    try:
        return func(*args, **kwargs)
    except ValidationError as error:
        first = error.errors(include_input=False)[0]
        location = first.get("loc", ())
        field = _safe_action_code(location[-1] if location else "input")
        return PublicFailure(
            "INVALID_INPUT",
            "validation",
            "Verifique o campo " + field.replace("_", " ") + ".",
        ).envelope()
    except Exception as error:
        known = classify(error)
        if known is not None:
            logger.warning(
                "api_action_failure action=%s code=%s failure_type=%s",
                _safe_action_code(getattr(func, "__name__", "unknown")),
                known.code,
                _safe_action_code(type(error).__name__),
            )
            return known.envelope()

        error_id = uuid4().hex
        logger.error(
            "api_internal_error error_id=%s action=%s error_type=%s frames=%s",
            error_id,
            _safe_action_code(getattr(func, "__name__", "unknown")),
            _safe_action_code(type(error).__name__),
            _sanitized_traceback(error),
        )
        envelope = PublicFailure(
            "INTERNAL_ERROR",
            "internal",
            "Ocorreu um erro interno. Informe o código " + error_id + " ao suporte.",
        ).envelope()
        envelope["error_id"] = error_id
        return envelope


def _active_provider_service():
    """Compatibility alias; provider dispatch now belongs to DeviceService."""
    return device_service


def _call_device(method_name: str, *args, **kwargs):
    return getattr(device_service, method_name)(*args, **kwargs)


def _call_device_read(method_name: str, context=None, *args, **kwargs):
    if device_service.vendor == "huawei" and _bool(_query(context).get("refresh")):
        kwargs["refresh"] = True
    return _call_device(method_name, *args, **kwargs)


def _call_active_provider(method_name: str, *args, **kwargs):
    """Legacy name kept while controllers migrate; no vendor resolution here."""
    return _call_device(method_name, *args, **kwargs)


# Domain modules intentionally import this facade while routes are being split.
# Include single-underscore HTTP helpers in star imports used by those modules.
__all__ = [name for name in globals() if not name.startswith("__")]

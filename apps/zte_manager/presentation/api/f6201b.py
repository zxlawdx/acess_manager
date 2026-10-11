from apps.zte_manager.services.zte_service import zte_service  # legacy test alias; never called here

from .common import *


def _active_f6201b_session() -> tuple[dict, bool]:
    """Return public session metadata and whether F6201B routes are applicable."""
    status = device_service.status()
    applicable = bool(
        status.get("connected") is True
        and str(status.get("vendor") or "").casefold() == "zte"
        and str(status.get("model") or "").strip().upper() == "F6201B"
    )
    return status, applicable


def _call_f6201b(method_name: str, *args, **kwargs):
    """Resolve an F6201B operation only on the active provider workspace."""
    return getattr(device_service, method_name)(*args, **kwargs)


# These routes remain intentionally ZTE/F6201B-specific. The difference is
# architectural: they no longer reach the global ZTE singleton and therefore
# cannot leak into a Huawei session.
@api.get("/f6201b/write/status")
def f6201b_write_status(context=None):
    status, applicable = _active_f6201b_session()
    if not applicable:
        return {
            "supported_firmware": False,
            "writes_enabled": False,
            "connected": bool(status.get("connected")),
            "vendor": status.get("vendor"),
            "model": status.get("model"),
            "reason": "active_session_is_not_f6201b",
        }
    return _safe_call(_call_f6201b, "f6201b_write_status")


@api.get("/f6201b/write/ssids")
def f6201b_write_ssids(context=None):
    return _safe_call(_call_f6201b, "f6201b_write_ssids")


@api.post("/f6201b/write/preview")
def f6201b_write_preview(context=None):
    body = _json(context)
    return _safe_call(
        _call_f6201b,
        "f6201b_write_preview",
        str(body.get("ssid_id") or "")[:64],
        body.get("config"),
    )


@api.post("/f6201b/write/apply")
def f6201b_write_apply(context=None):
    body = _json(context)
    return _safe_call(
        _call_f6201b,
        "f6201b_write_apply",
        str(body.get("nonce") or "")[:100],
        str(body.get("confirmation") or "")[:50],
    )


@api.post("/f6201b/write/update")
def f6201b_write_update(context=None):
    body = _json(context)
    return _safe_call(
        _call_f6201b,
        "f6201b_ssid_update",
        str(body.get("ssid_id") or "")[:64],
        body.get("config"),
    )


@api.get("/f6201b/wan/summary")
def f6201b_wan_summary(context=None):
    return _safe_call(_call_f6201b, "f6201b_wan_summary")


@api.get("/f6201b/dns/status")
def f6201b_dns_status(context=None):
    return _safe_call(_call_f6201b, "f6201b_dns_status")


@api.post("/f6201b/dns/preview")
def f6201b_dns_preview(context=None):
    return _safe_call(
        _call_f6201b,
        "f6201b_dns_preview",
        _json(context).get("changes"),
    )


@api.post("/f6201b/dns/apply")
def f6201b_dns_apply(context=None):
    body = _json(context)
    return _safe_call(
        _call_f6201b,
        "f6201b_dns_apply",
        str(body.get("nonce") or "")[:100],
        str(body.get("confirmation") or "")[:50],
    )


@api.post("/f6201b/dns/update")
def f6201b_dns_update(context=None):
    return _safe_call(
        _call_f6201b,
        "f6201b_dns_update",
        _json(context).get("changes"),
    )


@api.get("/f6201b/workbench/catalog")
def f6201b_workbench_catalog(context=None):
    return _safe_call(_call_f6201b, "captured_workbench_catalog")


@api.post("/f6201b/workbench/inspect")
def f6201b_workbench_inspect(context=None):
    return _safe_call(
        _call_f6201b,
        "captured_workbench_inspect",
        str(_json(context).get("tag") or "")[:100],
    )


@api.post("/f6201b/workbench/preview")
def f6201b_workbench_preview(context=None):
    body = _json(context)
    return _safe_call(
        _call_f6201b,
        "captured_workbench_preview",
        str(body.get("tag") or "")[:100],
        str(body.get("instance_id") or "")[:128],
        body.get("changes"),
    )


@api.post("/f6201b/workbench/apply")
def f6201b_workbench_apply(context=None):
    body = _json(context)
    return _safe_call(
        _call_f6201b,
        "captured_workbench_apply",
        str(body.get("nonce") or "")[:100],
        str(body.get("confirmation") or "")[:50],
        body.get("risk_ack") is True,
    )


@api.post("/f6201b/workbench/update")
def f6201b_workbench_update(context=None):
    body = _json(context)
    return _safe_call(
        _call_f6201b,
        "captured_workbench_update",
        str(body.get("tag") or "")[:100],
        str(body.get("instance_id") or "")[:128],
        body.get("changes"),
    )


@api.get("/multimodel/mapped-routes")
def mapped_f6201b_routes(context=None):
    return _safe_call(_call_f6201b, "mapped_f6201b_routes")


@api.post("/multimodel/mapped-inspect")
def inspect_mapped_f6201b_route(context=None):
    tag = str(_json(context).get("tag") or "").strip()[:100]
    return _safe_call(_call_f6201b, "inspect_mapped_f6201b_route", tag)


@api.post("/f6201b/profile/preview")
def f6201b_profile_preview(context=None):
    def action():
        data = _validated(AttendantRequest, context)
        return _call_f6201b("f6201b_profile_preview", data.attendant)
    return _safe_call(action)


@api.post("/f6201b/profile/apply-saved")
def f6201b_profile_apply_saved(context=None):
    def action():
        data = _validated(AttendantRequest, context)
        return _call_f6201b("f6201b_profile_apply_saved", data.attendant)
    return _safe_call(action)


@api.post("/f6201b/profile/apply")
def f6201b_profile_apply(context=None):
    body = _json(context)
    return _safe_call(
        _call_f6201b,
        "f6201b_profile_apply",
        str(body.get("nonce") or "")[:100],
        str(body.get("confirmation") or "")[:50],
    )

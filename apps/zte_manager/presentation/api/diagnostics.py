from .common import *


@api.post("/diagnostics/ping")
def ping(context=None):
    def action():
        data = _validated(PingRequest, context)
        return device_service.ping(data.model_dump())
    return _safe_call(action)


@api.post("/diagnostics/traceroute")
def traceroute(context=None):
    def action():
        data = _validated(TracerouteRequest, context)
        return device_service.traceroute(data.model_dump())
    return _safe_call(action)


@api.post("/diagnostics/automatic")
def automatic_diagnostic(context=None):
    def action():
        data = _validated(AutomaticDiagnosticRequest, context)
        return device_service.automatic_diagnostic(data.model_dump())
    return _safe_call(action)


@api.get("/diagnostics/support/progress")
def support_diagnostic_progress(context=None):
    return _safe_call(_call_active_provider, "support_progress")


@api.post("/diagnostics/support")
def support_diagnostic(context=None):
    def action():
        data = _validated(SupportDiagnosticRequest, context)
        return device_service.support_diagnostic(data.model_dump())
    return _safe_call(action)


@api.post("/diagnostics/support/f6201b")
def support_diagnostic_f6201b(context=None):
    def action():
        data = _validated(SupportDiagnosticRequest, context)
        return zte_service.f6201b_support_diagnostic(data.model_dump())
    return _safe_call(action)


@api.post("/diagnostics/remediate")
def remediate_diagnostic(context=None):
    def action():
        data = _validated(DiagnosticRemediationRequest, context)
        return device_service.remediate_diagnostic(data.model_dump())
    return _safe_call(action)


@api.get("/diagnostics/workstation")
def workstation_diagnostic(context=None):
    return _safe_call(_call_device, "workstation_diagnostic")


@api.post("/diagnostics/speedtest")
def speedtest(context=None):
    def action():
        data = _validated(SpeedTestRequest, context)
        return device_service.speedtest(data.model_dump())
    return _safe_call(action)


@api.post("/diagnostics/attendance")
def generate_attendance(context=None):
    def action():
        data = _validated(AttendanceReportRequest, context)
        return device_service.generate_attendance(data.diagnostic_id)
    return _safe_call(action)


@api.post("/history/snapshot")
def capture_snapshot(context=None):
    reason = str(_json(context).get("reason") or "manual")[:120]
    return _safe_call(device_service.capture_snapshot, reason)


@api.get("/history")
def history(context=None):
    query = _query(context)
    try:
        limit = int(query.get("limit") or 50)
    except (TypeError, ValueError):
        limit = 50
    return _safe_call(device_service.history, limit)

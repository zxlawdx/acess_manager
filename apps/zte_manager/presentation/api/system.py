from .common import *


@api.get("/health")
def health(context=None):
    return {
        "status": "ok",
        "service": "Access Manager",
        "runtime": "Vela Framework",
    }


@api.get("/desktop/capabilities")
def desktop_capabilities(context: dict | None = None) -> dict[str, object]:
    return get_desktop_capabilities()


@api.post("/desktop/clipboard")
def desktop_clipboard(context=None):
    return _safe_call(copy_desktop_text, _json(context).get("text"))


@api.post("/connect")
def connect(context=None):
    def action():
        data = _validated(ConnectRequest, context)
        return device_service.connect(
            ip=data.ip,
            username=data.username,
            password=data.password,
            https=data.https,
            attendant=data.attendant,
            model_hint=data.model_hint,
        )
    return _safe_call(action)


@api.post("/disconnect")
def disconnect(context=None):
    def action():
        device_service.disconnect()
        return {"success": True, "message": "Console local desconectado."}
    return _safe_call(action)


@api.get("/connection/status")
def connection_status(context=None):
    """Expose only the public DeviceService session contract."""
    return device_service.status()


@api.get("/debug/security")
def security_status(context=None):
    """Explicit ZTE-only diagnostic retained until a neutral contract exists."""
    return _safe_call(zte_service.security_status)

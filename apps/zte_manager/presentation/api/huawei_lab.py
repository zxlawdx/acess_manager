from .common import *


@api.get("/huawei/lab")
def huawei_lab_status(context=None):
    return _safe_call(_call_device, "lab_status")


@api.post("/huawei/lab/mode")
def huawei_lab_mode(context=None):
    def action():
        data = _json(context)
        enabled = _bool(data.get("enabled"))
        return _call_device("set_lab_mode", enabled)
    return _safe_call(action)


@api.post("/huawei/lab/write")
def huawei_lab_write(context=None):
    def action():
        data = _json(context)
        operation = str(data.get("operation") or "").strip() or None
        path = str(data.get("path") or "").strip() or None
        if not operation and not path:
            raise ValueError("Informe operation ou path para a mutation Huawei de laboratório.")
        return _call_device(
            "lab_write",
            operation=operation,
            path=path,
            payload=data.get("config") or data.get("payload") or {},
            referer=str(data.get("referer") or "/index.asp"),
            token_page=(str(data.get("token_page")) if data.get("token_page") else None),
            readback_path=(str(data.get("readback_path")) if data.get("readback_path") else None),
            readback_method=str(data.get("readback_method") or "GET"),
            readback_payload=data.get("readback_payload") or {},
            readback_expect=data.get("readback_expect") or None,
        )
    return _safe_call(action)


@api.post("/huawei/lab/reboot")
def huawei_lab_reboot(context=None):
    def action():
        data = _json(context)
        request = data.get("request")
        if request is not None and not isinstance(request, dict):
            raise ValueError("request deve ser um objeto com path/payload/referer.")
        return _call_device(
            "lab_reboot",
            variant=str(data.get("variant") or "reboot"),
            request=request,
        )
    return _safe_call(action)

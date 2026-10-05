from .common import *


@api.get("/device/status")
def device_status(context=None):
    return _safe_call(_call_device_read, "device_status", context)


@api.get("/device/optical")
def optical_status(context=None):
    return _safe_call(_call_device_read, "optical_status", context)


@api.get("/device/accounts")
def account_status(context=None):
    return _safe_call(_call_device, "account_status")


@api.post("/device/password")
def change_admin_password(context=None):
    def action():
        data = _validated(AdminPasswordRequest, context)
        return device_service.change_admin_password(data.new_password)
    return _safe_call(action)


@api.post("/device/reboot")
def reboot_device(context=None):
    return _safe_call(_call_device, "reboot")

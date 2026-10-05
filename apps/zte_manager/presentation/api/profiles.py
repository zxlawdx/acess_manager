from .common import *


@api.get("/configuration/current")
def current_configuration(context=None):
    return _safe_call(_call_device, "current_configuration")


@api.get("/profiles")
def profiles(context=None):
    return _safe_call(lambda: {"profiles": device_service.profiles()})


@api.post("/profiles/get")
def get_profile(context=None):
    def action():
        data = _validated(AttendantRequest, context)
        return device_service.get_profile(data.attendant)
    return _safe_call(action)


@api.post("/profiles/save")
def save_profile(context=None):
    def action():
        data = _validated(ProfileRequest, context)
        return device_service.save_profile(
            data.attendant,
            {"wifi": data.wifi, "dns": data.dns},
        )
    return _safe_call(action)


# ZTE named presets remain explicitly provider-specific until DeviceService
# exposes a neutral persistent-preset contract.
@api.post("/profiles/named/list")
def list_named_presets(context=None):
    def action():
        data = _validated(AttendantRequest, context)
        return {"names": zte_service.list_named_presets(data.attendant)}
    return _safe_call(action)


@api.post("/profiles/named/get")
def get_named_preset(context=None):
    def action():
        data = _validated(NamedPresetRequest, context)
        return zte_service.get_named_preset(data.attendant, data.name)
    return _safe_call(action)


@api.post("/profiles/named/save")
def save_named_preset(context=None):
    def action():
        data = _validated(NamedPresetSaveRequest, context)
        return zte_service.save_named_preset(
            data.attendant,
            data.name,
            {"wifi": data.wifi, "dns": data.dns},
        )
    return _safe_call(action)


@api.post("/profiles/named/delete")
def delete_named_preset(context=None):
    def action():
        data = _validated(NamedPresetRequest, context)
        return {"success": zte_service.delete_named_preset(data.attendant, data.name)}
    return _safe_call(action)


@api.post("/profiles/named/apply")
def apply_named_preset(context=None):
    def action():
        data = _validated(NamedPresetRequest, context)
        return device_service.apply_named_preset(data.attendant, data.name)
    return _safe_call(action)


@api.post("/profiles/capture")
def capture_profile(context=None):
    def action():
        data = _validated(AttendantRequest, context)
        return device_service.capture_profile(data.attendant)
    return _safe_call(action)


@api.post("/profiles/apply")
def apply_profile(context=None):
    def action():
        data = _validated(AttendantRequest, context)
        return device_service.apply_profile(data.attendant)
    return _safe_call(action)

from .common import *


@api.get("/wifi/networks")
def wifi_networks(context=None):
    query = _query(context)
    return _safe_call(
        _call_device_read,
        "wifi_networks",
        context,
        reveal_password=_bool(query.get("reveal_password")),
    )


@api.post("/wifi/network/update")
def set_wifi_network(context=None):
    def action():
        data = _validated(WifiSSIDRequest, context)
        if not data.ssid_id:
            raise ValueError("Informe o identificador do SSID.")
        config = data.model_dump(exclude_none=True, exclude={"ssid_id"})
        if not config:
            raise ValueError("Nenhuma alteração foi informada.")
        return device_service.set_ssid_config(data.ssid_id, config)
    return _safe_call(action)


@api.get("/wifi/radios")
def get_radios(context=None):
    return _safe_call(_call_device_read, "wifi_radios", context)


@api.get("/wifi/channels")
def get_channels(context=None):
    query = _query(context)
    return _safe_call(
        _call_device,
        "wifi_channels",
        band=query.get("band"),
        bandwidth=query.get("bandwidth"),
        country=query.get("country") or "BRI",
    )


@api.post("/wifi/radio/update")
def set_radio(context=None):
    def action():
        data = _validated(WifiRadioRequest, context)
        if not data.band:
            raise ValueError("Informe a banda do rádio.")
        config = data.model_dump(exclude_none=True, exclude={"band"})
        if not config:
            raise ValueError("Nenhuma alteração foi informada.")
        return device_service.set_wifi_radio(data.band, config)
    return _safe_call(action)


@api.get("/wifi/power")
def wifi_power_status(context=None):
    return _safe_call(_call_device_read, "radio_power_status", context)


@api.post("/wifi/power/update")
def set_wifi_power(context=None):
    def action():
        data = _validated(RadioPowerRequest, context)
        return device_service.set_radio_power(data.band, data.enabled)
    return _safe_call(action)


@api.get("/wifi/schedule")
def wifi_schedule_status(context=None):
    return _safe_call(_call_device, "wifi_schedule_status")


@api.post("/wifi/schedule/update")
def set_wifi_schedule(context=None):
    def action():
        data = _validated(WifiScheduleRequest, context)
        return device_service.set_wifi_schedule(data.model_dump())
    return _safe_call(action)


@api.get("/wifi/wps")
def wifi_wps_status(context=None):
    return _safe_call(_call_device, "wps_status")


@api.post("/wifi/wps/update")
def set_wifi_wps(context=None):
    def action():
        data = _validated(WpsRequest, context)
        return device_service.set_wps(data.band, data.mode)
    return _safe_call(action)


@api.get("/wifi/band-steering")
def band_steering_status(context=None):
    return _safe_call(_call_device, "band_steering_status")


@api.post("/wifi/band-steering/update")
def set_band_steering(context=None):
    def action():
        data = _validated(BandSteeringRequest, context)
        return device_service.set_band_steering(data.enabled)
    return _safe_call(action)


@api.post("/wifi/band-steering/configure")
def configure_band_steering(context=None):
    def action():
        data = _validated(BandSteeringConfigRequest, context)
        return device_service.configure_band_steering(
            data.model_dump(exclude_none=True)
        )
    return _safe_call(action)

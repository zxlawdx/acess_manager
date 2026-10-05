from .common import *


@api.get("/wan/status")
def wan_status(context=None):
    return _safe_call(_call_device_read, "wan_status", context)


@api.get("/wan/pppoe")
def pppoe_status(context=None):
    query = _query(context)
    return _safe_call(
        _call_device_read,
        "pppoe_status",
        context,
        reveal_password=_bool(query.get("reveal_password")),
    )


@api.get("/clients/wifi")
def wifi_clients(context=None):
    return _safe_call(_call_device_read, "wifi_clients", context)


@api.get("/clients/lan")
def lan_clients(context=None):
    return _safe_call(_call_device_read, "lan_clients", context)


@api.get("/lan/ports")
def lan_ports(context=None):
    return _safe_call(_call_device_read, "lan_ports", context)

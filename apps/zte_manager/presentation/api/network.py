from .common import *


@api.get("/upnp")
def upnp_status(context=None):
    return _safe_call(_call_device, "upnp_status")


@api.post("/upnp/update")
def set_upnp(context=None):
    def action():
        data = _validated(UpnpRequest, context)
        return device_service.set_upnp(data.model_dump(exclude_none=True))
    return _safe_call(action)


@api.get("/dns/status")
def dns_status(context=None):
    return _safe_call(_call_device_read, "dns_status", context)


@api.post("/dns/update")
def set_dns(context=None):
    def action():
        data = _validated(DnsRequest, context)
        return device_service.set_dns(
            data.model_dump(exclude_none=True, exclude_unset=True)
        )
    return _safe_call(action)


@api.get("/network/dhcp")
def dhcp_status(context=None):
    return _safe_call(_call_device_read, "dhcp_status", context)


@api.post("/network/dhcp/update")
def update_dhcp(context=None):
    def action():
        data = _validated(DhcpBasicRequest, context)
        return device_service.set_dhcp_basic(data.model_dump(exclude_none=True))
    return _safe_call(action)


@api.post("/network/dhcp/reservation/save")
def save_dhcp_reservation(context=None):
    def action():
        data = _validated(DhcpReservationRequest, context)
        return device_service.save_dhcp_reservation(data.model_dump())
    return _safe_call(action)


@api.post("/network/dhcp/reservation/delete")
def delete_dhcp_reservation(context=None):
    def action():
        data = _validated(ResourceIdRequest, context)
        return device_service.delete_dhcp_reservation(data.id)
    return _safe_call(action)


@api.get("/network/port-forwarding")
def port_forwarding_status(context=None):
    return _safe_call(_call_device, "port_forwarding_status")


@api.post("/network/port-forwarding/save")
def save_port_forward(context=None):
    def action():
        data = _validated(PortForwardRequest, context)
        return device_service.save_port_forward(data.model_dump())
    return _safe_call(action)


@api.post("/network/port-forwarding/delete")
def delete_port_forward(context=None):
    def action():
        data = _validated(ResourceIdRequest, context)
        return device_service.delete_port_forward(data.id, confirm=data.confirm)
    return _safe_call(action)


@api.get("/network/dmz")
def dmz_status(context=None):
    return _safe_call(_call_device_read, "dmz_status", context)


@api.post("/network/dmz/update")
def update_dmz(context=None):
    def action():
        data = _validated(DmzRequest, context)
        return device_service.set_dmz(data.model_dump())
    return _safe_call(action)

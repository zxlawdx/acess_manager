from .common import *


@api.get("/management/backups")
def management_backups(context=None):
    device_id = _query(context).get("device_id")
    return _safe_call(
        cpe_management_service.backups,
        int(device_id) if device_id else None,
    )


@api.post("/management/backups/create")
def management_backup_create(context=None):
    def action():
        data = _validated(ManagementBackupRequest, context)
        return cpe_management_service.backup(device_service, data.model_dump())
    return _safe_call(action)


@api.post("/management/backups/compare")
def management_backup_compare(context=None):
    def action():
        data = _validated(BackupCompareRequest, context)
        return cpe_management_service.compare_backups(data.model_dump())
    return _safe_call(action)


@api.post("/management/backups/restore")
def management_backup_restore(context=None):
    def action():
        data = _validated(RestoreBackupRequest, context)
        return cpe_management_service.restore(device_service, data.model_dump())
    return _safe_call(action)


@api.get("/management/firmware")
def management_firmware(context=None):
    return _safe_call(
        cpe_management_service.firmware_list,
        _query(context).get("model"),
    )


@api.post("/management/firmware/register")
def management_firmware_register(context=None):
    def action():
        data = _validated(FirmwareRegisterRequest, context)
        return cpe_management_service.firmware_register(data.model_dump())
    return _safe_call(action)


@api.get("/management/firmware/status")
def management_firmware_status(context=None):
    return _safe_call(_call_device, "firmware_management_status")


@api.post("/management/firmware/upgrade")
def management_firmware_upgrade(context=None):
    def action():
        data = _validated(FirmwareUpgradeRequest, context)
        return cpe_management_service.firmware_upgrade(
            device_service,
            data.model_dump(),
        )
    return _safe_call(action)


@api.get("/management/acs")
def management_acs_status(context=None):
    return _safe_call(cpe_management_service.acs_status)


@api.post("/management/acs/configure")
def management_acs_configure(context=None):
    def action():
        data = _validated(ACSConfigRequest, context)
        return cpe_management_service.configure_acs(data.model_dump())
    return _safe_call(action)


@api.get("/management/acs/discover")
def management_acs_discover(context=None):
    device_id = _query(context).get("device_id")
    if not device_id:
        return {"error": "Informe ?device_id=.", "type": "validation"}
    return _safe_call(cpe_management_service.acs_discover, int(device_id))


@api.post("/management/acs/parameters")
def management_acs_parameters(context=None):
    def action():
        data = _validated(ACSParameterRequest, context)
        return cpe_management_service.acs_parameters(data.model_dump())
    return _safe_call(action)


@api.post("/management/zero-touch")
def management_zero_touch(context=None):
    def action():
        data = _validated(ZeroTouchRequest, context)
        return cpe_management_service.zero_touch(device_service, data.model_dump())
    return _safe_call(action)

from .common import *


@api.get("/management/inventory")
def management_inventory(context=None):
    query = _query(context)
    try:
        limit = int(query.get("limit") or 500)
    except (TypeError, ValueError):
        limit = 500
    return _safe_call(
        cpe_management_service.devices,
        query=query.get("q"),
        status=query.get("status"),
        limit=limit,
    )


@api.post("/management/inventory/sync")
def management_inventory_sync(context=None):
    def action():
        data = _validated(InventorySyncRequest, context)
        return cpe_management_service.sync_inventory(
            device_service,
            data.model_dump(),
        )
    return _safe_call(action)


@api.post("/management/inventory/update")
def management_inventory_update(context=None):
    def action():
        data = _validated(InventoryUpdateRequest, context)
        values = data.model_dump(exclude_none=True, exclude={"device_id"})
        return cpe_management_service.update_device(data.device_id, values)
    return _safe_call(action)


@api.get("/management/profiles")
def management_profiles(context=None):
    return _safe_call(cpe_management_service.profiles)


@api.post("/management/profiles/save")
def management_profile_save(context=None):
    def action():
        data = _validated(ManagementProfileRequest, context)
        return cpe_management_service.save_profile(data.model_dump())
    return _safe_call(action)


@api.post("/management/drift")
def management_drift(context=None):
    def action():
        data = _validated(DriftRequest, context)
        return cpe_management_service.drift(device_service, data.model_dump())
    return _safe_call(action)


@api.post("/management/drift/remediate")
def management_drift_remediate(context=None):
    def action():
        data = _validated(DriftRequest, context)
        return cpe_management_service.remediate_drift(
            device_service,
            data.model_dump(),
        )
    return _safe_call(action)


@api.post("/management/batch")
def management_batch_create(context=None):
    def action():
        data = _validated(BatchManagementRequest, context)
        return cpe_management_service.create_batch(
            device_service,
            data.model_dump(),
        )
    return _safe_call(action)


@api.get("/management/batch")
def management_batch_jobs(context=None):
    return _safe_call(cpe_management_service.batch_jobs)


@api.get("/management/batch/job")
def management_batch_job(context=None):
    job_id = _query(context).get("id")
    if not job_id:
        return {"error": "Informe ?id= do job.", "type": "validation"}
    return _safe_call(cpe_management_service.batch_job, int(job_id))


@api.get("/management/agents")
def management_agents(context=None):
    return _safe_call(cpe_management_service.agents)


@api.post("/management/agents/save")
def management_agent_save(context=None):
    def action():
        data = _validated(AgentRequest, context)
        return cpe_management_service.save_agent(data.model_dump())
    return _safe_call(action)


@api.post("/management/agents/test")
def management_agent_test(context=None):
    def action():
        data = _validated(NumericIdRequest, context)
        return cpe_management_service.test_agent(data.id)
    return _safe_call(action)


@api.get("/management/remote/sessions")
def management_remote_sessions(context=None):
    return _safe_call(cpe_management_service.remote_sessions)


@api.post("/management/remote/open")
def management_remote_open(context=None):
    def action():
        data = _validated(RemoteAccessRequest, context)
        return cpe_management_service.open_remote(
            device_service,
            data.model_dump(),
        )
    return _safe_call(action)


@api.post("/management/remote/close")
def management_remote_close(context=None):
    def action():
        data = _validated(NumericIdRequest, context)
        return cpe_management_service.close_remote(data.id)
    return _safe_call(action)


@api.post("/management/gateway/bufferbloat")
def management_gateway_bufferbloat(context=None):
    def action():
        data = _validated(BufferbloatRequest, context)
        return cpe_management_service.bufferbloat(data.model_dump())
    return _safe_call(action)


@api.post("/management/gateway/command")
def management_gateway_command(context=None):
    def action():
        data = _validated(GatewayCommandRequest, context)
        return cpe_management_service.gateway_command(data.model_dump())
    return _safe_call(action)


@api.post("/management/monitor/start")
def management_monitor_start(context=None):
    def action():
        data = _validated(MonitorStartRequest, context)
        return cpe_management_service.start_monitor(
            device_service,
            data.model_dump(),
        )
    return _safe_call(action)


@api.get("/management/monitor/status")
def management_monitor_status(context=None):
    run_id = _query(context).get("id")
    if not run_id:
        return {"error": "Informe ?id= do monitor.", "type": "validation"}
    return _safe_call(cpe_management_service.monitor_status, int(run_id))


@api.post("/management/monitor/stop")
def management_monitor_stop(context=None):
    def action():
        data = _validated(NumericIdRequest, context)
        return cpe_management_service.stop_monitor(data.id)
    return _safe_call(action)


@api.get("/management/topology")
def management_topology(context=None):
    device_id = _query(context).get("device_id")
    if not device_id:
        return {"error": "Informe ?device_id=.", "type": "validation"}
    return _safe_call(
        cpe_management_service.topology,
        device_service,
        int(device_id),
    )


@api.get("/management/incidents")
def management_incidents(context=None):
    return _safe_call(
        cpe_management_service.incidents,
        _query(context).get("status"),
    )


@api.post("/management/incidents/correlate")
def management_incidents_correlate(context=None):
    data = _json(context)
    return _safe_call(
        cpe_management_service.correlate_incidents,
        data.get("minimum_devices") or 5,
    )

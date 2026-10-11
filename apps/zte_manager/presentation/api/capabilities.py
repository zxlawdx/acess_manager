from .common import *


@api.post("/system/backup")
def export_configuration_backup(context=None):
    return _safe_call(_call_device, "export_user_configuration")


@api.get("/device/capabilities")
def capability_catalog(context=None):
    return _safe_call(device_service.capability_catalog)


@api.post("/device/capabilities/probe")
def capability_probe(context=None):
    def action():
        data = _validated(CapabilityProbeRequest, context)
        return device_service.probe_capabilities(data.features or None)
    return _safe_call(action)


@api.get("/huawei/ipv4-filters")
def huawei_ipv4_filters(context=None):
    return _safe_call(
        device_service.list_ipv4_filters,
        refresh=_bool(_query(context).get("refresh")),
    )


@api.get("/huawei/session-snapshot")
def huawei_session_snapshot(context=None):
    return _safe_call(device_service.huawei_session_snapshot)


@api.post("/huawei/session-snapshot/warm")
def huawei_session_snapshot_warm(context=None):
    return _safe_call(
        device_service.warm_huawei_session_snapshot,
        refresh=_bool(_query(context).get("refresh")),
    )


@api.post("/huawei/ipv4-filters/create")
def huawei_ipv4_filter_create(context=None):
    def action():
        data = _validated(HuaweiIPv4FilterRuleRequest, context)
        return device_service.create_ipv4_filter(
            data.model_dump(exclude={"instance_or_domain"})
        )
    return _safe_call(action)


@api.post("/huawei/ipv4-filters/update")
def huawei_ipv4_filter_update(context=None):
    def action():
        data = _validated(HuaweiIPv4FilterRuleRequest, context)
        if data.instance_or_domain is None:
            raise ValueError("Informe a instância da regra IPv4.")
        return device_service.update_ipv4_filter(
            data.instance_or_domain,
            data.model_dump(exclude={"instance_or_domain"}),
        )
    return _safe_call(action)


@api.post("/huawei/ipv4-filters/delete")
def huawei_ipv4_filter_delete(context=None):
    def action():
        data = _validated(HuaweiIPv4FilterDeleteRequest, context)
        return device_service.delete_ipv4_filter(data.instance_or_domain)
    return _safe_call(action)


@api.post("/huawei/features/update")
def huawei_feature_update(context=None):
    def action():
        data = _validated(HuaweiFeatureUpdateRequest, context)
        return device_service.update_captured_feature(data.feature, data.config)
    return _safe_call(action)


@api.get("/huawei/mapped")
def huawei_mapped_catalog(context=None):
    return _safe_call(_call_device, "mapped_catalog")


@api.post("/huawei/mapped/read")
def huawei_mapped_read(context=None):
    def action():
        data = _json(context)
        feature = str(data.get("feature") or "").strip()
        if feature:
            return _call_device("mapped_read_feature", feature)
        path = str(data.get("path") or "").strip()
        if not path:
            raise ValueError("Informe feature ou path para a leitura Huawei.")
        return _call_device(
            "mapped_read_request",
            path,
            method=str(data.get("method") or "GET"),
            payload=data.get("payload") or {},
            referer=str(data.get("referer") or "/index.asp"),
            token_page=str(data.get("token_page")) if data.get("token_page") else None,
        )
    return _safe_call(action)


@api.post("/huawei/mapped/write")
def huawei_mapped_write(context=None):
    def action():
        data = _json(context)
        operation = str(data.get("operation") or "").strip()
        if operation:
            return _call_device(
                "mapped_write_feature",
                operation,
                data.get("config") or data.get("payload") or {},
            )
        path = str(data.get("path") or "").strip()
        if not path:
            raise ValueError("Informe operation ou path para a escrita Huawei.")
        return _call_device(
            "mapped_write_request",
            path,
            data.get("payload") or {},
            referer=str(data.get("referer") or "/index.asp"),
            token_page=str(data.get("token_page")) if data.get("token_page") else None,
            readback_path=(
                str(data.get("readback_path")) if data.get("readback_path") else None
            ),
            readback_method=str(data.get("readback_method") or "GET"),
            readback_payload=data.get("readback_payload") or {},
            readback_expect=data.get("readback_expect") or None,
        )
    return _safe_call(action)


@api.get("/discovery/bootstrap")
def discovery_bootstrap(context=None):
    return _safe_call(device_service.discovery_bootstrap)


@api.get("/multimodel/catalog")
def multimodel_catalog(context=None):
    return _safe_call(device_service.multimodel_catalog)


@api.post("/multimodel/diagnostic")
def multimodel_diagnostic(context=None):
    body = _json(context)
    requested = str(body.get("model") or "")[:50].strip()
    section = str(body.get("section") or "")[:32].strip() or None
    return _safe_call(
        device_service.multimodel_diagnostic,
        requested or None,
        section,
    )


@api.post("/multimodel/mesh")
def multimodel_mesh(context=None):
    model = str(_json(context).get("model") or "")[:50].strip()
    return _safe_call(device_service.multimodel_mesh, model or None)


@api.post("/multimodel/probe")
def multimodel_probe(context=None):
    body = _json(context)
    model = str(body.get("model") or "")[:50].strip()
    try:
        count = min(10, max(1, int(body.get("max_endpoints", 4))))
        start = min(1000, max(0, int(body.get("start", 0))))
    except (TypeError, ValueError):
        count, start = 4, 0
    return _safe_call(
        device_service.multimodel_probe,
        model or None,
        count,
        start,
    )


@api.get("/features/shape")
def feature_shape(context=None):
    feature = str(_query(context).get("feature") or "").strip()
    if not feature:
        return {"error": "Informe ?feature=.", "type": "validation"}
    return _safe_call(device_service.capability_shape, feature)


@api.get("/features/read")
def read_feature(context=None):
    query = _query(context)
    feature = str(query.get("feature") or "").strip()
    if not feature:
        return {"error": "Informe a capability em ?feature=.", "type": "validation"}
    return _safe_call(
        device_service.read_capability,
        feature,
        refresh=_bool(query.get("refresh")),
    )

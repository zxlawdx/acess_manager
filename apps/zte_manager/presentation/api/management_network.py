from .common import *


@api.get("/management/network")
def management_network_overview(context=None):
    return _safe_call(cpe_management_service.network_overview, device_service)


@api.get("/management/mesh")
def management_mesh_status(context=None):
    return _safe_call(cpe_management_service.mesh_status, device_service)


@api.post("/management/mesh/configure")
def management_mesh_configure(context=None):
    def action():
        data = _validated(MeshConfigRequest, context)
        return cpe_management_service.mesh_configure(
            device_service,
            data.model_dump(),
        )
    return _safe_call(action)


@api.post("/management/mesh/pair")
def management_mesh_pair(context=None):
    def action():
        data = _validated(MeshPairRequest, context)
        return cpe_management_service.mesh_pair(
            device_service,
            data.model_dump(),
        )
    return _safe_call(action)


@api.get("/management/qos")
def management_qos(context=None):
    return _safe_call(_call_device, "qos_management_status")


@api.post("/management/qos/save")
def management_qos_save(context=None):
    def action():
        data = _validated(QoSManagementRequest, context)
        return cpe_management_service.qos_save(device_service, data.model_dump())
    return _safe_call(action)


@api.post("/management/qos/delete")
def management_qos_delete(context=None):
    def action():
        data = _validated(QoSManagementRequest, context)
        if not data.id:
            raise ValueError("Informe o id da regra QoS.")
        return cpe_management_service.qos_delete(device_service, data.model_dump())
    return _safe_call(action)


@api.get("/management/firewall")
def management_firewall(context=None):
    return _safe_call(_call_device, "firewall_management_status")


@api.post("/management/firewall/update")
def management_firewall_update(context=None):
    def action():
        data = _validated(FirewallManagementRequest, context)
        return cpe_management_service.firewall_set(device_service, data.model_dump())
    return _safe_call(action)


@api.get("/management/firewall/rules")
def management_firewall_rules(context=None):
    return _safe_call(cpe_management_service.firewall_rules, device_service)


@api.post("/management/firewall/rules/save")
def management_firewall_rule_save(context=None):
    def action():
        data = _validated(FirewallRuleManagementRequest, context)
        return cpe_management_service.firewall_rule_save(
            device_service,
            data.model_dump(),
        )
    return _safe_call(action)


@api.post("/management/firewall/rules/delete")
def management_firewall_rule_delete(context=None):
    def action():
        data = _validated(FirewallRuleManagementRequest, context)
        return cpe_management_service.firewall_rule_delete(
            device_service,
            data.model_dump(),
        )
    return _safe_call(action)


@api.post("/management/firewall/filter-global")
def management_filter_global(context=None):
    def action():
        data = _validated(FilterGlobalManagementRequest, context)
        return cpe_management_service.filter_global_set(
            device_service,
            data.model_dump(),
        )
    return _safe_call(action)


@api.get("/management/sntp")
def management_sntp(context=None):
    return _safe_call(_call_device, "sntp_management_status")


@api.post("/management/sntp/update")
def management_sntp_update(context=None):
    def action():
        data = _validated(SNTPManagementRequest, context)
        return cpe_management_service.sntp_set(device_service, data.model_dump())
    return _safe_call(action)


@api.get("/tr069/providers")
def list_tr069_providers(context=None):
    return _safe_call(lambda: {"profiles": tr069_provider_profiles.list()})


@api.post("/tr069/providers/save")
def save_tr069_provider(context=None):
    def action():
        data = _validated(TR069ProviderSaveRequest, context)
        return tr069_provider_profiles.save(data.profile)
    return _safe_call(action)


@api.post("/tr069/providers/delete")
def delete_tr069_provider(context=None):
    def action():
        data = _validated(TR069ProviderDeleteRequest, context)
        return {"success": tr069_provider_profiles.delete(data.name)}
    return _safe_call(action)


@api.get("/tr069/setup")
def tr069_setup(context=None):
    return _safe_call(_call_device_read, "tr069_setup", context)


@api.post("/tr069/providers/apply")
def apply_tr069_provider(context=None):
    def action():
        data = _validated(TR069ProviderApplyRequest, context)
        if data.confirm is not True:
            raise ValueError("Confirme a aplicação dos parâmetros ACS.")
        return device_service.apply_tr069_provider(
            data.name,
            data.wan_name,
            password=data.password,
            connection_request_password=data.connection_request_password,
        )
    return _safe_call(action)


@api.get("/management/tr069")
def management_tr069(context=None):
    return _safe_call(_call_device_read, "tr069_management_status", context)


@api.post("/management/tr069/update")
def management_tr069_update(context=None):
    def action():
        data = _validated(TR069ManagementRequest, context)
        return cpe_management_service.tr069_set(device_service, data.model_dump())
    return _safe_call(action)


@api.get("/management/wan")
def management_wan(context=None):
    return _safe_call(_call_device, "wan_configurations")


@api.post("/management/wan/create")
def management_wan_create(context=None):
    def action():
        data = _validated(WANCreateRequest, context)
        return cpe_management_service.wan_create(device_service, data.model_dump())
    return _safe_call(action)


@api.post("/management/wan/update")
def management_wan_update(context=None):
    def action():
        data = _validated(WANManagementRequest, context)
        return cpe_management_service.wan_update(device_service, data.model_dump())
    return _safe_call(action)


@api.post("/management/wan/delete")
def management_wan_delete(context=None):
    def action():
        data = _validated(WANDeleteRequest, context)
        return cpe_management_service.wan_delete(device_service, data.model_dump())
    return _safe_call(action)


@api.post("/management/wan/action")
def management_wan_action(context=None):
    def action():
        data = _validated(WANActionRequest, context)
        return cpe_management_service.wan_action(device_service, data.model_dump())
    return _safe_call(action)


@api.post("/management/bridge")
def management_bridge(context=None):
    def action():
        data = _validated(BridgeModeRequest, context)
        return cpe_management_service.bridge(device_service, data.model_dump())
    return _safe_call(action)

"use strict";

import {createManagementApi} from "../services/management_api.js";

export function installManagementBridge(core = globalThis.AccessManagerCore) {
    if (!core?.apiClient?.apiRequest) {
        throw new Error("Management bridge requer AccessManagerCore.apiClient.");
    }
    const managementApi = createManagementApi(core.apiClient.apiRequest);

    // Temporary adapter for management.js. All existing actions immediately
    // stop talking to apiRequest directly; feature controllers can migrate to
    // named methods one by one without changing the backend contract.
    globalThis.managementRequest = (path, options = {}) =>
        managementApi.request(path, options);

    globalThis.AccessManagerManagement = Object.freeze({
        api: managementApi,
        bridge: "classic-management-request",
    });
    return managementApi;
}

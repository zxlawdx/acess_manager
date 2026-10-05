"use strict";

const PREFIX = "/management";

function safePath(path) {
    const value = String(path || "");
    if (!value.startsWith(PREFIX) || value.startsWith("//") || /:\/\//.test(value)) {
        throw new TypeError("ManagementApi aceita somente rotas /management do serviço local.");
    }
    return value;
}

export function createManagementApi(apiRequest) {
    if (typeof apiRequest !== "function") {
        throw new TypeError("ManagementApi requer apiRequest.");
    }

    function request(path, {method = "GET", body = null, ...options} = {}) {
        const endpoint = safePath(path);
        return apiRequest(endpoint, {
            method,
            expected: options.expected || "object",
            ...options,
            ...(body !== null ? {body: JSON.stringify(body)} : {}),
        });
    }

    return Object.freeze({
        request,
        inventory: () => request("/management/inventory"),
        profiles: () => request("/management/profiles"),
        agents: () => request("/management/agents"),
        incidents: () => request("/management/incidents"),
        backups: () => request("/management/backups"),
        firmware: () => request("/management/firmware"),
        acs: () => request("/management/acs"),
        async overview() {
            const [inventory, profiles, agents, incidents, backups, firmware, acs] =
                await Promise.all([
                    this.inventory(),
                    this.profiles(),
                    this.agents(),
                    this.incidents(),
                    this.backups(),
                    this.firmware(),
                    this.acs(),
                ]);
            return {inventory, profiles, agents, incidents, backups, firmware, acs};
        },
        syncInventory: body => request("/management/inventory/sync", {method: "POST", body}),
        saveProfile: body => request("/management/profiles/save", {method: "POST", body}),
        drift: body => request("/management/drift", {method: "POST", body}),
        remediateDrift: body => request("/management/drift/remediate", {method: "POST", body}),
        runBatch: body => request("/management/batch", {method: "POST", body}),
        batchStatus: () => request("/management/batch"),
        saveAgent: body => request("/management/agents/save", {method: "POST", body}),
        testAgent: body => request("/management/agents/test", {method: "POST", body}),
        restoreBackup: body => request("/management/backups/restore", {method: "POST", body}),
        upgradeFirmware: body => request("/management/firmware/upgrade", {method: "POST", body}),
        remoteOpen: body => request("/management/remote/open", {method: "POST", body}),
        remoteSessions: () => request("/management/remote/sessions"),
        gatewayCommand: body => request("/management/gateway/command", {method: "POST", body}),
        monitorStart: body => request("/management/monitor/start", {method: "POST", body}),
        monitorStatus: id => request(`/management/monitor/status?id=${encodeURIComponent(id)}`),
        monitorStop: body => request("/management/monitor/stop", {method: "POST", body}),
        correlateIncidents: body => request("/management/incidents/correlate", {method: "POST", body}),
        topology: deviceId => request(`/management/topology?device_id=${encodeURIComponent(deviceId)}`),
        mesh: () => request("/management/mesh"),
        configureMesh: body => request("/management/mesh/configure", {method: "POST", body}),
    });
}

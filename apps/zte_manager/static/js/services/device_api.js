"use strict";

export function createDeviceApi(apiRequest) {
    if (typeof apiRequest !== "function") {
        throw new TypeError("DeviceApi requer apiRequest.");
    }
    return Object.freeze({
        connect({ip, username, password, https = false, attendant = null, modelHint = null}) {
            return apiRequest("/connect", {
                method: "POST",
                expected: "object",
                operation: "Autenticando na ONT...",
                body: JSON.stringify({
                    ip,
                    username,
                    password,
                    https,
                    attendant,
                    model_hint: modelHint,
                }),
            });
        },
        disconnect() {
            return apiRequest("/disconnect", {
                method: "POST",
                operation: "Encerrando sessão...",
            });
        },
        status({silent = false} = {}) {
            return apiRequest("/connection/status", {
                expected: "object",
                silent,
                operation: "Recuperando sessão...",
            });
        },
        deviceStatus({refresh = false} = {}) {
            const query = refresh ? "?refresh=1" : "";
            return apiRequest(`/device/status${query}`, {expected: "object"});
        },
    });
}

"use strict";

export function createWifiApi(apiRequest) {
    if (typeof apiRequest !== "function") {
        throw new TypeError("WifiApi requer apiRequest.");
    }
    const post = (endpoint, body, options = {}) => apiRequest(endpoint, {
        method: "POST",
        expected: "object",
        ...options,
        body: JSON.stringify(body),
    });
    return Object.freeze({
        networks: ({revealPassword = false} = {}) => apiRequest(
            `/wifi/networks?reveal_password=${revealPassword ? 1 : 0}`,
            {expected: "object"},
        ),
        radios: () => apiRequest("/wifi/radios", {expected: "object"}),
        bandSteering: () => apiRequest("/wifi/band-steering", {expected: "object"}),
        schedule: () => apiRequest("/wifi/schedule", {expected: "object"}),
        updateSchedule: payload => post("/wifi/schedule/update", payload),
        updateRadio: payload => post("/wifi/radio/update", payload),
        updateSsid: payload => post("/wifi/ssid/update", payload),
        updateBandSteering: payload => post("/wifi/band-steering/update", payload),
        configureBandSteering: payload => post("/wifi/band-steering/configure", payload),
    });
}

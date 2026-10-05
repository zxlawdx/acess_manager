"use strict";

export function createWifiApi(apiRequest) {
    if (typeof apiRequest !== "function") {
        throw new TypeError("WifiApi requer apiRequest.");
    }
    return Object.freeze({
        schedule() {
            return apiRequest("/wifi/schedule", {expected: "object"});
        },
        updateSchedule(payload) {
            return apiRequest("/wifi/schedule/update", {
                method: "POST",
                expected: "object",
                body: JSON.stringify(payload),
            });
        },
    });
}

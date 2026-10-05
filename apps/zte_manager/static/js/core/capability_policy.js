"use strict";

const ALWAYS_AVAILABLE = new Set([
    "connection",
    "management",
]);

// A page may be backed by more than one capability. Any confirmed readable
// capability makes the page usable. Missing capability evidence is not turned
// into positive support.
const PAGE_REQUIREMENTS = Object.freeze({
    dashboard: ["wan", "wifi_basic", "wifi_radio", "optical"],
    wifi: ["wifi_basic", "wifi_radio"],
    wan: ["wan", "wan_config"],
    clients: ["user_devices", "ethernet_info", "wifi_basic"],
    diagnostics: ["diagnostics_webui", "speed_test"],
    supportDiagnostic: ["diagnostics_webui", "speed_test"],
    tr069: ["tr069_url"],
    device: ["optical", "account", "reboot"],
    advanced: [
        "dhcp", "dns", "dmz", "firewall_level", "ipv4_filter",
        "ipv6_firewall", "internet_control", "upnp", "mac_filter",
        "layer3", "lan_ipv4", "ipv6_lan", "sntp",
    ],
    // Profiles are local technician data. Applying them is capability-gated
    // separately; opening/editing the page must remain possible offline/read-only.
    profiles: [],
});

export function createCapabilityPolicy(deviceState) {
    if (!deviceState || typeof deviceState.snapshot !== "function"
            || typeof deviceState.supports !== "function") {
        throw new TypeError("CapabilityPolicy requer DeviceState.");
    }

    function page(pageName) {
        const name = String(pageName || "");
        if (ALWAYS_AVAILABLE.has(name)) return true;
        const device = deviceState.snapshot();
        if (!device.connected) return false;
        if (name === "profiles") return true;
        const requirements = PAGE_REQUIREMENTS[name];
        if (!requirements) return null;
        if (!deviceState.hasCapabilities()) return null;
        if (!requirements.length) return true;

        let sawExplicitFalse = false;
        for (const feature of requirements) {
            const value = deviceState.supports(feature, "read");
            if (value === true) return true;
            if (value === false) sawExplicitFalse = true;
        }
        // Once a capability catalog exists, no confirmed requirement means the
        // UI stays conservative. An explicit false and an absent feature both
        // prevent the page from claiming support.
        return sawExplicitFalse ? false : false;
    }

    function feature(feature, operation = "read") {
        return deviceState.supports(feature, operation);
    }

    return Object.freeze({page, feature, PAGE_REQUIREMENTS});
}

export {PAGE_REQUIREMENTS};

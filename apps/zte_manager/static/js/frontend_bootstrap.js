"use strict";

import "./core/bootstrap.js";
import {installManagementBridge} from "./management/legacy_bridge.js";
import {installAdvancedWifiFields} from "./advanced/wifi_radio_fields.js";

const core = globalThis.AccessManagerCore;
const managementApi = installManagementBridge(core);
const advancedWifi = installAdvancedWifiFields({
    deviceState: core.deviceState,
    escapeHtml: globalThis.escapeHtml,
});

// Temporary composition root used while the generated template still loads
// classic app/advanced/management scripts. The templates PR will load feature
// modules explicitly and remove this compatibility bootstrap.
globalThis.AccessManagerFrontend = Object.freeze({
    core,
    managementApi,
    advancedWifi,
    bridge: "classic-feature-composition",
});

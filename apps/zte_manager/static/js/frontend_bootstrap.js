"use strict";

import "./core/bootstrap.js";
import {installManagementBridge} from "./management/legacy_bridge.js";
import {installAdvancedWifiFields} from "./advanced/wifi_radio_fields.js";
import {installWifiScheduleFeature} from "./advanced/wifi_schedule.js";
import {createWifiApi} from "./services/wifi_api.js";

const core = globalThis.AccessManagerCore;
const managementApi = installManagementBridge(core);
const wifiApi = createWifiApi(core.apiClient.apiRequest);
const advancedWifi = installAdvancedWifiFields({
    deviceState: core.deviceState,
    escapeHtml: globalThis.escapeHtml,
});
const wifiSchedule = installWifiScheduleFeature({
    wifiApi,
    documentRef: globalThis.document,
    setBusy: globalThis.setBusy,
    showToast: globalThis.showToast,
    featureUnavailable: globalThis.featureUnavailable,
});

// Temporary composition root used while the generated template still loads
// classic app/advanced/management scripts. The templates PR will load feature
// modules explicitly and remove this compatibility bootstrap.
globalThis.AccessManagerFrontend = Object.freeze({
    core,
    managementApi,
    wifiApi,
    advancedWifi,
    wifiSchedule,
    bridge: "classic-feature-composition",
});

"use strict";

import "./core/bootstrap.js";
import {createManagementApi} from "./services/management_api.js";
import {installAdvancedWifiFields} from "./advanced/wifi_radio_fields.js";
import {installWifiScheduleFeature} from "./advanced/wifi_schedule.js";
import {createWifiApi} from "./services/wifi_api.js";

const core = globalThis.AccessManagerCore;
const managementApi = createManagementApi(core.apiClient.apiRequest);
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

// Compatibility for the remaining classic management.js controller. The
// request implementation is owned by ManagementApi; this single alias can be
// removed when that controller is migrated to ES modules.
globalThis.managementRequest = (path, options = {}) =>
    managementApi.request(path, options);

globalThis.AccessManagerFrontend = Object.freeze({
    core,
    managementApi,
    wifiApi,
    advancedWifi,
    wifiSchedule,
});

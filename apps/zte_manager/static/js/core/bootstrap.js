"use strict";

import {createApiClient} from "./api_client.js";
import {requestState} from "./request_state.js";
import {sessionState} from "./session_state.js";
import {deviceState} from "./device_state.js";
import {createCapabilityPolicy} from "./capability_policy.js";
import {createLoadingFeedback} from "../components/loading_feedback.js";
import {createDeviceApi} from "../services/device_api.js";

const apiClient = createApiClient({
    baseUrl: "/api",
    errors: globalThis.AccessManagerErrors || null,
    requestState,
});
const deviceApi = createDeviceApi(apiClient.apiRequest);
const capabilityPolicy = createCapabilityPolicy(deviceState);
const loadingFeedback = createLoadingFeedback({requestState});
const connectionStatusEpoch = new Map();
const legacyVendorSupportsPage = typeof globalThis.vendorSupportsPage === "function"
    ? globalThis.vendorSupportsPage
    : null;

apiClient.events.on("request:start", detail => {
    if (detail.endpoint === "/connection/status") {
        connectionStatusEpoch.set(detail.requestId, sessionState.captureEpoch());
    }
});

apiClient.events.on("request:success", detail => {
    if (detail.endpoint !== "/connection/status") return;
    const epoch = connectionStatusEpoch.get(detail.requestId);
    if (!sessionState.isCurrent(epoch)) return;
    if (detail.data?.connected === true) {
        sessionState.apply(detail.data, {epoch});
        deviceState.apply(detail.data);
    } else {
        sessionState.clear({epoch});
        deviceState.reset();
    }
});

apiClient.events.on("request:finish", detail => {
    connectionStatusEpoch.delete(detail.requestId);
});

apiClient.events.on("request:error", detail => {
    if (detail.silent) return;
    const error = detail.error;
    if (!globalThis.document?.dispatchEvent || !globalThis.CustomEvent || !error?.code) {
        return;
    }
    globalThis.document.dispatchEvent(new CustomEvent("am:api-failure", {
        detail: {
            code: error.code,
            kind: error.kind,
            status: error.status || 0,
            retryable: error.retryable,
        },
    }));
});

async function connectDevice(ip, username, password, https, attendant, modelHint = null) {
    const epoch = sessionState.beginTransition("connect");
    const response = await deviceApi.connect({
        ip,
        username,
        password,
        https,
        attendant,
        modelHint,
    });
    if (sessionState.isCurrent(epoch)) {
        sessionState.apply(response, {epoch});
        deviceState.apply(response);
    }
    return response;
}

async function disconnectDevice() {
    const epoch = sessionState.beginTransition("disconnect");
    try {
        await deviceApi.disconnect();
    } catch (error) {
        console.error("Erro ao desconectar:", error);
    } finally {
        if (sessionState.isCurrent(epoch)) {
            sessionState.clear({epoch});
            deviceState.reset();
        }
    }
}

function capabilityAwarePageSupport(pageName) {
    const decision = capabilityPolicy.page(pageName);
    if (decision !== null) return decision;
    // Providers that do not yet publish a capability catalog keep the legacy
    // navigation contract. Once capabilities exist, they are authoritative.
    return legacyVendorSupportsPage
        ? Boolean(legacyVendorSupportsPage(pageName))
        : false;
}

// Compatibility bridge while app.js consumers are migrated feature-by-feature.
// These globals keep the existing Vela screen operational, but their runtime
// implementation now belongs to explicit core/services modules.
globalThis.apiRequest = apiClient.apiRequest;
globalThis.connectONT = connectDevice;
globalThis.disconnectONT = disconnectDevice;
globalThis.vendorSupportsPage = capabilityAwarePageSupport;
globalThis.setBusy = loadingFeedback.setBusy;
globalThis.renderBusyOverlay = loadingFeedback.renderOverlay;
globalThis.startActionFeedback = loadingFeedback.startActionFeedback;
globalThis.updateRequestStatus = message => {
    if (message) loadingFeedback.reportError(new Error(String(message)));
    else loadingFeedback.renderStatus();
};

globalThis.AccessManagerCore = Object.freeze({
    apiClient,
    deviceApi,
    requestState,
    sessionState,
    deviceState,
    capabilityPolicy,
    loadingFeedback,
    bridge: "classic-app-runtime",
});

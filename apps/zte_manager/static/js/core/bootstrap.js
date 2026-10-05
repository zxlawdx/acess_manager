"use strict";

import {createApiClient} from "./api_client.js";
import {requestState} from "./request_state.js";
import {createLoadingFeedback} from "../components/loading_feedback.js";

const apiClient = createApiClient({
    baseUrl: "/api",
    errors: globalThis.AccessManagerErrors || null,
    requestState,
});

const loadingFeedback = createLoadingFeedback({requestState});

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

// Compatibility bridge while app.js consumers are migrated feature-by-feature.
// The global bindings created by classic app.js are mutable; replacing them
// here makes the extracted modules the runtime implementation before
// DOMContentLoaded executes the application bootstrap.
globalThis.apiRequest = apiClient.apiRequest;
globalThis.setBusy = loadingFeedback.setBusy;
globalThis.renderBusyOverlay = loadingFeedback.renderOverlay;
globalThis.startActionFeedback = loadingFeedback.startActionFeedback;
globalThis.updateRequestStatus = message => {
    if (message) loadingFeedback.reportError(new Error(String(message)));
    else loadingFeedback.renderStatus();
};

globalThis.AccessManagerCore = Object.freeze({
    apiClient,
    requestState,
    loadingFeedback,
    bridge: "classic-app-runtime",
});

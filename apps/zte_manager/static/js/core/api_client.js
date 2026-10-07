"use strict";

import {requestState as defaultRequestState} from "./request_state.js";

function createEventBus() {
    const listeners = new Map();
    return Object.freeze({
        on(type, listener) {
            if (typeof listener !== "function") {
                throw new TypeError("Listener técnico deve ser uma função.");
            }
            const group = listeners.get(type) || new Set();
            group.add(listener);
            listeners.set(type, group);
            return () => group.delete(listener);
        },
        emit(type, detail) {
            for (const listener of [...(listeners.get(type) || [])]) {
                try {
                    listener(detail);
                } catch (error) {
                    console.error("ApiClient event listener falhou:", error);
                }
            }
        },
    });
}

function fallbackError(message, status = 0) {
    const error = new Error(message || "Não foi possível concluir a operação.");
    error.status = status;
    if (status === 401) error.code = "AUTH_FAILED";
    else if (status === 403) error.code = "OPERATION_FORBIDDEN";
    else if (status === 404 || status === 405) error.code = "ROUTE_UNCONFIRMED";
    else if (status >= 500) error.code = "INTERNAL_ERROR";
    else error.code = "OPERATION_STATE";
    return error;
}

function abortSignal({signal, timeoutMs, setTimeoutImpl, clearTimeoutImpl}) {
    if (!signal && !(timeoutMs > 0)) {
        return {signal: undefined, dispose() {}};
    }
    const controller = new AbortController();
    let timer = null;
    let disposed = false;
    const abortFromCaller = () => controller.abort(signal?.reason);
    if (signal) {
        if (signal.aborted) controller.abort(signal.reason);
        else signal.addEventListener("abort", abortFromCaller, {once: true});
    }
    if (timeoutMs > 0) {
        timer = setTimeoutImpl(() => controller.abort("timeout"), timeoutMs);
    }
    return {
        signal: controller.signal,
        dispose() {
            if (disposed) return;
            disposed = true;
            if (timer !== null) clearTimeoutImpl(timer);
            signal?.removeEventListener?.("abort", abortFromCaller);
        },
    };
}

export function createApiClient({
    baseUrl = "/api",
    fetchImpl = globalThis.fetch?.bind(globalThis),
    errors = globalThis.AccessManagerErrors || null,
    requestState = defaultRequestState,
    setTimeoutImpl = globalThis.setTimeout?.bind(globalThis),
    clearTimeoutImpl = globalThis.clearTimeout?.bind(globalThis),
} = {}) {
    if (typeof fetchImpl !== "function") {
        throw new TypeError("ApiClient requer uma implementação de fetch.");
    }
    const events = createEventBus();
    let requestSequence = 0;

    async function apiRequest(endpoint, options = {}) {
        const requestId = ++requestSequence;
        const silent = options.silent === true;
        const expected = options.expected;
        const timeoutMs = Number(options.timeoutMs || 0);
        const operation = options.operation || "Consultando equipamento...";
        const stateId = silent ? null : requestState.begin({endpoint, operation});
        const abort = abortSignal({
            signal: options.signal,
            timeoutMs,
            setTimeoutImpl,
            clearTimeoutImpl,
        });
        const {
            expected: _expected,
            silent: _silent,
            timeoutMs: _timeoutMs,
            operation: _operation,
            signal: _callerSignal,
            ...fetchOptions
        } = options;
        const config = {
            method: "GET",
            headers: {
                "Content-Type": "application/json",
                ...(options.headers || {}),
            },
            ...fetchOptions,
        };
        if (abort.signal) config.signal = abort.signal;
        const detail = Object.freeze({requestId, endpoint, silent, method: config.method});
        events.emit("request:start", detail);

        try {
            const response = await fetchImpl(`${baseUrl}${endpoint}`, config);
            const contentType = response.headers?.get?.("content-type") || "";
            let data = null;
            if (response.status !== 204) {
                if (contentType.includes("application/json")) {
                    try {
                        data = await response.json();
                    } catch (parseError) {
                        if (response.ok) {
                            throw errors
                                ? new errors.OperationError("INVALID_DEVICE_RESPONSE")
                                : fallbackError(
                                    "A resposta do equipamento não pôde ser interpretada.",
                                    response.status,
                                );
                        }
                    }
                } else {
                    try {
                        data = await response.text();
                    } catch {
                        data = null;
                    }
                }
            }

            // Ping/traceroute are observations, not mutations. A completed
            // diagnostic may legitimately report success:false (for example
            // 100% packet loss or max-hop exceeded) and the operator still
            // needs the measured result. Transport/backend failures keep an
            // explicit `error` and continue through the normal error policy.
            const diagnosticObservation = (
                endpoint === "/diagnostics/ping"
                || endpoint === "/diagnostics/traceroute"
            );
            const semanticFailure = data && typeof data === "object"
                && !Array.isArray(data)
                && (
                    data.error
                    || (data.success === false && !diagnosticObservation)
                );
            if (!response.ok || semanticFailure) {
                if (errors) {
                    const payload = data && typeof data === "object"
                        ? data : {error: ""};
                    throw errors.fromPayload(
                        payload.error
                            ? payload
                            : {...payload, error: payload.message || ""},
                        {status: response.status},
                    );
                }
                throw fallbackError(
                    data && typeof data === "object"
                        ? (data.error || data.message || "")
                        : "Falha na comunicação com o serviço.",
                    response.status,
                );
            }

            if (expected === "object") {
                if (errors) errors.ensureObject(data);
                else if (!data || typeof data !== "object" || Array.isArray(data)) {
                    throw fallbackError(
                        "A resposta do equipamento não pôde ser interpretada.",
                        response.status,
                    );
                }
            }

            if (stateId !== null) requestState.finish(stateId);
            events.emit("request:success", {
                ...detail,
                status: response.status,
                data,
            });
            return data;
        } catch (error) {
            let friendly = error;
            if (errors) friendly = errors.fromThrown(error);
            else if (error?.name === "AbortError") {
                friendly = fallbackError("A consulta excedeu o tempo de resposta.");
                friendly.name = "AbortError";
                friendly.code = "TIMEOUT";
            } else if (!(error instanceof Error)) {
                friendly = fallbackError(String(error || "Falha na operação."));
            }
            if (stateId !== null) requestState.fail(stateId, friendly);
            events.emit("request:error", {...detail, error: friendly});
            throw friendly;
        } finally {
            abort.dispose();
            events.emit("request:finish", detail);
        }
    }

    return Object.freeze({apiRequest, events, baseUrl});
}

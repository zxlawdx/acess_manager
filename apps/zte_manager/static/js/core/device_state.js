"use strict";

function cloneCapabilities(value) {
    if (!value || typeof value !== "object" || Array.isArray(value)) return {};
    return Object.fromEntries(Object.entries(value).map(([key, item]) => [
        key,
        item && typeof item === "object" && !Array.isArray(item)
            ? {...item}
            : item,
    ]));
}

function readPath(source, path) {
    return String(path || "").split(".").filter(Boolean).reduce(
        (current, key) => current && typeof current === "object"
            ? current[key]
            : undefined,
        source,
    );
}

export class DeviceState {
    constructor() {
        this._listeners = new Set();
        this.reset({emit: false});
    }

    snapshot() {
        return Object.freeze({
            connected: this._connected,
            vendor: this._vendor,
            model: this._model,
            host: this._host,
            provider: this._provider,
            profile: this._profile,
            capabilities: cloneCapabilities(this._capabilities),
            writesEnabled: this._writesEnabled,
            modelVerified: this._modelVerified,
            sessionRevision: this._sessionRevision,
        });
    }

    subscribe(listener) {
        if (typeof listener !== "function") {
            throw new TypeError("DeviceState listener deve ser uma função.");
        }
        this._listeners.add(listener);
        listener(this.snapshot());
        return () => this._listeners.delete(listener);
    }

    apply(status) {
        const value = status && typeof status === "object" ? status : {};
        this._connected = value.connected === true || value.success === true;
        this._vendor = value.vendor || this._vendor || null;
        this._model = value.model || value.device?.modelo || this._model || null;
        this._host = value.host || this._host || null;
        this._provider = value.provider || this._provider || null;
        this._profile = value.profile || value.adapter || this._profile || null;
        if (value.capabilities && typeof value.capabilities === "object") {
            this._capabilities = cloneCapabilities(value.capabilities);
        }
        if (value.writes_enabled !== undefined) {
            this._writesEnabled = value.writes_enabled !== false;
        }
        if (value.model_verified !== undefined) {
            this._modelVerified = value.model_verified === true;
        }
        this._sessionRevision = value.session_revision || this._sessionRevision || null;
        this._emit();
        return this.snapshot();
    }

    reset({emit = true} = {}) {
        this._connected = false;
        this._vendor = null;
        this._model = null;
        this._host = null;
        this._provider = null;
        this._profile = null;
        this._capabilities = {};
        this._writesEnabled = true;
        this._modelVerified = false;
        this._sessionRevision = null;
        if (emit) this._emit();
    }

    capability(path) {
        return readPath(this._capabilities, path);
    }

    hasCapabilities() {
        return Object.keys(this._capabilities).length > 0;
    }

    supports(feature, operation = "read") {
        const capability = this.capability(feature);
        if (capability === true) return true;
        if (capability === false) return false;
        if (!capability || typeof capability !== "object") return null;
        const direct = capability[operation];
        if (direct === true || direct === false) return direct;
        if (operation === "read" && capability.supported !== undefined) {
            return capability.supported === true;
        }
        return null;
    }

    _emit() {
        const snapshot = this.snapshot();
        for (const listener of [...this._listeners]) {
            try {
                listener(snapshot);
            } catch (error) {
                console.error("DeviceState listener falhou:", error);
            }
        }
    }
}

export const deviceState = new DeviceState();

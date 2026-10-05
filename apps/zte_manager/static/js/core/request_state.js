"use strict";

export class RequestState {
    constructor() {
        this._requests = new Map();
        this._listeners = new Set();
        this._busy = false;
        this._busyText = "Processando...";
        this._lastOperation = "Consultando equipamento...";
        this._lastError = null;
        this._sequence = 0;
    }

    snapshot() {
        return Object.freeze({
            pending: this._requests.size,
            busy: this._busy,
            busyText: this._busyText,
            lastOperation: this._lastOperation,
            lastError: this._lastError,
        });
    }

    subscribe(listener) {
        if (typeof listener !== "function") {
            throw new TypeError("RequestState listener deve ser uma função.");
        }
        this._listeners.add(listener);
        listener(this.snapshot());
        return () => this._listeners.delete(listener);
    }

    begin({endpoint = "", operation = "Consultando equipamento..."} = {}) {
        const id = ++this._sequence;
        this._requests.set(id, {endpoint, operation});
        if (operation) this._lastOperation = String(operation);
        this._emit();
        return id;
    }

    finish(id) {
        this._requests.delete(id);
        this._emit();
    }

    fail(id, error) {
        this._requests.delete(id);
        this._lastError = error instanceof Error
            ? error
            : new Error(String(error || "Falha na operação."));
        this._emit();
    }

    clearError() {
        if (this._lastError === null) return;
        this._lastError = null;
        this._emit();
    }

    setBusy(busy, text = "Processando...") {
        this._busy = Boolean(busy);
        if (this._busy && text) {
            this._busyText = String(text);
            this._lastOperation = String(text);
        }
        this._emit();
    }

    setLastOperation(text) {
        const value = String(text || "").trim();
        if (!value) return;
        this._lastOperation = value;
        this._emit();
    }

    reset() {
        this._requests.clear();
        this._busy = false;
        this._busyText = "Processando...";
        this._lastOperation = "Consultando equipamento...";
        this._lastError = null;
        this._emit();
    }

    _emit() {
        const snapshot = this.snapshot();
        for (const listener of [...this._listeners]) {
            try {
                listener(snapshot);
            } catch (error) {
                console.error("RequestState listener falhou:", error);
            }
        }
    }
}

export const requestState = new RequestState();

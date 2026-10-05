"use strict";

export class SessionState {
    constructor() {
        this._listeners = new Set();
        this._epoch = 0;
        this._authenticated = false;
        this._attendant = null;
        this._sessionRevision = null;
        this._transition = null;
    }

    snapshot() {
        return Object.freeze({
            epoch: this._epoch,
            authenticated: this._authenticated,
            attendant: this._attendant,
            sessionRevision: this._sessionRevision,
            transition: this._transition,
        });
    }

    subscribe(listener) {
        if (typeof listener !== "function") {
            throw new TypeError("SessionState listener deve ser uma função.");
        }
        this._listeners.add(listener);
        listener(this.snapshot());
        return () => this._listeners.delete(listener);
    }

    beginTransition(kind = "session") {
        this._epoch += 1;
        this._transition = String(kind || "session");
        this._emit();
        return this._epoch;
    }

    captureEpoch() {
        return this._epoch;
    }

    isCurrent(epoch) {
        return Number(epoch) === this._epoch;
    }

    apply(status, {epoch = this._epoch} = {}) {
        if (!this.isCurrent(epoch)) return false;
        const value = status && typeof status === "object" ? status : {};
        this._authenticated = value.connected === true || value.success === true;
        this._attendant = value.attendant || this._attendant || null;
        this._sessionRevision = value.session_revision || this._sessionRevision || null;
        this._transition = null;
        this._emit();
        return true;
    }

    clear({epoch = this._epoch} = {}) {
        if (!this.isCurrent(epoch)) return false;
        this._authenticated = false;
        this._attendant = null;
        this._sessionRevision = null;
        this._transition = null;
        this._emit();
        return true;
    }

    reset() {
        this._epoch += 1;
        this._authenticated = false;
        this._attendant = null;
        this._sessionRevision = null;
        this._transition = null;
        this._emit();
        return this._epoch;
    }

    _emit() {
        const snapshot = this.snapshot();
        for (const listener of [...this._listeners]) {
            try {
                listener(snapshot);
            } catch (error) {
                console.error("SessionState listener falhou:", error);
            }
        }
    }
}

export const sessionState = new SessionState();

import test from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs";
import vm from "node:vm";

const root = new URL("../", import.meta.url);
const source = path => fs.readFileSync(new URL(path, root), "utf8");
const dataUrl = value => "data:text/javascript;base64," + Buffer.from(value).toString("base64");

const requestStateSource = source("apps/zte_manager/static/js/core/request_state.js");
const requestStateUrl = dataUrl(requestStateSource);
const apiClientSource = source("apps/zte_manager/static/js/core/api_client.js")
    .replace("./request_state.js", requestStateUrl);
const loadingSource = source("apps/zte_manager/static/js/components/loading_feedback.js");
const sessionSource = source("apps/zte_manager/static/js/core/session_state.js");
const deviceSource = source("apps/zte_manager/static/js/core/device_state.js");
const deviceApiSource = source("apps/zte_manager/static/js/services/device_api.js");

const {RequestState} = await import(requestStateUrl);
const {createApiClient} = await import(dataUrl(apiClientSource));
const {createLoadingFeedback} = await import(dataUrl(loadingSource));
const {SessionState} = await import(dataUrl(sessionSource));
const {DeviceState} = await import(dataUrl(deviceSource));
const {createDeviceApi} = await import(dataUrl(deviceApiSource));

function errorFacade() {
    const context = {window: {}};
    vm.runInNewContext(
        source("apps/zte_manager/static/js/core/api_errors.js"),
        context,
    );
    return context.window.AccessManagerErrors;
}

function response(status, body, contentType = "application/json") {
    return {
        ok: status >= 200 && status < 300,
        status,
        headers: {get: key => key === "content-type" ? contentType : null},
        async json() {
            if (body instanceof Error) throw body;
            return body;
        },
        async text() { return String(body ?? ""); },
    };
}

function harness(fetchImpl) {
    const state = new RequestState();
    const events = [];
    const client = createApiClient({
        fetchImpl,
        errors: errorFacade(),
        requestState: state,
    });
    for (const name of ["request:start", "request:success", "request:error", "request:finish"]) {
        client.events.on(name, detail => events.push([name, detail]));
    }
    return {state, events, request: client.apiRequest};
}

test("ApiClient handles success and exposes normalized data to technical events", async () => {
    const ok = harness(async () => response(200, {model: "F6600P"}));
    assert.deepEqual(await ok.request("/device/status", {expected: "object"}), {model: "F6600P"});
    assert.equal(ok.state.snapshot().pending, 0);
    assert.equal(ok.events[0][0], "request:start");
    const success = ok.events.find(([name]) => name === "request:success");
    assert.deepEqual(success[1].data, {model: "F6600P"});
    assert.equal(ok.events.at(-1)[0], "request:finish");

    const empty = harness(async () => response(204, null, ""));
    assert.equal(await empty.request("/disconnect", {method: "POST"}), null);
});

test("invalid JSON on a successful response is INVALID_DEVICE_RESPONSE", async () => {
    const h = harness(async () => response(200, new SyntaxError("raw router page")));
    await assert.rejects(h.request("/wan/status"), error => {
        assert.equal(error.code, "INVALID_DEVICE_RESPONSE");
        assert.doesNotMatch(error.message, /raw router page/i);
        return true;
    });
    assert.equal(h.state.snapshot().pending, 0);
});

for (const [status, code] of [
    [401, "AUTH_FAILED"],
    [403, "OPERATION_FORBIDDEN"],
    [404, "ROUTE_UNCONFIRMED"],
    [405, "ROUTE_UNCONFIRMED"],
    [500, "INTERNAL_ERROR"],
]) {
    test(`HTTP ${status} maps to ${code}`, async () => {
        const h = harness(async () => response(status, "private router body", "text/html"));
        await assert.rejects(h.request("/private"), error => {
            assert.equal(error.code, code);
            assert.doesNotMatch(error.message, /private router body/i);
            return true;
        });
    });
}

test("backend semantic error envelope rejects even with HTTP 200", async () => {
    const h = harness(async () => response(200, {
        success: false,
        code: "OPERATION_PARTIAL",
        completed: 1,
        total: 3,
        error: "POST /router?token=PRIVATE",
    }));
    await assert.rejects(h.request("/profiles/apply"), error => {
        assert.equal(error.code, "OPERATION_PARTIAL");
        assert.match(error.message, /1 de 3/);
        assert.doesNotMatch(error.message, /PRIVATE|POST|token/i);
        return true;
    });
});

test("timeout aborts fetch and preserves AbortError/timeout contract", async () => {
    const h = harness((_url, options) => new Promise((_resolve, reject) => {
        options.signal.addEventListener("abort", () => {
            reject(new DOMException("aborted", "AbortError"));
        }, {once: true});
    }));
    await assert.rejects(h.request("/slow", {timeoutMs: 5}), error => {
        assert.equal(error.name, "AbortError");
        assert.equal(error.code, "TIMEOUT");
        return true;
    });
    assert.equal(h.state.snapshot().pending, 0);
});

test("caller AbortSignal is forwarded without a second request", async () => {
    const controller = new AbortController();
    let calls = 0;
    const h = harness((_url, options) => new Promise((_resolve, reject) => {
        calls += 1;
        options.signal.addEventListener("abort", () => {
            reject(new DOMException("aborted", "AbortError"));
        }, {once: true});
    }));
    const pending = h.request("/cancel", {signal: controller.signal});
    controller.abort();
    await assert.rejects(pending, error => error.name === "AbortError");
    assert.equal(calls, 1);
});

test("silent request emits technical events but does not occupy RequestState", async () => {
    const h = harness(async () => response(200, {devices: []}));
    const seen = [];
    h.state.subscribe(snapshot => seen.push(snapshot.pending));
    const result = await h.request("/management/inventory", {
        expected: "object",
        silent: true,
    });
    assert.deepEqual(result, {devices: []});
    assert.deepEqual(seen, [0]);
    assert.equal(h.events[0][1].silent, true);
});

test("RequestState keeps request, busy and last operation as independent state", () => {
    const state = new RequestState();
    const snapshots = [];
    state.subscribe(value => snapshots.push(value));
    const id = state.begin({endpoint: "/wifi/radios", operation: "Lendo Wi-Fi..."});
    state.setBusy(true, "Aplicando rádio...");
    assert.equal(state.snapshot().pending, 1);
    assert.equal(state.snapshot().busy, true);
    assert.equal(state.snapshot().lastOperation, "Aplicando rádio...");
    state.finish(id);
    assert.equal(state.snapshot().pending, 0);
    assert.equal(state.snapshot().busy, true);
    state.setBusy(false);
    assert.equal(state.snapshot().busy, false);
    assert.ok(snapshots.length >= 5);
});

test("SessionState rejects stale restore responses after a newer login transition", () => {
    const state = new SessionState();
    const restoreEpoch = state.beginTransition("restore");
    const loginEpoch = state.beginTransition("connect");
    assert.equal(state.apply({
        connected: true,
        attendant: "old",
        session_revision: "old-revision",
    }, {epoch: restoreEpoch}), false);
    assert.equal(state.snapshot().authenticated, false);
    assert.equal(state.apply({
        success: true,
        attendant: "law",
        session_revision: "new-revision",
    }, {epoch: loginEpoch}), true);
    assert.equal(state.snapshot().authenticated, true);
    assert.equal(state.snapshot().attendant, "law");
    assert.equal(state.snapshot().sessionRevision, "new-revision");
});

test("SessionState logout invalidates earlier asynchronous work", () => {
    const state = new SessionState();
    const loginEpoch = state.beginTransition("connect");
    state.apply({success: true, attendant: "law"}, {epoch: loginEpoch});
    const staleEpoch = state.captureEpoch();
    const logoutEpoch = state.beginTransition("disconnect");
    assert.equal(state.clear({epoch: logoutEpoch}), true);
    assert.equal(state.snapshot().authenticated, false);
    assert.equal(state.apply({connected: true, attendant: "stale"}, {epoch: staleEpoch}), false);
    assert.equal(state.snapshot().authenticated, false);
});

test("DeviceState exposes capabilities with conservative unknown fallback", () => {
    const state = new DeviceState();
    state.apply({
        connected: true,
        vendor: "huawei",
        model: "EG8041X7-10",
        host: "192.168.100.1",
        writes_enabled: false,
        model_verified: true,
        capabilities: {
            wifi: {read: true, write: true},
            ipv4_filter: {read: false, create: false},
            diagnostics: true,
        },
    });
    assert.equal(state.supports("wifi", "read"), true);
    assert.equal(state.supports("wifi", "write"), true);
    assert.equal(state.supports("ipv4_filter", "read"), false);
    assert.equal(state.supports("diagnostics"), true);
    assert.equal(state.supports("mesh"), null);
    assert.equal(state.snapshot().writesEnabled, false);
    const external = state.snapshot().capabilities;
    external.wifi.read = false;
    assert.equal(state.supports("wifi", "read"), true);
    state.reset();
    assert.equal(state.snapshot().connected, false);
    assert.equal(state.supports("wifi", "read"), null);
});

test("DeviceApi owns connection endpoints and request payload construction", async () => {
    const calls = [];
    const api = createDeviceApi(async (endpoint, options = {}) => {
        calls.push({endpoint, options});
        return endpoint === "/connection/status"
            ? {connected: true}
            : {success: true};
    });
    await api.connect({
        ip: "192.168.100.1",
        username: "telecomadmin",
        password: "secret",
        https: false,
        attendant: "law",
        modelHint: "EG8041X7-10",
    });
    assert.equal(calls[0].endpoint, "/connect");
    const payload = JSON.parse(calls[0].options.body);
    assert.deepEqual(payload, {
        ip: "192.168.100.1",
        username: "telecomadmin",
        password: "secret",
        https: false,
        attendant: "law",
        model_hint: "EG8041X7-10",
    });
    assert.equal(calls[0].options.expected, "object");
    await api.status({silent: true});
    assert.equal(calls[1].endpoint, "/connection/status");
    assert.equal(calls[1].options.silent, true);
    await api.disconnect();
    assert.equal(calls[2].endpoint, "/disconnect");
    assert.equal(calls[2].options.method, "POST");
});

function fakeElement() {
    const classes = new Set(["hidden"]);
    return {
        textContent: "",
        attrs: {},
        classList: {
            toggle(name, active) { active ? classes.add(name) : classes.delete(name); },
            add(name) { classes.add(name); },
            remove(name) { classes.delete(name); },
            contains(name) { return classes.has(name); },
        },
        setAttribute(name, value) { this.attrs[name] = value; },
    };
}

test("LoadingFeedback is a DOM observer, not the owner of request lifecycle", () => {
    const state = new RequestState();
    const overlay = fakeElement();
    const label = fakeElement();
    const indicator = fakeElement();
    const doc = {
        getElementById(id) {
            return {busyOverlay: overlay, busyText: label,
                requestStatusIndicator: indicator}[id] || null;
        },
    };
    const timers = [];
    const loading = createLoadingFeedback({
        requestState: state,
        documentRef: doc,
        setTimeoutImpl(fn) { timers.push(fn); return timers.length; },
        clearTimeoutImpl() {},
        now: () => 100,
    });
    const id = state.begin({operation: "Lendo equipamento..."});
    assert.equal(overlay.classList.contains("hidden"), false);
    assert.equal(label.textContent, "Lendo equipamento...");
    assert.match(indicator.textContent, /1 requisição/);
    state.finish(id);
    assert.equal(state.snapshot().pending, 0);
    loading.setBusy(true, "Aplicando...");
    assert.equal(label.textContent, "Aplicando...");
    loading.setBusy(false);
    loading.dispose();
});

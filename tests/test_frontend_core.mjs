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

const {RequestState} = await import(requestStateUrl);
const {createApiClient} = await import(dataUrl(apiClientSource));
const {createLoadingFeedback} = await import(dataUrl(loadingSource));

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

test("ApiClient handles success and 204 without leaking transport details", async () => {
    const ok = harness(async () => response(200, {model: "F6600P"}));
    assert.deepEqual(await ok.request("/device/status", {expected: "object"}), {model: "F6600P"});
    assert.equal(ok.state.snapshot().pending, 0);
    assert.equal(ok.events[0][0], "request:start");
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

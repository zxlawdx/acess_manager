/* Regressão: recuperação da sessão deve buscar dados, sem sobrescrever novo login. */
const assert = require("node:assert/strict");
const fs = require("node:fs");
const vm = require("node:vm");
const source = fs.readFileSync("apps/zte_manager/static/js/app.js", "utf8");
const begin = source.indexOf("async function restoreDesktopSession() {");
const end = source.indexOf("function initZteAutomatic()", begin);
assert.ok(begin >= 0 && end > begin);

function harness(status, isReadOnly = false) {
    const calls = [];
    const nodes = {};
    for (const id of ["connectedHost", "connectedAttendant", "connectedModel",
        "dashboardProfileName", "profileAttendant", "topDeviceChip",
        "connectionResult"]) {
        nodes[id] = {
            textContent: "", className: "",
            classList: { remove() {}, add() {} }
        };
    }
    const ctx = {
        console, sessionEpoch: 0, ontConnected: false, routerWriteEnabled: true,
        currentHost: null, currentAttendant: null,
        CustomEvent: class { constructor(type) { this.type = type; } },
        document: {
            getElementById: id => nodes[id],
            querySelector: () => ({ id: "page-connection" }),
            dispatchEvent: event => calls.push("event:" + event.type)
        },
        apiRequest: async endpoint => {
            calls.push(endpoint);
            assert.equal(endpoint, "/connection/status");
            return { ...status, writes_enabled: !isReadOnly };
        },
        openPage: page => calls.push("page:" + page),
        setConnectionStatus: connected => {
            ctx.ontConnected = connected;
            calls.push("connected:" + connected);
        },
        loadProfile: async () => { calls.push("profile"); },
        loadAll: async () => {
            calls.push("data");
            return { essentialLoaded: 3, failed: [] };
        },
        showToast: () => {}
    };
    vm.createContext(ctx);
    vm.runInContext(source.slice(begin, end), ctx);
    return { ctx, calls, nodes };
}

(async () => {
    const connected = harness({ connected: true, host: "192.0.2.30",
        attendant: "tester", model: "F6600P" });
    await vm.runInContext("restoreDesktopSession()", connected.ctx);
    assert.ok(connected.calls.includes("page:dashboard"));
    assert.ok(connected.calls.includes("profile"));
    assert.ok(connected.calls.includes("data"));
    assert.equal(connected.nodes.connectedModel.textContent, "F6600P");

    const readonly = harness({ connected: true, host: "192.0.2.31" }, true);
    await vm.runInContext("restoreDesktopSession()", readonly.ctx);
    assert.ok(readonly.calls.includes("page:advanced"));
    assert.ok(!readonly.calls.includes("data"),
        "Firmware experimental não executa leituras ThinkLua tradicionais");

    const disconnected = harness({ connected: false });
    await vm.runInContext("restoreDesktopSession()", disconnected.ctx);
    assert.ok(disconnected.calls.includes("page:connection"));
    assert.ok(!disconnected.calls.includes("data"));

    let finish;
    const race = harness({ connected: true });
    race.ctx.apiRequest = () => new Promise(resolve => { finish = resolve; });
    const restoring = vm.runInContext("restoreDesktopSession()", race.ctx);
    race.ctx.sessionEpoch++;
    finish({ connected: true, host: "192.0.2.40" });
    await restoring;
    assert.ok(!race.calls.includes("data"));
    assert.ok(!race.calls.includes("connected:true"));
    console.log("Sessão: restauração completa, read-only, offline e corrida OK");
})().catch(error => { console.error(error); process.exitCode = 1; });

/* Reproduz o bug: capability GET antigo pode atrasar e o modelo não aparecia. */
const fs = require("node:fs");
const vm = require("node:vm");
const assert = require("node:assert/strict");
const js = fs.readFileSync("apps/zte_manager/static/js/advanced.js", "utf8");
const extract = (from, to) => {
    const a = js.indexOf(from), b = js.indexOf(to, a + from.length);
    assert.ok(a >= 0 && b > a, from);
    return js.slice(a, b);
};
const sources = [
    extract("let discoveryBootPromise = null;", "// Faz uma coleta pequena"),
    extract("async function loadOperationsConsoleInternal() {",
        "window.startQuickProbe =")
];
const elements = {};
const fakeSelect = () => ({
    dataset: {},
    value: "",
    options: [],
    replaceChildren(...children) { this.options = [...children]; },
    add(option) { this.options.push(option); }
});
elements.multimodelSelect = fakeSelect();
for (const id of ["trackerDiscoveryStatus", "adapterBadge", "trackerCapabilityGrid"]) {
    elements[id] = { textContent: "", innerHTML: "" };
}
const calls = [];
const context = {
    console,
    Promise,
    currentHost: "192.0.2.25",
    ontConnected: true,
    routerWriteEnabled: true,
    advancedState: { loaded: false },
    document: { getElementById: id => elements[id] || null },
    Option: function(label, value) { this.label = label; this.value = value; },
    discoveryRequest: async (endpoint) => {
        calls.push(endpoint);
        assert.equal(endpoint, "/discovery/bootstrap");
        return {
            connected: true,
            model: "F6600P",
            catalog: { models: [
                { model: "F6600P", family: "f6640", protocol: "thinklua",
                  candidate_features: ["wifi_clients", "lan_clients"] }
            ] }
        };
    },
    apiRequest: async () => { throw Error("Não deveria chamar API antiga"); },
    renderTrackerDiscovery: data => {
        calls.push("render:" + data.model);
        elements.trackerCapabilityGrid.textContent = JSON.stringify(data);
    },
    autoDiscoverTracker: async () => { calls.push("autoProbe"); },
    loadCapabilityCatalog: async () => {
        calls.push("capability");
        return new Promise(() => {}); // reproduz backend legado bloqueado
    },
    loadDhcpOperations: async () => {},
    loadNatOperations: async () => {},
    loadHistory: async () => {}
};
vm.createContext(context);
vm.runInContext(sources.join("\n"), context);
(async () => {
    const pending = vm.runInContext("loadOperationsConsoleInternal()", context);
    await new Promise(resolve => setTimeout(resolve, 35));
    assert.equal(elements.multimodelSelect.value, "F6600P");
    assert.equal(elements.multimodelSelect.dataset.loaded, "true");
    assert.ok(calls.indexOf("render:F6600P") >= 0);
    assert.ok(calls.indexOf("autoProbe") < calls.indexOf("capability"));
    assert.match(elements.trackerCapabilityGrid.textContent, /wifi_clients/);
    // pending intencionalmente não aguardado: o bootstrap deve renderizar
    // mesmo que uma rota de capabilities antiga nunca conclua.
    void pending;
    console.log("Descoberta inicial independe de APIs legadas bloqueadas");
})().catch(err => { console.error(err); process.exitCode = 1; });

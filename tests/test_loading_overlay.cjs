/* Regressão: o modal não pode sumir antes do backend terminar. */
const assert = require("node:assert/strict");
const fs = require("node:fs");
const vm = require("node:vm");
const source = fs.readFileSync(
    "apps/zte_manager/static/js/app.js", "utf8"
).split("function updateRequestStatus(")[0];
const fullSource = fs.readFileSync("apps/zte_manager/static/js/app.js", "utf8");
const setBusySource = fullSource.slice(
    fullSource.indexOf("function setBusy("),
    fullSource.indexOf("function setConnectionStatus(")
);

const ids = {};
function element(id) {
    if (ids[id]) return ids[id];
    const values = new Set(["hidden"]);
    const obj = {
        textContent: "",
        attributes: {},
        classList: {
            toggle(name, enabled) {
                if (enabled) values.add(name); else values.delete(name);
            },
            contains(name) { return values.has(name); }
        },
        setAttribute(key, value) { this.attributes[key] = value; }
    };
    ids[id] = obj;
    return obj;
}
const events = {};
const timeouts = [];
const sandbox = {
    console, Date, 
    document: {
        getElementById: element,
        addEventListener(name, fn) { events[name] = fn; }
    },
    setTimeout(fn, delay) {
        timeouts.push({ fn, delay });
        return timeouts.length;
    },
    clearTimeout() {}
};
vm.createContext(sandbox);
vm.runInContext(source + '\n' + setBusySource, sandbox);

function isVisible() {
    return !element("busyOverlay").classList.contains("hidden");
}
const action = {
    disabled: false,
    textContent: "Detectar recursos",
    matches() { return false; }
};
events.click({ target: { closest() { return action; } } });
assert.equal(isVisible(), true, "Clique precisa mostrar loading imediato");
assert.match(element("busyText").textContent, /Detectar recursos/);

vm.runInContext("pendingApiRequests = 2; renderBusyOverlay();", sandbox);
vm.runInContext('setBusy(true, "Processando menus...")', sandbox);
vm.runInContext("setBusy(false)", sandbox);
assert.equal(isVisible(), true, "setBusy(false) não encerra requisições pendentes");
assert.match(element("busyText").textContent, /Processando menus/);

vm.runInContext("pendingApiRequests = 1; renderBusyOverlay();", sandbox);
assert.equal(isVisible(), true, "O segundo request mantém o modal");

vm.runInContext(
    "pendingApiRequests = 0; clickFeedbackUntil = 0; renderBusyOverlay();",
    sandbox
);
assert.equal(isVisible(), false, "Fecha quando todas as operações terminarem");

const navigation = { disabled: false, textContent: "Dashboard", matches() { return true; } };
events.click({ target: { closest() { return navigation; } } });
assert.equal(isVisible(), false, "Navegação não bloqueia tela com modal");
console.log("Modal: clique, concorrência, conclusão e navegação OK");

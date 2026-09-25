/* Adaptação visual não executa ações na ONT nem expõe credenciais. */
const fs = require("node:fs");
const vm = require("node:vm");
const assert = require("node:assert/strict");

class Element {
    constructor(tag = "div") {
        this.tagName = tag.toUpperCase();
        this.children = [];
        this.textContent = "";
        this.className = "";
        this.style = {};
        this.classList = { add: () => {} };
    }
    append(...nodes) { this.children.push(...nodes); }
    prepend(...nodes) { this.children.unshift(...nodes); }
    replaceChildren(...nodes) { this.children = [...nodes]; }
    get childElementCount() { return this.children.length; }
}
const flatten = node => String(node?.textContent ?? "") +
    (node?.children || []).map(flatten).join(" ");
const scripts = fs.readFileSync(
    "apps/zte_manager/static/js/adaptive_firmware.js", "utf8"
);
const win = {};
const sandbox = {
    window: win,
    document: {
        createElement: tag => new Element(tag),
        addEventListener() {}
    },
    console,
    Date
};
vm.createContext(sandbox);
vm.runInContext(scripts, sandbox);

const report = {
    model: "F6201B",
    firmware: "V9.3.10P7N7",
    sections: {
        wifi_clients: { available: true, data: { connected: 1 } },
        lan_ports: { available: true, data: [{ port: "1", status: "Up" }] },
        dhcp_leases: { available: true, data: { leases: 3 } },
        device: {
            available: true,
            data: {
                identity: [{ model: "F6201B", firmware: "V9.3.10P7N7",
                    password: "do-not-display" }],
                resources: [{ cpu1: "5", memory_percent: "23" }]
            }
        },
        wan: { available: false, reason: "no_data_from_firmware" }
    }
};
const mount = new Element("div");
win.renderAdaptiveDiagnostic(report, mount);
const body = flatten(mount);
assert.match(body, /F6201B/);
assert.match(body, /Clientes Wi-Fi/);
assert.match(body, /Leases DHCP/);
assert.match(body, /Indisponível/);
assert.ok(!body.includes("do-not-display"), "Nunca renderizar credenciais");
assert.ok(!body.includes('"sections"'), "Não despejar JSON bruto");

const attendance = win.composeFirmwareAttendance(report);
assert.match(attendance, /Clientes Wi-Fi: connected=1/);
assert.match(attendance, /Leases DHCP: leases=3/);
assert.ok(!attendance.includes("do-not-display"));
assert.ok(!attendance.includes("password"));
console.log("UI adaptativa e atendimento: cards, zero de dados e sigilo OK");

/* Regression: F6600P/F670L never inherit F6201B adaptive cards. */
const assert = require("node:assert/strict");
const fs = require("node:fs");
const vm = require("node:vm");
const source = fs.readFileSync(
    "apps/zte_manager/static/js/adaptive_firmware.js", "utf8"
);
const primary = source.slice(0, source.indexOf("/* Catalog explorer"));
assert.ok(primary.includes("window.clearAdaptiveFirmwareState"));

const handlers = {};
let bootstrap = {
    connected: true, model: "F6600P", detected_model: "F6600P",
    session_revision: "router-a",
    catalog: {models: [
        {model: "F6600P", candidate_features: ["wifi_ssids", "wan"]},
        {model: "F6201B", candidate_features: ["wifi_ssids"]}
    ]}
};
let mutated = 0;
let diagnosticCalls = 0;
const sections = {};
for (const page of ["dashboard","wifi","wan","clients","device"]) {
    const panel = {
        children: [{classList:{contains:()=>true,add:()=>{},remove:()=>{}}}],
        querySelector() {return null;},
        querySelectorAll() {return [];},
        append() {mutated++;},
    };
    sections["page-"+page] = panel;
}
const ctx = {
    console,
    window: {},
    routerWriteEnabled: false, ontConnected: true,
    currentHost: "192.0.2.20",
    Date,
    document: {
        addEventListener(type,fn) {handlers[type] = fn;},
        getElementById(id) {return sections[id] || null;},
        createElement() {return {children:[],classList:{add(){}},append(){}};}
    },
    apiRequest: async endpoint => {
        if (endpoint === "/discovery/bootstrap") return bootstrap;
        diagnosticCalls++;
        throw new Error("unexpected request");
    }
};
vm.createContext(ctx);
vm.runInContext(primary,ctx);
async function settle() {
    for(let i=0;i<7;i++) await new Promise(resolve=>setTimeout(resolve,0));
}
(async()=>{
    handlers["zte:page-open"]({detail:{pageName:"wifi"}});
    await settle();
    assert.equal(mutated,0,"Native F6600P page must remain unchanged");
    assert.equal(diagnosticCalls,0,"No multimodel diagnosis on native F6600P");
    bootstrap={...bootstrap,model:"F670L",detected_model:"F670L",
        session_revision:"router-b"};
    ctx.currentHost="192.0.2.21";
    handlers["zte:session-changed"]();
    handlers["zte:page-open"]({detail:{pageName:"wan"}});
    await settle();
    assert.equal(mutated,0,"Native F670L page must remain unchanged");
    assert.equal(diagnosticCalls,0);
    bootstrap={...bootstrap,model:"F6201B",detected_model:"F6600P",
        session_revision:"router-c"};
    handlers["zte:page-open"]({detail:{pageName:"wifi"}});
    await settle();
    assert.equal(mutated,0,"Contradictory device model must block experimental UI");
    assert.equal(diagnosticCalls,0);
    console.log("Native F6600P/F670L and mismatched model UI isolation OK");
})().catch(e=>{console.error(e);process.exitCode=1});

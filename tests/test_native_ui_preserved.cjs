/* Regression: preserve original ZTE native cards, never append an extra
   experimental editor; read-only F6201B uses existing page containers. */
const assert = require("node:assert/strict");
const fs = require("node:fs");
const vm = require("node:vm");
const native=fs.readFileSync("apps/zte_manager/static/js/app.js","utf8");
const adaptive=fs.readFileSync("apps/zte_manager/static/js/adaptive_firmware.js","utf8");
const profile=fs.readFileSync("apps/zte_manager/static/js/f6201b_editor.js","utf8");
const template=fs.readFileSync("apps/zte_manager/templates/index.html","utf8");
for (const id of ["wifiNetworks","wifiRadios","wanConnections",
    "wifiClientsTable","lanClientsTable","deviceDetails","opticalDetails"]) {
    assert.ok(template.includes('id="'+id+'"'),"Missing native container "+id);
    assert.ok(profile.includes('"'+id+'"'),"Profile did not reuse "+id);
}
for(const cls of ["ssid-card","ssid-card-head","switch-row","form-grid",
    "form-footer","wan-card","port-card"]){
    assert.ok(native.includes(cls),"Existing class missing: "+cls);
    assert.ok(cls === "wan-card"
        ? profile.includes("renderWanCard(")
        : profile.includes(cls),
        "F6201B not using native class or original renderer: "+cls);
}
assert.ok(!profile.includes('panel f6201b-editor'),
    "Old full-width experimental panel must be removed");
assert.ok(adaptive.includes(
    "Nunca substituir as páginas Visão geral"),
    "Read-only overlay must not hide native pages");
assert.ok(profile.includes("preview") && profile.includes("nonce"),
    "Guarded SSID confirmation must be preserved");

const handlers={};
const ctx={
    document:{
        addEventListener:(name,fn)=>{handlers[name]=fn;},
        querySelectorAll:()=>[]
    },
    window:{},
    console,
    ontConnected:true,
    routerWriteEnabled:true,
    apiRequest:async()=>{throw Error("Native device must not use F6201B API")}
};
vm.createContext(ctx);
vm.runInContext(profile,ctx);
assert.ok(handlers["zte:page-open"]);
handlers["zte:page-open"]({detail:{pageName:"wifi"}});
(async()=>{
    await new Promise(resolve=>setTimeout(resolve,0));
    console.log("Old native layout for both families is preserved.");
})().catch(e=>{console.error(e);process.exitCode=1});

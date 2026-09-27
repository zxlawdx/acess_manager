/* Native GET diagnostics must not be coupled to write permission. */
"use strict";
const assert = require("node:assert/strict");
const fs = require("node:fs");
const vm = require("node:vm");

const text = fs.readFileSync(
    "apps/zte_manager/static/js/support_diagnostics.js", "utf8"
);
const first = text.indexOf("async function loadFirmwareDiagnosticOptions()");
const last = text.indexOf("async function detectFirmwareDiagnosticOptions()", first);
assert.ok(first >= 0 && last > first, "Native diagnostics component missing");
const source = text.slice(first, last);
assert.ok(!source.includes("bootstrap.writes_enabled"),
    "GET diagnostics must never depend on POST availability");

async function scenario(model, native, catalog) {
    const calls = [];
    const status = {textContent:""};
    const state = {
        host:null, model:null, revision:null,
        options:[], selected:new Set(), source:null,
        classicMode:false, scanComplete:false
    };
    const panel = {
        querySelector(selector) {
            assert.equal(selector, "#firmwareDiagnosticStatus");
            return status;
        }
    };
    const context = {
        window:{},
        console, Set, Object, String,
        ontConnected:true,
        currentHost:"192.0.2.1",
        firmwareDiagnosticState:state,
        supportDiagnosticState:{firmwareReport:null},
        firmwareDiagnosticPanel:()=>panel,
        renderFirmwareDiagnosticOptions:()=>{},
        FIRMWARE_DIAGNOSTIC_SECTIONS:{wan:"wan"},
        apiRequest:async path=>{
            calls.push(path);
            if(path === "/discovery/bootstrap") return {
                connected:true, model, detected_model:model,
                model_verified:true, session_revision:"rev-1",
                writes_enabled:false,
                native_diagnostics_available:native,
                catalog:{models:catalog}
            };
            if(path === "/device/capabilities") return {
                features:{
                    wifi_clients:{label:"Clientes Wi-Fi",dangerous:false},
                    reboot:{label:"Reiniciar",dangerous:true},
                    dns_lookup:{label:"DNS local",dangerous:false}
                }
            };
            throw Error("Unexpected backend route: "+path);
        }
    };
    vm.createContext(context);
    vm.runInContext(source,context);
    await vm.runInContext("loadFirmwareDiagnosticOptions()",context);
    return {state,calls,status};
}
(async()=>{
    const f6600=await scenario("F6600P",true,[
        {model:"F6600P",candidate_features:["wan"]}
    ]);
    assert.equal(f6600.state.source,"native");
    assert.deepEqual([...f6600.state.options.map(x=>x.name)],["wifi_clients"]);
    assert.ok(f6600.calls.includes("/device/capabilities"));

    const f670=await scenario("F670L",true,[]);
    assert.equal(f670.state.source,"native");
    assert.equal(f670.state.options.length,1);

    const unknown=await scenario("UNRECOGNIZED",false,[
        {model:"UNRECOGNIZED",candidate_features:["wan"]}
    ]);
    assert.equal(unknown.state.source,"multimodel");
    assert.ok(!unknown.calls.includes("/device/capabilities"));
    console.log("Native F670L/F6600P GET diagnostics independent from write permissions.");
})().catch(error=>{console.error(error);process.exitCode=1});

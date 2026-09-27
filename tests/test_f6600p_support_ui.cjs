/* Confirm visible diagnostic stages while the full backend request is pending. */
"use strict";
const fs=require("node:fs"),vm=require("node:vm"),assert=require("node:assert/strict");
const code=fs.readFileSync("apps/zte_manager/static/js/support_diagnostics.js","utf8");
const start=code.indexOf("// The full diagnostic is intentionally sequential");
const end=code.indexOf("async function runSupportDiagnostic(",start);
assert.ok(start>=0&&end>start);
const label=[];let polls=0;
const ctx={
 console,setTimeout,clearTimeout,AbortController,
 setBusy:(busy,text)=>label.push([busy,text]),
 fetch:async endpoint=>{
   assert.equal(endpoint,"/api/diagnostics/support/progress");
   polls++;
   return {ok:true,json:async()=>({running:true,stage:"wifi_environment",
     completed:3,total:7})};
 }
};
vm.createContext(ctx);
vm.runInContext(code.slice(start,end),ctx);
const output={textContent:"",setAttribute(k,v){this[k]=v;}};
(async()=>{
 const stop=vm.runInContext("beginSupportProgress",ctx)(output);
 await new Promise(resolve=>setTimeout(resolve,960));
 stop();
 assert.ok(polls>=1);
 assert.match(output.textContent,/Analisando ambiente e canais Wi-Fi · 3\/7/);
 assert.equal(output["aria-live"],"polite");
 assert.ok(label.some(x=>x[0]===true));
 assert.ok(code.includes("requestController.abort()") &&
   code.includes("stopProgress()") && code.includes("clearTimeout(deadline)"),
   "Full POST must have a bounded timeout and cleanup");
 assert.ok(code.includes("output.insertAdjacentHTML"),
   "One incompatible diagnostic section must not hide the entire report");
 console.log("Support diagnostic renders progress, bounded timeout and partial sections.");
})().catch(e=>{console.error(e);process.exitCode=1});
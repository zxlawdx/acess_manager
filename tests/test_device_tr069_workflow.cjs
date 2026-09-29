"use strict";
const test=require("node:test"),assert=require("node:assert/strict");
const fs=require("node:fs"),vm=require("node:vm");
const src=fs.readFileSync("apps/zte_manager/templates/index.html","utf8");
const device=fs.readFileSync("apps/zte_manager/templates/source/pages/device.html","utf8");
const tr069=fs.readFileSync("apps/zte_manager/templates/source/pages/tr069.html","utf8");
const shell=fs.readFileSync("apps/zte_manager/static/js/tangerine_shell.js","utf8");

test("device screen uses live identity and opt-in original firmware actions",()=>{
 for(const doc of [src,device]) {
  assert.match(doc,/class="am-device-summary"/);
  assert.match(doc,/id="deviceIdentityModel"/);
  assert.match(doc,/id="deviceIdentityHost"/);
  assert.match(doc,/<details class="am-device-maintenance">/);
  assert.match(doc,/id="adminPasswordForm"/);
  assert.match(doc,/id="rebootDeviceButton"/);
  assert.match(doc,/data-jump="advanced"/);
 }
 const start=shell.indexOf("function syncOverview()");
 const end=shell.indexOf("    syncOverview();",start);
 assert.ok(start>=0&&end>start);
 const fields=new Map(Object.entries({
  connectedModel:{textContent:"F6645P"},
  connectedHost:{textContent:"192.0.2.42"},
  deviceIdentityModel:{textContent:""},
  deviceIdentityHost:{textContent:""},
  deviceIdentityState:{textContent:""}
 }));
 let connected=true;
 const ctx={document:{
  body:{classList:{contains:()=>connected}},
  getElementById:id=>fields.get(id)||null
 }};
 vm.runInNewContext(shell.slice(start,end)+"\nthis.sync=syncOverview;",ctx);
 ctx.sync();
 assert.equal(fields.get("deviceIdentityModel").textContent,"F6645P");
 assert.equal(fields.get("deviceIdentityHost").textContent,"192.0.2.42");
 assert.match(fields.get("deviceIdentityState").textContent,/autenticado/);
 connected=false;ctx.sync();
 assert.equal(fields.get("deviceIdentityHost").textContent,"Sem endereço confirmado");
 assert.doesNotMatch(fields.get("deviceIdentityModel").textContent,/F6645P/);
});
test("TR-069 uses grouped controls, optional secrets and existing API bindings",()=>{
 for(const doc of [src,tr069]) {
  assert.match(doc,/class="advanced-grid am-tr069-workspace"/);
  assert.match(doc,/class="form-stack am-tr069-form"/);
  assert.match(doc,/class="am-tr069-credentials"/);
  assert.match(doc,/type="password" id="tr069ProviderPassword"/);
  assert.match(doc,/type="password" id="tr069ProviderRequestPassword"/);
  for(const id of ["tr069ProviderSelect","tr069ProviderSave",
    "tr069EligibleWan","tr069ProviderApply","tr069ProviderFeedback"])
    assert.ok(doc.includes('id="'+id+'"'),id);
 }
});

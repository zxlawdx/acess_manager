"use strict";
const test=require("node:test"),assert=require("node:assert/strict");
const fs=require("node:fs"),vm=require("node:vm");
const root="apps/zte_manager/static/js/";
const advanced=fs.readFileSync(root+"advanced.js","utf8");
const management=fs.readFileSync(root+"management.js","utf8");
const results=fs.readFileSync(root+"tangerine_results.js","utf8");
const app=fs.readFileSync(root+"app.js","utf8");

function operationHarness(response,readback=true){
  const begin=advanced.indexOf("async function operationRequest(");
  const end=advanced.indexOf("function valueOrNull(",begin);
  assert.ok(begin>=0&&end>begin);
  const calls=[],scope={
    setBusy:v=>calls.push(["busy",v]),
    apiRequest:async()=>response,
    showToast:v=>calls.push(["toast",v]),
    loadHistory:async()=>calls.push(["history"])
  };
  vm.runInNewContext(advanced.slice(begin,end)+
    "\nthis.callOperation=operationRequest;",scope);
  return {run:()=>scope.callOperation("/network/dhcp/update",{},"Enviando",
    "DHCP atualizado.",async()=>readback),calls};
}
test("advanced mutation accepted without verified readback never claims success",async()=>{
  const h=operationHarness({success:true,verified:false,audit_outcome:"accepted"});
  await h.run();
  const messages=h.calls.filter(item=>item[0]==="toast").map(item=>item[1]);
  assert.ok(messages.some(msg=>/pendente/.test(msg)));
  assert.ok(!messages.some(msg=>msg==="DHCP atualizado."));
  assert.ok(h.calls.some(item=>item[0]==="history"));
});
test("confirmed mutations show success, failed refresh remains a separate warning",async()=>{
  const h=operationHarness({success:true,verified:true,audit_outcome:"verified"},false);
  await h.run();
  assert.ok(h.calls.some(item=>item[1]==="DHCP atualizado."));
  assert.ok(h.calls.some(item=>item[0]==="toast"&&/não foi possível atualizar/i.test(item[1])));
});
test("partially applied operation is not declared completed",async()=>{
  const h=operationHarness({success:true,partial:true,audit_outcome:"uncertain"});
  await h.run();
  const messages=h.calls.filter(item=>item[0]==="toast").map(item=>item[1]);
  assert.ok(messages.some(msg=>/parte da alteração/i.test(msg)));
  assert.ok(!messages.includes("DHCP atualizado."));
});
test("all advanced management writes share the same audit-aware operator policy",()=>{
  const begin=management.indexOf("function managementNotifyOutcome(");
  const end=management.indexOf("async function managementCopyText(",begin);
  assert.ok(begin>=0&&end>begin);
  const messages=[],scope={showToast:msg=>messages.push(msg)};
  vm.runInNewContext(management.slice(begin,end)+
    "\nthis.notify=managementNotifyOutcome;",scope);
  scope.notify({success:true,verified:false,audit_outcome:"accepted"},"QoS atualizado.");
  scope.notify({success:true,verified:false,audit_outcome:"uncertain"},"WAN atualizada.");
  assert.ok(messages[0].includes("aguarda confirmação"));
  assert.ok(messages[1].includes("parcialmente"));
  assert.ok(!messages.includes("QoS atualizado."));
  scope.notify({success:true,verified:true,audit_outcome:"verified"},"QoS atualizado.");
  assert.equal(messages[2],"QoS atualizado.");
  for(const text of ["QoS atualizado.","Firewall atualizado.","TR-069 atualizado.",
      "SNTP atualizado.","WAN atualizada."]){
    assert.ok(management.includes('managementNotifyOutcome(result, "'+text+'")'));
  }
});
test("result cards translate the same audit codes without English internals",()=>{
  const w={};
  vm.runInNewContext(results,{window:w});
  const sanitize=w.TangerineResults.sanitize;
  for(const [source,expected] of Object.entries({
    accepted:"Solicitação recebida",verified:"Alteração confirmada",
    uncertain:"Resultado não confirmado",failed:"Operação não concluída"
  })){
    const displayed=sanitize({success:true,audit_outcome:source});
    assert.equal(displayed.audit_outcome,expected);
  }
  assert.match(app,/profileOutcome = result.audit_outcome/);
  assert.doesNotMatch(app.slice(app.indexOf("async function applyProfile()"),
    app.indexOf("function renderProfileApplyResult(")),/if \(result\.success\) \{\s*showToast/);
});

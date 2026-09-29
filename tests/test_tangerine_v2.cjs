"use strict";
const assert=require("node:assert/strict");
const test=require("node:test");
const fs=require("node:fs"),vm=require("node:vm");
const root="apps/zte_manager/";
const html=fs.readFileSync(root+"templates/index.html","utf8");
const code=fs.readFileSync(root+"static/js/tangerine_forms.js","utf8");
const editorIds=["managementProfileJson","managementBatchPayload",
"managementQosJson","managementFirewallRuleJson","managementFirewallGlobalJson",
"managementSntpJson","managementTr069Json","managementWanJson"];
test("JSON forms preserve every existing backend textarea ID",()=>{
  for(const id of editorIds) {
    assert.match(html,new RegExp('<textarea id="'+id+'"'));
    assert.ok(code.includes('"'+id+'"'),id);
  }
  assert.match(html,/zte_manager\/js\/tangerine_forms\.js/);
  assert.match(html,/zte_manager\/css\/tangerine_forms\.css/);
});
test("pure form conversion does not flatten nested firmware configuration",()=>{
  const context={document:{readyState:"loading",addEventListener(){}},window:{}};
  vm.runInNewContext(code,context);
  const c=context.window.TangerineFormsCore;
  assert.equal(c.labelFor("auto_channel"),"Canal automático");
  const original={wifi:{"5GHz":{auto_channel:true}},dns:{}};
  c.assignPath(original,["wifi","5GHz","auto_channel"],false);
  c.assignPath(original,["dns","server1"],"1.1.1.1");
  assert.deepEqual(JSON.parse(JSON.stringify(original)),
    {wifi:{"5GHz":{auto_channel:false}},dns:{server1:"1.1.1.1"}});
  assert.equal(c.coerce("300","number"),300);
  assert.equal(c.coerce(false,"boolean"),false);
  assert.throws(()=>c.coerce("NaN","number"),/número válido/);
});
test("UI has ten page-specific visual headers, preserves actual session IDs",()=>{
 const sections=["wifi","wan","clients","supportDiagnostic","diagnostics",
 "profiles","tr069","advanced","device","management"];
 for(const id of sections){
   const start=html.indexOf('<section id="page-'+id+'" class="page">');
   assert.ok(start>0,id);
   const next=html.indexOf('<section id="page-',start+10);
   const chunk=html.slice(start,next<0?undefined:next);
   assert.match(chunk,/section-intro am-section-intro/,id);
   assert.match(chunk,/am-page-emblem/,id);
 }
 for(const id of ["pageTitle","pageSubtitle","consoleSessionDot",
  "consoleHostText","overviewHost","connectButton","topDeviceChip","appearanceSelect"]){
   assert.ok(html.includes('id="'+id+'"'),id);
 }
 assert.match(html,/class="login-hero am-connect-story"/);
 assert.doesNotMatch(html,/window-dot red/);
});


test("native Wi-Fi, WAN and radio cards are explicitly redesigned",()=>{
 const native=fs.readFileSync(root+"static/js/app.js","utf8");
 const cards=fs.readFileSync(root+"static/css/tangerine_cards.css","utf8");
 for(const name of ["am-wifi-card","am-radio-card","am-wan-card"]){
  assert.ok(native.includes(name),name+" must be emitted by native renderer");
  assert.ok(cards.includes("."+name),name+" must have native component styles");
 }
 assert.ok(html.includes("zte_manager/css/tangerine_cards.css"));
});

test("management results are readable and redact unsafe data",()=>{
 const script=fs.readFileSync(root+"static/js/tangerine_results.js","utf8");
 const sandbox={window:{}};vm.runInNewContext(script,sandbox);
 const sample=sandbox.window.TangerineResults.sanitize({
  device_id:12,password:"PRIVATE_SECRET",nested:{model:"F6600P",endpoint:"/private",
  message:"POST /hidden?password=PRIVATE_SECRET"}});
 const text=JSON.stringify(sample);
 assert.doesNotMatch(text,/PRIVATE_SECRET|POST|endpoint/);
 assert.match(text,/F6600P/);
 assert.ok(html.includes("tangerine_results.js"));
});

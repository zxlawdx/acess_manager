"use strict";
const test=require("node:test");
const assert=require("node:assert/strict");
const fs=require("node:fs"),vm=require("node:vm");
const code=fs.readFileSync(
 "apps/zte_manager/static/js/features/history.js","utf8");
const advanced=fs.readFileSync(
 "apps/zte_manager/static/js/advanced.js","utf8");
const html=fs.readFileSync("apps/zte_manager/templates/index.html","utf8");
const source=fs.readFileSync(
 "apps/zte_manager/templates/source/shell_end.html","utf8");

function setup(responder) {
 const elements=new Map(),handlers={},events={},toasts=[],calls=[];
 function make(tag="div") {
  return {tagName:tag.toUpperCase(),className:"",textContent:"",
   attributes:{},children:[],
   append(...nodes){this.children.push(...nodes);},
   appendChild(node){this.children.push(node);},
   replaceChildren(...nodes){this.children=[...nodes];},
   setAttribute(name,value){this.attributes[name]=value;}};
 }
 for(const id of ["historyOutput","backupResult"]){
  elements.set(id,make());
 }
 const ctx={window:{confirm:()=>true},document:{
  createElement:make, getElementById:id=>elements.get(id),
  addEventListener:(event,fn)=>{events[event]=fn;}
 },ontConnected:true,routerWriteEnabled:true,currentHost:"192.0.2.4",
 apiRequest:async (path,options)=>{
  calls.push({path,options});return responder(path,options);
 },showToast:message=>toasts.push(message),setBusy:()=>{}};
 vm.runInNewContext(code,ctx);
 return {controller:ctx.window.AccessManagerHistory,ctx,elements,events,toasts,calls};
}
const text=node=>String(node.textContent||"")+
 (node.children||[]).map(text).join(" ");

test("history module is loaded from source and compiled Vela templates",()=>{
 for(const src of [html,source]){
  assert.ok(src.includes("js/features/history.js"));
  assert.ok(src.indexOf("js/features/history.js")>
    src.indexOf("js/advanced.js"));
 }
 for(const fn of ["backupConfiguration","captureSnapshot","loadHistory"])
  assert.match(advanced,new RegExp("async function "+fn+"\\("));
});

test("live SQLite history is a semantic timeline without raw targets or secrets",async()=>{
 const h=setup(async()=>({changes:[
  {operation:"Wi-Fi alterado",target:"ssid=?password=SECRET",success:true,created_at:"2026-09-29T01:20:00"},
  {operation:"POST /api?token=PRIVATE",success:false,created_at:"2026-09-29T01:21:00"}
 ],diagnostics:[{status:"Concluído",summary:"senha:PRIVATE",created_at:"2026-09-29T01:18:00"}]}));
 await h.controller.load();
 const result=text(h.elements.get("historyOutput"));
 assert.match(result,/Wi-Fi alterado/);
 assert.match(result,/Diagnóstico registrado/);
 assert.match(result,/Verificar resultado/);
 assert.doesNotMatch(result,/SECRET|PRIVATE|password|\/api|senha:/);
 assert.equal(h.calls[0].path,"/history?limit=20");
 assert.equal(h.elements.get("historyOutput").attributes["aria-busy"],"false");
});

test("partial snapshot is explicitly communicated without pretending success",async()=>{
 const h=setup(async path=>path==="/history/snapshot"?
   {snapshot_id:12,partial:true,failed_sections:["internal secret"]}:
   {changes:[],diagnostics:[]});
 await h.controller.snapshot();
 assert.match(h.toasts.join(" "),/parcial/);
 assert.doesNotMatch(h.toasts.join(" "),/secret/);
 assert.equal(h.calls[0].path,"/history/snapshot");
 assert.equal(h.calls[0].options.method,"POST");
});

test("backup exposes only a validated basename, never raw filesystem paths",async()=>{
 const h=setup(async path=>path==="/system/backup"?
   {path:"/tmp/private/firmware/config.xml",size:312}:
   {changes:[],diagnostics:[]});
 await h.controller.backup();
 const result=text(h.elements.get("backupResult"));
 assert.match(result,/config\.xml/);
 assert.doesNotMatch(result,/\/tmp\/|private/);
 assert.match(h.toasts[0],/concluído/);
});

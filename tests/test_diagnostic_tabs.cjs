"use strict";
const test=require("node:test"),assert=require("node:assert/strict");
const fs=require("node:fs"),vm=require("node:vm");
const script=fs.readFileSync("apps/zte_manager/static/js/workbench_tabs.js","utf8");
const generated=fs.readFileSync("apps/zte_manager/templates/index.html","utf8");
const source=fs.readFileSync("apps/zte_manager/templates/source/pages/diagnostics.html","utf8");
test("diagnostic selector exposes only implemented Ping/Traceroute APIs",()=>{
 for(const doc of [source,generated]){
  for(const id of ["pingForm","tracerouteForm","pingOutput","tracerouteOutput",
    "diagnostic-tab-ping","diagnostic-tab-trace","diagnostic-panel-ping",
    "diagnostic-panel-trace"])assert.ok(doc.includes('id="'+id+'"'),id);
  assert.match(doc,/class="diagnostic-grid am-diagnostic-workspace am-diagnostic-tabbed"/);
  const begin=doc.indexOf('id="page-diagnostics"');
  const end=doc.indexOf('id="page-profiles"',begin);
  const page=doc.slice(begin,end);
  assert.equal([...page.matchAll(/data-am-tab="([^"]+)"/g)].length,2);
  assert.equal([...page.matchAll(/data-am-panel="([^"]+)"/g)].length,2);
  assert.doesNotMatch(page,/fake|sample output|192\.168\.1\.10/);
 }
});
test("network tool navigation keeps existing real result nodes active",()=>{
 const events={},ids=["ping","trace"];
 const tabs=ids.map(name=>({dataset:{amTab:name},attrs:{},
  classList:{toggle(){}},setAttribute(key,v){this.attrs[key]=v;},
  addEventListener(kind,fn){events[name+kind]=fn;},focus(){}}));
 const panels=ids.map(name=>({dataset:{amPanel:name},hidden:false}));
 const section={id:"page-diagnostics",querySelectorAll:selector=>
   selector.includes("tabpanel")?panels:tabs,
   querySelector:()=>null,addEventListener(){}};
 const doc={readyState:"complete",getElementById:id=>
   id==="page-diagnostics"?section:null};
 const win={};vm.runInNewContext(script,{document:doc,window:win,
   sessionStorage:{getItem:()=>null,setItem(){}}});
 assert.equal(tabs[0].attrs["aria-selected"],"true");
 assert.equal(panels[1].hidden,true);
 events.pingkeydown({key:"ArrowRight",preventDefault(){}});
 assert.equal(tabs[1].attrs["aria-selected"],"true");
 assert.equal(panels[0].hidden,true);
 assert.equal(panels[1].hidden,false);
 assert.equal(typeof win.AccessManagerDiagnosticsTabs.activate,"function");
});

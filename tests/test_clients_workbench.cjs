"use strict";
const test=require("node:test"),assert=require("node:assert/strict");
const fs=require("node:fs"),vm=require("node:vm");
const script=fs.readFileSync("apps/zte_manager/static/js/workbench_tabs.js","utf8");
const html=fs.readFileSync("apps/zte_manager/templates/index.html","utf8");
const source=fs.readFileSync(
 "apps/zte_manager/templates/source/pages/clients.html","utf8");
test("client Wi-Fi and Ethernet panels preserve live renderer targets",()=>{
 for(const doc of [html,source]){
  for(const id of ["wifiClientCount","lanClientCount","wifiClientsTable",
    "lanClientsTable","clientsSearch","clientsRefreshButton"])
   assert.ok(doc.includes('id="'+id+'"'),id);
  for(const tab of ["wireless","ethernet"]) {
   assert.match(doc,new RegExp('data-am-tab="'+tab+'"'));
   assert.match(doc,new RegExp('data-am-panel="'+tab+'"'));
  }
 }
});
test("client selector filters live table rows and refreshes through native loader",async()=>{
 const events={},key="am-workbench:page-clients";
 const tabs=["wireless","ethernet"].map(label=>({
  dataset:{amTab:label},attrs:{},classList:{toggle(){}},
  setAttribute(n,v){this.attrs[n]=v;},addEventListener(t,fn){events[label+t]=fn;},
  focus(){}
 }));
 const panels=["wireless","ethernet"].map(label=>({
  dataset:{amPanel:label},hidden:false
 }));
 const rows=[
  {textContent:"Notebook Escritório 192.0.2.20",hidden:false,querySelector:()=>null},
  {textContent:"Telefone 192.0.2.21",hidden:false,querySelector:()=>null}
 ];
 const wifi={querySelectorAll:()=>rows};
 const lan={querySelectorAll:()=>[
  {textContent:"PC Cabeado 192.0.2.30",hidden:false,querySelector:()=>null}
 ]};
 const search={value:"",addEventListener:(t,fn)=>events.search=fn};
 const refresh={disabled:false,attrs:{},
  addEventListener:(t,fn)=>events.refresh=fn,
  setAttribute(n,v){this.attrs[n]=v;}};
 const clients={
  id:"page-clients",classList:{contains:()=>true},
  querySelectorAll:s=>s.includes("tabpanel")?panels:tabs,
  querySelector:s=>null,addEventListener(t,fn){events[t]=fn;}
 };
 let loads=0;
 const doc={
  readyState:"complete",body:{classList:{contains:()=>true}},
  getElementById:id=>({
   "page-clients":clients,clientsSearch:search,clientsRefreshButton:refresh,
   wifiClientsTable:wifi,lanClientsTable:lan
  }[id]||null)
 };
 const win={};
 vm.runInNewContext(script,{document:doc,window:win,
  sessionStorage:{getItem(){return null;},setItem(){}},
  loadClients:async()=>{loads++;},
  showToast(){throw Error("Unexpected error");}
 });
 assert.equal(tabs[0].attrs["aria-selected"],"true");
 assert.equal(panels[1].hidden,true);
 search.value="notebook";events.search();
 assert.equal(rows[0].hidden,false);
 assert.equal(rows[1].hidden,true);
 tabs[1].focus=()=>{};events.ethernetclick();
 assert.equal(panels[1].hidden,false);
 await events.refresh();
 assert.equal(loads,1);
 assert.equal(refresh.disabled,false);
 assert.equal(refresh.attrs["aria-busy"],"false");
 assert.ok(win.AccessManagerClientsWorkbench?.activate);
});

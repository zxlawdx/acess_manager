"use strict";
const assert=require("node:assert/strict"),test=require("node:test");
const fs=require("node:fs"),vm=require("node:vm");
const script=fs.readFileSync("apps/zte_manager/static/js/management.js","utf8");
const html=fs.readFileSync("apps/zte_manager/templates/index.html","utf8");
const source=fs.readFileSync("apps/zte_manager/templates/source/pages/management.html","utf8");
const keys=["fleet","remote","monitor","network","mesh","lifecycle","provisioning"];
test("management tabs have matching real ARIA panels without extra UI copies",()=>{
 for(const doc of [html,source]) {
  for(const key of keys) {
   assert.match(doc,new RegExp('id="management-tab-'+key+'"'));
   assert.match(doc,new RegExp('id="management-panel-'+key+'"'));
   assert.match(doc,new RegExp('aria-controls="management-panel-'+key+'"'));
  }
  assert.match(doc,/role="tablist"/);
 }
});
test("switchManagementTab reveals exactly one pane and updates focus",()=>{
 const list=keys.map(key=>({
  dataset:{managementTab:key},classList:{current:false,toggle(label,flag){this.current=flag;}},
  aria:{},setAttribute(k,v){this.aria[k]=v;},tabIndex:0
 }));
 const panes=keys.map(key=>({
  dataset:{managementPane:key},hidden:key!=="fleet",
  classList:{current:false,toggle(label,flag){this.current=flag;}}
 }));
 const ctx={document:{querySelectorAll:selector=>
  selector===".management-tab"?list:selector===".management-pane"?panes:[]}};
 const start=script.indexOf("function switchManagementTab(name)"),
   end=script.indexOf("async function refreshManagement(",start);
 assert.ok(start>=0&&end>start);
 vm.runInNewContext(script.slice(start,end)+"\nthis.activate=switchManagementTab;",ctx);
 ctx.activate("network");
 assert.equal(list[3].aria["aria-selected"],"true");
 assert.equal(list[3].tabIndex,0);
 assert.equal(list[0].aria["aria-selected"],"false");
 assert.equal(panes.filter(panel=>panel.hidden===false).length,1);
 assert.equal(panes[3].hidden,false);
 ctx.activate("non-existent");
 assert.equal(panes.filter(panel=>panel.hidden===false).length,1);
});

"use strict";
const test=require("node:test"),assert=require("node:assert/strict");
const fs=require("node:fs"),vm=require("node:vm");
const root="apps/zte_manager/";
const topology=fs.readFileSync(root+"static/js/features/device_topology.js","utf8");
const inspector=fs.readFileSync(root+"static/js/features/firmware_inspector.js","utf8");
const app=fs.readFileSync(root+"static/js/app.js","utf8");
const advanced=fs.readFileSync(root+"static/js/advanced.js","utf8");
const css=fs.readFileSync(root+"static/css/tangerine.css","utf8");
const source=fs.readFileSync(root+"templates/source/pages/clients.html","utf8");
const html=fs.readFileSync(root+"templates/index.html","utf8");

function fakeNode(tag="div"){
  const attr={},handlers={};
  return {
    tagName:tag.toUpperCase(),children:[],attrs:attr,handlers,
    textContent:"",className:"",value:"",
    classList:{names:new Set(),add(v){this.names.add(v);},
      remove(v){this.names.delete(v);},contains(v){return this.names.has(v);}},
    setAttribute(key,value){attr[key]=String(value);if(key==="class")this.className=String(value);},
    addEventListener(name,fn){handlers[name]=fn;},
    append(...nodes){this.children.push(...nodes);},
    appendChild(el){this.children.push(el);return el;},
    replaceChildren(...nodes){this.children=[...nodes];},
    querySelectorAll(){return [];},
    focus(){this.focused=true;},
    matches(selector){return selector.split(",").some(item=>item.trim().toUpperCase()===this.tagName);},
    scrollIntoView(){this.scrolled=true;}
  };
}
function allText(el) {
  return [String(el?.textContent||""),...(el?.children||[]).map(allText)].join(" ");
}
test("Vela template mounts the real topology and operator inspection modules",()=>{
  for(const filename of [
    "css/components/topology.css","css/components/firmware_inspector.css",
    "js/features/device_topology.js","js/features/firmware_inspector.js"
  ])assert.ok(html.includes("zte_manager/"+filename),filename);
  for(const id of ["topologyGraph","topologyDetails","topologyRssiOneMeter",
     "topologyPathLoss","firmwareFeatureSelect","firmwareInspectButton"]){
    assert.match(html,new RegExp('id="'+id+'"'));
  }
  assert.match(source,/id="topologySection"/);
  assert.ok(app.includes('"am:clients-updated"'),
    "graph must use existing real /clients/wifi and /clients/lan responses");
  assert.doesNotMatch(advanced,/output\.value\s*=\s*JSON\.stringify\(report/);
});
test("zoom scales only the grid shell, never the viewport body",()=>{
  const part=app.slice(app.indexOf("function applyUiZoom("),
    app.indexOf("function changeUiZoom("));
  assert.match(part,/shell\.style\.zoom/);
  assert.doesNotMatch(part,/document\.body\.style\.zoom\s*=\s*String\(uiZoom\)/);
  assert.match(css,/grid-template-columns:var\(--am-current-sidebar\) minmax\(0,1fr\)/);
  assert.match(css,/width:calc\(100% \/ var\(--am-zoom,1\)\)/);
});
test("RSSI estimates require actual calibration, never imply measured distance",()=>{
  const doc={readyState:"loading",addEventListener(){}},w={};
  vm.runInNewContext(topology,{document:doc,window:w});
  const api=w.AccessManagerTopology;
  assert.ok(api);
  assert.equal(api.estimateDistance(-60,-40,2),10);
  assert.equal(api.estimateDistance(-60,NaN,2),null);
  assert.equal(api.estimateDistance(-60,-40,0),null);
  assert.equal(api.estimateDistance(null,-40,2),null);
  assert.equal(api.rssiValue("-68 dBm"),-68);
  assert.equal(api.rssiValue("GET /secret"),null);
  assert.match(api.clientType("iPhone"),/Possível celular/);
  assert.match(api.clientType("Smart TV"),/Possível televisão/);
  assert.equal(api.clientType("02:AB:CD:EF:12:34"),"Tipo não identificado");
});
test("graph shows only live client fields, supports keyboard, averages real samples",()=>{
  const ids={topologySection:fakeNode(),topologyGraph:fakeNode(),
    topologyDeviceCount:fakeNode(),topologyDetails:fakeNode(),
    connectedHost:fakeNode(),connectedModel:fakeNode(),
    topologyRssiOneMeter:fakeNode("input"),topologyPathLoss:fakeNode("input")};
  ids.connectedHost.textContent="test-on-device";
  ids.connectedModel.textContent="F6600P";
  ids.topologyRssiOneMeter.value="-40";
  ids.topologyPathLoss.value="2";
  const doc={readyState:"loading",addEventListener(){},
    getElementById:id=>ids[id]||null,
    createElement:fakeNode,createElementNS:(ns,tag)=>fakeNode(tag)};
  const w={};
  vm.runInNewContext(topology,{document:doc,window:w});
  const api=w.AccessManagerTopology;
  const device={hostname:"Notebook",ip:"192.0.2.8",mac:"02:11:22:33:44:55",
    ssid:"Wi-Fi local",rssi:-60,snr:33};
  api.render([device],[]);
  const svg=ids.topologyGraph.children[0];
  const chip=svg.children.find(n=>n.attrs.role==="button");
  assert.ok(chip,"real Wi-Fi client must be a selectable graph node");
  assert.equal(chip.attrs.tabindex,"0");
  chip.handlers.keydown({key:"Enter",preventDefault(){}});
  assert.match(allText(ids.topologyDetails),/192\.0\.2\.8/);
  assert.match(allText(ids.topologyDetails),/10\.0 m/);
  api.render([{...device,rssi:-62}],[]);
  assert.match(allText(ids.topologyDetails),/média de 2 leituras/);
  api.reset();
  assert.match(ids.topologyGraph.textContent,/Aguardando/);
});
test("firmware inspection removes internal paths, keys and credential-bearing values",()=>{
  const document={readyState:"loading",addEventListener(){},createElement:fakeNode};
  const w={};
  vm.runInNewContext(inspector,{document,window:w});
  const api=w.AccessManagerInspector;
  assert.equal(api.label("tr069","think_lua_internal"),"Gerenciamento remoto TR-069");
  assert.equal(api.label("new_feature","ThinkLua_v3"),"Funcionalidade do equipamento");
  const firmware={feature:"tr069",label:"TR-069 / ACS",
    available:true,probeable:true,writable:false,dangerous:true,
    endpoint:{view:"remoteMgr",tag:"tr069_remotemgr_lua.lua"},
    objects:{OBJ_MANAGESERVER_ID:[{URL:"https://admin:PRIVATE@host",
      UserName:"admin",ConnectionRequestURL:"http://TOKEN",
      Password:"SECRET",PeriodicInformEnable:"1",
      PeriodicInformInterval:"3600"}]}};
  const fields=api.summary(firmware);
  const raw=JSON.stringify(fields);
  assert.match(raw,/Informes periódicos/);
  assert.match(raw,/Intervalo de comunicação/);
  assert.doesNotMatch(raw,/PRIVATE|TOKEN|SECRET|Username|remoteMgr|tr069_remotemgr|https/);
  const output=fakeNode();
  vm.runInNewContext(inspector,{
    document,window:w
  }); // no side effects or network writes
  api.render("tr069",firmware,output);
  const visible=allText(output);
  assert.match(visible,/Gerenciamento remoto TR-069/);
  assert.doesNotMatch(visible,/PRIVATE|TOKEN|SECRET|remoteMgr|\.lua/);
});
test("editing links to existing forms and never creates a generic firmware POST",()=>{
  const ids={managementQosKind:fakeNode("select"),
    managementQosSave:fakeNode("button")};
  const actions=[];
  const document={readyState:"loading",addEventListener(){},
    createElement:fakeNode,getElementById:id=>ids[id]||null};
  const w={};
  vm.runInNewContext(inspector,{
    document,window:w,openPage:name=>actions.push(name),
    switchManagementTab:name=>actions.push(name),CustomEvent:class{}
  });
  assert.equal(w.AccessManagerInspector.goToEditor("qos_speed"),true);
  assert.deepEqual(actions,["management","network"]);
  assert.equal(ids.managementQosKind.value,"policer");
  assert.equal(ids.managementQosSave.focused,true);
  assert.equal(w.AccessManagerInspector.goToEditor("factory_reset"),false);
  assert.doesNotMatch(inspector,/fetch\(|session\.post|\/features\/write/);
});

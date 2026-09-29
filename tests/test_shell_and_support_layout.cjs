"use strict";
const test=require("node:test"),assert=require("node:assert/strict");
const fs=require("node:fs"),vm=require("node:vm");
const r="apps/zte_manager/";
const html=fs.readFileSync(r+"templates/index.html","utf8");
const shell=fs.readFileSync(r+"static/css/components/shell_layout.css","utf8");
const diagnostics=fs.readFileSync(r+"static/css/tangerine_workflows.css","utf8");
const tangerine=fs.readFileSync(r+"static/css/tangerine.css","utf8");
const telecom=fs.readFileSync(r+"static/css/telecom_console.css","utf8");
const supportJs=fs.readFileSync(r+"static/js/support_diagnostics.js","utf8");
const ui=fs.readFileSync(r+"static/js/app.js","utf8");
const nav=fs.readFileSync(r+"static/js/tangerine_shell.js","utf8");
test("single app-shell geometry owns sidebar and workspace",()=>{
  assert.match(html,/css\/components\/shell_layout\.css/);
  assert.match(shell,/grid-template-columns:var\(--am-shell-column\) minmax\(0,1fr\)/);
  assert.match(shell,/\.app-shell>.workspace\s*\{[\s\S]*?margin:0!important/);
  assert.match(shell,/\.app-shell>.sidebar\s*\{[\s\S]*?position:sticky!important/);
  assert.match(shell,/@media\(max-width:920px\)/);
  assert.match(nav,/document\.documentElement\.dataset\.sidebarCollapsed/);
  assert.doesNotMatch(tangerine,/width:calc\(100% \/ var\(--am-zoom/);
  assert.doesNotMatch(telecom,/width: calc\(100% - var\(--sidebar-width\)\)/);
});
test("A+/A- change typography without changing layout viewport coordinates",()=>{
  const current=ui.slice(ui.indexOf("function applyUiZoom("),
    ui.indexOf("function changeUiZoom("));
  assert.match(current,/--am-font-scale/);
  assert.match(current,/document\.body\.style\.zoom = ""/);
  assert.match(current,/shell\.style\.zoom = ""/);
  assert.doesNotMatch(current,/shell\.style\.zoom\s*=\s*String\(uiZoom\)/);
  assert.match(html,/aria-label="Tamanho do texto"/);
  assert.match(html,/aria-label="Aumentar tamanho do texto"/);
  assert.match(nav,/sidebarCollapsed/);
});
test("support workbench uses full width and compact progressive disclosure",()=>{
  assert.match(diagnostics,/\.am-support-workspace\s*\{[\s\S]{0,160}grid-template-columns:minmax\(0,1fr\)/);
  assert.match(diagnostics,/#firmwareDiagnosticChoices/);
  assert.match(diagnostics,/\.am-pending-features/);
  assert.doesNotMatch(diagnostics,/grid-template-columns:minmax\(330px,/);
  assert.doesNotMatch(diagnostics,/grid-row:1 \/ span 4/);
  assert.match(supportJs,/details/);
  assert.match(supportJs,/Recurso do equipamento/);
});
class FakeElement {
  constructor(tag){this.tag=tag;this.children=[];this.id="";this.className="";this.textContent="";
    this.classList={toggle(){}};this.disabled=false;this.open=false;}
  append(...nodes){this.children.push(...nodes)}
  replaceChildren(...nodes){this.children=[...nodes]}
  querySelector(sel){return this.children.find(c=>"#"+c.id===sel)||null}
  addEventListener(){}
}
test("no verified feature renders one small prompt with collapsed pending list",()=>{
  const from=supportJs.indexOf("function renderFirmwareDiagnosticOptions() {");
  const end=supportJs.indexOf("async function loadFirmwareDiagnosticOptions()",from);
  assert.ok(from>=0&&end>from);
  const grid=new FakeElement("div");
  const status=new FakeElement("p");
  const run=new FakeElement("button"),detect=new FakeElement("button");
  const panel={classList:{toggle(){}},querySelector:s=>({
      "#firmwareDiagnosticChoices":grid,
      "#firmwareDiagnosticStatus":status,
      "#firmwareDiagnosticRun":run,
      "#firmwareDiagnosticDetect":detect,
      "#firmwareDiagnosticPending":grid.children.find(n=>n.id==="firmwareDiagnosticPending")
    })[s]||null
  };
  const form={querySelectorAll:()=>[]};
  const state={classicMode:false,model:"F6600P",options:[
    {name:"wifi_clients",label:"Clientes Wi-Fi",confirmed:false},
    {name:"dhcp",label:"Servidor DHCP",confirmed:false},
    {name:"tr069_status",label:"Gerenciamento remoto",confirmed:false}
  ],selected:new Set(),scanComplete:false,probeRunning:false};
  const ctx={
    firmwareDiagnosticPanel:()=>panel,
    firmwareDiagnosticState:state,
    ontConnected:true,routerWriteEnabled:true,
    document:{
      getElementById:id=>id==="supportDiagnosticForm"?form:null,
      createElement:tag=>new FakeElement(tag)
    },
    FIRMWARE_DIAGNOSTIC_LABELS:{
      wifi_clients:"Clientes Wi-Fi",dhcp:"Servidor DHCP",
      tr069_status:"Gerenciamento remoto"
    }
  };
  vm.createContext(ctx);
  vm.runInContext(supportJs.slice(from,end),ctx);
  vm.runInContext("renderFirmwareDiagnosticOptions()",ctx);
  assert.equal(run.disabled,true);
  assert.equal(grid.children.length,2);
  assert.equal(grid.children[0].className,"am-features-empty");
  assert.equal(grid.children[1].tag,"details");
  assert.equal(grid.children[1].open,false);
  assert.match(grid.children[1].children[0].textContent,/3 recurso/);
  state.options[0].confirmed=true;
  vm.runInContext("renderFirmwareDiagnosticOptions()",ctx);
  assert.equal(run.disabled,false);
  assert.equal(grid.children[0].tag,"fieldset");
  assert.equal(grid.children[1].tag,"details");
  assert.match(status.textContent,/1 recurso/);
});

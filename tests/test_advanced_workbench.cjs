"use strict";
const assert=require("node:assert/strict"),test=require("node:test");
const fs=require("node:fs"),vm=require("node:vm");
const shell=fs.readFileSync("apps/zte_manager/static/js/workbench_tabs.js","utf8");
const advanced=fs.readFileSync("apps/zte_manager/static/js/advanced.js","utf8");
const template=fs.readFileSync("apps/zte_manager/templates/index.html","utf8");

test("advanced workbench has five real panels with existing command IDs",()=>{
  const ids=["discovery","diagnostics","dhcp","nat","inspector"];
  const section=template.slice(template.indexOf('id="page-advanced"'),
    template.indexOf('id="page-device"'));
  for(const id of ids){
    assert.match(section,new RegExp('data-am-tab="'+id+'"'));
    assert.match(section,new RegExp('data-am-panel="'+id+'"'));
    assert.match(section,new RegExp('aria-controls="advanced-panel-'+id+'"'));
  }
  for(const id of ["probeCapabilitiesButton","multimodelProbeButton",
    "refreshAdvancedNetworkButton","multimodelDiagnosticButton",
    "automaticDiagnosticForm","dhcpBasicForm","portForwardForm",
    "dmzForm","featureInspectorOutput"]){
    assert.ok(section.includes('id="'+id+'"'),id);
  }
});

test("real workbench keyboard and toolbar navigation preserve existing handlers",()=>{
  const keys=["discovery","diagnostics","dhcp","nat","inspector"];
  const events={},tabs=keys.map(key=>({
    dataset:{amTab:key},attributes:{},tabIndex:0,
    classList:{toggle(){}},setAttribute(name,value){this.attributes[name]=value;},
    addEventListener(name,cb){events[key+name]=cb;},focus(){events.focus=key;}
  }));
  const panels=keys.map(key=>({dataset:{amPanel:key},hidden:false}));
  const toolbar={addEventListener:(name,cb)=>events.toolbar=cb};
  const section={
    id:"page-advanced",
    querySelectorAll(selector){return selector.includes("tabpanel")?panels:tabs;},
    querySelector(selector){return selector==="#refreshAdvancedNetworkButton"?toolbar:null;},
    addEventListener(name,cb){events[name]=cb;}
  };
  const storage=new Map(),w={};
  vm.runInNewContext(shell,{
    document:{readyState:"complete",
      getElementById:id=>id==="page-advanced"?section:null},
    window:w,
    sessionStorage:{
      getItem:key=>storage.get(key)||null,setItem:(key,value)=>storage.set(key,value)
    }
  });
  assert.equal(tabs[0].attributes["aria-selected"],"true");
  assert.equal(panels[4].hidden,true);
  events["discoverykeydown"]({key:"ArrowRight",preventDefault(){}});
  assert.equal(tabs[1].attributes["aria-selected"],"true");
  assert.equal(events.focus,"diagnostics");
  events.toolbar();
  assert.equal(tabs[2].attributes["aria-selected"],"true");
  assert.equal(panels[2].hidden,false);
  assert.equal(panels[0].hidden,true);
  assert.equal(storage.get("am-workbench:page-advanced"),"dhcp");
  events["am:show-panel"]({detail:{panel:"inspector"}});
  assert.equal(panels[4].hidden,false);
});

test("failed live capability probes never imply unsupported firmware",()=>{
  const a=advanced.indexOf("function renderNativeDetection("),
        b=advanced.indexOf("async function probeCapabilities(",a);
  assert.ok(a>=0&&b>a);
  let report;
  const ctx={renderTrackerDiscovery:next=>{report=next;}};
  vm.runInNewContext(advanced.slice(a,b),ctx);
  vm.runInNewContext(
    'renderNativeDetection({wifi:{label:"Wi-Fi"},dns:{label:"DNS"}},'+
      '[{feature:"wifi",available:false,status:"inconclusive",'+
      'reason:"probe_inconclusive"},{feature:"dns",available:true}],'+
      '"F6600P");',ctx);
  assert.equal(report.candidate_features[0].status,"inconclusive");
  assert.equal(report.candidate_features[1].status,"detected");
  assert.equal(report.reason.includes("confirmados"),true);
});

test("capability renderer keeps inconclusive state neutral",()=>{
  const a=advanced.indexOf("function renderCapabilities("),
        b=advanced.indexOf("// DIAGNÓSTICO AUTOMÁTICO",a);
  assert.ok(a>=0&&b>a);
  const output={innerHTML:""};
  const ctx={document:{getElementById:()=>output},escapeHtml:x=>String(x)};
  vm.runInNewContext(advanced.slice(a,b),ctx);
  vm.runInNewContext(
    'renderCapabilities({wifi:{label:"Wi-Fi",writable:true}},'+
      '[{feature:"wifi",available:false,status:"inconclusive"}]);',ctx);
  assert.match(output.innerHTML,/Sondagem inconclusiva/);
  assert.doesNotMatch(output.innerHTML,/capability-state unavailable/);
});

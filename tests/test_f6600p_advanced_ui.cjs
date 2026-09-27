/* Real authenticated F6600P aliases must populate Advanced before router probes. */
"use strict";
const fs=require("node:fs"),vm=require("node:vm"),assert=require("node:assert/strict");
const source=fs.readFileSync("apps/zte_manager/static/js/advanced.js","utf8");
const from=source.indexOf("function resolvedModelCode(");
const to=source.indexOf("// Faz uma coleta pequena",from);
assert.ok(from>=0 && to>from);
const elements={
  multimodelSelect:{
    dataset:{},value:"",options:[],
    replaceChildren(...items){this.options=items;},
    add(item){this.options.push(item);}
  },
  trackerDiscoveryStatus:{textContent:""},
  trackerCapabilityGrid:{textContent:"Aguardando identificação do dispositivo."},
  adapterBadge:{textContent:"NÃO DETECTADO"},
  multimodelProbeOutput:{textContent:""},
  multimodelProbeButton:{disabled:false},
  multimodelDiagnosticButton:{disabled:false}
};
let renderCount=0;const toasts=[];const ctx={
 console,AbortController,setTimeout,clearTimeout,
 showToast:message=>toasts.push(String(message)),
 setBusy:()=>{},
 window:{renderAdaptiveDiagnostic:()=>{}},
 ontConnected:true,currentHost:"192.0.2.1",
 trackerDetectedModel:null,trackerSelectedFamily:null,
 trackerSessionGeneration:0,
 discoveryBootPromise:null,discoveryCatalogHost:null,discoveryCatalogRevision:null,
 globalThis:{currentZteRevision:"rev-1"},
 Option:function(label,value){this.label=label;this.value=value;},
 document:{getElementById:id=>elements[id]||null},
 renderTrackerDiscovery: data=>{
   renderCount++;
   elements.trackerCapabilityGrid.textContent=
     JSON.stringify(data.candidate_features);
 },
 apiRequest:async path=>{
   assert.equal(path,"/discovery/bootstrap");
   return {
     connected:true,model:"ZXHN F6600P",detected_model:"F6600P",
     model_verified:true,session_revision:"rev-1",firmware:"V9.0.10P6N34",
     native_diagnostics_available:true,
     catalog:{models:[{
       model:"F6600P",family:"f6640",protocol:"thinklua",
       candidate_features:["device_info","wifi_clients","lan_clients"]
     }]}
   };
 }
};
vm.createContext(ctx);
vm.runInContext(source.slice(from,to),ctx);
(async()=>{
  const result=await vm.runInContext("loadMultimodelCatalog()",ctx);
  assert.equal(result.native_diagnostics_available,true);
  assert.equal(elements.multimodelSelect.value,"F6600P");
  assert.match(elements.adapterBadge.textContent,/F6600P/);
  assert.equal(renderCount,1);
  assert.match(elements.trackerCapabilityGrid.textContent,/device_info/);
  assert.equal(elements.trackerDiscoveryStatus.textContent.includes("diferente"),false);
  assert.equal(vm.runInContext('resolvedModelCode("ZXHN F6600P",[{model:"F6600P"}])',ctx),"F6600P");
  assert.equal(vm.runInContext('resolvedModelCode("F670L",[{model:"F6600P"},{model:"F670L"}])',ctx),"F670L");
  // Manual model identification must be a local bootstrap, not a router scan.
  await vm.runInContext("detectConnectedModel()",ctx);
  assert.match(elements.multimodelProbeOutput.textContent,/F6600P/);
  assert.match(elements.multimodelProbeOutput.textContent,/V9.0.10P6N34/);
  assert.equal(elements.multimodelProbeButton.disabled,false);
  assert.ok(!source.includes("await autoDiscoverTracker();"),
    "Entering Advanced must not occupy the single ONT session with hidden GETs");

  // Native GET discovery remains available when POST/writing is disabled.
  const nativeFrom=source.indexOf("async function loadCapabilityCatalog()");
  const nativeTo=source.indexOf("// Relatório independente",nativeFrom);
  assert.ok(nativeFrom>=0 && nativeTo>nativeFrom);
  ctx.advancedState={capabilities:null,capabilityProbe:null};
  ctx.trackerProbeBusy=false;
  // The VM loads selected function slices; full advanced.js initializes these
  // independent operation guards before registering browser event handlers.
  ctx.modelDiagnosticRunning=false;
  ctx.advancedNetworkBusy=false;
  ctx.meshProbeBusy=false;
  ctx.routerWriteEnabled=false;
  ctx.renderCapabilities=()=>{};
  const called=[];
  ctx.apiRequest=async (path,options)=>{
    called.push(path);
    if(path==="/discovery/bootstrap") return result;
    if(path==="/device/capabilities") return {
      adapter:"zte-f6600p-thinklua",
      features:{device_info:{label:"Device"},wifi_clients:{label:"Wi-Fi"}}
    };
    if(path==="/device/capabilities/probe")
      return {features:JSON.parse(options.body).features.map(feature=>({
        feature,available:true
      }))};
    throw Error("Unexpected native discovery endpoint: "+path);
  };
  vm.runInContext(source.slice(nativeFrom,nativeTo),ctx);
  await vm.runInContext("probeCapabilities()",ctx);
  assert.equal(called.filter(p=>p==="/device/capabilities/probe").length,1);
  assert.equal(called.filter(p=>p==="/multimodel/probe").length,0);
  assert.match(elements.trackerCapabilityGrid.textContent,/detected/);

  // A vendor prefix must not reject the verified F6201B model diagnostic.
  const diagFrom=source.indexOf("let modelDiagnosticRunning = false;");
  const diagTo=source.indexOf("async function showMultimodelMesh()",diagFrom);
  assert.ok(diagFrom>=0 && diagTo>diagFrom);
  const diagCalls=[];
  ctx.apiRequest=async (path,options)=>{
    if(path==="/discovery/bootstrap") return {
      connected:true,model:"ZXHN F6201B",detected_model:"F6201B",
      model_verified:true,catalog:{models:[{
        model:"F6201B",family:"f6201b_candidate"
      }]}
    };
    if(path==="/multimodel/diagnostic"){
      const section=JSON.parse(options.body).section;
      diagCalls.push(section);
      return {model:"F6201B",family:"f6201b_candidate",
        sections:{[section]:{available:true}}};
    }
    throw Error("Unexpected diagnostic endpoint: "+path);
  };
  vm.runInContext(source.slice(diagFrom,diagTo),ctx);
  await vm.runInContext("runMultimodelDiagnostic()",ctx);
  assert.ok(diagCalls.includes("optical") && diagCalls.includes("wan"),
    "Verified F6201B aliases must reach live per-section diagnostics");
  assert.equal(elements.multimodelDiagnosticButton.disabled,false);
  console.log("Advanced local identity, explicit native GET detection, and F6201B aliases pass.");
})().catch(e=>{console.error(e);process.exitCode=1});
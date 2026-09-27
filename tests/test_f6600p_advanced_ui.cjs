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
  adapterBadge:{textContent:"NÃO DETECTADO"}
};
let renderCount=0;const ctx={
 console,AbortController,setTimeout,clearTimeout,
 ontConnected:true,currentHost:"192.0.2.1",
 trackerDetectedModel:null,trackerSelectedFamily:null,
 trackerSessionGeneration:0,
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
  console.log("F6600P actual authenticated model populates Advanced without false mismatch.");
})().catch(e=>{console.error(e);process.exitCode=1});
"use strict";
const assert=require("node:assert/strict"),test=require("node:test");
const vm=require("node:vm"),fs=require("node:fs");
const source=fs.readFileSync(
 "apps/zte_manager/static/js/features/connection_inventory.js","utf8");
const html=fs.readFileSync("apps/zte_manager/templates/index.html","utf8");
const page=fs.readFileSync(
 "apps/zte_manager/templates/source/pages/connection.html","utf8");
function mount(responder){
 const documentEvents={},nodes=new Map(),requests=[];
 const elem=(tag="div")=>({
  tagName:tag.toUpperCase(),textContent:"",className:"",children:[],
  attributes:{},value:"",handlers:{},
  classList:{contains:key=>key==="active",add(){},toggle(){}},
  setAttribute(k,v){this.attributes[k]=v;},
  addEventListener(k,fn){this.handlers[k]=fn;},
  dispatchEvent(e){this.handlers[e.type]?.(e);},
  append(...nodes){this.children.push(...nodes);},
  appendChild(node){this.children.push(node);},
  replaceChildren(...nodes){this.children=[...nodes];},
  querySelectorAll(key){return this.children.filter(node=>
    node.className?.includes(key.replace(".","")));},
  focus(){this.focused=true;}
 });
 for(const id of ["connectionInventorySearch","connectionNewTarget",
  "connectionInventoryList","connectionInventoryCount","zteIp",
  "zteUsername","page-connection"])nodes.set(id,elem());
 const doc={readyState:"complete",getElementById:id=>nodes.get(id)||null,
  createElement:elem,addEventListener:(k,fn)=>documentEvents[k]=fn};
 const ctx={document:doc,window:{},Event:class{constructor(type){this.type=type;}},
  currentHost:"",apiRequest:async(url,options)=>{
    requests.push({url,options});return responder(url,options);
  }};
 vm.runInNewContext(source,ctx);
 return {ctx,nodes,requests,documentEvents};
}
const content=node=>[String(node.textContent||""),...
  (node.children||[]).map(content)].join(" ");
const ready=()=>new Promise(resolve=>setImmediate(resolve));
test("source HTML is synchronized, preserves real connection form and no mock devices",()=>{
 for(const text of [html,page]){
  assert.match(text,/class="login-hero am-connect-story am-inventory-panel"/);
  assert.match(text,/id="connectionInventorySearch"/);
  assert.match(text,/id="connectionForm"/);
  assert.doesNotMatch(text,/Production Server|Dev Server|6 online/);
 }
 assert.match(html,/js\/features\/connection_inventory\.js/);
});
test("inventory API is the sole source: unsafe/duplicate hosts excluded",async()=>{
 const h=mount(async()=>({devices:[
  {host:"192.0.2.14",model:"F6600P",status:"online"},
  {host:"192.0.2.14",model:"F6600P",status:"offline"},
  {host:"http://admin:secret@router.example",model:"F680"},
  {host:"192.0.2.19:8080",model:"F680"}
 ]}));
 await ready();
 const list=h.nodes.get("connectionInventoryList");
 assert.equal(h.requests[0].url,"/management/inventory?limit=100");
 assert.equal(h.requests[0].options.expected,"object");
 assert.equal(list.children.length,2);
 assert.match(content(list),/192\.0\.2\.14/);
 assert.doesNotMatch(content(list),/secret|online|offline|Dev Server/);
 assert.equal(h.nodes.get("connectionInventoryCount").textContent,
   "2 equipamento(s) registrado(s)");
 list.children[0].handlers.click();
 assert.equal(h.nodes.get("zteIp").value,"192.0.2.14");
 assert.equal(h.nodes.get("zteUsername").focused,true);
 assert.equal(h.nodes.get("zteIp").type,undefined,"username/password fields are not autofilled");
 h.nodes.get("connectionInventorySearch").value="F680";
 h.nodes.get("connectionInventorySearch").handlers.input();
 assert.equal(list.children.length,1);
 assert.match(content(list),/192\.0\.2\.19/);
 h.nodes.get("connectionNewTarget").handlers.click();
 assert.equal(h.nodes.get("zteIp").value,"");
 assert.equal(h.nodes.get("connectionInventorySearch").value,"");
});
test("inventory failure leaves connection form usable",async()=>{
 const h=mount(async()=>{throw new Error("GET /api?password=secret");});
 await ready();
 assert.match(content(h.nodes.get("connectionInventoryList")),
   /conexão manual continua disponível/);
 assert.doesNotMatch(content(h.nodes.get("connectionInventoryList")),/secret|GET/);
 assert.equal(h.nodes.get("connectionInventoryList").attributes["aria-busy"],"false");
});

"use strict";
const test=require("node:test"),assert=require("node:assert/strict");
const fs=require("node:fs"),vm=require("node:vm");
const formJS=fs.readFileSync("apps/zte_manager/static/js/tangerine_forms.js","utf8");
const managementJS=fs.readFileSync("apps/zte_manager/static/js/management.js","utf8");
function mount(initial='{"mtu":1492}') {
  const listeners={};
  function element(tag) {
    return {tagName:tag.toUpperCase(),className:"",children:[],textContent:"",
      value:"",attributes:{},style:{},setAttribute(k,v){this.attributes[k]=v;},
      classList:{add(){}},addEventListener(k,fn){(this.handlers||=(new Map())).set(k,fn);},
      fire(name){this.handlers?.get(name)?.({target:this});},
      append(...items){this.children.push(...items);},
      appendChild(item){this.children.push(item);},
      insertBefore(item,following){
        const index=this.children.indexOf(following);
        if(index<0)this.children.push(item);else this.children.splice(index,0,item);
      },focus(){},remove(){this.removed=true;}}
  }
  const parent=element("div");
  const label=element("label");
  label.querySelector=selector=>selector==="span"?{textContent:"WAN"}:null;
  label.parentNode=parent;
  const source=element("textarea");
  source.id="managementWanJson";source.value=initial;
  source.closest=()=>label;
  source.dispatchEvent=()=>{};
  const doc={
    readyState:"complete",body:{classList:{add(){}}},
    getElementById:id=>id==="managementWanJson"?source:null,
    createElement:element,
    addEventListener(k,fn){listeners[k]=fn;}
  };
  const window={},scope={document:doc,window,Event:class {}};
  vm.runInNewContext(formJS,scope);
  const editor=parent.children.find(node=>node.className==="am-form-editor");
  function find(node,predicate) {
    if(!node)return null;
    if(predicate(node))return node;
    for(const child of node.children||[]) {
      const result=find(child,predicate);if(result)return result;
    }
    return null;
  }
  return {source,editor,window,find};
}
test("invalid numeric field blocks actual management payload",()=>{
 const h=mount();
 assert.ok(h.editor,"real structured editor did not mount");
 const number=h.find(h.editor,n=>n.tagName==="INPUT"&&n.type==="number");
 assert.ok(number,"typed input did not mount");
 number.value="invalido";number.fire("input");number.fire("change");
 assert.throws(()=>h.window.TangerineFormController.assertValid(h.source.id),
   /Revise os campos/);
 const begin=managementJS.indexOf("function managementParseJson(");
 const end=managementJS.indexOf("function managementOutput(",begin);
 const ctx={document:{getElementById:()=>h.source},window:h.window};
 vm.runInNewContext(managementJS.slice(begin,end)+"\nthis.parse = managementParseJson;",ctx);
 assert.throws(()=>ctx.parse("managementWanJson"),/Revise os campos/);
 assert.equal(JSON.parse(h.source.value).mtu,1492,
   "invalid field must not corrupt last known valid configuration");
 number.value="1500";number.fire("input");number.fire("change");
 assert.equal(ctx.parse("managementWanJson").mtu,1500);
});
test("unfinished dynamic parameter blocks submission, removal restores safety",()=>{
 const h=mount("{}");
 const add=h.find(h.editor,n=>n.className==="am-add-setting");
 assert.ok(add);add.fire("click");
 assert.throws(()=>h.window.TangerineFormController.assertValid(h.source.id));
 const row=h.find(h.editor,n=>n.className==="am-dynamic-field");
 assert.ok(row); const [name,type,value,remove]=row.children;
 name.value="channel";type.value="number";value.value="36";
 name.fire("change");value.fire("change");
 assert.equal(h.window.TangerineFormController.assertValid(h.source.id),true);
 assert.equal(JSON.parse(h.source.value).channel,36);
 name.value="__proto__";name.fire("input");name.fire("change");
 assert.throws(()=>h.window.TangerineFormController.assertValid(h.source.id));
 assert.equal(JSON.parse(h.source.value).channel,36,"failed rename must keep saved value");
 remove.fire("click");
 assert.equal(h.window.TangerineFormController.assertValid(h.source.id),true);
 assert.deepEqual(JSON.parse(h.source.value),{});
});
test("prototype injection and deep malicious JSON are always rejected",()=>{
 const h=mount("{}"),core=h.window.TangerineFormsCore;
 assert.throws(()=>core.assignPath({},["__proto__","polluted"],true));
 assert.throws(()=>core.assignPath({},["constructor","prototype"],{}));
 assert.throws(()=>core.validateConfig(JSON.parse(
   '{"wifi":{"__proto__":{"polluted":"yes"}}}')));
 assert.equal({}.polluted,undefined);
});
test("technical management exports redact secrets at all depths",()=>{
 const start=managementJS.indexOf("function managementJson(");
 const end=managementJS.indexOf("function managementParseJson(",start);
 assert.ok(start>=0&&end>start);
 const ctx={};vm.runInNewContext(managementJS.slice(start,end)+
   "\nthis.redacted=managementJson;",ctx);
 const result=ctx.redacted({
   model:"F6600P",enabled:true,password:"DO_NOT_SHARE",
   config:{session_token:"SECRET_123",url:"https://user:pass@example.com",
     message:"password=very-secret",wlan:{ssid:"MinhaRede"}}
 });
 assert.doesNotMatch(result,/DO_NOT_SHARE|SECRET_123|very-secret|user:pass/);
 assert.match(result,/F6600P|MinhaRede/);
 assert.equal(JSON.parse(result).enabled,true);
});

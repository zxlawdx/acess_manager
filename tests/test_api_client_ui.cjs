"use strict";
const test = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const vm = require("node:vm");
const errors = fs.readFileSync(
  "apps/zte_manager/static/js/core/api_errors.js","utf8");
const app = fs.readFileSync(
  "apps/zte_manager/static/js/app.js","utf8");
const start=app.indexOf("async function apiRequest(");
const end=app.indexOf("// CONEXÃO",start);
assert.ok(start>0 && end>start,"API function not found");

function harness(responder){
  const events=[],updates=[];
  const context={
    console,AbortController,Date,
    fetch:responder,window:{},API_BASE:"/api",
    pendingApiRequests:0,explicitBusy:false,clickFeedbackUntil:0,
    lastActionText:"",renderBusyOverlay(){},
    updateRequestStatus(message){updates.push(message||"");},
    clearTimeout(){},setTimeout(){return 1;},
    document:{getElementById(){return {classList:{contains(){return false}}};},
      dispatchEvent(event){events.push(event.detail);}},
    CustomEvent:class{constructor(name,init){this.name=name;this.detail=init.detail;}}
  };
  vm.createContext(context);
  vm.runInContext(errors,context);
  vm.runInContext(app.slice(start,app.lastIndexOf("// =========================================================",end)),context);
  return {request:context.apiRequest,context,events,updates};
}
const response=(status,body,contentType="application/json")=>({
  ok:status>=200&&status<300,status,
  headers:{get(key){return key==="content-type"?contentType:null;}},
  async json(){return body;},async text(){return String(body);}
});

test("true success and expected-object schema pass unchanged",async()=>{
  const h=harness(async()=>response(200,{model:"F6600P",success:true}));
  const result=await h.request("/connect",{method:"POST",expected:"object"});
  assert.equal(result.model,"F6600P");
  assert.equal(h.context.pendingApiRequests,0);
});
test("body errors returned with HTTP 200 still reject and classify auth",async()=>{
  const h=harness(async()=>response(200,{
    error:"POST /login?password=PRIVATE",type:"authentication",code:"AUTH_FAILED"
  }));
  await assert.rejects(h.request("/connect"),error=>{
    assert.equal(error.code,"AUTH_FAILED");
    assert.doesNotMatch(error.message,/PRIVATE|POST|\/login/i);
    return true;
  });
  assert.equal(h.context.pendingApiRequests,0);
  assert.equal(h.events[0].kind,"authentication");
});
test("partial operation is not reported as success",async()=>{
  const h=harness(async()=>response(200,{
    success:false,code:"OPERATION_PARTIAL",completed:2,total:4,
    error:"POST /router?token=PRIVATE"
  }));
  await assert.rejects(h.request("/profiles/apply"),error=>{
    assert.equal(error.kind,"partial");
    assert.match(error.message,/2 de 4/);
    assert.doesNotMatch(error.message,/PRIVATE/);
    return true;
  });
});
test("HTTP 404 is an unconfirmed route not absent firmware",async()=>{
  const h=harness(async()=>response(404,"POST /api/login?password=PRIVATE","text/html"));
  await assert.rejects(h.request("/discovery/capabilities"),error=>{
    assert.equal(error.code,"ROUTE_UNCONFIRMED");
    assert.notEqual(error.kind,"unsupported");
    assert.doesNotMatch(error.message,/PRIVATE|POST|\/api/);
    return true;
  });
});
test("unexpected successful JSON and transport failures remain distinct",async()=>{
  const h=harness(async()=>({
    ok:true,status:200,headers:{get(){return "application/json"}},
    async json(){throw new SyntaxError("router internal raw HTTP");}
  }));
  await assert.rejects(h.request("/wan/status"),error=>{
    assert.equal(error.code,"INVALID_DEVICE_RESPONSE");
    assert.doesNotMatch(error.message,/HTTP/);
    return true;
  });
  const n=harness(vm.runInNewContext("(async()=>{throw new TypeError('Failed to fetch')})"));
  await assert.rejects(n.request("/wan/status"),/Não foi possível/);
});
test("explicit positive firmware evidence is the only absent capability",()=>{
  const context={window:{}};
  vm.runInNewContext(errors,context);
  const classify=context.window.AccessManagerErrors;
  assert.equal(classify.fromPayload({code:"FEATURE_ABSENT"}).kind,"unsupported");
  assert.notEqual(classify.fromPayload({}, {status:404}).kind,"unsupported");
});

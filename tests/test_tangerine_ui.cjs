"use strict";
/* DOM- and firmware-free smoke tests for the Tangerine integration.
 * Run with: node --test tests/test_tangerine_ui.cjs
 */
const test = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const vm = require("node:vm");
const root = "apps/zte_manager";
const html = fs.readFileSync(root+"/templates/index.html", "utf8");
const css = fs.readFileSync(root+"/static/css/tangerine.css", "utf8");
const app = fs.readFileSync(root+"/static/js/app.js", "utf8");
const theme = fs.readFileSync(root+"/static/js/neutral_theme.js", "utf8");
const shell = fs.readFileSync(root+"/static/js/tangerine_shell.js", "utf8");
const advanced = fs.readFileSync(root+"/static/js/advanced.js", "utf8");

test("Vela page contracts survive the Tangerine navigation change", () => {
  const ids = [...html.matchAll(/class="menu-item[^"]*" data-page="([^"]+)"/g)].map(x=>x[1]);
  const expected = ["connection","dashboard","clients","device","wifi","wan",
    "profiles","tr069","supportDiagnostic","diagnostics","advanced","management"];
  assert.deepEqual([...ids].sort(), [...expected].sort());
  for (const id of expected) assert.match(html, new RegExp('id="page-'+id+'"'));
  for (const action of ["connectionForm","connectButton","applyProfileButton","trackerCapabilityGrid"]) {
    assert.ok(html.includes('id="'+action+'"'), action+" must keep backend handlers");
  }
  assert.match(html, /zte_manager\/css\/tangerine\.css/);
  assert.match(html, /zte_manager\/js\/tangerine_shell\.js/);
  assert.match(html, /id="appearanceSelect"/);
  assert.match(html, /id="sidebarCollapseToggle"/);
  assert.doesNotMatch(html, /12 devices online|SSH connection established|acme-corp\.local/);
});

test("Tangerine tokens include both Figma palettes and reduced-motion support", () => {
  for (const fragment of ["--am-bg:#FFFDF8", "--am-primary:#FF6C37",
    "--am-sidebar:#FFF3E8","--am-bg:#211C19","--am-primary:#FF8654",
    "--am-sidebar:#28211D","prefers-reduced-motion","is-collapsed"]) {
    assert.ok(css.includes(fragment),fragment);
  }
});

test("HTTP/firmware raw errors are not rendered by the common API helper", () => {
  const start = app.indexOf("function normalizeApiErrorMessage(");
  const end = app.indexOf("// Indicador independente",start);
  assert.ok(start>=0 && end>start);
  const ctx = {};
  vm.runInNewContext(app.slice(start,end)+"\nthis.safe = normalizeApiErrorMessage;",ctx);
  assert.doesNotMatch(ctx.safe('POST /api/wan?password=secret HTTP/1.1').toLowerCase(),
    /post|password|\/api\/|secret/);
  assert.match(ctx.safe("ignored",404),/não está disponível/i);
  assert.match(ctx.safe("Internal Server Error",500),/não conseguiu concluir/i);
  assert.match(ctx.safe(new Error("Failed to fetch")),/sem comunicação/i);
  assert.equal(ctx.safe("Perfil não encontrado"),"Perfil não encontrado");
  assert.ok(app.includes("normalizeApiErrorMessage(") && app.includes("response.status,"));
  assert.ok(app.includes('data && typeof data === "object" ? data.type'));
  assert.match(ctx.safe("Recurso não implementado", 0, "unsupported"),/não está disponível/i);
  assert.match(ctx.safe("Not Found", 404),/ainda não foi confirmado/i);
  assert.match(advanced,/escapeHtml\(normalizeApiErrorMessage\(message/);
});

test("automatic appearance tracks OS changes, manual choice stays persisted", () => {
  const memory = new Map();
  const listeners = {};
  const select = {value:"",addEventListener:(type,fn)=>listeners.select=fn};
  const button = {setAttribute:()=>{},addEventListener:(type,fn)=>listeners.toggle=fn};
  const doc = {documentElement:{dataset:{}},readyState:"complete",
    getElementById:id=>id==="appearanceSelect"?select:id==="themeToggle"?button:null};
  const media={matches:false,addEventListener:(type,fn)=>listeners.media=fn};
  vm.runInNewContext(theme,{document:doc,localStorage:{
    getItem:key=>memory.get(key)||null,setItem:(key,v)=>memory.set(key,v)
  },matchMedia:()=>media});
  assert.equal(doc.documentElement.dataset.appearance,"auto");
  assert.equal(doc.documentElement.dataset.theme,"light");
  media.matches=true;listeners.media();
  assert.equal(doc.documentElement.dataset.theme,"dark");
  select.value="light";listeners.select({target:select});
  assert.equal(memory.get("zte-automatic-theme"),"light");
  media.matches=false;listeners.media();
  assert.equal(doc.documentElement.dataset.theme,"light");
  select.value="auto";listeners.select({target:select});
  media.matches=true;listeners.media();
  assert.equal(doc.documentElement.dataset.theme,"dark");
});


test("dashboard mirrors real session and hides untrusted history payloads", async () => {
  const handlers={},elements=new Map();
  function element(id,text="") {
    const state={id,_text:text,children:[],classList:{
      contains:()=>id==="page-dashboard",toggle(){}},
      get textContent(){return this._text;},
      set textContent(v){this._text=v;this.children=[];},
      setAttribute(){},addEventListener:(kind,fn)=>{handlers[id+kind]=fn;},
      querySelector:()=>({textContent:""}),
      replaceChildren(){this.children=[];},
      appendChild(child){this.children.push(child);}
    };
    elements.set(id,state);
    return state;
  }
  for(const id of ["sidebarCollapseToggle","overviewModel","overviewHost",
    "overviewHistory","overviewHistoryRefresh","overviewConnectionStatus",
    "page-dashboard","connectionStatus"]) element(id);
  element("connectedModel","F6201B");
  element("connectedHost","192.0.2.4");
  const doc={
    readyState:"complete",body:{classList:{contains:()=>true}},
    querySelector:()=>({classList:{toggle(){}},querySelectorAll:()=>[]}),
    getElementById:id=>elements.get(id)||null,addEventListener(){},
    createElement:tag=>({tagName:tag,textContent:"",children:[],
      append(...items){this.children.push(...items);}})
  };
  let called="";
  vm.runInNewContext(shell,{
    document:doc,localStorage:{getItem:()=>null,setItem(){}},
    MutationObserver:class{observe(){}},
    apiRequest:async endpoint=>{
      called=endpoint;
      return {changes:[
        {operation:"Wi-Fi alterado",success:true,created_at:"2026-09-29T11:33:22"},
        {operation:"POST /api?password=private",success:false,
          created_at:"2026-09-29T12:33:22"}
      ],diagnostics:[]};
    }
  });
  await handlers["overviewHistoryRefreshclick"]();
  assert.equal(elements.get("overviewModel").textContent,"F6201B");
  assert.equal(elements.get("overviewHost").textContent,"192.0.2.4");
  assert.equal(called,"/history?limit=5");
  const cards=elements.get("overviewHistory").children;
  assert.equal(cards.length,2);
  assert.equal(cards[0].children[0].textContent,"Alteração de configuração");
  assert.equal(cards[1].children[0].textContent,"Wi-Fi alterado");
  assert.doesNotMatch(JSON.stringify(cards),/password|private|POST|\/api/);
});

test("collapse persists without triggering backend navigation", () => {
  const saved = new Map(),listeners={},classes = new Set();
  const sidebar = {classList:{toggle:(name,enabled)=>enabled?classes.add(name):classes.delete(name)},
    querySelectorAll:()=>[]};
  const glyph={textContent:""};
  const toggle={setAttribute:()=>{},querySelector:()=>glyph,
    addEventListener:(type,fn)=>listeners.click=fn};
  const doc={readyState:"complete",querySelector:()=>sidebar,
    getElementById:id=>id==="sidebarCollapseToggle"?toggle:null};
  vm.runInNewContext(shell,{document:doc,localStorage:{
    getItem:key=>saved.get(key)||null,setItem:(key,v)=>saved.set(key,v)
  }});
  assert.equal(classes.has("is-collapsed"),false);
  listeners.click();
  assert.equal(classes.has("is-collapsed"),true);
  assert.equal(saved.get("access-manager-sidebar-collapsed"),"true");
});

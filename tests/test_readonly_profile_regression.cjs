/* Real regressions: no blank 2.4/5 GHz presets on read-only F6201B.
 * Run with built-in node:vm only. Absolutely no physical ONT required. */
const assert = require("node:assert/strict");
const fs = require("node:fs");
const vm = require("node:vm");
const app = fs.readFileSync("apps/zte_manager/static/js/app.js", "utf8");
const editor = fs.readFileSync("apps/zte_manager/static/js/f6201b_editor.js", "utf8");
const extract = (begin, end) => {
  const start = app.indexOf(begin), finish = app.indexOf(end, start + begin.length);
  assert.ok(start !== -1 && finish > start, begin + " missing");
  return app.slice(start, finish);
};
const loading = extract("async function loadProfile()", "async function renderProfileForm(");
const channels = extract("async function fillChannelSelect(", "function securitySelect(");

async function testSavedAttendantProfile() {
  const calls = [];
  const preset = {wifi: {
    "2.4GHz": {auto_channel: false, channel: 11, bandwidth: "20MHz"},
    "5GHz": {auto_channel: false, channel: 149, bandwidth: "80MHz"}
  }, dns: {ipv4_1: "192.0.2.1"}};
  const nodes = {
    profileAttendant: {textContent:""},
    dashboardProfileName: {textContent:""}
  };
  const ctx = {
    console, Promise, sessionEpoch:1, currentAttendant:"tech-A",
    currentProfile:null, profileLoadedFor:null, profileLoadPending:null,
    document: {
      getElementById: id => nodes[id],
      querySelector: selector => /2.4GHz|5GHz/.test(selector) ? {} : null
    },
    apiRequest: async (path,options) => {
      calls.push([path,JSON.parse(options.body).attendant]);
      assert.equal(path, "/profiles/get");
      return preset;
    },
    renderProfileForm: async profile => calls.push([
      "render", profile.wifi["2.4GHz"].channel, profile.wifi["5GHz"].channel
    ])
  };
  vm.createContext(ctx);
  vm.runInContext(loading,ctx);
  await Promise.all([
    vm.runInContext("ensureAttendantProfile()",ctx),
    vm.runInContext("ensureAttendantProfile()",ctx)
  ]);
  assert.equal(calls.filter(item=>item[0]==="/profiles/get").length,1,
    "deduplicate local preset loads on page open and read-only login");
  assert.equal(ctx.currentProfile.wifi["2.4GHz"].channel,11);
  assert.equal(ctx.currentProfile.wifi["5GHz"].channel,149);
  assert.equal(ctx.profileLoadedFor,"1:tech-A");
  assert.equal(nodes.profileAttendant.textContent,"tech-A");
  // Switching the technician must NOT retain the former profile.
  ctx.sessionEpoch=2;
  ctx.currentAttendant="tech-B";
  await vm.runInContext("ensureAttendantProfile()",ctx);
  assert.equal(calls.filter(item=>item[0]==="/profiles/get").length,2);
  assert.equal(calls.at(-2)[1],"tech-B");
}

async function testOfflineChannels() {
  const selects = new Map();
  function selectFor(id) {
    if(!selects.has(id)) {
      const obj={options:[],value:""};
      Object.defineProperty(obj,"innerHTML",{set(text) {
        assert.match(text,/Auto/);
        this.options=[{value:"Auto",textContent:"Auto"}];
      }});
      obj.add = function(option){this.options.push(option)};
      selects.set(id,obj);
    }
    return selects.get(id);
  }
  let requests=0;
  const ctx={
    console, Promise,
    Option:function(label,value){this.label=label;this.value=value;},
    bandKey:band=>band.replaceAll(".","_"),
    document:{getElementById:id=>selectFor(id)},
    apiRequest: async()=>{requests++;throw new Error("No compatible router API");},
  };
  vm.createContext(ctx);
  vm.runInContext(channels,ctx);
  await vm.runInContext('fillChannelSelect("2.4GHz","20MHz",11,"BRI","profile")',ctx);
  await vm.runInContext('fillChannelSelect("5GHz","80MHz",149,"BRI","profile")',ctx);
  assert.equal(selectFor("profileChannel-2_4GHz").value,"11");
  assert.equal(selectFor("profileChannel-5GHz").value,"149");
  assert.equal(requests,0,"saved presets must not call model-dependent endpoints");
  await vm.runInContext('fillChannelSelect("5GHz","80MHz",165,"XX","profile")',ctx);
  assert.equal(selectFor("profileChannel-5GHz").value,"165",
    "preserve manually saved channels for unsupported country lists too");
}

function testReadOnlyAndDnsIsolation() {
  assert.ok(app.includes("if (response.writes_enabled === false)"));
  assert.ok(app.includes("await ensureAttendantProfile()"),
    "experimental login needs the local profile before early return");
  const restore=extract("async function restoreDesktopSession()", "function initZteAutomatic()");
  assert.ok(restore.indexOf("await ensureAttendantProfile()") <
    restore.indexOf("if (routerWriteEnabled)"),
    "desktop restores experimental profiles before native-only router queries");
  const dns=editor.slice(editor.indexOf("async function renderDnsProfile()"),
    editor.indexOf("async function open(page)"));
  assert.ok(!dns.includes("primary.value = current.ipv4_1"));
  assert.ok(!dns.includes("secondary.value = current.ipv4_2"));
  assert.ok(dns.includes('await apiRequest("/f6201b/dns/status")'));
  const apply=extract("async function applyExperimentalF6201BProfile()",
    "async function applyProfile()");
  assert.ok(apply.includes("proposal.noop === true"),
    "matching profile must not attempt an undefined-nonce Apply");
  assert.ok(apply.includes("renderProfileActionError(profileStage, error)"));
}
(async()=>{
  await testSavedAttendantProfile();
  await testOfflineChannels();
  testReadOnlyAndDnsIsolation();
  console.log("Read-only profiles: both bands, saved channels, DNS isolation, no-op and errors OK");
})().catch(error=>{console.error(error);process.exitCode=1});

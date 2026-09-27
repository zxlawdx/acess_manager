/* Regression contracts: unique DHCP controls, isolated ACS secrets and named presets. */
"use strict";
const assert=require("node:assert/strict"),fs=require("node:fs");
const read=p=>fs.readFileSync("apps/zte_manager/"+p,"utf8");
const html=read("templates/index.html"),app=read("static/js/app.js"),
advanced=read("static/js/advanced.js"),dhcp=read("static/js/dhcp_module.js"),
tr069=read("static/js/tr069_profiles.js"),
named=read("static/js/named_presets.js");
for(const id of [
 "dhcpEnabled","advancedDhcpEnabled","dhcpDns1","advancedDhcpDns1",
 "dhcpDns2","advancedDhcpDns2"
]){
 assert.equal((html.match(new RegExp('id="'+id+'"','g'))||[]).length,1,
   "Duplicated/missing DHCP input id: "+id);
}
assert.ok(advanced.includes('"advancedDhcpEnabled"'));
assert.ok(advanced.includes('"advancedDhcpDns1"'));
assert.ok(dhcp.includes('id("dhcpEnabled")'));
assert.ok(dhcp.includes("data.write_safe !== false"));
assert.ok(html.includes('data-page="tr069"'));
assert.ok(html.includes('id="page-tr069"'));
assert.ok(app.includes("tr069: {"));
for(const text of [
 '"/tr069/providers"','"/tr069/providers/save"',
 '"/tr069/providers/apply"','"/tr069/setup"',
 "clearSecrets();",
 "Selecione a WAN PPPoE"
]) assert.ok(tr069.includes(text),text);
assert.ok(!/localStorage|sessionStorage/.test(tr069),
 "ACS credentials must never be saved in WebView storage");
for(const path of ["tr069_profiles.js","named_presets.js"])
 assert.ok(html.includes("zte_manager/js/"+path),"Missing script "+path);
assert.ok(named.includes('"/profiles/named/save"'));
assert.ok(named.includes('"/profiles/named/apply"'));
assert.ok(named.includes("collectProfileForm()"));
assert.ok(app.includes("globalThis.activeNamedPreset"));
console.log("DHCP unique IDs; named presets and session-only TR069 form contracts OK.");

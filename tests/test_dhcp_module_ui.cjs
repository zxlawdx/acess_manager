/* Contracts for device-driven DHCP and native F6201B network tests. */
const assert = require("node:assert/strict");
const fs = require("node:fs");
const html = fs.readFileSync("apps/zte_manager/templates/index.html","utf8");
const js = fs.readFileSync("apps/zte_manager/static/js/dhcp_module.js","utf8");
const app = fs.readFileSync("apps/zte_manager/static/js/app.js","utf8");
const css = fs.readFileSync("apps/zte_manager/static/css/dhcp_module.css","utf8");
const zte = fs.readFileSync("apps/zte_manager/static/js/f6201b_editor.js","utf8");
for (const id of [
  "dhcpModule","dhcpConfigForm","dhcpApply","dhcpLeases","dhcpIpv6",
  "pingCount","pingSize","pingTimeout","pingOutput","tracerouteOutput"
]) assert.ok(html.includes('id="'+id+'"'),"Missing control "+id);
assert.ok(html.includes("dhcp_module.css") && html.includes("dhcp_module.js"));
assert.ok(js.includes("/network/dhcp/update"));
assert.ok(js.includes("/network/dhcp"));
assert.ok(js.includes("/f6201b/workbench/update"));
assert.ok(js.includes("renderIpv6") && js.includes("renderReservations"));
assert.ok(!js.includes("risk_ack") && !js.includes("confirmation"),
  "DHCP must not require duplicate internal approvals");
assert.ok(app.includes("perda_percentual") && app.includes("data_size"));
assert.ok(app.includes("Array.isArray(data.hops)"));
assert.ok(zte.includes("/f6201b/write/update") &&
          zte.includes("/f6201b/dns/update"));
assert.ok(!zte.includes('"/f6201b/dns/preview"') &&
          !zte.includes('"/f6201b/write/preview"'));
assert.ok(css.includes("--ui-elevated") && css.includes("@media"));
console.log("Device-driven DHCP, native diagnostics and one-click UI contracts passed");

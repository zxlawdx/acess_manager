// Contract guard: the new lab must not alter native model handlers.
const assert = require("node:assert/strict");
const fs = require("node:fs");
const index = fs.readFileSync("apps/zte_manager/templates/index.html", "utf8");
const js = fs.readFileSync("apps/zte_manager/static/js/f6201b_workbench.js", "utf8");
const css = fs.readFileSync("apps/zte_manager/static/css/f6201b_workbench.css", "utf8");
assert.ok(index.includes("zte_manager/js/f6201b_workbench.js"));
assert.ok(index.includes("zte_manager/css/f6201b_workbench.css"));
assert.ok(index.indexOf("brmodelo_workbench.css") <
          index.indexOf("f6201b_workbench.css"),
          "Workbench only extends the existing skin");
assert.ok(index.indexOf("neutral_theme.js") <
          index.indexOf("f6201b_workbench.js"),
          "Keep native theme/DOM setup intact");
for (const id of [
  "featureInspectorOutput", "wifiNetworks", "wanConnections",
  "lanPorts", "wifiClientsTable", "supportDiagnosticForm"
]) assert.ok(index.includes('id="' + id + '"'), "Native component lost: " + id);
for (const contract of [
  "zte:session-changed", "zte:page-open", "checkedModel",
  "model_verified", "writes_enabled === false", "/discovery/bootstrap",
  "/f6201b/workbench/catalog", "/f6201b/workbench/inspect",
  "/f6201b/workbench/preview", "/f6201b/workbench/apply",
  "risk_ack", "current.nonce", "textContent"
]) assert.ok(js.includes(contract), "Missing UI/session contract: " + contract);
assert.ok(!js.includes("innerHTML"), "No firmware-controlled HTML injection");
assert.ok(css.includes("#f6201b-workbench"), "Scoped workbench styles");
assert.ok(css.includes("--ui-accent") && css.includes("@media"),
    "Match BRModelo palette and responsive constraints");
assert.ok(!/(?:linear|radial|conic)-gradient\s*\(/.test(css),
    "No futuristic/decorative gradients");
console.log("F6201B captured form UI contract/asset tests passed.");

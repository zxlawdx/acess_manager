const assert = require("node:assert/strict");
const fs = require("node:fs");
const css = fs.readFileSync("apps/zte_manager/static/css/brmodelo_workbench.css","utf8");
const index = fs.readFileSync("apps/zte_manager/templates/index.html","utf8");
assert.ok(index.includes('zte_manager/css/brmodelo_workbench.css'));
assert.ok(index.indexOf("neutral_console.css") <
          index.indexOf("brmodelo_workbench.css"),
    "Workbench must override existing theme without altering base DOM");
for (const token of [
  "--ui-bg","--ui-sidebar","--ui-surface","--ui-text","--ui-accent",
  "--ui-success","--ui-warning","--ui-danger"
]) assert.ok(css.includes(token+":"),"Missing CSS theme token: "+token);
assert.ok(css.includes('html[data-theme="light"]'));
assert.ok(css.includes('html[data-theme="dark"]'));
assert.ok(css.includes(".sidebar") && css.includes(".menu-item.active"));
assert.ok(css.includes(".ssid-card") && css.includes(".port-card"));
assert.ok(css.includes(".wan-card") && css.includes(".table-wrap"));
assert.ok(!/(?:linear|radial|conic)-gradient\s*\(/.test(css),
    "No decorative gradients in workbench design");
for(const preserved of ["wifiNetworks","lanPorts","wifiClientsTable",
                        "profileApplyResult","supportDiagnosticForm"]){
    assert.ok(index.includes('id="'+preserved+'"'),
              "Original component missing: "+preserved);
}
console.log("brModelo-inspired workbench skin preserves existing components.");

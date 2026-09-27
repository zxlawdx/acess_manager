/* F6201B normal operator writes and captured READ menu regression. */
"use strict";
const fs = require("node:fs"), assert = require("node:assert/strict");
const read = name => fs.readFileSync(
  "apps/zte_manager/static/js/" + name, "utf8"
);
const editor = read("f6201b_editor.js");
const workbench = read("f6201b_workbench.js");
const support = read("support_diagnostics.js");
const advanced = read("advanced.js");

assert.ok(editor.includes('endsWith("F6201B")'),
  "Vendor-prefixed verified model must work");
assert.ok(workbench.includes('norm.endsWith("F6201B")'));
assert.ok(!editor.includes('!ontConnected || routerWriteEnabled'),
  "Writable sessions must not hide specialized F6201B reading");
assert.ok(!workbench.includes('info?.writes_enabled === false'),
  "Workbench should not depend on artificial read-only state");
assert.ok(workbench.includes('api("/multimodel/mapped-routes")'));
assert.ok(workbench.includes('api("/multimodel/mapped-inspect"'));
assert.ok(workbench.includes("renderGetInventory(root)"));
assert.ok(support.includes("Protocol selection is independent"));
assert.ok(support.includes("classicF6201BDiagnostic(state, {full, dashboard})"));
assert.ok(advanced.includes("await runMultimodelDiagnostic()"),
  "GET diagnostic discovery remains available when POST unavailable");
console.log("F6201B native operator write/read UI contract passed.");

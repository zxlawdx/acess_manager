/* F6201B should reuse the original support form, not an oversized new panel. */
const fs = require("node:fs");
const assert = require("node:assert/strict");
const source = fs.readFileSync(
    "apps/zte_manager/static/js/support_diagnostics.js","utf8"
);
const template = fs.readFileSync(
    "apps/zte_manager/templates/index.html","utf8"
);
for (const item of [
    "supportDiagnosticForm", "supportDiagnosticMode",
    "supportDiagnosticOutput", "supportGenerateAttendance"
]) assert.ok(template.includes('id="'+item+'"'),"Missing old component "+item);
assert.ok(source.includes("classicF6201BDiagnostic(state)"),
    "Read-only F6201B does not use native report");
assert.ok(source.includes("firmwareDiagnosticState.classicMode"),
    "Original form mode not selected");
assert.ok(source.includes('panel.classList.toggle("hidden", classic)'),
    "Fullscreen technical panel may cover old support form");
for(const name of [
    "supportIncludeSpeedtest", "supportAutoOptimizeWifi",
    "supportIncludeTraceroute"
]) assert.ok(source.includes(name),"Unsafe checkbox not protected: "+name);
assert.ok(source.includes("supportDiagnosticState.firmwareReport = report"),
    "Native attendance generation must remain available");
assert.ok(source.includes("bootstrap.session_revision"),
    "Running diagnosis must be tied to the active session");
console.log("Classic support layout and read-only command isolation preserved.");

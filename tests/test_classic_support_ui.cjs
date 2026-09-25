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
assert.ok(source.includes("classicF6201BDiagnostic(state, {full, dashboard})"),
    "Classic F6201B layout must run the full authenticated workflow");
assert.ok(source.includes("firmwareDiagnosticState.classicMode"),
    "Original form mode not selected");
assert.ok(source.includes('panel.classList.toggle("hidden", classic)'),
    "Fullscreen technical panel may cover old support form");
for(const name of [
    "supportIncludeSpeedtest", "supportAutoOptimizeWifi",
    "supportIncludeTraceroute"
]) assert.ok(source.includes(name),"Original checkbox missing: "+name);
assert.ok(!source.includes("element.disabled = classic"),
    "F6201B checkboxes must never be forcibly disabled by app profile");
assert.ok(source.includes('"/diagnostics/support/f6201b"'),
    "Checkbox selection must reach a real backend diagnostic");
assert.ok(source.includes('"/diagnostics/attendance"'),
    "Every model uses the same session-wide attendance service");
assert.ok(!source.includes("window.composeFirmwareAttendance(supportDiagnosticState.firmwareReport)"),
    "Never generate a truncated browser-only F6201B attendance report");
assert.ok(source.includes("supportDiagnosticState.firmwareReport = report"),
    "Native diagnostic results must be included in attendance");
assert.ok(source.includes("bootstrap.session_revision"),
    "Running diagnosis must be tied to the active session");
console.log("Classic support UI: all checkboxes enabled, live F6201B workflow and session-wide attendance.");

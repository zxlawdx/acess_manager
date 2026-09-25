/* Profile Apply must never bypass captured F6201B preflight. */
const assert = require("node:assert/strict");
const fs = require("node:fs");
const app = fs.readFileSync("apps/zte_manager/static/js/app.js","utf8");
const editor = fs.readFileSync("apps/zte_manager/static/js/f6201b_editor.js","utf8");
const body = app.slice(
    app.indexOf("async function applyExperimentalF6201BProfile()"),
    app.indexOf("async function applyProfile()")
);
assert.ok(body.includes('"/discovery/bootstrap"'));
assert.ok(body.includes("identity.model_verified !== true"));
assert.ok(body.includes('await ensureAttendantProfile()'),
    "Require the authenticated attendant's saved profile");
assert.ok(body.includes('await saveProfile(true)'),
    "Persist what is on screen before any request to the ONT");
assert.ok(body.includes('"/f6201b/profile/apply-saved"'),
    "One click must trigger the real server Apply, not stop at preview");
assert.ok(!body.includes('"/f6201b/profile/preview"'));
assert.ok(!body.includes('"/f6201b/profile/apply"'));
assert.ok(!body.includes('confirmation.value'),
    "Never require a second typed confirmation from the attendant");
assert.ok(body.includes('report.noop') && body.includes('report.failed_stage'),
    "Display verified no-op or precise failed write stage");
assert.ok(body.includes("profileApplyInProgress"),
    "Concurrent clicks must not repeat ONT writes");
assert.ok(body.includes("report.not_included"),"Warn about unsupported fields");
const handler=app.slice(
    app.indexOf("async function applyProfile()"),
    app.indexOf("function renderProfileApplyResult")
);
assert.ok(handler.includes("await applyExperimentalF6201BProfile()"));
assert.ok(handler.includes('"/profiles/apply"'),
    "Preserve original native family flow");
assert.ok(app.includes('void renderProfileForm(currentProfile || {'),
    "Profile page must mount editable 2.4/5 GHz cards immediately");
assert.ok(app.includes('"2.4GHz": {}') && app.includes('"5GHz": {}'),
    "Immediate profile draft must expose both radio bands");
assert.ok(editor.includes('"/f6201b/write/status"'),
    "Dashboard profile CTA must be opt-in gated");
console.log("F6201B profile runs saved preset with one click; preflight and readback remain inside server.");

const fs = require("node:fs");
const assert = require("node:assert/strict");

const body = fs.readFileSync(
  "apps/zte_manager/static/js/named_presets.js",
  "utf8"
);
const api = fs.readFileSync(
  "apps/zte_manager/presentation/api/profiles.py",
  "utf8"
);

assert.ok(
  body.includes('post("/profiles/apply", {attendant: owner})'),
  "Primary Profile apply must use the generic provider-dispatched endpoint"
);
assert.ok(
  body.includes('post("/profiles/named/list", {attendant: owner})') &&
  body.includes('post("/profiles/named/get", {') &&
  body.includes('post("/profiles/named/save", {') &&
  body.includes('post("/profiles/named/delete", {') &&
  body.includes('post("/profiles/named/apply", {'),
  "Named preset lifecycle must use provider-neutral profile endpoints"
);
assert.ok(
  !body.includes("huaweiPrimaryControls") &&
  !body.includes("Variantes nomeadas ainda são específicas do provider ZTE") &&
  !body.includes("if (isHuawei())"),
  "Huawei must not be forced back to the primary preset"
);
assert.ok(
  body.includes('event.target.closest("#applyProfileButton")'),
  "Historical primary Apply listener must still be intercepted"
);
assert.ok(
  body.includes("event.stopImmediatePropagation()"),
  "Legacy model-specific primary Apply listener must not run after the generic handler"
);
assert.ok(
  body.includes("result.unsupported.join"),
  "Capability-preflight failures must be visible instead of silently partially applying"
);
assert.ok(
  body.includes("changed.every(step => step?.verified === true)"),
  "Huawei profile confirmation must be derived from per-stage readback verification"
);
assert.ok(
  body.includes("aplicada(s) e confirmada(s) pela releitura da ONT"),
  "Successful Huawei application must show an explicit readback confirmation"
);
assert.ok(
  api.includes("named_preset_service.list(data.attendant)") &&
  api.includes("named_preset_service.get(data.attendant, data.name)") &&
  api.includes("named_preset_service.save(") &&
  api.includes("named_preset_service.delete(data.attendant, data.name)"),
  "Named preset persistence must not be hard-wired to zte_service"
);
assert.ok(
  api.includes("device_service.apply_named_preset(data.attendant, data.name)"),
  "Named preset application must dispatch through the active provider"
);
assert.ok(
  api.includes("device_service.apply_profile(data.attendant)"),
  "Generic profile API must dispatch through DeviceService"
);
assert.ok(
  !body.includes('post("/f6201b/profile/apply-saved"'),
  "Provider-neutral compatibility layer must never call the F6201B profile endpoint"
);

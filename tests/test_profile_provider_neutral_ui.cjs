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
  body.includes('event.target.closest("#applyProfileButton")'),
  "The visible primary Apply button must be intercepted from the legacy F6201B listener"
);
assert.ok(
  body.includes("event.stopImmediatePropagation()"),
  "Legacy model-specific Apply listener must not run after the generic handler"
);
assert.ok(
  body.includes("result.unsupported.join"),
  "Capability-preflight failures must be visible instead of silently partially applying"
);
assert.ok(
  api.includes("device_service.apply_profile(data.attendant)"),
  "Generic profile API must dispatch through DeviceService"
);
assert.ok(
  !body.includes('post("/f6201b/profile/apply-saved"'),
  "Provider-neutral compatibility layer must never call the F6201B profile endpoint"
);

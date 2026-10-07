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
  body.includes('event.target.closest("#applyProfileButton, #namedPresetApply")'),
  "Both visible Huawei Apply controls must be intercepted from legacy/model-specific listeners"
);
assert.ok(
  body.includes("if (isHuawei())") && body.includes("huaweiPrimaryControls()"),
  "Huawei profile UI must be forced to the provider-neutral primary profile"
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
  body.includes("changed.every(step => step?.verified === true)"),
  "Huawei profile confirmation must be derived from per-stage readback verification"
);
assert.ok(
  body.includes("aplicada(s) e confirmada(s) pela releitura da ONT"),
  "Successful Huawei application must show an explicit readback confirmation"
);
assert.ok(
  api.includes("device_service.apply_profile(data.attendant)"),
  "Generic profile API must dispatch through DeviceService"
);
assert.ok(
  !body.includes('post("/f6201b/profile/apply-saved"'),
  "Provider-neutral compatibility layer must never call the F6201B profile endpoint"
);

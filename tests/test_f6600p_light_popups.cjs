/* Light-mode Qt combo popup contrast + untouched dark design contract. */
"use strict";
const fs=require("node:fs"),assert=require("node:assert/strict");
const root="apps/zte_manager/static/css/";
const light=fs.readFileSync(root+"light_mode_refine.css","utf8");
const neutral=fs.readFileSync(root+"neutral_console.css","utf8");
const base=fs.readFileSync(root+"style.css","utf8");
const telecom=fs.readFileSync(root+"telecom_console.css","utf8");
const template=fs.readFileSync("apps/zte_manager/templates/index.html","utf8");
assert.ok(template.indexOf("light_mode_refine.css")>
  template.indexOf("telecom_console.css"),"Light rules must follow legacy dark CSS");
for(const value of [
  "--ui-surface-light:#ffffff",
  "--ui-text-light:#111827",
  "--ui-border-light:#d1d5db",
  'html[data-theme="light"] select option',
  'html[data-theme="light"] select optgroup',
  'html[data-theme="light"] .hero-flow > div',
  'html[data-theme="light"] .capability-card',
  'html[data-theme="light"] #trackerDiscoverySection .operation-row',
  "color-scheme: light !important",
  "-webkit-text-fill-color: var(--ui-text-light, #111827) !important"
]) assert.ok(light.includes(value),"Missing: "+value);
assert.match(neutral,/--select-option-bg: #18191e/);
assert.match(neutral,/--select-option-bg: #ffffff/);
assert.ok(base.includes("--select-option-bg, var(--surface)"));
assert.ok(telecom.includes("--select-option-bg, #18191e"));
assert.ok(!light.includes('html[data-theme="dark"] {'),
  "Light fix must not override dark mode palette");
console.log("Light mode dropdowns + legacy cards have explicit contrast; dark tokens retained.");

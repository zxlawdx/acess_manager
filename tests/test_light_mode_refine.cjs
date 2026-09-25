/* Accessibility contract for post-legacy light-mode CSS.
 * Guards the regression where old dark-only rules overrode the light theme. */
const assert = require("node:assert/strict");
const fs = require("node:fs");
const css = fs.readFileSync(
  "apps/zte_manager/static/css/light_mode_refine.css", "utf8"
);
const html = fs.readFileSync(
  "apps/zte_manager/templates/index.html", "utf8"
);
const ref = "zte_manager/css/light_mode_refine.css";
assert.ok(html.includes(ref));
assert.ok(html.indexOf(ref) > html.indexOf("f6201b_workbench.css"),
  "Bright refinements must win the CSS cascade after all legacy styles");
const palette = css.match(/html\[data-theme="light"\] \{([^}]+)\}/);
assert.ok(palette, "Missing explicit light-mode palette");
const token = name => {
  const pattern = new RegExp(name + ":\\s*(#[a-fA-F0-9]{6})\\s*;");
  const result = palette[1].match(pattern);
  assert.ok(result, "Missing " + name);
  return result[1];
};
const channel = v => {
  const n = v / 255;
  return n <= 0.04045 ? n / 12.92 : ((n + 0.055) / 1.055)**2.4;
};
const luminance = hex => {
  const values = [1,3,5].map(i => parseInt(hex.slice(i,i+2), 16));
  return values.map(channel).reduce((sum,n,i) =>
    sum + n * [0.2126,0.7152,0.0722][i],0);
};
const contrast = (a,b) => {
  const x=luminance(a),y=luminance(b);
  return (Math.max(x,y)+.05)/(Math.min(x,y)+.05);
};
const white = token("--ui-surface");
assert.ok(contrast(white,token("--ui-text")) >= 7,
  "Light mode main text requires high contrast");
assert.ok(contrast(white,token("--ui-text-secondary")) >= 4.5);
assert.ok(contrast(white,token("--ui-muted")) >= 4.5);
assert.ok(contrast(white,token("--ui-accent")) >= 4.5,
  "Primary button must be legible using white-on-accent contrast");
assert.ok(contrast("#ffffff",token("--ui-accent")) >= 4.5);
for (const required of [
  ".sidebar", ".topbar", ".panel", ".menu-item.active",
  ".login-hero h2", ".adaptive-summary", ".adaptive-route-row",
  ".management-terminal", ".support-summary", ".firmware-json",
  ".f6201b-warning", "#f6201b-workbench",
  "#profileRadios", ".profile-radio-card", ".profile-action-error"
]) assert.ok(css.includes(required), "Missing light coverage for " + required);
assert.ok(!/(?:linear|radial|conic)-gradient\s*\(/.test(css),
  "The light workbench must not reintroduce decorative gradients");
assert.ok(css.includes('html[data-theme="light"]') &&
  !css.includes('html[data-theme="dark"] {'),
  "Do not override dark palette");
console.log("Bright workbench coverage and high-contrast palette OK");

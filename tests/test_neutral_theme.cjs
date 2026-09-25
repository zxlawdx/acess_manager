const assert = require("node:assert/strict");
const fs = require("node:fs");
const app = fs.readFileSync("apps/zte_manager/static/js/app.js", "utf8");
const markup = fs.readFileSync("apps/zte_manager/templates/index.html", "utf8");
const theme = fs.readFileSync("apps/zte_manager/static/js/neutral_theme.js", "utf8");
const css = fs.readFileSync("apps/zte_manager/static/css/neutral_console.css", "utf8");
const lightCss = fs.readFileSync("apps/zte_manager/static/css/light_mode_refine.css", "utf8");
const collect = app.slice(app.indexOf("function collectProfileForm()"),
                          app.indexOf("async function saveProfile(",app.indexOf("function collectProfileForm()")));
assert.ok(collect.includes("if (!card)"), "Profile card null guard missing");
assert.ok(collect.indexOf("if (!card)") <
          collect.indexOf("const channel = card.querySelector"),
          "Guard must run before accessing card.querySelector");
const apply = app.slice(app.indexOf("async function applyProfile()"),
                        app.indexOf("function renderProfileApplyResult("));
assert.ok(apply.includes("if (!routerWriteEnabled)"),
    "Unknown F6201B must not run native batch configuration");
assert.ok(apply.indexOf("await renderProfileForm(") <
          apply.indexOf("await saveProfile("),
          "Mount profile radio cards before collection");
assert.ok(markup.includes('id="themeToggle"'),"Missing theme toggle");
assert.ok(markup.includes("neutral_console.css") &&
          markup.includes("neutral_theme.js"),"Theme assets not loaded");
assert.ok(css.includes('html[data-theme="light"]') &&
          css.includes('html[data-theme="dark"]'),"Both theme palettes required");
assert.ok(!css.includes("linear-gradient(") && !css.includes("radial-gradient("),
    "Neutral theme must contain no gradients");
assert.ok(lightCss.includes('.kpi-card.cyan') &&
          lightCss.includes('#pingOutput.terminal-output') &&
          lightCss.includes('.detail-tile') &&
          lightCss.includes('.adaptive-choice-group'),
    "Light mode must override dark-only high-specificity console surfaces");
assert.ok(theme.includes("localStorage.setItem(STORAGE,next)"),
    "Preference must be persisted");
console.log("Profile null guard and neutral UI theme contracts OK");

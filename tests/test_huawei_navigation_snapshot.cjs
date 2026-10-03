const test = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");

const app = fs.readFileSync(
  "apps/zte_manager/static/js/app.js",
  "utf8"
);
const advanced = fs.readFileSync(
  "apps/zte_manager/static/js/advanced.js",
  "utf8"
);
const tr069 = fs.readFileSync(
  "apps/zte_manager/static/js/tr069_profiles.js",
  "utf8"
);

test("Huawei tab navigation is render-only", () => {
  assert.match(app, /Huawei navigation is render-only/);
  assert.doesNotMatch(
    app,
    /event\.detail\?\.vendor !== "huawei"[\s\S]{0,1800}await loadWifi\(/
  );
  assert.doesNotMatch(app, /huawei:ipv4-filter-refresh/);
});

test("Huawei core refresh is explicit", () => {
  assert.match(
    app,
    /"refreshButton"[\s\S]{0,520}warmHuaweiSessionState\(\{refresh: true\}\)/
  );
  assert.match(
    app,
    /"clientsRefreshButton"[\s\S]{0,280}loadClients\(\{refresh: true\}\)/
  );
  assert.match(app, /function snapshotReadUrl\(path, refresh = false\)/);
  assert.match(app, /query\.set\("refresh", "1"\)/);
});

test("Advanced Huawei state is warmed once and refreshed only by operator", () => {
  assert.match(advanced, /window\.warmHuaweiAdvancedSnapshot/);
  assert.match(
    advanced,
    /currentVendor === "huawei"[\s\S]{0,180}advancedState\.loaded/
  );
  assert.match(
    advanced,
    /huaweiIpv4FilterRefresh[\s\S]{0,220}loadHuaweiIpv4Filters\(true\)/
  );
  assert.match(
    advanced,
    /huaweiSecurityRefresh[\s\S]{0,220}loadHuaweiSecurityControls\(true\)/
  );
});

test("TR-069 Huawei state does not re-read on every page open", () => {
  assert.match(tr069, /window\.warmHuaweiTr069Snapshot/);
  assert.match(
    tr069,
    /loadedEpoch === epoch[\s\S]{0,120}setupSnapshot/
  );
  assert.match(
    tr069,
    /tr069ProviderRefresh[\s\S]{0,180}refreshWan\(true\)/
  );
});

test("Advanced shortcut never auto-probes Huawei", () => {
  assert.match(
    app,
    /jump === "advanced"[\s\S]{0,300}currentVendor !== "huawei"/
  );
});

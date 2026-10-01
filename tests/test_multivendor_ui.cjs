const fs = require("node:fs");
const assert = require("node:assert/strict");
const test = require("node:test");

const read = path => fs.readFileSync(path, "utf8");

const app = read("apps/zte_manager/static/js/app.js");
const advanced = read("apps/zte_manager/static/js/advanced.js");
const management = read("apps/zte_manager/static/js/management.js");
const support = read("apps/zte_manager/static/js/support_diagnostics.js");
const tr069 = read("apps/zte_manager/static/js/tr069_profiles.js");
const shell = read("apps/zte_manager/templates/source/shell_start.html");

test("frontend uses vendor-neutral device lifecycle events", () => {
    for (const source of [app, advanced, management, support, tr069]) {
        assert.doesNotMatch(source, /zte:page-open/);
        assert.doesNotMatch(source, /zte:session-changed/);
    }
    assert.match(app, /device:page-open/);
    assert.match(app, /device:session-changed/);
});

test("Huawei pages do not dispatch ZTE-only loaders", () => {
    assert.match(
        app,
        /HUAWEI_SUPPORTED_PAGES = new Set\(\[[\s\S]*"connection"[\s\S]*"device"[\s\S]*"advanced"/
    );
    assert.match(
        app,
        /if \(!vendorSupportsPage\(pageName\)\)/
    );
    assert.match(
        management,
        /event\.detail\?\.vendor === "huawei"\) return/
    );
    assert.match(
        support,
        /event\.detail\?\.vendor === "huawei"\) return/
    );
    assert.match(
        tr069,
        /event\.detail\?\.vendor === "huawei"\) return/
    );
});

test("branding is Access Manager and workspace vendor is dynamic", () => {
    assert.doesNotMatch(shell, /Gerenciamento de equipamentos ZTE/);
    assert.doesNotMatch(shell, /WORKSPACE[^\n]*\/[^\n]*ZTE/);
    assert.match(shell, /Gerenciamento de equipamentos \/ ONTs/);
    assert.match(shell, /id="workspaceVendorLabel">EQUIPAMENTOS/);
    assert.match(app, /document\.title = "Access Manager"/);
    assert.match(app, /currentVendor === "huawei"[\s\S]*"HUAWEI"/);
});

test("Huawei profile and unsupported pages are not exposed as normal controls", () => {
    assert.match(
        app,
        /button\.classList\.toggle\("hidden", unavailable\)/
    );
    assert.match(
        app,
        /Recurso ainda não disponível para \$\{label\}\./
    );
});

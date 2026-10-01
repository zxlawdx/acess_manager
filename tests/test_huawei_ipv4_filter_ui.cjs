const fs = require("node:fs");
const vm = require("node:vm");
const assert = require("node:assert/strict");
const test = require("node:test");

const js = fs.readFileSync(
    "apps/zte_manager/static/js/advanced.js",
    "utf8"
);

const extract = (from, to) => {
    const a = js.indexOf(from);
    const b = js.indexOf(to, a + from.length);
    assert.ok(a >= 0 && b > a, from);
    return js.slice(a, b);
};

test("test_huawei_create_button_enabled", async () => {
    const elements = {
        huaweiIpv4FilterStatus: {
            textContent: "",
            innerHTML: ""
        },
        huaweiIpv4FilterSave: {
            disabled: true
        }
    };
    const context = {
        console,
        ontConnected: true,
        currentVendor: "huawei",
        huaweiIpv4FilterState: {
            rules: [],
            capability: null,
            loading: false
        },
        document: {
            getElementById: id => elements[id] || null
        },
        apiRequest: async endpoint => {
            assert.equal(endpoint, "/huawei/ipv4-filters");
            return {
                rules: [],
                capability: {
                    read: true,
                    create: true,
                    update: true,
                    delete: true,
                    verified: true
                }
            };
        },
        hydrateHuaweiFilterOptions: () => {},
        renderHuaweiIpv4Filters: () => {},
        showToast: message => {
            throw new Error("unexpected toast: " + message);
        }
    };
    vm.createContext(context);
    vm.runInContext(
        extract(
            "async function loadHuaweiIpv4Filters() {",
            "function collectHuaweiIpv4FilterPayload() {"
        ),
        context
    );
    await vm.runInContext(
        "loadHuaweiIpv4Filters()",
        context
    );
    assert.equal(
        elements.huaweiIpv4FilterSave.disabled,
        false
    );
});

test("test_huawei_update_button_enabled", () => {
    assert.match(
        js,
        /const canUpdate = capability\.update === true;/
    );
    assert.match(
        js,
        /\$\{canUpdate \? "" : "disabled"\}/
    );
    assert.doesNotMatch(
        js,
        /canUpdate\s*=\s*capability\.verified/
    );
});

test("test_huawei_delete_button_enabled", () => {
    assert.match(
        js,
        /const canDelete = capability\.delete === true;/
    );
    assert.match(
        js,
        /\$\{canDelete \? "" : "disabled"\}/
    );
    assert.doesNotMatch(
        js,
        /canDelete\s*=\s*capability\.verified/
    );
});

import test from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs";

const root = new URL("../", import.meta.url);
const source = path => fs.readFileSync(new URL(path, root), "utf8");
const dataUrl = value => "data:text/javascript;base64," + Buffer.from(value).toString("base64");

const managementSource = source("apps/zte_manager/static/js/services/management_api.js");
const advancedWifiSource = source("apps/zte_manager/static/js/advanced/wifi_radio_fields.js");
const bootstrapSource = source("apps/zte_manager/static/js/frontend_bootstrap.js");
const inventoryViewSource = source("apps/zte_manager/static/js/management/inventory_view.js");
const shellEndSource = source("apps/zte_manager/templates/source/shell_end.html");
const {createManagementApi} = await import(dataUrl(managementSource));
const {installAdvancedWifiFields} = await import(dataUrl(advancedWifiSource));

test("ManagementApi centralizes domain endpoints and JSON bodies", async () => {
    const calls = [];
    const api = createManagementApi(async (endpoint, options = {}) => {
        calls.push({endpoint, options});
        return {success: true};
    });
    await api.syncInventory({customer_name: "Cliente"});
    await api.saveProfile({name: "Padrão", config: {}});
    await api.topology(17);
    assert.equal(calls[0].endpoint, "/management/inventory/sync");
    assert.equal(calls[0].options.method, "POST");
    assert.deepEqual(JSON.parse(calls[0].options.body), {customer_name: "Cliente"});
    assert.equal(calls[1].endpoint, "/management/profiles/save");
    assert.equal(calls[2].endpoint, "/management/topology?device_id=17");
    assert.equal(calls.every(item => item.options.expected === "object"), true);
});

test("ManagementApi rejects URLs outside the local management namespace", async () => {
    const api = createManagementApi(async () => ({}));
    assert.throws(() => api.request("https://router.local/private"), /somente rotas \/management/);
    assert.throws(() => api.request("/wifi/radios"), /somente rotas \/management/);
});

test("ManagementApi overview keeps collection fan-out in the service", async () => {
    const endpoints = [];
    const api = createManagementApi(async endpoint => {
        endpoints.push(endpoint);
        return {endpoint};
    });
    const result = await api.overview();
    assert.equal(Object.keys(result).length, 7);
    assert.deepEqual(endpoints, [
        "/management/inventory",
        "/management/profiles",
        "/management/agents",
        "/management/incidents",
        "/management/backups",
        "/management/firmware",
        "/management/acs",
    ]);
});

test("frontend composition owns management compatibility without a bridge module", () => {
    assert.match(bootstrapSource, /createManagementApi/);
    assert.doesNotMatch(bootstrapSource, /legacy_bridge/);
    assert.match(
        bootstrapSource,
        /globalThis\.managementRequest\s*=\s*\(path, options = \{\}\) =>\s*managementApi\.request/s,
    );
    assert.doesNotMatch(bootstrapSource, /AccessManagerManagement/);
    assert.equal(
        fs.existsSync(new URL(
            "apps/zte_manager/static/js/management/legacy_bridge.js",
            root,
        )),
        false,
    );
});

test("classic management controller loads before the module composition root", () => {
    const classicIndex = shellEndSource.indexOf("zte_manager/js/management.js");
    const inventoryIndex = shellEndSource.indexOf(
        "zte_manager/js/management/inventory_view.js",
    );
    assert.ok(classicIndex >= 0, "management.js must remain in the application shell");
    assert.ok(
        inventoryIndex > classicIndex,
        "inventory module must load after the classic management controller",
    );
    assert.match(inventoryViewSource, /^import "\.\.\/frontend_bootstrap\.js";/);
    assert.doesNotMatch(shellEndSource, /frontend_bootstrap\.js/);
});

function fakeForm(fields) {
    return {
        querySelector(selector) {
            const match = selector.match(/data-field="([^"]+)"/);
            return match ? fields[match[1]] || null : null;
        },
    };
}

test("Advanced Wi-Fi fields use Huawei presentation only for Huawei device context", () => {
    const previousCollect = globalThis.collectRadioFormPayload;
    const previousRender = globalThis.renderRadioAdvancedFields;
    try {
        globalThis.collectRadioFormPayload = () => ({base: true});
        const deviceState = {
            snapshot: () => ({vendor: "huawei"}),
        };
        installAdvancedWifiFields({
            deviceState,
            escapeHtml: value => String(value),
        });
        const html = globalThis.renderRadioAdvancedFields({
            banda: "5GHz",
            rts_cts: 2346,
            dtim: 1,
            band_steering: false,
            airtime_fairness: false,
        });
        assert.match(html, /HUAWEI RF MAPEADO/);
        assert.match(html, /bandwidth_code/);
    } finally {
        globalThis.collectRadioFormPayload = previousCollect;
        globalThis.renderRadioAdvancedFields = previousRender;
    }
});

test("Advanced Wi-Fi payload adapter preserves base payload and provider fields", () => {
    const previousCollect = globalThis.collectRadioFormPayload;
    const previousRender = globalThis.renderRadioAdvancedFields;
    try {
        globalThis.collectRadioFormPayload = (_form, channel) => ({channel, base: true});
        let vendor = "huawei";
        const deviceState = {snapshot: () => ({vendor})};
        installAdvancedWifiFields({deviceState, escapeHtml: value => String(value)});
        const huawei = globalThis.collectRadioFormPayload(fakeForm({
            band_steering: {checked: true, value: "on"},
            airtime_fairness: {checked: false, value: "on"},
            rts_cts: {value: "2346"},
            dtim: {value: "1"},
            frag_threshold: {value: "2346"},
            bandwidth_code: {value: "4"},
            band_steering_policy: {value: "0"},
            auto_channel_scope: {value: "1"},
        }), "auto");
        assert.deepEqual(huawei, {
            channel: "auto",
            base: true,
            band_steering: true,
            airtime_fairness: false,
            rts_cts: 2346,
            dtim: 1,
            frag_threshold: 2346,
            bandwidth_code: "4",
            band_steering_policy: "0",
            auto_channel_scope: "1",
        });

        vendor = "zte";
        const generic = globalThis.collectRadioFormPayload(fakeForm({
            mu_mimo: {checked: true, value: "on"},
            uplink_mu_mimo: {checked: false, value: "on"},
            downlink_mu_mimo: {checked: false, value: "on"},
            uplink_ofdma: {checked: true, value: "on"},
            downlink_ofdma: {checked: false, value: "on"},
            twt: {checked: true, value: "on"},
            spatial_reuse: {checked: false, value: "on"},
            ssid_isolation: {checked: false, value: "on"},
            rts_cts: {value: "2347"},
            dtim: {value: "2"},
            frag_threshold: {value: ""},
            qos_type: {value: "WMM"},
            work_mode: {value: "normal"},
            preamble_type: {value: "1"},
        }), "36");
        assert.equal(generic.mu_mimo, true);
        assert.equal(generic.uplink_ofdma, true);
        assert.equal(generic.twt, true);
        assert.equal(generic.qos_type, "WMM");
        assert.equal(generic.preamble_type, "1");
    } finally {
        globalThis.collectRadioFormPayload = previousCollect;
        globalThis.renderRadioAdvancedFields = previousRender;
    }
});

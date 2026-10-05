import test from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs";

const root = new URL("../", import.meta.url);
const source = path => fs.readFileSync(new URL(path, root), "utf8");
const dataUrl = value => "data:text/javascript;base64," + Buffer.from(value).toString("base64");

const deviceSource = source("apps/zte_manager/static/js/core/device_state.js");
const policySource = source("apps/zte_manager/static/js/core/capability_policy.js");
const {DeviceState} = await import(dataUrl(deviceSource));
const {createCapabilityPolicy} = await import(dataUrl(policySource));

function connected(capabilities = {}) {
    const state = new DeviceState();
    state.apply({
        connected: true,
        vendor: "huawei",
        model: "EG8041X7-10",
        capabilities,
    });
    return state;
}

test("confirmed capability makes the corresponding page available", () => {
    const state = connected({
        wifi_basic: {read: true, update: true},
        wan: {read: true},
    });
    const policy = createCapabilityPolicy(state);
    assert.equal(policy.page("wifi"), true);
    assert.equal(policy.page("wan"), true);
});

test("explicit false or absent capability in a published catalog stays conservative", () => {
    const state = connected({
        wifi_basic: {read: false},
        wan: {read: true},
    });
    const policy = createCapabilityPolicy(state);
    assert.equal(policy.page("wifi"), false);
    assert.equal(policy.page("diagnostics"), false);
    assert.equal(policy.page("tr069"), false);
});

test("provider without capability catalog returns null so compatibility fallback can decide", () => {
    const state = connected({});
    const policy = createCapabilityPolicy(state);
    assert.equal(policy.page("wifi"), null);
    assert.equal(policy.page("wan"), null);
});

test("local profiles remain editable even when router capability catalog lacks Wi-Fi writes", () => {
    const state = connected({wan: {read: true}});
    const policy = createCapabilityPolicy(state);
    assert.equal(policy.page("profiles"), true);
});

test("disconnected device exposes only connection and management navigation", () => {
    const state = new DeviceState();
    const policy = createCapabilityPolicy(state);
    assert.equal(policy.page("connection"), true);
    assert.equal(policy.page("management"), true);
    assert.equal(policy.page("wifi"), false);
    assert.equal(policy.page("advanced"), false);
});

test("advanced page is enabled by any confirmed advanced capability", () => {
    const state = connected({
        dhcp: {read: false},
        ipv4_filter: {read: true, create: true},
    });
    const policy = createCapabilityPolicy(state);
    assert.equal(policy.page("advanced"), true);
});

test("feature operation remains tri-state instead of guessing support", () => {
    const state = connected({
        ipv4_filter: {read: true, create: false},
    });
    const policy = createCapabilityPolicy(state);
    assert.equal(policy.feature("ipv4_filter", "read"), true);
    assert.equal(policy.feature("ipv4_filter", "create"), false);
    assert.equal(policy.feature("ipv4_filter", "update"), null);
    assert.equal(policy.feature("mesh", "read"), null);
});

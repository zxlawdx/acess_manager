"use strict";

const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const test = require("node:test");

const root = path.resolve(__dirname, "..");
const css = relative => fs.readFileSync(path.join(root, "apps/zte_manager/static/css", relative), "utf8");

const tokensSource = css("foundation/tangerine_tokens.css");
const legacySource = css("tangerine.css");
const workflowsSource = css("tangerine_workflows.css");
const lightEntrypoint = css("light_mode_refine.css");
const formsEntrypoint = css("tangerine_forms.css");
const cardsEntrypoint = css("tangerine_cards.css");
const structuredForms = css("components/structured_forms.css");
const configurationCards = css("components/configuration_cards.css");
const topology = css("components/topology.css");
const firmwareInspector = css("components/firmware_inspector.css");
const providerDiagnostics = css("components/provider_diagnostics.css");
const operatorResults = css("components/operator_results.css");
const nativeControlsLight = css("components/native_controls_light.css");
const supportWorkbench = css("pages/support_workbench.css");
const diagnosticsWorkbench = css("pages/diagnostics_workbench.css");
const profileWorkbench = css("pages/profile_workbench.css");
const tangerineBaseCompat = css("themes/tangerine_base_compat.css");
const tangerineTerminalCompat = css("themes/tangerine_terminal_compat.css");
const editorialWorkspace = css("layout/editorial_workspace.css");
const dashboardTangerine = css("pages/dashboard_tangerine.css");
const advancedTangerine = css("pages/advanced_tangerine.css");
const historyTimeline = css("components/history_timeline.css");
const connectionInventory = css("pages/connection_inventory.css");
const clientsTangerine = css("pages/clients_tangerine.css");
const deviceTangerine = css("pages/device_tangerine.css");
const tr069Tangerine = css("pages/tr069_tangerine.css");
const diagnosticsTangerine = css("pages/diagnostics_tangerine.css");

const migratedConsumers = [
    ["structured forms", structuredForms],
    ["configuration cards", configurationCards],
    ["topology", topology],
    ["firmware inspector", firmwareInspector],
    ["provider diagnostics", providerDiagnostics],
    ["operator results", operatorResults],
    ["support workbench", supportWorkbench],
    ["diagnostics workbench", diagnosticsWorkbench],
    ["profile workbench", profileWorkbench],
    ["native light controls", nativeControlsLight],
    ["Tangerine base compatibility", tangerineBaseCompat],
    ["Tangerine terminal compatibility", tangerineTerminalCompat],
    ["editorial workspace", editorialWorkspace],
    ["dashboard Tangerine", dashboardTangerine],
    ["advanced Tangerine", advancedTangerine],
    ["history timeline", historyTimeline],
    ["connection inventory", connectionInventory],
    ["clients Tangerine", clientsTangerine],
    ["device Tangerine", deviceTangerine],
    ["TR-069 Tangerine", tr069Tangerine],
    ["diagnostics Tangerine", diagnosticsTangerine],
];

const legacyTangerineReference = /var\(--am-(?:bg|surface|sidebar|primary|primary-deep|primary-wash|selected|text|text-2|border|success|success-wash|warning|warning-wash|danger|danger-wash|primary-ink|shadow)\)/i;

test("Tangerine workflow stylesheet loads foundation then real page/component layers", () => {
    assert.match(
        workflowsSource,
        /^@import url\("\.\/foundation\/tangerine_tokens\.css"\);\s*@import url\("\.\/pages\/support_workbench\.css"\);\s*@import url\("\.\/pages\/diagnostics_workbench\.css"\);\s*@import url\("\.\/pages\/profile_workbench\.css"\);\s*@import url\("\.\/pages\/workbench_responsive\.css"\);\s*@import url\("\.\/components\/operator_results\.css"\);/s,
    );
});

test("Tangerine theme entrypoint delegates to functional owners", () => {
    assert.match(
        legacySource,
        /^@import url\("\.\/foundation\/tangerine_tokens\.css"\);\s*@import url\("\.\/themes\/tangerine_base_compat\.css"\);\s*@import url\("\.\/pages\/dashboard_tangerine\.css"\);\s*@import url\("\.\/themes\/tangerine_terminal_compat\.css"\);\s*@import url\("\.\/layout\/editorial_workspace\.css"\);\s*@import url\("\.\/pages\/advanced_tangerine\.css"\);\s*@import url\("\.\/components\/history_timeline\.css"\);\s*@import url\("\.\/pages\/connection_inventory\.css"\);\s*@import url\("\.\/pages\/clients_tangerine\.css"\);\s*@import url\("\.\/pages\/device_tangerine\.css"\);\s*@import url\("\.\/pages\/tr069_tangerine\.css"\);\s*@import url\("\.\/pages\/diagnostics_tangerine\.css"\);/s,
    );
});

test("light refine stylesheet delegates theme values and compatibility layers", () => {
    assert.match(
        lightEntrypoint,
        /^@import url\("\.\/foundation\/tangerine_tokens\.css"\);\s*@import url\("\.\/themes\/light_base_compat\.css"\);\s*@import url\("\.\/themes\/light_feature_compat\.css"\);\s*@import url\("\.\/themes\/light_console_compat\.css"\);\s*@import url\("\.\/components\/native_controls_light\.css"\);/s,
    );
    assert.doesNotMatch(lightEntrypoint, /--ui-[a-z0-9-]+\s*:/i);
});

test("canonical tokens own theme values and legacy names are aliases", () => {
    assert.match(tokensSource, /:root,\s*html\[data-theme="light"\]/);
    assert.match(tokensSource, /html\[data-theme="dark"\]/);

    assert.match(tokensSource, /--am-color-primary:#FF6C37;/);
    assert.match(tokensSource, /--am-color-primary:#FF8654;/);
    assert.match(tokensSource, /--am-color-bg:#FFFDF8;/);
    assert.match(tokensSource, /--am-color-bg:#211C19;/);
    assert.match(tokensSource, /--am-color-text:#29221E;/);
    assert.match(tokensSource, /--am-color-text:#FFF8F1;/);

    assert.match(tokensSource, /--am-color-neutral:#405548;/);
    assert.match(tokensSource, /--am-color-native-surface:#FFFFFF;/);
    assert.match(tokensSource, /--am-color-native-selected-bg:#E4F2E8;/);
    assert.match(tokensSource, /--am-color-native-disabled-text:#526056;/);

    assert.match(tokensSource, /--am-bg:var\(--am-color-bg\);/);
    assert.match(tokensSource, /--am-primary:var\(--am-color-primary\);/);
    assert.match(tokensSource, /--ui-accent:var\(--am-color-primary\);/);
    assert.match(tokensSource, /--ui-neutral:var\(--am-color-neutral\);/);
    assert.match(tokensSource, /--ui-surface-light:var\(--am-color-native-surface\);/);
    assert.match(tokensSource, /--bg:var\(--am-color-bg\);/);
    assert.match(tokensSource, /--font-mono:var\(--am-font-mono\);/);

    assert.match(tokensSource, /--am-radius-sm:8px;/);
    assert.match(tokensSource, /--am-space-4:16px;/);
    assert.match(tokensSource, /--am-focus-width:2px;/);
    assert.match(tokensSource, /--am-transition-standard:180ms ease;/);
});

test("Tangerine entrypoint and compat layers are not token sources", () => {
    for (const [name, source] of [
        ["Tangerine entrypoint", legacySource],
        ["Tangerine base compatibility", tangerineBaseCompat],
        ["Tangerine terminal compatibility", tangerineTerminalCompat],
    ]) {
        assert.doesNotMatch(source, /--[a-z0-9-]+\s*:/i, `${name} must consume foundation tokens`);
    }
});

test("component entrypoints delegate instead of owning component rules", () => {
    assert.match(formsEntrypoint, /^@import url\("\.\/components\/structured_forms\.css"\);/);
    assert.match(cardsEntrypoint, /^@import url\("\.\/components\/configuration_cards\.css"\);/);

    assert.doesNotMatch(formsEntrypoint, /\.am-form-editor\s*\{/);
    assert.doesNotMatch(cardsEntrypoint, /\.am-wifi-card[\s,]/);
    assert.match(structuredForms, /\.am-form-editor\s*\{/);
    assert.match(configurationCards, /\.am-wifi-card,/);
});

test("migrated CSS consumers use canonical tokens directly", () => {
    for (const [name, source] of migratedConsumers) {
        assert.match(source, /var\(--am-(?:color|font|shadow)-/i, `${name} should use canonical design tokens`);
        assert.doesNotMatch(source, legacyTangerineReference, `${name} must not regress to Tangerine aliases`);
    }

    assert.doesNotMatch(nativeControlsLight, /var\(--ui-/i);
    assert.doesNotMatch(nativeControlsLight, /#[0-9a-f]{3,8}\b/i);
});

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
const formsEntrypoint = css("tangerine_forms.css");
const cardsEntrypoint = css("tangerine_cards.css");
const structuredForms = css("components/structured_forms.css");
const configurationCards = css("components/configuration_cards.css");
const topology = css("components/topology.css");
const firmwareInspector = css("components/firmware_inspector.css");
const providerDiagnostics = css("components/provider_diagnostics.css");
const operatorResults = css("components/operator_results.css");
const supportWorkbench = css("pages/support_workbench.css");
const diagnosticsWorkbench = css("pages/diagnostics_workbench.css");
const profileWorkbench = css("pages/profile_workbench.css");

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
];

const legacyTangerineReference = /var\(--am-(?:bg|surface|sidebar|primary|primary-deep|primary-wash|selected|text|text-2|border|success|success-wash|warning|warning-wash|danger|danger-wash|primary-ink|shadow)\)/i;

test("Tangerine workflow stylesheet loads foundation then real page/component layers", () => {
    assert.match(
        workflowsSource,
        /^@import url\("\.\/foundation\/tangerine_tokens\.css"\);\s*@import url\("\.\/pages\/support_workbench\.css"\);\s*@import url\("\.\/pages\/diagnostics_workbench\.css"\);\s*@import url\("\.\/pages\/profile_workbench\.css"\);\s*@import url\("\.\/pages\/workbench_responsive\.css"\);\s*@import url\("\.\/components\/operator_results\.css"\);/s,
    );
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

    assert.match(tokensSource, /--am-bg:var\(--am-color-bg\);/);
    assert.match(tokensSource, /--am-primary:var\(--am-color-primary\);/);
    assert.match(tokensSource, /--ui-accent:var\(--am-color-primary\);/);
    assert.match(tokensSource, /--bg:var\(--am-color-bg\);/);
    assert.match(tokensSource, /--font-mono:var\(--am-font-mono\);/);

    assert.match(tokensSource, /--am-radius-sm:8px;/);
    assert.match(tokensSource, /--am-space-4:16px;/);
    assert.match(tokensSource, /--am-focus-width:2px;/);
    assert.match(tokensSource, /--am-transition-standard:180ms ease;/);
});

test("legacy Tangerine stylesheet does not define the canonical namespace", () => {
    assert.doesNotMatch(legacySource, /--am-color-[a-z0-9-]+\s*:/i);
    assert.doesNotMatch(legacySource, /--am-space-[a-z0-9-]+\s*:/i);
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
        assert.match(source, /var\(--am-color-/i, `${name} should use canonical color tokens`);
        assert.doesNotMatch(source, /var\(--ui-/i, `${name} must not regress to ui aliases`);
        assert.doesNotMatch(source, legacyTangerineReference, `${name} must not regress to Tangerine aliases`);
        assert.doesNotMatch(source, /#[0-9a-f]{3,8}\b/i, `${name} should not hard-code palette colors`);
    }
});

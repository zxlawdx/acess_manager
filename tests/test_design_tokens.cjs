"use strict";

const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const test = require("node:test");

const root = path.resolve(__dirname, "..");
const tokensPath = path.join(
    root, "apps/zte_manager/static/css/foundation/tangerine_tokens.css"
);
const workflowsPath = path.join(
    root, "apps/zte_manager/static/css/tangerine_workflows.css"
);
const legacyPath = path.join(
    root, "apps/zte_manager/static/css/tangerine.css"
);

function compact(value) {
    return String(value).replace(/\s+/g, "");
}

function declarations(source) {
    return [...source.matchAll(/(--[a-z0-9-]+)\s*:\s*([^;]+);/gi)]
        .map(match => `${match[1]}:${compact(match[2])};`);
}

test("Tangerine workflow stylesheet loads the canonical token module first", () => {
    const source = fs.readFileSync(workflowsPath, "utf8");
    assert.match(
        source,
        /^@import url\("\.\/foundation\/tangerine_tokens\.css"\);/
    );
});

test("extracted design tokens preserve the current Tangerine values", () => {
    const tokens = fs.readFileSync(tokensPath, "utf8");
    const legacy = compact(fs.readFileSync(legacyPath, "utf8"));
    const extracted = declarations(tokens);

    assert.ok(extracted.length >= 50, "expected theme and compatibility tokens");
    for (const declaration of extracted) {
        assert.ok(
            legacy.includes(declaration),
            `legacy Tangerine value changed or token missing: ${declaration}`
        );
    }
});

test("token module carries light, dark and legacy compatibility contracts", () => {
    const source = fs.readFileSync(tokensPath, "utf8");
    assert.match(source, /:root,\s*html\[data-theme="light"\]/);
    assert.match(source, /html\[data-theme="dark"\]/);
    assert.match(source, /--am-primary:#FF6C37;/);
    assert.match(source, /--am-primary:#FF8654;/);
    assert.match(source, /--ui-accent:var\(--am-primary\);/);
    assert.match(source, /--bg:var\(--am-bg\);/);
    assert.match(source, /--font-mono:"JetBrains Mono"/);
});

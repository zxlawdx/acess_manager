const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const test = require("node:test");
const vm = require("node:vm");

function loadErrors() {
    const source = fs.readFileSync(
        path.join(__dirname, "..", "apps", "zte_manager", "static", "js", "core", "api_errors.js"),
        "utf8"
    );
    const context = {window: {}, console};
    vm.createContext(context);
    vm.runInContext(source, context, {filename: "api_errors.js"});
    return context.window.AccessManagerErrors;
}

test("HTTP 200 semantic profile failure keeps backend reason", () => {
    const errors = loadErrors();
    const failure = errors.fromPayload({
        success: false,
        error: "Falha ao aplicar DNS / hosts: a remoção solicitada não foi enviada.",
        step: "dns",
        reason: "A remoção solicitada não foi enviada.",
        error_code: "unsupported_delete"
    }, {status: 200});

    assert.equal(failure.code, "OPERATION_STATE");
    assert.match(failure.message, /DNS \/ hosts/);
    assert.doesNotMatch(failure.message, /não pôde ser interpretada/i);
});

test("malformed successful payload still uses invalid-device-response", () => {
    const errors = loadErrors();
    assert.throws(
        () => errors.ensureObject("not-an-object"),
        error => error.code === "INVALID_DEVICE_RESPONSE"
    );
});

test("profile cards have an explicit padded dynamic body", () => {
    const cssRoot = path.join(
        __dirname, "..", "apps", "zte_manager", "static", "css"
    );
    const entrypoint = fs.readFileSync(
        path.join(cssRoot, "tangerine_forms.css"),
        "utf8"
    );
    const component = fs.readFileSync(
        path.join(cssRoot, "components", "structured_forms.css"),
        "utf8"
    );

    assert.match(
        entrypoint,
        /^@import url\("\.\/components\/structured_forms\.css"\);/
    );
    assert.match(component, /\.profile-radio-card \.profile-fields\s*\{/);
    assert.match(component, /padding:15px 16px 16px/);
});

/* Regression: Windows Qt MUST NEVER call browser clipboard or execCommand. */
const fs = require("node:fs");
const vm = require("node:vm");
const assert = require("node:assert/strict");

const source = fs.readFileSync(
    "apps/zte_manager/static/js/desktop_clipboard.js", "utf8"
);
assert.ok(!source.includes("execCommand"), "Legacy copy path must not exist");
assert.ok(!source.includes("userAgent"), "Host, not User-Agent, selects clipboard");

function sandboxed(hostNavigator) {
    const w = { isSecureContext: true, navigator: hostNavigator };
    vm.runInNewContext(source, { window: w, Promise, Error, TypeError });
    return w.desktopClipboard;
}

function field() {
    return {
        focused: 0,
        selected: 0,
        focus() { this.focused++; },
        select() { this.selected++; }
    };
}

(async function main() {
    let webAccesses = 0;
    const dangerousWindowsNavigator = {};
    Object.defineProperty(dangerousWindowsNavigator, "clipboard", {
        get() { webAccesses++; throw new Error("QtWebEngine crash regression"); }
    });
    const native = sandboxed(dangerousWindowsNavigator);
    const calls = [];
    const req = async (path, options) => {
        calls.push(path);
        if (path === "/desktop/capabilities") {
            return {
                platform: "win32", native_clipboard: true,
                web_clipboard_allowed: false
            };
        }
        assert.equal(options.method, "POST");
        assert.equal(JSON.parse(options.body).text, "attendance");
        return { success: true };
    };
    assert.equal(await native.copy("attendance", field(), req), "native");
    assert.equal(await native.copy("attendance", field(), req), "native");
    assert.deepEqual(calls, [
        "/desktop/capabilities", "/desktop/clipboard", "/desktop/clipboard"
    ], "Capability request must be cached without bypassing native copy");
    assert.equal(webAccesses, 0);

    const nativeFailure = sandboxed(dangerousWindowsNavigator);
    const manualNative = field();
    assert.equal(await nativeFailure.copy("attendance", manualNative, async (path) => {
        if (path === "/desktop/capabilities") {
            return {
                platform: "win32", native_clipboard: true,
                web_clipboard_allowed: false
            };
        }
        throw new Error("Win32 clipboard busy");
    }), "manual");
    assert.equal(manualNative.selected, 1);
    assert.equal(webAccesses, 0);

    const unknownHost = sandboxed(dangerousWindowsNavigator);
    const manualUnknown = field();
    let lookups = 0;
    const failingCapabilities = async () => {
        lookups++;
        throw new Error("Network is down");
    };
    assert.equal(
        await unknownHost.copy("attendance", manualUnknown, failingCapabilities),
        "manual"
    );
    assert.equal(
        await unknownHost.copy("attendance", manualUnknown, failingCapabilities),
        "manual"
    );
    assert.equal(lookups, 2, "Do not cache rejected capability fetch forever");
    assert.equal(webAccesses, 0);

    let webCalls = 0;
    const linux = sandboxed({ clipboard: {
        writeText: async () => { webCalls++; }
    } });
    assert.equal(await linux.copy("attendance", field(), async () => ({
        platform: "linux", native_clipboard: false, web_clipboard_allowed: true
    })), "web");
    assert.equal(webCalls, 1);
    const disabledWeb = sandboxed({ clipboard: {
        writeText: () => { throw new Error("Must not access web clipboard"); }
    } });
    const manualLinux = field();
    assert.equal(
        await disabledWeb.copy("attendance", manualLinux, async () => ({
            platform: "linux", native_clipboard: false,
            web_clipboard_allowed: false
        })),
        "manual"
    );
    assert.equal(manualLinux.focused, 1);
    console.log("Desktop clipboard: Win32 only, cached capability, safe manual fallback");
})().catch(error => { console.error(error); process.exitCode = 1; });

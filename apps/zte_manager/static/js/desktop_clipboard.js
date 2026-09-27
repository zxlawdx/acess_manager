/* Host-capability based clipboard; never probe WebEngine clipboard on Windows. */
(function (global) {
    "use strict";

    let capabilitiesPromise = null;

    function capabilities(request) {
        if (!capabilitiesPromise) {
            capabilitiesPromise = Promise.resolve().then(function () {
                return request("/desktop/capabilities");
            }).then(function (result) {
                if (!result || typeof result.platform !== "string") {
                    throw new Error("Invalid desktop capabilities");
                }
                return result;
            }).catch(function (error) {
                // Transient HTTP failures must not poison a later retry.
                capabilitiesPromise = null;
                throw error;
            });
        }
        return capabilitiesPromise;
    }

    function selectManually(textarea) {
        textarea.focus();
        textarea.select();
        return "manual";
    }

    async function copy(text, textarea, request) {
        if (!textarea || typeof textarea.focus !== "function"
                || typeof textarea.select !== "function") {
            throw new TypeError("Campo de atendimento indisponível.");
        }
        if (typeof text !== "string" || !text.length || text.length > 100000
                || typeof request !== "function") {
            return selectManually(textarea);
        }

        try {
            const host = await capabilities(request);
            if (host.platform === "win32") {
                // This must remain the ONLY automated path on Windows,
                // including when Win32 reports an error or is unavailable.
                if (host.native_clipboard !== true) {
                    return selectManually(textarea);
                }
                const result = await request("/desktop/clipboard", {
                    method: "POST",
                    body: JSON.stringify({ text: text })
                });
                if (!result || result.success !== true) {
                    return selectManually(textarea);
                }
                return "native";
            }
            if (host.web_clipboard_allowed === true
                    && global.isSecureContext === true
                    && global.navigator
                    && global.navigator.clipboard
                    && typeof global.navigator.clipboard.writeText === "function") {
                await global.navigator.clipboard.writeText(text);
                return "web";
            }
        } catch (_) {
            // Unknown host platform could be Windows: never guess and never
            // attempt a browser clipboard fallback when capabilities fail.
        }
        return selectManually(textarea);
    }

    global.desktopClipboard = Object.freeze({ copy: copy });
})(window);

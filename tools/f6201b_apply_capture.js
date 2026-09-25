/*
 * F6201B: captura MINIMIZADA de um POST Apply executado manualmente.
 *
 * Cole APENAS no Console do navegador autenticado no seu próprio equipamento.
 * Nenhum valor de formulário, cookie, senha, token, header ou IP é guardado.
 * Depois de fazer uma mudança pequena usando o painel ORIGINAL do roteador:
 *   window.exportF6201BApplyMap()
 * Para desativar: window.stopF6201BApplyMap()
 *
 * Não utilizar este script como substituto de backup/acesso local.
 */
(() => {
    "use strict";
    if (window.stopF6201BApplyMap) {
        console.warn("Captura já instalada nesta aba.");
        return;
    }
    const original = {
        fetch: window.fetch,
        open: XMLHttpRequest.prototype.open,
        send: XMLHttpRequest.prototype.send,
        setRequestHeader: XMLHttpRequest.prototype.setRequestHeader
    };
    const events = [];
    let currentView = null;
    let enabled = true;
    function tagOf(url) {
        try {
            const target = new URL(String(url), window.location.href);
            return {
                tag: target.searchParams.get("_tag") || null,
                type: target.searchParams.get("_type") || null,
                query_keys: [...new Set(target.searchParams.keys())]
                    .filter(key => !["_", "_tag", "_type", "_sessionTOKEN"].includes(key))
                    .sort()
            };
        } catch (_) {
            return { tag: null, type: null, query_keys: [] };
        }
    }
    function postStructure(body) {
        let pairs = [];
        try {
            if (typeof body === "string") {
                pairs = [...new URLSearchParams(body).entries()];
            } else if (body instanceof URLSearchParams || body instanceof FormData) {
                pairs = [...body.entries()];
            }
        } catch (_) {}
        return {
            ordered_keys: pairs.map(([key]) => key),
            action: pairs.find(([key]) => key === "IF_ACTION")?.[1] || null,
            has_session_token: pairs.some(([key]) => key === "_sessionTOKEN"),
            has_encode: pairs.some(([key]) => key === "encode")
        };
    }
    function responseShape(raw) {
        if (typeof raw !== "string" || !raw.trimStart().startsWith("<")) {
            return { format: "not_xml_or_unavailable" };
        }
        try {
            const doc = new DOMParser().parseFromString(raw, "application/xml");
            if (doc.querySelector("parsererror")) return { format: "malformed_xml" };
            const roots = [...doc.documentElement.children].filter(node =>
                node.tagName.startsWith("OBJ_")
            );
            return {
                format: "xml",
                root: doc.documentElement.tagName,
                if_error_id: doc.querySelector("IF_ERRORID")?.textContent?.trim() || null,
                objects: roots.map(node => ({
                    name: node.tagName,
                    instance_count: node.querySelectorAll(":scope > Instance").length,
                    field_names: [...new Set(
                        [...node.querySelectorAll("ParaName")]
                            .map(el => el.textContent.trim())
                    )].sort()
                }))
            };
        } catch (_) {
            return { format: "unavailable" };
        }
    }
    function record(method, url, body, headers, response) {
        if (!enabled) return;
        const endpoint = tagOf(url);
        if (endpoint.type === "menuView" && method === "GET") {
            currentView = endpoint.tag;
            return;
        }
        if (endpoint.type !== "menuData" || method !== "POST") return;
        const fields = postStructure(body);
        // Ação nula/unknown é mantida para diagnosticar diferentes firmwares;
        // não guardar quaisquer VALORES de campo, exceto IF_ACTION.
        const result = {
            captured_at: new Date().toISOString(),
            method: "POST", type: "menuData",
            tag: endpoint.tag, last_view: currentView,
            query_keys: endpoint.query_keys,
            form: fields,
            header_presence: {
                check: headers.includes("check"),
                content_type: headers.includes("content-type")
            },
            response: responseShape(response)
        };
        events.push(result);
        console.info("[F6201B map] Capturado somente metadados:",
                     endpoint.tag, fields.action || "ação não identificada");
    }
    window.fetch = function (...args) {
        const request = args[0];
        const init = args[1] || {};
        const method = String(init.method || request?.method || "GET").toUpperCase();
        const url = typeof request === "string" ? request : request?.url;
        const body = init.body || null; // Não consumir/clonar o body de Request.
        const headers = init.headers ? new Headers(init.headers) : new Headers();
        const names = [...headers.keys()].map(key => key.toLowerCase());
        const promise = original.fetch.apply(this, args);
        if (!enabled || !url) return promise;
        return promise.then(response => {
            if (tagOf(url).type === "menuView") {
                record(method, url, body, names, null);
            }
            if (method === "POST" && tagOf(url).type === "menuData") {
                response.clone().text().then(raw =>
                    record(method, url, body, names, raw)
                ).catch(() => record(method, url, body, names, null));
            }
            return response;
        });
    };
    XMLHttpRequest.prototype.open = function (method, url, ...rest) {
        this.__f6201bMap = {
            method: String(method).toUpperCase(), url, body: null, headers: []
        };
        return original.open.call(this, method, url, ...rest);
    };
    XMLHttpRequest.prototype.setRequestHeader = function (name, value) {
        if (this.__f6201bMap) {
            this.__f6201bMap.headers.push(String(name).toLowerCase());
        }
        return original.setRequestHeader.call(this, name, value);
    };
    XMLHttpRequest.prototype.send = function (body) {
        const info = this.__f6201bMap;
        if (enabled && info) {
            if (info.method === "GET") {
                record("GET", info.url, null, info.headers, null);
            } else if (info.method === "POST") {
                this.addEventListener("loadend", () => {
                    let raw = null;
                    try {
                        if (this.responseType === "" || this.responseType === "text")
                            raw = this.responseText;
                    } catch (_) {}
                    record(info.method, info.url, body, info.headers, raw);
                }, { once: true });
            }
        }
        return original.send.call(this, body);
    };
    window.exportF6201BApplyMap = () => {
        const payload = {
            schema: 1, device_model: "F6201B",
            comment: "Não inclui URL/host, valores de formulário ou segredos.",
            events
        };
        const blob = new Blob([JSON.stringify(payload, null, 2)], {
            type: "application/json"
        });
        const link = document.createElement("a");
        link.href = URL.createObjectURL(blob);
        link.download = "F6201B_POST_MAP_SANITIZADO.json";
        link.click();
        setTimeout(() => URL.revokeObjectURL(link.href), 1500);
        return events.length;
    };
    window.stopF6201BApplyMap = () => {
        enabled = false;
        window.fetch = original.fetch;
        XMLHttpRequest.prototype.open = original.open;
        XMLHttpRequest.prototype.send = original.send;
        XMLHttpRequest.prototype.setRequestHeader = original.setRequestHeader;
        delete window.stopF6201BApplyMap;
        delete window.exportF6201BApplyMap;
        console.info("[F6201B map] Captura desativada.");
    };
    console.info("[F6201B map] Ativo. Execute Apply manual no seu equipamento, " +
                 "depois window.exportF6201BApplyMap(); não envie HAR bruto.");
})();

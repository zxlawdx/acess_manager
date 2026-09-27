/**
 * CPE inventory view: DOM-only rendering and persistent selection.
 *
 * ES module loaded by Vela's existing index.html after the classic
 * management.js shim. It publishes one narrowly scoped bridge instead of
 * replacing the legacy management state's global API.
 *
 * @typedef {Object} InventoryDevice
 * @property {number|string} id
 * @property {string=} model
 * @property {string=} serial
 * @property {string=} mac
 * @property {string=} key
 * @property {string=} firmware
 * @property {boolean=} firmware_compliant
 * @property {string=} customer_name
 * @property {string=} host
 * @property {number|string=} rx_power
 * @property {string=} pop
 * @property {string=} olt
 * @property {string=} cto
 * @property {string=} status
 * @property {string=} last_seen
 */

/** @param {unknown} value @returns {number|null} */
function deviceId(value) {
    if (value === null || value === undefined || value === "") return null;
    const id = Number(value);
    return Number.isSafeInteger(id) && id > 0 ? id : null;
}

/** @param {unknown} value @param {string} [fallback] @returns {string} */
function asText(value, fallback = "-") {
    return value === null || value === undefined || value === ""
        ? fallback : String(value);
}

/**
 * @param {HTMLElement} parent
 * @param {string} tag
 * @param {unknown} value
 * @param {string} [className]
 * @returns {HTMLElement}
 */
function appendText(parent, tag, value, className = "") {
    const element = parent.ownerDocument.createElement(tag);
    element.textContent = asText(value);
    if (className) element.className = className;
    parent.append(element);
    return element;
}

/**
 * @param {HTMLTableRowElement} row
 * @param {InventoryDevice} item
 * @param {(value: unknown) => string} relativeTime
 */
function fillRow(row, item, relativeTime) {
    const doc = row.ownerDocument;
    const id = deviceId(item.id);

    const checkCell = doc.createElement("td");
    const check = doc.createElement("input");
    check.className = "management-device-check";
    check.type = "checkbox";
    check.value = String(id);
    check.setAttribute("aria-label", "Selecionar equipamento");
    checkCell.append(check);
    row.append(checkCell);

    const identityCell = doc.createElement("td");
    appendText(identityCell, "strong", item.model || "ZTE");
    appendText(identityCell, "small", item.serial || item.mac || item.key);
    const compliance = item.firmware_compliant === true ? " • homologado"
        : item.firmware_compliant === false ? " • fora do padrão" : "";
    appendText(identityCell, "small", "FW " + asText(item.firmware) + compliance);
    row.append(identityCell);

    const customerCell = doc.createElement("td");
    appendText(customerCell, "span", item.customer_name);
    row.append(customerCell);

    const hostCell = doc.createElement("td");
    hostCell.className = "mono";
    hostCell.textContent = asText(item.host);
    row.append(hostCell);

    const signalCell = doc.createElement("td");
    signalCell.textContent = item.rx_power === null || item.rx_power === undefined
        ? "-" : String(item.rx_power) + " dBm";
    row.append(signalCell);

    const topologyCell = doc.createElement("td");
    topologyCell.textContent = [item.pop, item.olt, item.cto]
        .filter(Boolean).join(" / ") || "-";
    row.append(topologyCell);

    const statusCell = doc.createElement("td");
    const badge = appendText(statusCell, "span", item.status || "unknown");
    badge.className = item.status === "online" ? "badge ok"
        : item.status === "offline" ? "badge critical" : "badge";
    row.append(statusCell);

    const lastSeenCell = doc.createElement("td");
    lastSeenCell.textContent = "há " + asText(relativeTime(item.last_seen));
    row.append(lastSeenCell);
    return check;
}

/**
 * Create exactly two delegated listeners for one tbody. On replacement,
 * dispose() aborts them; rerendering never registers additional listeners.
 *
 * @param {{
 *   body: HTMLElement,
 *   onSelect: (id:number)=>void,
 *   onCheckedChange?: (ids:number[])=>void,
 *   relativeTime?: (value:unknown)=>string,
 * }} options
 * @returns {{
 *   render: (state:{devices:InventoryDevice[],selectedDeviceId:number|null,query?:string})=>void,
 *   getCheckedIds: ()=>number[],
 *   checkedIds: Set<number>,
 *   dispose: ()=>void,
 * }}
 */
export function createInventoryView(options) {
    const {body, onSelect, onCheckedChange = () => {},
        relativeTime = () => "-"} = options;
    if (!body || typeof body.addEventListener !== "function"
            || typeof onSelect !== "function") {
        throw new TypeError("Contêiner ou callbacks do inventário inválidos.");
    }
    const controller = new AbortController();
    const checkedIds = new Set();
    let disposed = false;

    body.addEventListener("click", event => {
        const target = event.target;
        if (!target || typeof target.closest !== "function") return;
        if (target.closest("input.management-device-check")) return;
        const row = target.closest("tr[data-device-id]");
        if (!row || !body.contains(row)) return;
        const id = deviceId(row.dataset.deviceId);
        if (id !== null) onSelect(id);
    }, {signal: controller.signal});

    body.addEventListener("change", event => {
        const target = event.target;
        if (!target || typeof target.closest !== "function") return;
        const input = target.closest("input.management-device-check");
        if (!input || !body.contains(input)) return;
        const id = deviceId(input.value);
        if (id === null) return;
        if (input.checked) checkedIds.add(id);
        else checkedIds.delete(id);
        onCheckedChange([...checkedIds]);
    }, {signal: controller.signal});

    function render({devices = [], selectedDeviceId = null, query = ""} = {}) {
        if (disposed) return;
        const entries = Array.isArray(devices) ? devices : [];
        const valid = new Set(entries.map(item => deviceId(item?.id))
            .filter(id => id !== null));
        for (const id of checkedIds) {
            if (!valid.has(id)) checkedIds.delete(id);
        }

        const search = String(query).trim().toLocaleLowerCase("pt-BR");
        const visible = entries.filter(item => {
            if (!item || deviceId(item.id) === null) return false;
            if (!search) return true;
            return [
                item.customer_name, item.host, item.model, item.serial,
                item.mac, item.olt, item.cto, item.pop
            ].some(value => asText(value, "").toLocaleLowerCase("pt-BR")
                .includes(search));
        });
        const doc = body.ownerDocument;
        const fragment = doc.createDocumentFragment();
        for (const item of visible) {
            const id = deviceId(item.id);
            const row = doc.createElement("tr");
            row.dataset.deviceId = String(id);
            if (id === deviceId(selectedDeviceId)) row.classList.add("selected");
            const checkbox = fillRow(row, item, relativeTime);
            checkbox.checked = checkedIds.has(id);
            fragment.append(row);
        }

        if (!visible.length) {
            const row = doc.createElement("tr");
            const cell = doc.createElement("td");
            cell.colSpan = 8;
            cell.className = "muted";
            cell.textContent = "Nenhuma ONT no inventário.";
            row.append(cell);
            fragment.append(row);
        }
        body.replaceChildren(fragment);
    }

    return Object.freeze({
        render,
        checkedIds,
        getCheckedIds: () => [...checkedIds],
        dispose() {
            if (disposed) return;
            controller.abort();
            checkedIds.clear();
            disposed = true;
        }
    });
}

// Bridge for Vela's existing classic scripts. No new global state beyond one
// component instance, no mutations of the legacy managementState.
if (typeof window !== "undefined" && typeof document !== "undefined") {
    const body = document.getElementById("managementInventoryBody");
    if (body) {
        window.managementInventoryView = createInventoryView({
            body,
            onSelect(id) {
                document.dispatchEvent(new CustomEvent(
                    "management:inventory-select", {detail: {id}}
                ));
            },
            relativeTime(value) {
                return typeof window.managementRelativeTime === "function"
                    ? window.managementRelativeTime(value) : "-";
            }
        });
        document.dispatchEvent(new CustomEvent("management:inventory-ready"));
    }
}

import test from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs";

const root = new URL("../", import.meta.url);
const source = path => fs.readFileSync(new URL(path, root), "utf8");
const dataUrl = value => "data:text/javascript;base64," + Buffer.from(value).toString("base64");

const wifiApiSource = source("apps/zte_manager/static/js/services/wifi_api.js");
const scheduleSource = source("apps/zte_manager/static/js/advanced/wifi_schedule.js");
const {createWifiApi} = await import(dataUrl(wifiApiSource));
const {createWifiScheduleFeature} = await import(dataUrl(scheduleSource));

test("WifiApi owns only the migrated schedule endpoints", async () => {
    const calls = [];
    const api = createWifiApi(async (endpoint, options = {}) => {
        calls.push({endpoint, options});
        return {success: true};
    });
    await api.schedule();
    await api.updateSchedule({enabled: true, start_hour: 2});
    assert.equal(calls[0].endpoint, "/wifi/schedule");
    assert.equal(calls[0].options.expected, "object");
    assert.equal(calls[1].endpoint, "/wifi/schedule/update");
    assert.equal(calls[1].options.method, "POST");
    assert.deepEqual(JSON.parse(calls[1].options.body), {enabled: true, start_hour: 2});
    assert.deepEqual(Object.keys(api).sort(), ["schedule", "updateSchedule"]);
});

function makeDocument() {
    const elements = new Map();
    const form = {
        listener: null,
        addEventListener(type, callback) {
            if (type === "submit") this.listener = callback;
        },
    };
    const container = {
        _html: "",
        set innerHTML(value) {
            this._html = value;
            if (value.includes("wifiScheduleForm")) elements.set("wifiScheduleForm", form);
        },
        get innerHTML() { return this._html; },
    };
    elements.set("wifiScheduleControl", container);
    return {
        elements,
        container,
        form,
        getElementById(id) { return elements.get(id) || null; },
        field(id, value = "", checked = false) {
            const field = {value: String(value), checked};
            elements.set(id, field);
            return field;
        },
    };
}

test("Wi-Fi schedule feature renders server state and binds its own controller", async () => {
    const doc = makeDocument();
    const feature = createWifiScheduleFeature({
        wifiApi: {
            async schedule() {
                return {
                    available: true,
                    enabled: true,
                    schedule: {
                        start_hour: 2,
                        start_minute: 10,
                        end_hour: 6,
                        end_minute: 20,
                    },
                };
            },
            async updateSchedule() { return {success: true}; },
        },
        documentRef: doc,
        setBusy() {},
        showToast() {},
    });
    await feature.load();
    assert.match(doc.container.innerHTML, /Agendamento diário/);
    assert.match(doc.container.innerHTML, /wifiScheduleStartHour/);
    assert.match(doc.container.innerHTML, /value="2"/);
    assert.equal(typeof doc.form.listener, "function");
});

test("Wi-Fi schedule save builds normalized payload, reports busy and reloads", async () => {
    const doc = makeDocument();
    doc.field("wifiScheduleEnabled", "", true);
    doc.field("wifiScheduleStartHour", 1);
    doc.field("wifiScheduleStartMinute", 30);
    doc.field("wifiScheduleEndHour", 5);
    doc.field("wifiScheduleEndMinute", 45);
    const payloads = [];
    const busy = [];
    const toasts = [];
    let reads = 0;
    const feature = createWifiScheduleFeature({
        wifiApi: {
            async schedule() {
                reads += 1;
                return {available: false, message: "indisponível", schedule: {}};
            },
            async updateSchedule(payload) {
                payloads.push(payload);
                return {success: true};
            },
        },
        documentRef: doc,
        setBusy(...args) { busy.push(args); },
        showToast(message) { toasts.push(message); },
        featureUnavailable: (_title, message) => `<div>${message}</div>`,
    });
    let prevented = false;
    await feature.save({preventDefault() { prevented = true; }});
    assert.equal(prevented, true);
    assert.deepEqual(payloads[0], {
        enabled: true,
        start_hour: 1,
        start_minute: 30,
        end_hour: 5,
        end_minute: 45,
    });
    assert.deepEqual(busy[0], [true, "Aplicando agendamento Wi-Fi..."]);
    assert.deepEqual(busy.at(-1), [false]);
    assert.equal(toasts[0], "Agendamento Wi-Fi atualizado.");
    assert.equal(reads, 1);
});

test("unavailable schedule uses feature-unavailable presentation without mutation", async () => {
    const doc = makeDocument();
    let writes = 0;
    const feature = createWifiScheduleFeature({
        wifiApi: {
            async schedule() { return {available: false, message: "Não mapeado"}; },
            async updateSchedule() { writes += 1; },
        },
        documentRef: doc,
        featureUnavailable: (title, message) => `<section>${title}: ${message}</section>`,
    });
    await feature.load();
    assert.match(doc.container.innerHTML, /Agendamento Wi-Fi: Não mapeado/);
    assert.equal(writes, 0);
});

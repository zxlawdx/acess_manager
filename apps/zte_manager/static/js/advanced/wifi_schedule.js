"use strict";

function timeField(id, label, value, max) {
    return `
        <label class="field compact-field">
            <span>${label}</span>
            <input id="${id}" type="number" min="0" max="${max}"
                value="${Number(value ?? 0)}">
        </label>
    `;
}

export function createWifiScheduleFeature({
    wifiApi,
    documentRef = globalThis.document,
    setBusy = globalThis.setBusy,
    showToast = globalThis.showToast,
    featureUnavailable = globalThis.featureUnavailable,
} = {}) {
    if (!wifiApi?.schedule || !wifiApi?.updateSchedule) {
        throw new TypeError("Wi-Fi schedule requer WifiApi.");
    }

    async function load() {
        const data = await wifiApi.schedule();
        const schedule = data.schedule || {};
        const container = documentRef?.getElementById?.("wifiScheduleControl");
        if (!container) return data;
        if (data?.available === false) {
            container.innerHTML = typeof featureUnavailable === "function"
                ? featureUnavailable(
                    "Agendamento Wi-Fi",
                    data.message || "Recurso não confirmado para este equipamento.",
                )
                : `<p class="muted">${data.message || "Agendamento indisponível."}</p>`;
            return data;
        }
        container.innerHTML = `
            <article class="panel schedule-card">
                <form id="wifiScheduleForm" class="schedule-layout">
                    <div>
                        <span class="section-kicker">GLOBAL TIMER</span>
                        <h3>Agendamento diário</h3>
                        <p class="muted">Configure a janela diária do Wi-Fi sem alterar o estado manual dos rádios.</p>
                        <label class="check-row with-top-space">
                            <input id="wifiScheduleEnabled" type="checkbox" ${data.enabled ? "checked" : ""}>
                            <span>Ativar agendamento</span>
                        </label>
                    </div>
                    <div>
                        <div class="schedule-time-grid">
                            ${timeField("wifiScheduleStartHour", "Início h", schedule.start_hour, 23)}
                            ${timeField("wifiScheduleStartMinute", "Início min", schedule.start_minute, 59)}
                            ${timeField("wifiScheduleEndHour", "Fim h", schedule.end_hour, 23)}
                            ${timeField("wifiScheduleEndMinute", "Fim min", schedule.end_minute, 59)}
                        </div>
                        <button class="button primary with-top-space" type="submit">Aplicar agendamento</button>
                    </div>
                </form>
            </article>
        `;
        documentRef.getElementById("wifiScheduleForm")?.addEventListener("submit", save);
        return data;
    }

    async function save(event) {
        event?.preventDefault?.();
        const value = id => Number(documentRef.getElementById(id)?.value || 0);
        const payload = {
            enabled: Boolean(documentRef.getElementById("wifiScheduleEnabled")?.checked),
            start_hour: value("wifiScheduleStartHour"),
            start_minute: value("wifiScheduleStartMinute"),
            end_hour: value("wifiScheduleEndHour"),
            end_minute: value("wifiScheduleEndMinute"),
        };
        setBusy?.(true, "Aplicando agendamento Wi-Fi...");
        try {
            const result = await wifiApi.updateSchedule(payload);
            showToast?.("Agendamento Wi-Fi atualizado.");
            await load();
            return result;
        } catch (error) {
            showToast?.(error.message);
            throw error;
        } finally {
            setBusy?.(false);
        }
    }

    return Object.freeze({load, save});
}

export function installWifiScheduleFeature(options = {}) {
    const feature = createWifiScheduleFeature(options);
    globalThis.loadWifiSchedule = feature.load;
    globalThis.saveWifiSchedule = feature.save;
    return feature;
}

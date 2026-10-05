"use strict";

function checked(value) {
    return value ? "checked" : "";
}

function huaweiFields(radio, escapeHtml) {
    return `
        <div class="advanced-radio-fields">
            <span class="section-kicker">HUAWEI RF MAPEADO</span>
            <div class="advanced-switch-grid with-top-space">
                <label class="advanced-switch">
                    <span>Band steering</span>
                    <input data-field="band_steering" type="checkbox" ${checked(radio.band_steering)}>
                </label>
                <label class="advanced-switch">
                    <span>Airtime fairness</span>
                    <input data-field="airtime_fairness" type="checkbox" ${checked(radio.airtime_fairness)}>
                </label>
            </div>
            <div class="form-grid two-fields with-top-space">
                <div class="form-group">
                    <label>RTS/CTS</label>
                    <input data-field="rts_cts" type="number" min="0" max="2347"
                        value="${escapeHtml(radio.rts_cts ?? 2346)}">
                </div>
                <div class="form-group">
                    <label>Fragmentação</label>
                    <input data-field="frag_threshold" type="number" min="256" max="2346"
                        value="${escapeHtml(radio.frag_threshold ?? 2346)}">
                </div>
                <div class="form-group">
                    <label>DTIM</label>
                    <input data-field="dtim" type="number" min="1" max="5"
                        value="${escapeHtml(radio.dtim ?? 1)}">
                </div>
                <div class="form-group">
                    <label>Código de largura do firmware</label>
                    <input data-field="bandwidth_code" type="text"
                        value="${escapeHtml(radio.bandwidth_code ?? "")}">
                </div>
                <div class="form-group">
                    <label>Política de band steering</label>
                    <input data-field="band_steering_policy" type="text"
                        value="${escapeHtml(radio.band_steering_policy ?? "")}">
                </div>
                ${radio.banda === "5GHz" ? `
                    <div class="form-group">
                        <label>Escopo do canal automático</label>
                        <input data-field="auto_channel_scope" type="text"
                            value="${escapeHtml(radio.auto_channel_scope ?? "0")}">
                    </div>
                ` : ""}
            </div>
            <p class="muted">
                Campos do formulário WLAN Advanced validado para o provider Huawei ativo.
            </p>
        </div>
    `;
}

function genericFields(radio, escapeHtml) {
    return `
        <div class="advanced-radio-fields">
            <span class="section-kicker">802.11 ADVANCED</span>
            <div class="advanced-switch-grid">
                ${[
                    ["mu_mimo", "MU-MIMO"],
                    ["uplink_mu_mimo", "MU-MIMO UL"],
                    ["downlink_mu_mimo", "MU-MIMO DL"],
                    ["uplink_ofdma", "OFDMA UL"],
                    ["downlink_ofdma", "OFDMA DL"],
                    ["twt", "TWT"],
                    ["spatial_reuse", "Spatial Reuse"],
                    ["ssid_isolation", "Isolamento global"],
                ].map(([field, label]) => `
                    <label class="advanced-switch">
                        <span>${label}</span>
                        <input data-field="${field}" type="checkbox" ${checked(radio[field])}>
                    </label>
                `).join("")}
            </div>
            <div class="form-grid two-fields with-top-space">
                <div class="form-group">
                    <label>RTS/CTS</label>
                    <input data-field="rts_cts" type="number" min="0" max="2347"
                        value="${escapeHtml(radio.rts_cts ?? 2347)}">
                </div>
                <div class="form-group">
                    <label>DTIM</label>
                    <input data-field="dtim" type="number" min="1" max="5"
                        value="${escapeHtml(radio.dtim ?? 1)}">
                </div>
                <div class="form-group">
                    <label>QoS type</label>
                    <input data-field="qos_type" type="text" value="${escapeHtml(radio.qos_type ?? "")}">
                </div>
                <div class="form-group">
                    <label>Work mode</label>
                    <input data-field="work_mode" type="text" value="${escapeHtml(radio.work_mode ?? "")}">
                </div>
                <div class="form-group">
                    <label>Preamble</label>
                    <select data-field="preamble_type">
                        <option value="" ${radio.preamble_type == null ? "selected" : ""}>Preservar</option>
                        <option value="0" ${String(radio.preamble_type) === "0" ? "selected" : ""}>0 / Long</option>
                        <option value="1" ${String(radio.preamble_type) === "1" ? "selected" : ""}>1 / Short</option>
                    </select>
                </div>
            </div>
        </div>
    `;
}

export function installAdvancedWifiFields({
    deviceState,
    escapeHtml = globalThis.escapeHtml,
} = {}) {
    if (!deviceState?.snapshot || typeof escapeHtml !== "function") {
        throw new TypeError("Advanced Wi-Fi fields requer DeviceState e escapeHtml.");
    }
    const baseCollect = globalThis.collectRadioFormPayload;
    if (typeof baseCollect !== "function") {
        throw new Error("collectRadioFormPayload base não foi carregado.");
    }

    globalThis.renderRadioAdvancedFields = radio => {
        const vendor = deviceState.snapshot().vendor;
        return vendor === "huawei"
            ? huaweiFields(radio, escapeHtml)
            : genericFields(radio, escapeHtml);
    };

    globalThis.collectRadioFormPayload = (form, channelValue) => {
        const payload = baseCollect(form, channelValue);
        const isHuawei = deviceState.snapshot().vendor === "huawei";
        const booleanFields = isHuawei
            ? ["band_steering", "airtime_fairness"]
            : [
                "mu_mimo", "uplink_mu_mimo", "downlink_mu_mimo",
                "uplink_ofdma", "downlink_ofdma", "twt",
                "spatial_reuse", "ssid_isolation",
            ];
        for (const name of booleanFields) {
            const field = form.querySelector(`[data-field="${name}"]`);
            if (field) payload[name] = field.checked;
        }
        for (const name of ["rts_cts", "dtim", "frag_threshold"]) {
            const field = form.querySelector(`[data-field="${name}"]`);
            if (field && field.value !== "") payload[name] = Number(field.value);
        }
        const textFields = isHuawei
            ? ["bandwidth_code", "band_steering_policy", "auto_channel_scope"]
            : ["qos_type", "work_mode", "preamble_type"];
        for (const name of textFields) {
            const field = form.querySelector(`[data-field="${name}"]`);
            if (field && field.value !== "") payload[name] = field.value;
        }
        return payload;
    };

    return Object.freeze({
        render: globalThis.renderRadioAdvancedFields,
        collect: globalThis.collectRadioFormPayload,
    });
}

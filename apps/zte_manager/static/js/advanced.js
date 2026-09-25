// =========================================================
// ZTE AUTOMATIC • OPERATIONS SUITE
// Extensão do app.js. Reusa API/helpers/renderers da console principal.
// =========================================================

const advancedState = {
    capabilities: null,
    capabilityProbe: null,
    dhcp: null,
    portForwarding: [],
    dmz: [],
    loaded: false
};


pageInfo.advanced = {
    title: "Avançado",
    subtitle: "Capabilities, diagnóstico automático, LAN, NAT e inspeção do firmware."
};


// =========================================================
// EXTENSÕES DO WI-FI SEM DUPLICAR O RENDERER BASE
// =========================================================

const baseCollectRadioFormPayload = collectRadioFormPayload;

renderRadioAdvancedFields = function (radio) {
    const checked = value => value ? "checked" : "";

    return `
        <div class="advanced-radio-fields">
            <span class="section-kicker">802.11 ADVANCED</span>

            <div class="advanced-switch-grid">
                <label class="advanced-switch">
                    <span>MU-MIMO</span>
                    <input data-field="mu_mimo" type="checkbox" ${checked(radio.mu_mimo)}>
                </label>

                <label class="advanced-switch">
                    <span>MU-MIMO UL</span>
                    <input data-field="uplink_mu_mimo" type="checkbox" ${checked(radio.uplink_mu_mimo)}>
                </label>

                <label class="advanced-switch">
                    <span>MU-MIMO DL</span>
                    <input data-field="downlink_mu_mimo" type="checkbox" ${checked(radio.downlink_mu_mimo)}>
                </label>

                <label class="advanced-switch">
                    <span>OFDMA UL</span>
                    <input data-field="uplink_ofdma" type="checkbox" ${checked(radio.uplink_ofdma)}>
                </label>

                <label class="advanced-switch">
                    <span>OFDMA DL</span>
                    <input data-field="downlink_ofdma" type="checkbox" ${checked(radio.downlink_ofdma)}>
                </label>

                <label class="advanced-switch">
                    <span>TWT</span>
                    <input data-field="twt" type="checkbox" ${checked(radio.twt)}>
                </label>

                <label class="advanced-switch">
                    <span>Spatial Reuse</span>
                    <input data-field="spatial_reuse" type="checkbox" ${checked(radio.spatial_reuse)}>
                </label>

                <label class="advanced-switch">
                    <span>Isolamento global</span>
                    <input data-field="ssid_isolation" type="checkbox" ${checked(radio.ssid_isolation)}>
                </label>
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
                    <input data-field="qos_type" type="text"
                        value="${escapeHtml(radio.qos_type ?? "")}">
                </div>

                <div class="form-group">
                    <label>Work mode</label>
                    <input data-field="work_mode" type="text"
                        value="${escapeHtml(radio.work_mode ?? "")}">
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
};


collectRadioFormPayload = function (
    form,
    channelValue
) {
    const payload = baseCollectRadioFormPayload(
        form,
        channelValue
    );

    const booleanFields = [
        "mu_mimo",
        "uplink_mu_mimo",
        "downlink_mu_mimo",
        "uplink_ofdma",
        "downlink_ofdma",
        "twt",
        "spatial_reuse",
        "ssid_isolation"
    ];

    for (const name of booleanFields) {
        const field = form.querySelector(
            `[data-field="${name}"]`
        );

        if (field) {
            payload[name] = field.checked;
        }
    }

    const numericFields = [
        "rts_cts",
        "dtim"
    ];

    for (const name of numericFields) {
        const field = form.querySelector(
            `[data-field="${name}"]`
        );

        if (
            field
            && field.value !== ""
        ) {
            payload[name] = Number(
                field.value
            );
        }
    }

    for (const name of [
        "qos_type",
        "work_mode",
        "preamble_type"
    ]) {
        const field = form.querySelector(
            `[data-field="${name}"]`
        );

        if (
            field
            && field.value !== ""
        ) {
            payload[name] = field.value;
        }
    }

    return payload;
};


renderBandSteeringAdvanced = function (params) {
    const numberValue = key => (
        params[key] ?? ""
    );

    return `
        <form id="bandSteeringAdvancedForm" class="band-steering-editor">
            <span class="section-kicker">THRESHOLDS</span>

            <div class="operations-form-grid with-top-space">
                <label class="field">
                    <span>RSSI LIMITE 2.4G</span>
                    <input data-bs="rssi_limit_24g" type="number" min="-120" max="0"
                        value="${escapeHtml(numberValue("rssi_limit_24g"))}">
                </label>

                <label class="field">
                    <span>RSSI LIMITE 5G</span>
                    <input data-bs="rssi_limit_5g" type="number" min="-120" max="0"
                        value="${escapeHtml(numberValue("rssi_limit_5g"))}">
                </label>

                <label class="field">
                    <span>UTILIZAÇÃO 2.4G %</span>
                    <input data-bs="bandwidth_util_24g" type="number" min="0" max="100"
                        value="${escapeHtml(numberValue("bandwidth_util_24g"))}">
                </label>

                <label class="field">
                    <span>UTILIZAÇÃO 5G %</span>
                    <input data-bs="bandwidth_util_5g" type="number" min="0" max="100"
                        value="${escapeHtml(numberValue("bandwidth_util_5g"))}">
                </label>

                <label class="field">
                    <span>RSSI ACEITE 2.4G</span>
                    <input data-bs="accept_rssi_24g" type="number" min="-120" max="0"
                        value="${escapeHtml(numberValue("accept_rssi_24g"))}">
                </label>

                <label class="field">
                    <span>RSSI ACEITE 5G</span>
                    <input data-bs="accept_rssi_5g" type="number" min="-120" max="0"
                        value="${escapeHtml(numberValue("accept_rssi_5g"))}">
                </label>

                <label class="field">
                    <span>IDLE RATE 2.4G</span>
                    <input data-bs="idle_rate_limit_24g" type="number" min="0"
                        value="${escapeHtml(numberValue("idle_rate_limit_24g"))}">
                </label>

                <label class="field">
                    <span>IDLE RATE 5G</span>
                    <input data-bs="idle_rate_limit_5g" type="number" min="0"
                        value="${escapeHtml(numberValue("idle_rate_limit_5g"))}">
                </label>
            </div>

            <button class="button ghost with-top-space" type="submit">
                Aplicar thresholds
            </button>
        </form>
    `;
};


bindBandSteeringAdvanced = function () {
    document
        .getElementById(
            "bandSteeringAdvancedForm"
        )
        ?.addEventListener(
            "submit",
            applyBandSteeringAdvanced
        );
};


async function applyBandSteeringAdvanced(event) {
    event.preventDefault();

    const form = event.currentTarget;
    const payload = {};

    form
        .querySelectorAll(
            "[data-bs]"
        )
        .forEach(
            input => {
                if (input.value !== "") {
                    payload[
                        input.dataset.bs
                    ] = Number(
                        input.value
                    );
                }
            }
        );

    setBusy(
        true,
        "Aplicando thresholds do Band Steering..."
    );

    try {
        await apiRequest(
            "/wifi/band-steering/configure",
            {
                method: "POST",
                body: JSON.stringify(
                    payload
                )
            }
        );

        showToast(
            "Band Steering avançado atualizado."
        );

        await loadBandSteering();
    } catch (error) {
        showToast(
            error.message
        );
    } finally {
        setBusy(false);
    }
}


// O carregamento base continua responsável por SSID/RF/WPS/BS.
// A extensão acrescenta somente o timer depois que o fluxo principal termina.
const baseLoadWifi = loadWifi;

loadWifi = async function () {
    await baseLoadWifi();

    try {
        await loadWifiSchedule();
    } catch (error) {
        const container = document.getElementById(
            "wifiScheduleControl"
        );

        if (container) {
            container.innerHTML = featureUnavailable(
                "Agendamento Wi-Fi",
                error.message
            );
        }
    }
};


async function loadWifiSchedule() {
    const data = await apiRequest(
        "/wifi/schedule"
    );

    const schedule = data.schedule || {};
    const container = document.getElementById(
        "wifiScheduleControl"
    );

    if (!container) {
        return;
    }

    container.innerHTML = `
        <article class="panel schedule-card">
            <form id="wifiScheduleForm" class="schedule-layout">
                <div>
                    <span class="section-kicker">GLOBAL TIMER</span>
                    <h3>Agendamento diário</h3>
                    <p class="muted">
                        O ThinkLua aplica um timer global ao Wi-Fi. O modo manual
                        dos rádios é preservado quando o timer é desativado.
                    </p>

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

                    <button class="button primary with-top-space" type="submit">
                        Aplicar agendamento
                    </button>
                </div>
            </form>
        </article>
    `;

    document
        .getElementById(
            "wifiScheduleForm"
        )
        .addEventListener(
            "submit",
            saveWifiSchedule
        );
}


function timeField(
    id,
    label,
    value,
    max
) {
    return `
        <label class="field">
            <span>${label}</span>
            <input id="${id}" type="number" min="0" max="${max}" value="${escapeHtml(value ?? 0)}">
        </label>
    `;
}


async function saveWifiSchedule(event) {
    event.preventDefault();

    const payload = {
        enabled: document.getElementById(
            "wifiScheduleEnabled"
        ).checked,
        start_hour: Number(
            document.getElementById(
                "wifiScheduleStartHour"
            ).value
        ),
        start_minute: Number(
            document.getElementById(
                "wifiScheduleStartMinute"
            ).value
        ),
        end_hour: Number(
            document.getElementById(
                "wifiScheduleEndHour"
            ).value
        ),
        end_minute: Number(
            document.getElementById(
                "wifiScheduleEndMinute"
            ).value
        )
    };

    setBusy(
        true,
        "Aplicando agendamento Wi-Fi..."
    );

    try {
        await apiRequest(
            "/wifi/schedule/update",
            {
                method: "POST",
                body: JSON.stringify(
                    payload
                )
            }
        );

        showToast(
            "Agendamento Wi-Fi atualizado."
        );

        await loadWifiSchedule();
    } catch (error) {
        showToast(
            error.message
        );
    } finally {
        setBusy(false);
    }
}


// =========================================================
// CAPABILITIES
// =========================================================

async function loadCapabilityCatalog() {
    const data = await apiRequest(
        "/device/capabilities"
    );

    advancedState.capabilities = data;

    document.getElementById(
        "adapterBadge"
    ).textContent = (
        data.adapter
        || "ThinkLua"
    );

    renderCapabilities(
        data.features || {},
        null
    );
}


async function probeCapabilities() {
    setBusy(true, "Detectando recursos por etapas...");

    try {
        // Lotes curtos evitam uma requisição longa contendo todos os menus
        // e mantêm os resultados obtidos mesmo se um lote falhar.
        if (!advancedState.capabilities) {
            await loadCapabilityCatalog();
        }

        const catalog = advancedState.capabilities?.features || {};
        const keys = Object.keys(catalog);
        const results = [];
        const batchSize = 3;

        for (let index = 0; index < keys.length; index += batchSize) {
            const batch = keys.slice(index, index + batchSize);
            try {
                const response = await apiRequest(
                    "/device/capabilities/probe",
                    {
                        method: "POST",
                        body: JSON.stringify({ features: batch })
                    }
                );
                results.push(...(response.features || []));
            } catch (error) {
                console.warn("Probe parcial:", batch, error);
                results.push(...batch.map(feature => ({
                    feature,
                    available: false,
                    error: error.message
                })));
            }

            advancedState.capabilityProbe = { features: results };
            renderCapabilities(catalog, results);
            showToast(
                `Recursos verificados: ${Math.min(index + batchSize, keys.length)}/${keys.length}`
            );
        }

        showToast("Detecção finalizada. Recursos indisponíveis identificados.");
    } catch (error) {
        showToast(error.message);
    } finally {
        setBusy(false);
    }
}

async function exportFeatureShapes() {
    const results = advancedState.capabilityProbe?.features || [];
    const available = results
        .filter(item => item.available)
        .map(item => item.feature);

    if (!available.length) {
        showToast("Execute Detectar recursos antes de gerar o mapa.");
        return;
    }

    const panel = document.getElementById("firmwareShapePanel");
    const output = document.getElementById("firmwareShapeOutput");
    panel.classList.remove("hidden");

    const report = {
        schema: 1,
        adapter: advancedState.capabilities?.adapter || "ThinkLua",
        notes: "Contém somente campos e contagens. Revisar antes de compartilhar.",
        features: []
    };

    setBusy(true, "Lendo estrutura do firmware...");

    try {
        // Uma leitura por vez: o firmware mantém sessão compartilhada.
        for (const [index, feature] of available.entries()) {
            try {
                const shape = await apiRequest(
                    `/features/shape?feature=${encodeURIComponent(feature)}`
                );
                report.features.push(shape);
            } catch (error) {
                report.features.push({
                    feature,
                    available: false,
                    error_type: "read_failed"
                });
                console.warn("Estrutura não disponível:", feature, error);
            }

            output.value = JSON.stringify(report, null, 2);
            showToast(
                `Estruturas analisadas: ${index + 1}/${available.length}`
            );
        }

        showToast("Mapa estrutural gerado. Revise antes de compartilhar.");
    } finally {
        setBusy(false);
    }
}


function renderCapabilities(
    catalog,
    probe
) {
    const states = new Map(
        (probe || []).map(
            item => [
                item.feature,
                item
            ]
        )
    );

    const entries = Object.entries(
        catalog
    );

    document.getElementById(
        "capabilityGrid"
    ).innerHTML = entries.length
        ? entries.map(
            ([key, spec]) => {
                const state = states.get(
                    key
                );

                const stateClass = state
                    ? (
                        state.available
                            ? "available"
                            : "unavailable"
                    )
                    : "";

                const stateText = state
                    ? (
                        state.available
                            ? "Disponível"
                            : "Indisponível"
                    )
                    : "Não testado";

                return `
                    <article class="capability-card">
                        <div class="capability-head">
                            <div>
                                <strong>${escapeHtml(spec.label || key)}</strong>
                                <p>${escapeHtml(stateText)}</p>
                            </div>
                            <i class="capability-state ${stateClass}"></i>
                        </div>

                        <div class="operation-meta">
                            ${spec.writable ? "<span>WRITE</span>" : "<span>READ</span>"}
                            ${spec.dangerous ? "<span>CONFIRM</span>" : ""}
                        </div>

                        ${spec.notes ? `<p>${escapeHtml(spec.notes)}</p>` : ""}
                    </article>
                `;
            }
        ).join("")
        : '<span class="muted">Nenhuma capability declarada.</span>';
}


// =========================================================
// DIAGNÓSTICO AUTOMÁTICO
// =========================================================

async function runAutomaticDiagnostic(event) {
    event.preventDefault();

    const payload = {
        ping_host: document.getElementById(
            "autoDiagHost"
        ).value.trim() || "8.8.8.8",
        include_traceroute: document.getElementById(
            "autoDiagTraceroute"
        ).checked,
        optical_rx_min: Number(
            document.getElementById(
                "autoDiagOpticalMin"
            ).value
        ),
        optical_rx_max: Number(
            document.getElementById(
                "autoDiagOpticalMax"
            ).value
        ),
        wifi_rssi_warning: Number(
            document.getElementById(
                "autoDiagRssiWarn"
            ).value
        ),
        wifi_rssi_bad: Number(
            document.getElementById(
                "autoDiagRssiBad"
            ).value
        ),
        expected_lan_mbps: Number(
            document.getElementById(
                "autoDiagLanMbps"
            ).value
        )
    };

    setBusy(
        true,
        "Coletando PON, WAN, LAN, Wi-Fi e conectividade..."
    );

    try {
        const data = await apiRequest(
            "/diagnostics/automatic",
            {
                method: "POST",
                body: JSON.stringify(
                    payload
                )
            }
        );

        renderAutomaticDiagnostic(
            data
        );

        await loadHistory();

        showToast(
            "Diagnóstico automático concluído."
        );
    } catch (error) {
        showToast(
            error.message
        );
    } finally {
        setBusy(false);
    }
}


function renderAutomaticDiagnostic(data) {
    const badge = document.getElementById(
        "automaticDiagnosticBadge"
    );

    badge.textContent = (
        data.status || "unknown"
    ).toUpperCase();

    const findings = data.findings || [];

    const result = document.getElementById(
        "automaticDiagnosticResult"
    );

    result.innerHTML = `
        <div class="operation-row">
            <strong>Resumo</strong>
            <p>${escapeHtml(data.summary || "-")}</p>
        </div>

        ${findings.map(
            item => `
                <div class="finding ${escapeHtml(item.severity || "ok")}">
                    <span class="finding-icon material-symbols-outlined">
                        ${findingIcon(item.severity)}
                    </span>
                    <div>
                        <strong>${escapeHtml(item.code || "diagnostic")}</strong>
                        <p>${escapeHtml(item.message || "")}</p>
                    </div>
                </div>
            `
        ).join("")}

        ${Object.keys(data.errors || {}).length
            ? `
                <div class="operation-row">
                    <strong>Coletas indisponíveis</strong>
                    <pre class="firmware-json">${escapeHtml(JSON.stringify(data.errors, null, 2))}</pre>
                </div>
            `
            : ""
        }
    `;
}


function findingIcon(severity) {
    if (severity === "critical") {
        return "error";
    }

    if (severity === "warning") {
        return "warning";
    }

    return "check_circle";
}


// =========================================================
// DHCP / LAN
// =========================================================

async function loadDhcpOperations() {
    try {
        const data = await apiRequest(
            "/network/dhcp"
        );

        advancedState.dhcp = data;

        const basic = data.basic || {};

        document.getElementById(
            "dhcpEnabled"
        ).checked = (
            String(basic.ServerEnable) === "1"
        );

        document.getElementById(
            "dhcpMinAddress"
        ).value = basic.MinAddress || "";

        document.getElementById(
            "dhcpMaxAddress"
        ).value = basic.MaxAddress || "";

        document.getElementById(
            "dhcpDns1"
        ).value = basic.DNSServer1 || "";

        document.getElementById(
            "dhcpDns2"
        ).value = basic.DNSServer2 || "";

        document.getElementById(
            "dhcpLeaseTime"
        ).value = basic.LeaseTime || "";

        renderDhcpLeases(
            data.leases || []
        );

        renderDhcpReservations(
            data.reservations || []
        );
    } catch (error) {
        document.getElementById(
            "dhcpLeaseList"
        ).innerHTML = featureUnavailable(
            "DHCP",
            error.message
        );

        document.getElementById(
            "dhcpReservationList"
        ).innerHTML = featureUnavailable(
            "Reservas DHCP",
            error.message
        );
    }
}


function renderDhcpLeases(items) {
    const container = document.getElementById(
        "dhcpLeaseList"
    );

    container.innerHTML = items.length
        ? items.map(
            item => `
                <div class="operation-row">
                    <div class="operation-row-head">
                        <strong>${escapeHtml(item.HostName || "Sem hostname")}</strong>
                        <small>${escapeHtml(item.ExpiredTime || "-")}</small>
                    </div>
                    <div class="operation-meta">
                        <span>${escapeHtml(item.IPAddr || "-")}</span>
                        <span>${escapeHtml(item.MACAddr || "-")}</span>
                        <span>${escapeHtml(item.PhyPortName || "-")}</span>
                    </div>
                </div>
            `
        ).join("")
        : '<span class="muted">Nenhum lease retornado.</span>';
}


function renderDhcpReservations(items) {
    const container = document.getElementById(
        "dhcpReservationList"
    );

    container.innerHTML = items.length
        ? items.map(
            (item, index) => `
                <div class="operation-row">
                    <div class="operation-row-head">
                        <strong>${escapeHtml(item.Name || "Reserva")}</strong>
                        <div>
                            <button class="text-action reservation-edit" data-index="${index}" type="button">Editar</button>
                            <button class="text-action reservation-delete" data-index="${index}" type="button">Excluir</button>
                        </div>
                    </div>
                    <div class="operation-meta">
                        <span>${escapeHtml(item.IPAddr || "-")}</span>
                        <span>${escapeHtml(item.MACAddr || "-")}</span>
                    </div>
                </div>
            `
        ).join("")
        : '<span class="muted">Nenhuma reserva cadastrada.</span>';

    container
        .querySelectorAll(
            ".reservation-edit"
        )
        .forEach(
            button => button.addEventListener(
                "click",
                editDhcpReservation
            )
        );

    container
        .querySelectorAll(
            ".reservation-delete"
        )
        .forEach(
            button => button.addEventListener(
                "click",
                deleteDhcpReservation
            )
        );
}


async function saveDhcpBasic(event) {
    event.preventDefault();

    const payload = {
        enabled: document.getElementById(
            "dhcpEnabled"
        ).checked,
        min_address: document.getElementById(
            "dhcpMinAddress"
        ).value.trim(),
        max_address: document.getElementById(
            "dhcpMaxAddress"
        ).value.trim(),
        dns1: document.getElementById(
            "dhcpDns1"
        ).value.trim(),
        dns2: document.getElementById(
            "dhcpDns2"
        ).value.trim(),
        lease_time: Number(
            document.getElementById(
                "dhcpLeaseTime"
            ).value
        )
    };

    await operationRequest(
        "/network/dhcp/update",
        payload,
        "Atualizando DHCP...",
        "DHCP atualizado.",
        loadDhcpOperations
    );
}


function editDhcpReservation(event) {
    const item = advancedState.dhcp?.reservations?.[
        Number(event.currentTarget.dataset.index)
    ];

    if (!item) {
        return;
    }

    document.getElementById(
        "dhcpReservationId"
    ).value = item._InstID || "";

    document.getElementById(
        "dhcpReservationName"
    ).value = item.Name || "";

    document.getElementById(
        "dhcpReservationIp"
    ).value = item.IPAddr || "";

    document.getElementById(
        "dhcpReservationMac"
    ).value = item.MACAddr || "";
}


async function saveDhcpReservation(event) {
    event.preventDefault();

    const payload = {
        id: valueOrNull(
            "dhcpReservationId"
        ),
        name: document.getElementById(
            "dhcpReservationName"
        ).value.trim(),
        ip: document.getElementById(
            "dhcpReservationIp"
        ).value.trim(),
        mac: document.getElementById(
            "dhcpReservationMac"
        ).value.trim()
    };

    await operationRequest(
        "/network/dhcp/reservation/save",
        payload,
        "Salvando reserva DHCP...",
        "Reserva DHCP salva.",
        async () => {
            document.getElementById(
                "dhcpReservationForm"
            ).reset();

            document.getElementById(
                "dhcpReservationId"
            ).value = "";

            await loadDhcpOperations();
        }
    );
}


async function deleteDhcpReservation(event) {
    const item = advancedState.dhcp?.reservations?.[
        Number(event.currentTarget.dataset.index)
    ];

    if (
        !item?._InstID
        || !window.confirm(
            "Excluir esta reserva DHCP?"
        )
    ) {
        return;
    }

    await operationRequest(
        "/network/dhcp/reservation/delete",
        {
            id: item._InstID
        },
        "Excluindo reserva...",
        "Reserva removida.",
        loadDhcpOperations
    );
}


// =========================================================
// PORT FORWARDING / DMZ
// =========================================================

async function loadNatOperations() {
    await loadPortForwarding();
    await loadDmz();
}


async function loadPortForwarding() {
    const container = document.getElementById(
        "portForwardList"
    );

    try {
        const data = await apiRequest(
            "/network/port-forwarding"
        );

        advancedState.portForwarding = (
            Array.isArray(data)
                ? data
                : []
        );

        renderPortForwarding();
    } catch (error) {
        container.innerHTML = featureUnavailable(
            "Port Forwarding",
            error.message
        );
    }
}


function renderPortForwarding() {
    const container = document.getElementById(
        "portForwardList"
    );

    const items = advancedState.portForwarding;

    container.innerHTML = items.length
        ? items.map(
            (item, index) => `
                <div class="operation-row">
                    <div class="operation-row-head">
                        <strong>${escapeHtml(item.Alias || item.Description || "Regra NAT")}</strong>
                        <div>
                            <button class="text-action port-edit" data-index="${index}" type="button">Editar</button>
                            <button class="text-action port-delete" data-index="${index}" type="button">Excluir</button>
                        </div>
                    </div>
                    <div class="operation-meta">
                        <span>${escapeHtml(item.Protocol || "-")}</span>
                        <span>${escapeHtml(item.ExternalPort || "-")} → ${escapeHtml(item.InternalClient || "-")}:${escapeHtml(item.InternalPort || "-")}</span>
                        <span>${String(item.Enable) === "1" ? "ON" : "OFF"}</span>
                    </div>
                </div>
            `
        ).join("")
        : '<span class="muted">Nenhuma regra de port forwarding.</span>';

    container.querySelectorAll(
        ".port-edit"
    ).forEach(
        button => button.addEventListener(
            "click",
            editPortForward
        )
    );

    container.querySelectorAll(
        ".port-delete"
    ).forEach(
        button => button.addEventListener(
            "click",
            deletePortForward
        )
    );
}


function editPortForward(event) {
    const item = advancedState.portForwarding[
        Number(event.currentTarget.dataset.index)
    ];

    if (!item) {
        return;
    }

    document.getElementById(
        "portForwardId"
    ).value = item._InstID || "";

    document.getElementById(
        "portForwardName"
    ).value = item.Alias || item.Description || "";

    document.getElementById(
        "portForwardProtocol"
    ).value = item.Protocol || "TCP";

    document.getElementById(
        "portForwardExternal"
    ).value = item.ExternalPort || "";

    document.getElementById(
        "portForwardClient"
    ).value = item.InternalClient || "";

    document.getElementById(
        "portForwardInternal"
    ).value = item.InternalPort || "";

    document.getElementById(
        "portForwardConfirm"
    ).checked = false;
}


async function savePortForward(event) {
    event.preventDefault();

    const payload = {
        id: valueOrNull(
            "portForwardId"
        ),
        name: document.getElementById(
            "portForwardName"
        ).value.trim(),
        protocol: document.getElementById(
            "portForwardProtocol"
        ).value,
        external_port: Number(
            document.getElementById(
                "portForwardExternal"
            ).value
        ),
        internal_client: document.getElementById(
            "portForwardClient"
        ).value.trim(),
        internal_port: Number(
            document.getElementById(
                "portForwardInternal"
            ).value
        ),
        confirm: document.getElementById(
            "portForwardConfirm"
        ).checked
    };

    await operationRequest(
        "/network/port-forwarding/save",
        payload,
        "Aplicando regra NAT...",
        "Port forwarding atualizado.",
        async () => {
            document.getElementById(
                "portForwardConfirm"
            ).checked = false;

            await loadPortForwarding();
        }
    );
}


async function deletePortForward(event) {
    const item = advancedState.portForwarding[
        Number(event.currentTarget.dataset.index)
    ];

    if (
        !item?._InstID
        || !window.confirm(
            "Excluir esta regra de port forwarding?"
        )
    ) {
        return;
    }

    await operationRequest(
        "/network/port-forwarding/delete",
        {
            id: item._InstID,
            confirm: true
        },
        "Excluindo regra NAT...",
        "Regra removida.",
        loadPortForwarding
    );
}


async function loadDmz() {
    const container = document.getElementById(
        "dmzStatus"
    );

    try {
        const data = await apiRequest(
            "/network/dmz"
        );

        advancedState.dmz = (
            Array.isArray(data)
                ? data
                : []
        );

        const item = advancedState.dmz[0] || {};

        document.getElementById(
            "dmzId"
        ).value = item._InstID || "";

        document.getElementById(
            "dmzEnabled"
        ).checked = (
            String(item.Enable) === "1"
        );

        document.getElementById(
            "dmzClient"
        ).value = item.InternalClient || "";

        document.getElementById(
            "dmzWan"
        ).value = item.WANCViewName || "";

        container.innerHTML = item._InstID
            ? `
                <div class="operation-row">
                    <strong>Estado atual</strong>
                    <div class="operation-meta">
                        <span>${String(item.Enable) === "1" ? "ATIVA" : "DESATIVADA"}</span>
                        <span>${escapeHtml(item.InternalClient || "-")}</span>
                        <span>${escapeHtml(item.WANCViewName || "-")}</span>
                    </div>
                </div>
            `
            : '<span class="muted">Nenhuma instância DMZ retornada.</span>';
    } catch (error) {
        container.innerHTML = featureUnavailable(
            "DMZ",
            error.message
        );
    }
}


async function saveDmz(event) {
    event.preventDefault();

    const payload = {
        id: valueOrNull(
            "dmzId"
        ),
        enabled: document.getElementById(
            "dmzEnabled"
        ).checked,
        internal_client: document.getElementById(
            "dmzClient"
        ).value.trim(),
        wan: valueOrNull(
            "dmzWan"
        ),
        confirm: document.getElementById(
            "dmzConfirm"
        ).checked
    };

    await operationRequest(
        "/network/dmz/update",
        payload,
        "Aplicando DMZ...",
        "DMZ atualizada.",
        async () => {
            document.getElementById(
                "dmzConfirm"
            ).checked = false;

            await loadDmz();
        }
    );
}


// =========================================================
// INSPECTOR DE FIRMWARE / BACKUP
// =========================================================

async function readFirmwareFeature(event) {
    const feature = event.currentTarget.dataset.featureRead;

    setBusy(
        true,
        `Lendo ${feature}...`
    );

    try {
        const data = await apiRequest(
            `/features/read?feature=${encodeURIComponent(feature)}`
        );

        document.getElementById(
            "featureInspectorOutput"
        ).textContent = JSON.stringify(
            data,
            null,
            2
        );
    } catch (error) {
        document.getElementById(
            "featureInspectorOutput"
        ).textContent = error.message;
    } finally {
        setBusy(false);
    }
}


async function backupConfiguration() {
    if (
        !window.confirm(
            "Exportar agora um backup local da configuração da ONT?"
        )
    ) {
        return;
    }

    setBusy(
        true,
        "Exportando configuração da ONT..."
    );

    try {
        const data = await apiRequest(
            "/system/backup",
            {
                method: "POST"
            }
        );

        document.getElementById(
            "backupResult"
        ).innerHTML = `
            <div class="operation-row with-top-space">
                <strong>Backup salvo</strong>
                <p class="mono">${escapeHtml(data.path || data.filename || "-")}</p>
                <div class="operation-meta">
                    <span>${escapeHtml(data.size ?? 0)} bytes</span>
                </div>
            </div>
        `;

        showToast("Backup local concluído.");

        // Falha no refresh visual não invalida o backup já persistido.
        try {
            await loadHistory();
        } catch (historyError) {
            console.warn("Backup salvo; histórico indisponível:", historyError);
        }
    } catch (error) {
        showToast(
            error.message
        );
    } finally {
        setBusy(false);
    }
}


// =========================================================
// HISTÓRICO / SNAPSHOT
// =========================================================

async function captureSnapshot() {
    setBusy(
        true,
        "Capturando snapshot operacional..."
    );

    try {
        const data = await apiRequest(
            "/history/snapshot",
            {
                method: "POST",
                body: JSON.stringify({
                    reason: "manual-ui"
                })
            }
        );

        showToast(
            `Snapshot #${data.snapshot_id} salvo.`
        );

        // Snapshot já persistido; atualização visual é independente.
        try {
            await loadHistory();
        } catch (historyError) {
            console.warn("Snapshot salvo; histórico indisponível:", historyError);
        }
    } catch (error) {
        showToast(
            error.message
        );
    } finally {
        setBusy(false);
    }
}


async function loadHistory() {
    const container = document.getElementById(
        "historyOutput"
    );

    try {
        const data = await apiRequest(
            "/history?limit=20"
        );

        const changes = data.changes || [];
        const diagnostics = data.diagnostics || [];

        const rows = [
            ...changes.map(
                item => ({
                    type: item.success ? "CHANGE" : "FAILED",
                    title: item.operation,
                    time: item.created_at,
                    detail: item.target || item.message || "-"
                })
            ),
            ...diagnostics.map(
                item => ({
                    type: "DIAG",
                    title: item.status || "diagnostic",
                    time: item.created_at,
                    detail: item.summary || "-"
                })
            )
        ].sort(
            (a, b) => String(b.time).localeCompare(
                String(a.time)
            )
        ).slice(
            0,
            20
        );

        container.innerHTML = rows.length
            ? rows.map(
                item => `
                    <div class="operation-row">
                        <div class="operation-row-head">
                            <strong>${escapeHtml(item.title || "-")}</strong>
                            <small>${escapeHtml(item.type)}</small>
                        </div>
                        <p>${escapeHtml(item.detail || "-")}</p>
                        <small class="mono">${escapeHtml(item.time || "-")}</small>
                    </div>
                `
            ).join("")
            : '<span class="muted">Histórico vazio.</span>';
    } catch (error) {
        container.innerHTML = featureUnavailable(
            "Histórico",
            error.message
        );
    }
}


// =========================================================
// HELPERS
// =========================================================

async function operationRequest(
    endpoint,
    payload,
    busyText,
    successText,
    after
) {
    setBusy(
        true,
        busyText
    );

    try {
        await apiRequest(
            endpoint,
            {
                method: "POST",
                body: JSON.stringify(
                    payload
                )
            }
        );

        showToast(
            successText
        );

        if (after) {
            await after();
        }

        await loadHistory();
    } catch (error) {
        showToast(
            error.message
        );
    } finally {
        setBusy(false);
    }
}


function valueOrNull(id) {
    const value = document.getElementById(
        id
    )?.value?.trim();

    return value || null;
}


function featureUnavailable(
    title,
    message
) {
    return `
        <div class="operation-row">
            <strong>${escapeHtml(title)} indisponível</strong>
            <p>${escapeHtml(message || "O firmware/login não expôs este recurso.")}</p>
        </div>
    `;
}


// =========================================================
// LOAD / EVENTS
// =========================================================

async function loadOperationsConsole() {
    if (!ontConnected) {
        return;
    }

    const loaders = [
        loadCapabilityCatalog,
        loadDhcpOperations,
        loadNatOperations,
        loadHistory
    ];

    for (const loader of loaders) {
        try {
            await loader();
        } catch (error) {
            console.warn(
                "Operations suite:",
                error
            );
        }
    }

    advancedState.loaded = true;
}


function initAdvancedOperations() {
    document
        .querySelector(
            '[data-page="advanced"]'
        )
        ?.addEventListener(
            "click",
            loadOperationsConsole
        );

    document
        .getElementById(
            "probeCapabilitiesButton"
        )
        ?.addEventListener(
            "click",
            probeCapabilities
        );

    document
        .getElementById(
            "exportFeatureShapesButton"
        )
        ?.addEventListener(
            "click",
            exportFeatureShapes
        );

    document
        .getElementById(
            "captureSnapshotButton"
        )
        ?.addEventListener(
            "click",
            captureSnapshot
        );

    document
        .getElementById(
            "backupConfigurationButton"
        )
        ?.addEventListener(
            "click",
            backupConfiguration
        );

    document
        .getElementById(
            "automaticDiagnosticForm"
        )
        ?.addEventListener(
            "submit",
            runAutomaticDiagnostic
        );

    document
        .getElementById(
            "refreshHistoryButton"
        )
        ?.addEventListener(
            "click",
            loadHistory
        );

    document
        .getElementById(
            "dhcpBasicForm"
        )
        ?.addEventListener(
            "submit",
            saveDhcpBasic
        );

    document
        .getElementById(
            "dhcpReservationForm"
        )
        ?.addEventListener(
            "submit",
            saveDhcpReservation
        );

    document
        .getElementById(
            "portForwardForm"
        )
        ?.addEventListener(
            "submit",
            savePortForward
        );

    document
        .getElementById(
            "dmzForm"
        )
        ?.addEventListener(
            "submit",
            saveDmz
        );

    document
        .querySelectorAll(
            "[data-feature-read]"
        )
        .forEach(
            button => button.addEventListener(
                "click",
                readFirmwareFeature
            )
        );
}


if (document.readyState === "loading") {
    document.addEventListener(
        "DOMContentLoaded",
        initAdvancedOperations,
        { once: true }
    );
} else {
    initAdvancedOperations();
}

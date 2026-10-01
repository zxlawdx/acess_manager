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
    loaded: false,
    networkLoaded: { dhcp: false, portForwarding: false, dmz: false }
};
let advancedNetworkBusy = false;
let meshProbeBusy = false;


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

    if (!data || typeof data.features !== "object" || !data.features ||
        Array.isArray(data.features)) {
        throw new Error("O catálogo nativo retornou um formato inválido.");
    }
    advancedState.capabilities = data;
    const badge = document.getElementById("adapterBadge");
    if (badge) badge.textContent = "Catálogo carregado";
    populateFirmwareSelector(data.features);

    renderCapabilities(data.features, null);
    return data;
}


function populateFirmwareSelector(features) {
    const select = document.getElementById("firmwareFeatureSelect");
    const button = document.getElementById("firmwareInspectButton");
    if (!select) return;
    const previous = select.value;
    select.replaceChildren();
    const catalog = Object.entries(features || {}).sort((a, b) => {
        const operator = globalThis.AccessManagerInspector;
        const left = operator?.label(a[0], a[1]?.label) || a[1]?.label || a[0];
        const right = operator?.label(b[0], b[1]?.label) || b[1]?.label || b[0];
        return left.localeCompare(right, "pt-BR");
    });
    const intro = document.createElement("option");
    intro.value = "";
    intro.textContent = catalog.length
        ? "Selecione uma funcionalidade" : "Nenhuma funcionalidade catalogada";
    select.appendChild(intro);
    for (const [feature, spec] of catalog) {
        const option = document.createElement("option");
        option.value = feature;
        option.textContent = globalThis.AccessManagerInspector?.label(feature, spec.label) ||
            "Funcionalidade do equipamento";
        select.appendChild(option);
    }
    if (catalog.some(([name]) => name === previous)) select.value = previous;
    select.disabled = !catalog.length;
    if (button) button.disabled = !select.value;
    const notice = document.getElementById("firmwareInspectorNotice");
    if (notice) notice.textContent = catalog.length
        ? catalog.length + " funcionalidades catalogadas. A disponibilidade de cada uma só é confirmada após a consulta."
        : "Este modelo não forneceu uma lista de funcionalidades. Revise a identificação.";
}

let nativeProbeBusy = false;

function renderNativeDetection(catalog, results, model) {
    const byFeature = new Map(results.map(item => [item.feature, item]));
    const rows = Object.entries(catalog).map(([feature, spec]) => {
        const result = byFeature.get(feature);
        return {
            feature, label: spec.label || feature,
            status: !result || result.not_tested
                ? "not_tested" : result.available ? "detected" :
                  result.status === "inconclusive" ? "inconclusive" : "not_confirmed",
            // A failed request is NOT evidence of an absent firmware feature.
            reason: result && !result.available && !result.not_tested
                ? (result.reason || "probe_inconclusive") : undefined
        };
    });
    const checked = rows.filter(row => row.status !== "not_tested").length;
    const confirmed = rows.filter(row => row.status === "detected").length;
    renderTrackerDiscovery({
        model, family: "thinklua_native", candidate_features: rows,
        reason: `Recursos consultados: ${checked}/${rows.length}, ${confirmed} confirmados. ` +
            "Uma consulta sem resposta não comprova ausência de funcionalidade."
    });
}

async function probeCapabilities() {
    if (!ontConnected) {
        showToast("Conecte-se à ONT para detectar recursos.");
        return;
    }
    if (nativeProbeBusy || trackerProbeBusy || modelDiagnosticRunning ||
        advancedNetworkBusy || meshProbeBusy) {
        showToast("Uma sondagem já está em andamento. Aguarde a conclusão.");
        return;
    }
    // GETs do adaptador são independentes de POSTs: sessão em modo
    // somente leitura não torna o catálogo nativo indisponível.
    let bootstrap;
    try {
        bootstrap = await discoveryRequest("/discovery/bootstrap", {
            timeoutMs: 10000
        });
    } catch (error) {
        showToast("Identificação temporariamente indisponível: " + error.message);
        return;
    }
    if (bootstrap.native_diagnostics_available !== true) {
        await probeMultimodel();
        return;
    }
    nativeProbeBusy = true;
    const scanGeneration = trackerSessionGeneration;
    setBusy(true, "Carregando catálogo de menus nativos...");

    try {
        // Lotes curtos evitam uma requisição longa contendo todos os menus
        // e mantêm os resultados obtidos mesmo se um lote falhar.
        if (!advancedState.capabilities) {
            await loadCapabilityCatalog();
        }

        const catalog = advancedState.capabilities?.features || {};
        const keys = Object.keys(catalog);
        if (!keys.length) {
            showToast("Não há recursos de inspeção catalogados. Confirme o modelo do equipamento.");
            return;
        }
        const results = [];
        const batchSize = 3;

        for (let index = 0; index < keys.length; index += batchSize) {
            const batch = keys.slice(index, index + batchSize);
            setBusy(true,
                `Detectar recursos: ${Math.min(index + batchSize, keys.length)}/${keys.length} menus...`);
            try {
                const response = await discoveryRequest(
                    "/device/capabilities/probe",
                    {
                        method: "POST",
                        body: JSON.stringify({ features: batch }),
                        timeoutMs: 70000
                    }
                );
                if (scanGeneration !== trackerSessionGeneration || !ontConnected) return;
                if (!Array.isArray(response.features)) {
                    throw new Error("O probe retornou um formato de recursos inválido.");
                }
                results.push(...response.features);
            } catch (error) {
                console.warn("Probe parcial:", batch, error);
                const timeout = /passou de \\d+s/.test(String(error.message));
                results.push(...batch.map(feature => ({
                    feature,
                    available: false,
                    error: error.message,
                    not_tested: timeout
                })));
                if (timeout) {
                    const info = document.getElementById("trackerDiscoveryStatus");
                    if (info) info.textContent =
                        "Sondagem nativa interrompida por demora. O firmware pode continuar processando.";
                    advancedState.capabilityProbe = { features: results };
                    renderCapabilities(catalog, results);
                    renderNativeDetection(catalog, results, bootstrap.detected_model || bootstrap.model);
                    break;
                }
            }

            advancedState.capabilityProbe = { features: results };
            renderCapabilities(catalog, results);
            renderNativeDetection(catalog, results, bootstrap.detected_model || bootstrap.model);
            showToast(
                `Recursos verificados: ${Math.min(index + batchSize, keys.length)}/${keys.length}`
            );
        }

        const available = results.filter(item => item.available).length;
        const unavailable = results.filter(item => !item.available && !item.not_tested).length;
        const pending = keys.length - results.filter(item => !item.not_tested).length;
        showToast(`Detecção: ${available} confirmado(s), ${unavailable} indisponível(is), ` +
            `${Math.max(0, pending)} pendente(s).`);
    } catch (error) {
        showToast(error.message);
    } finally {
        nativeProbeBusy = false;
        setBusy(false);
    }
}

// Relatório independente dos menus comuns F6600P. Alguns modelos usam
// vueData e não possuem sequer o mesmo endpoint menuView.
let trackerQuickScanKey = null;
let trackerQuickScanPromise = null;
let trackerDetectedModel = null;
let trackerSelectedFamily = null;

function renderTrackerDiscovery(data) {
    const grid = document.getElementById("trackerCapabilityGrid");
    const status = document.getElementById("trackerDiscoveryStatus");
    if (!grid || !status) return;
    const features = [
        ...(data.capabilities || []),
        ...(data.candidate_features || [])
    ];
    const found = features.filter(item => item.status === "detected").length;
    const notConfirmed = features.filter(
        item => item.status === "not_confirmed"
    ).length;
    const model = data.model || trackerDetectedModel || "Não identificado";
    status.textContent = data.reason ? normalizeApiErrorMessage(data.reason) :
        `${model} • ${found} confirmado(s), ${notConfirmed} não confirmado(s), ${features.length - found - notConfirmed} pendente(s)`;
    grid.innerHTML = features.length ? features.map(item => {
        const confirmed = item.status === "detected";
        const unconfirmed = item.status === "not_confirmed" || item.status === "inconclusive";
        const absent = item.reason === "confirmed_absence";
        const reasonLabels = {
            session_expired: "Sessão expirada — reconecte",
            login_page_instead_of_data: "Firmware retornou página de login",
            invalid_xml: "Resposta do menu em formato inesperado",
            unexpected_firmware_response: "Objeto esperado não retornado",
            network_timeout: "O equipamento não respondeu a tempo",
            not_exposed_or_permission_denied: "O menu não pôde ser confirmado",
            probe_inconclusive: "Sondagem inconclusiva. Revise a sessão e tente novamente.",
            confirmed_absence: "Firmware confirmou ausência do recurso"
        };
        const label = confirmed ? "Confirmado neste equipamento"
            : unconfirmed
                ? (reasonLabels[item.reason] || "Recurso não confirmado")
                : "Documentado, ainda não testado";
        return `<article class="capability-card">
            <div class="capability-head"><div>
                <strong>${escapeHtml(globalThis.AccessManagerInspector?.label(item.feature, item.label) || "Funcionalidade do equipamento")}</strong>
                <p>${escapeHtml(label)}</p>
            </div><i class="capability-state ${confirmed ? "available" : absent ? "unavailable" : ""}"></i></div>
            <div class="operation-meta"><span>IDENTIFICAÇÃO</span><span>Leitura vinculada à sessão atual</span></div>
        </article>`;
    }).join("") : '<p class="muted">Nenhum endpoint documentado confirmado para este perfil.</p>';
}

let discoveryBootPromise = null;
let discoveryCatalogHost = null;
let discoveryCatalogRevision = null;
let trackerSessionGeneration = 0;

// Algumas ONTs retornam "ZXHN F6600P" em vez de "F6600P". Não
// tratar prefixos do fabricante como divergência de identidade: o
// backend já fez a verificação da sessão real.
function resolvedModelCode(value, models = []) {
    const normalized = String(value || "").toUpperCase()
        .replace(/[^A-Z0-9]/g, "");
    const names = models.map(item => String(item.model || "").toUpperCase()
        .replace(/[^A-Z0-9]/g, "")).sort((a, b) => b.length - a.length);
    return names.find(code => code && normalized.endsWith(code)) || normalized;
}

// O bootstrap não consulta a ONT: a lista de modelos precisa aparecer mesmo
// se outro diagnóstico estiver segurando o contexto HTTP do equipamento.
async function loadMultimodelCatalog({ refresh = false } = {}) {
    const select = document.getElementById("multimodelSelect");
    const info = document.getElementById("trackerDiscoveryStatus");
    if (!select) return null;
    if (!refresh && select.dataset.loaded === "true"
        && discoveryCatalogHost === currentHost &&
        discoveryCatalogRevision === globalThis.currentZteRevision) return null;
    if (discoveryBootPromise) return discoveryBootPromise;
    if (info) info.textContent = "Lendo o estado da sessão local...";

    const startGeneration = trackerSessionGeneration;
    discoveryBootPromise = (async () => {
        // O servidor não realiza I/O com o roteador nesta rota.
        const response = await discoveryRequest("/discovery/bootstrap", {
            timeoutMs: 10000
        });
        if (startGeneration !== trackerSessionGeneration) return response;
        if (response.error) throw new Error(normalizeApiErrorMessage(response.error));
        if (!response.connected) {
            if (info) info.textContent =
                response.reason ? normalizeApiErrorMessage(response.reason) : "Conecte-se ao equipamento primeiro.";
            return response;
        }

        // Recriar options impede duplicatas após reconexão/troca de ONT.
        const catalogModels = response.catalog?.models || [];
        select.replaceChildren(new Option("Usar identificação automática", ""));
        for (const item of catalogModels) {
            select.add(new Option(
                item.model,
                item.model
            ));
        }

        // O backend conhece o modelo selecionado no LOGIN. Nunca mudar
        // silenciosamente o perfil de uma sessão já autenticada.
        const detected = resolvedModelCode(
            response.detected_model, catalogModels
        );
        const selected = resolvedModelCode(response.model, catalogModels);
        if (detected && detected !== "ZTE" && selected && selected !== detected) {
            trackerDetectedModel = null;
            trackerSelectedFamily = null;
            if (info) info.textContent =
                "Modelo escolhido diferente do detectado. Reconecte para corrigir.";
            return response;
        }
        trackerDetectedModel = detected && detected !== "ZTE"
            ? response.detected_model : response.model || null;
        globalThis.currentZteRevision = response.session_revision || "";
        const normalized = resolvedModelCode(
            trackerDetectedModel, catalogModels
        );
        const matched = catalogModels.find(item =>
            normalized === resolvedModelCode(item.model, catalogModels)
        );
        trackerSelectedFamily = matched?.family || null;
        if (matched) select.value = matched.model;
        select.dataset.loaded = "true";
        discoveryCatalogHost = currentHost;
        discoveryCatalogRevision = response.session_revision || null;

        const badge = document.getElementById("adapterBadge");
        if (badge) badge.textContent = trackerDetectedModel
            ? `PERFIL ${trackerDetectedModel}` : "MODELO NÃO INFORMADO";

        if (matched) {
            const candidates = (matched.candidate_features || []).map(feature => ({
                feature,
                label: feature.replace(/_/g, " "),
                status: "not_tested"
            }));
            renderTrackerDiscovery({
                model: matched.model, family: matched.family,
                candidate_features: candidates
            });
        } else if (info) {
            info.textContent = trackerDetectedModel
                ? "Modelo identificado, mas sem perfil documentado. Consultando o catálogo nativo."
                : "O backend ainda não retornou um modelo verificado.";
            const grid = document.getElementById("trackerCapabilityGrid");
            if (grid) grid.textContent = trackerDetectedModel
                ? "Use Detectar recursos para consultar as capacidades nativas."
                : "A identificação ainda não terminou. Tente novamente.";
        }
        return response;
    })().catch(error => {
        if (info) info.textContent =
            "Falha ao carregar catálogo: " + String(error.message || error);
        throw error;
    }).finally(() => { discoveryBootPromise = null; });
    return discoveryBootPromise;
}

// Identificar modelo é uma leitura LOCAL do login, não uma sequência de
// 20+ GETs lentos. A sondagem é uma ação separada: "Detectar recursos".
async function detectConnectedModel() {
    if (!ontConnected) {
        showToast("Conecte-se à ONT para identificar o modelo.");
        return;
    }
    const button = document.getElementById("multimodelProbeButton");
    const output = document.getElementById("multimodelProbeOutput");
    const status = document.getElementById("trackerDiscoveryStatus");
    if (button) button.disabled = true;
    try {
        const bootstrap = await loadMultimodelCatalog({ refresh: true });
        const catalog = bootstrap?.catalog?.models || [];
        const detected = resolvedModelCode(bootstrap?.detected_model, catalog);
        const selected = resolvedModelCode(bootstrap?.model, catalog);
        const profile = catalog.find(item =>
            resolvedModelCode(item.model, catalog) === (detected || selected)
        );
        if (!bootstrap?.connected || !bootstrap.model_verified ||
            !profile || (detected && selected && detected !== selected)) {
            const reason = "Modelo ainda não confirmado pela sessão autenticada. " +
                "Reconecte e confira a identidade no equipamento.";
            if (status) status.textContent = reason;
            if (output) output.textContent = reason;
            showToast(reason);
            return;
        }
        const message = `Modelo: ${profile.model} · Firmware: ${bootstrap.firmware || "não informado"}` +
            " · Identificação confirmada no login. " +
            "Use Detectar recursos para validar os GETs disponíveis.";
        if (output) output.textContent = message;
        if (status) status.textContent = message;
        showToast("Modelo identificado. Recursos ainda não testados.");
    } catch (error) {
        const message = "Falha ao identificar o modelo: " + error.message;
        if (status) status.textContent = message;
        if (output) output.textContent = message;
        showToast(message);
    } finally {
        if (button) button.disabled = false;
    }
}

// Timeout somente nas rotas de descoberta. Não encerra a sessão da ONT:
// uma falha ou diagnóstico prolongado é exibido e os outros botões
// permanecem operacionais no QtWebEngine.
async function discoveryRequest(endpoint, {
    method = "GET", body = undefined, timeoutMs = 55000
} = {}) {
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), timeoutMs);
    try {
        const data = await apiRequest(endpoint, { method, body,
            signal: controller.signal
        });
        if (!data || typeof data !== "object" || Array.isArray(data)) {
            throw new Error(
                "Não foi possível interpretar os recursos retornados pelo equipamento. " +
                "Confirme a versão instalada e tente novamente."
            );
        }
        return data;
    } catch (error) {
        if (error?.name === "AbortError") {
            throw new Error(
                `A consulta excedeu ${Math.round(timeoutMs / 1000)} segundos. ` +
                "A sessão pode continuar ativa; aguarde antes de repetir."
            );
        }
        throw error;
    } finally {
        clearTimeout(timer);
    }
}

// Faz uma coleta pequena na primeira abertura, sem sondar dezenas de
// páginas e competir com o login/diagnóstico do firmware.
function autoDiscoverTracker() {
    if (!ontConnected || !trackerDetectedModel) return Promise.resolve();
    const key = `${globalThis.currentZteRevision || ""}:${currentHost || ""}:${trackerDetectedModel}`;
    if (trackerQuickScanKey === key) return trackerQuickScanPromise || Promise.resolve();
    trackerQuickScanKey = key;
    trackerQuickScanPromise = probeMultimodel({ quick: true })
        .catch(error => {
            trackerQuickScanKey = null;
            console.warn("Leitura automática não confirmada:", error);
        })
        .finally(() => { trackerQuickScanPromise = null; });
    return trackerQuickScanPromise;
}


let modelDiagnosticRunning = false;
async function runMultimodelDiagnostic() {
    const output = document.getElementById("multimodelProbeOutput");
    const button = document.getElementById("multimodelDiagnosticButton");
    if (!ontConnected) {
        showToast("Conecte ao equipamento antes do diagnóstico.");
        return;
    }
    if (modelDiagnosticRunning || nativeProbeBusy || trackerProbeBusy ||
        advancedNetworkBusy || meshProbeBusy) {
        showToast("Aguarde a leitura avançada atual antes de iniciar outra.");
        return;
    }
    modelDiagnosticRunning = true;
    if (button) button.disabled = true;
    // Reconsultar identificação autoritativa nesta sessão. Não usar o
    // trackerProbe possivelmente carregado antes de trocar de ONT.
    let bootstrap;
    try {
        bootstrap = await discoveryRequest("/discovery/bootstrap");
        if (!bootstrap.connected) throw new Error("Sessão não conectada");
        const knownModels = bootstrap.catalog?.models || [];
        const detected = resolvedModelCode(bootstrap.detected_model, knownModels);
        const selected = resolvedModelCode(bootstrap.model, knownModels);
        if (!bootstrap.model_verified ||
            (detected && detected !== "ZTE" && selected && selected !== detected))
            throw new Error("Modelo não verificado ou perfil divergente da sessão.");
        trackerDetectedModel = detected && detected !== "ZTE"
            ? bootstrap.detected_model : bootstrap.model;
    } catch (error) {
        modelDiagnosticRunning = false;
        if (button) button.disabled = false;
        showToast("Identificação atual indisponível: " + error.message);
        return;
    }
    const knownModels = bootstrap.catalog?.models || [];
    const normalized = resolvedModelCode(trackerDetectedModel, knownModels);
    const profile = knownModels.find(
        item => resolvedModelCode(item.model, knownModels) === normalized
    );
    const family = profile?.family || null;
    // Consultar somente páginas documentadas para a família, em vez de
    // gastar 10-20 segundos em cada menu que não existe na F6600P.
    const profiles = {
        f6640: ["device", "wan", "wifi_ssids",
            "wifi_clients", "lan_clients"],
        h288a: ["device", "wan", "wifi_clients", "lan_clients"],
        h388x: ["device", "wan", "wifi_clients", "lan_clients"],
        h2640: ["device", "dsl", "wifi_clients", "lan_clients"],
        vue: ["wan", "wifi_clients", "lan_clients"],
        f6201b_candidate: ["device", "optical", "wan", "wifi_ssids",
            "wifi_clients", "dhcp_leases", "wifi_radios", "lan_ports",
            "band_steering", "wps", "mesh", "dns", "dhcp",
            "route_table", "arp", "firewall", "voip_status",
            "tr069_status", "upnp", "wifi_schedule",
            "ping_history", "traceroute_history"]
    };
    const sections = [...(profiles[family] || [
        "device", "wan", "wifi_clients", "lan_clients"
    ])];
    if (family === "f6640" &&
        String(trackerDetectedModel || "").toUpperCase().includes("F6600P")) {
        sections.splice(2, 0, "optical");
    }
    const diagnosticGeneration = trackerSessionGeneration;
    const report = {
        model: trackerDetectedModel || "Sessão atual",
        read_only: true, sections: {}, errors: {}
    };
    const render = (step, total) => {
        if (!output) return;
        const ok = Object.values(report.sections).filter(
            item => item?.available
        ).length;
        if (window.renderAdaptiveDiagnostic) {
            window.renderAdaptiveDiagnostic(report, output, {
                progress: "Diagnóstico " + step + "/" + total +
                          " · " + ok + " leituras confirmadas"
            });
        } else output.textContent = "Diagnóstico " + step + "/" + total;
    };
    setBusy(true, "Preparando diagnóstico por modelo...");
    render(0, sections.length);
    try {
        // Toda consulta tem resposta própria. Erro em LAN/DSL não impede
        // visualizar WAN, recursos ou GPON já obtidos.
        for (const [index, section] of sections.entries()) {
            setBusy(true,
                `Diagnóstico ${index + 1}/${sections.length}: ${section}...`);
            try {
                const data = await discoveryRequest("/multimodel/diagnostic", {
                    method: "POST",
                    body: JSON.stringify({ section }),
                    timeoutMs: 48000
                });
                if (diagnosticGeneration !== trackerSessionGeneration ||
                    !ontConnected) return;
                report.model = data.model || report.model;
                report.family = data.family;
                Object.assign(report.sections, data.sections || {});
                if (data.reason) report.errors[section] = data.reason;
            } catch (error) {
                report.errors[section] = String(error.message || error);
                // Timeout não invalida o que já temos, mas a consulta
                // anterior pode ainda estar executando no backend.
                if (/passou de \d+s/.test(String(error.message))) {
                    render(index + 1, sections.length);
                    showToast("Diagnóstico parcial: tempo esgotado. Dados anteriores mantidos.");
                    break;
                }
            }
            render(index + 1, sections.length);
        }
        const found = Object.values(report.sections).filter(
            item => item?.available
        ).length;
        showToast(found
            ? `Diagnóstico finalizado: ${found} seções com dados.`
            : "Diagnóstico sem dados confirmados. Consulte os motivos no relatório.");
    } finally {
        modelDiagnosticRunning = false;
        if (button) button.disabled = false;
        setBusy(false);
    }
}

async function showMultimodelMesh() {
    if (meshProbeBusy || nativeProbeBusy || trackerProbeBusy ||
        modelDiagnosticRunning || advancedNetworkBusy) {
        showToast("Aguarde a leitura avançada atual antes do resumo Mesh.");
        return;
    }
    meshProbeBusy = true;
    const output = document.getElementById("multimodelProbeOutput");
    const select = document.getElementById("multimodelSelect");
    setBusy(true, "Consultando topologia Mesh...");
    try {
        const result = await discoveryRequest("/multimodel/mesh", {
            method: "POST",
            body: JSON.stringify({ model: trackerDetectedModel || null }),
            timeoutMs: 50000
        });
        if (window.renderAdaptiveDiagnostic) {
            window.renderAdaptiveDiagnostic({
                model: trackerDetectedModel || "ZTE",
                sections: { mesh: {
                    available: result.available === true,
                    data: result.available ? result : null,
                    reason: result.reason
                } }
            }, output);
        }
        showToast(
            result.available
                ? "Resumo Mesh consultado. Nenhum dado pessoal exportado."
                : (result.reason || "Topologia não disponível neste modelo.")
        );
    } catch (error) {
        output.textContent = "Topologia indisponível para este firmware.";
        showToast(error.message);
    } finally {
        meshProbeBusy = false;
        setBusy(false);
    }
}


document.addEventListener("zte:session-changed", () => {
    trackerSessionGeneration++;
    trackerQuickScanKey = null;
    trackerQuickScanPromise = null;
    trackerDetectedModel = null;
    trackerSelectedFamily = null;
    discoveryBootPromise = null;
    discoveryCatalogHost = null;
    discoveryCatalogRevision = null;
    globalThis.currentZteRevision = null;
    advancedState.capabilities = null;
    advancedState.capabilityProbe = null;
    advancedState.trackerProbe = null;
    advancedState.networkLoaded = { dhcp: false, portForwarding: false, dmz: false };
    advancedState.dhcp = null;
    huaweiIpv4FilterState.rules = [];
    huaweiIpv4FilterState.capability = null;
    resetHuaweiIpv4FilterForm();
    syncAdvancedNetworkForms();
    syncHuaweiAdvancedMode();
    const select = document.getElementById("multimodelSelect");
    if (select) {
        select.dataset.loaded = "false";
        select.replaceChildren(new Option("Detectar automaticamente", ""));
    }
    for (const id of ["trackerCapabilityGrid", "multimodelProbeOutput"]) {
        document.getElementById(id)?.replaceChildren();
    }
    const status = document.getElementById("trackerDiscoveryStatus");
    if (status) status.textContent = "Aguardando identificação da ONT conectada.";
});

let trackerProbeBusy = false;

async function probeMultimodel({ quick = false } = {}) {
    const output = document.getElementById("multimodelProbeOutput");
    const select = document.getElementById("multimodelSelect");
    if (!ontConnected) {
        showToast("Conecte-se ao equipamento primeiro.");
        return;
    }
    if (trackerProbeBusy || nativeProbeBusy || modelDiagnosticRunning ||
        advancedNetworkBusy || meshProbeBusy) {
        if (!quick) showToast("Aguarde a leitura avançada atual.");
        return;
    }
    trackerProbeBusy = true;
    const scanGeneration = trackerSessionGeneration;
    const button = document.getElementById("multimodelProbeButton");
    if (button) button.disabled = true;

    if (!trackerDetectedModel) {
        try {
            await loadMultimodelCatalog();
        } catch (error) {
            trackerProbeBusy = false;
            if (button) button.disabled = false;
            if (output) output.textContent =
                "Erro ao obter modelo do servidor: " + error.message;
            showToast(error.message);
            return;
        }
    }
    const model = select?.value || trackerDetectedModel || null;
    if (!model) {
        trackerProbeBusy = false;
        if (button) button.disabled = false;
        const status = document.getElementById("trackerDiscoveryStatus");
        if (status) status.textContent =
            "Não foi possível identificar o modelo. Reconecte escolhendo-o no login.";
        showToast("Identifique o modelo antes da sondagem.");
        return;
    }
    if (!quick) setBusy(true, "Detectando endpoints documentados...");
    const status = document.getElementById("trackerDiscoveryStatus");
    if (status) status.textContent = quick
        ? "Iniciando leitura automática do firmware..."
        : "Verificando recursos reais, por etapas...";
    const verified = new Map();
    const candidates = new Map();
    const endpoints = {};
    let total = 0;
    let offset = 0;
    let last = null;

    try {
        // Requisições sequenciais: os menus ZTE compartilham o contexto.
        // O operador consegue ver o que foi confirmado após cada lote,
        // sem aguardar o último endpoint nem interpretar candidato como real.
        do {
            const batch = await discoveryRequest("/multimodel/probe", {
                method: "POST",
                body: JSON.stringify({
                    model,
                    max_endpoints: 2,
                    start: offset
                }),
                timeoutMs: 55000
            });
            if (scanGeneration !== trackerSessionGeneration ||
                !ontConnected) return;
            last = batch;
            total = Number(batch.total_candidates || 0);
            for (const item of batch.capabilities || []) {
                verified.set(item.feature, item);
                candidates.delete(item.feature);
            }
            for (const item of batch.candidate_features || []) {
                if (!verified.has(item.feature)) {
                    candidates.set(item.feature, item);
                }
            }
            Object.assign(endpoints, batch.endpoints || {});
            const combined = {
                ...batch,
                endpoints,
                capabilities: [...verified.values()],
                candidate_features: [...candidates.values()]
            };
            advancedState.trackerProbe = combined;
            renderTrackerDiscovery(combined);
            offset = Number(batch.next_offset ?? (offset + 2));
            const confirmed = [...verified.values()].filter(item => item.available).length;
            if (status && total) {
                status.textContent =
                    `${batch.model || model}: ${Math.min(offset, total)}/${total} verificações · ${confirmed} confirmado(s)`;
            }
            if (output) {
                if (window.renderAdaptiveDiagnostic) {
                    const sections = {};
                    Object.entries(endpoints).forEach(([name, value]) => {
                        sections[name] = {
                            available: value.available === true,
                            data: null, // availability is not an actual data reading
                            reason: value.reason
                        };
                    });
                    window.renderAdaptiveDiagnostic({
                        model: batch.model || model,
                        sections, probe_only: true
                    }, output, {
                        progress: "Verificação " + Math.min(offset, total) +
                                  "/" + total
                    });
                }
            }
            if (batch.session_expired) {
                if (status) status.textContent =
                    "Sessão expirada durante a leitura. Reconecte à ONT antes de continuar.";
                break;
            }
            if (quick || !total) break;
        } while (offset < total);

        const confirmed = [...verified.values()].filter(item => item.available).length;
        const badge = document.getElementById("adapterBadge");
        if (badge) badge.textContent = `${confirmed} CONFIRMADO(S)`;
        if (!quick) showToast(
            confirmed
                ? `${confirmed} recurso(s) de leitura validado(s) neste firmware.`
                : "Não foi possível confirmar endpoints. Verifique as permissões."
        );
        return {
            ...last,
            endpoints,
            capabilities: [...verified.values()],
            candidate_features: [...candidates.values()],
        };
    } catch (error) {
        if (status) {
            status.textContent = "Leitura parcial ou falhou: " + error.message;
        }
        if (output) output.textContent += "\nFalha: " + error.message;
        if (!quick) showToast(error.message);
        throw error;
    } finally {
        trackerProbeBusy = false;
        if (button) button.disabled = false;
        if (!quick) setBusy(false);
    }
}

async function exportFeatureShapes() {
    const results = advancedState.capabilityProbe?.features || [];
    const available = results
        .filter(item => item.available)
        .map(item => item.feature);

    const tracker = advancedState.trackerProbe || null;
    if (!available.length && !tracker) {
        showToast("Detecte os menus nativos ou o modelo antes de gerar o mapa.");
        return;
    }

    const panel = document.getElementById("firmwareShapePanel");
    const output = document.getElementById("firmwareShapeOutput");
    panel.classList.remove("hidden");

    const report = {
        schema: 1,
        adapter: "Equipamento identificado",
        notes: "Contém apenas estrutura de menu e contagens. Revisar antes de compartilhar.",
        tracker: tracker ? {
            model: tracker.model,
            family: tracker.family,
            endpoints: tracker.endpoints,
            features: tracker.capabilities,
            untested: tracker.candidate_features,
        } : null,
        features: []
    };
    // O tracker já entregou campos/contagens sem valores pessoais. Isto
    // também funciona quando não existe um adaptador ThinkLua nativo.
    const drawMap = () => {
        if (globalThis.AccessManagerInspector?.renderMap) {
            globalThis.AccessManagerInspector.renderMap(report, output);
        } else {
            output.textContent = "A visualização dos recursos não está disponível nesta instalação.";
        }
    };
    drawMap();

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

            drawMap();
        }

        drawMap();
        showToast("Mapa atualizado com as leituras confirmadas da sessão.");
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

                const stateClass = state?.available ? "available" :
                    state?.status === "absent" ? "unavailable" : "";
                const stateText = !state ? "Não testado" :
                    state.available ? "Confirmado nesta sessão" :
                    state.status === "absent" ? "Ausência confirmada" :
                    state.status === "inconclusive" ? "Sondagem inconclusiva" :
                    state.probeable === false ? "Sem adaptador de leitura; não verificado" :
                    "Não testado";

                return `
                    <article class="capability-card">
                        <div class="capability-head">
                            <div>
                                <strong>${escapeHtml(globalThis.AccessManagerInspector?.label(key, spec.label) || "Funcionalidade do equipamento")}</strong>
                                <p>${escapeHtml(stateText)}</p>
                            </div>
                            <i class="capability-state ${stateClass}"></i>
                        </div>

                        <div class="operation-meta">
                            ${spec.writable ? "<span>Configuração prevista no perfil</span>" : "<span>Consulta neste aplicativo</span>"}
                            ${spec.dangerous ? "<span>CONFIRMAÇÃO</span>" : ""}
                        </div>

                        
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
    if (!routerWriteEnabled) {
        // A ausência de escrita não bloqueia diagnóstico GET.
        await runMultimodelDiagnostic();
        return;
    }

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
                    ${Object.entries(data.errors || {}).map(([section, reason]) => `
                        <p class="adaptive-footnote"><strong>${escapeHtml(section)}:</strong>
                        ${escapeHtml(String(reason).slice(0, 160))}</p>
                    `).join("")}
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

// Prevent accidental DHCP/NAT writes with empty/stale forms when the
// expensive read is now operator-initiated. This is data readiness, not a
// firmware/version permission gate; backend still checks the live device.
function syncAdvancedNetworkForms() {
    const loaded = advancedState.networkLoaded;
    const controls = [
        ["dhcp", "#dhcpBasicForm button[type=submit]"],
        ["dhcp", "#dhcpReservationForm button[type=submit]"],
        ["portForwarding", "#portForwardForm button[type=submit]"],
        ["dmz", "#dmzForm button[type=submit]"]
    ];
    for (const [key, selector] of controls) {
        const control = document.querySelector(selector);
        if (!control) continue;
        const ready = Boolean(ontConnected && routerWriteEnabled && loaded[key]) &&
            (key !== "dhcp" || advancedState.dhcp?.write_safe !== false);
        control.disabled = !ready;
        control.title = ready ? "" : "Carregue os dados atuais antes de configurar.";
    }
}

async function loadDhcpOperations() {
    try {
        const data = await apiRequest(
            "/network/dhcp"
        );

        advancedState.dhcp = data;

        const basic = data.basic || {};
        const apply = document.querySelector("#dhcpBasicForm button[type=submit]");
        if (apply) apply.disabled = data.write_safe === false;
        if (data.write_safe === false) {
            const list = document.getElementById("dhcpLeaseList");
            if (list) list.textContent = (
                (data.warnings || []).join(" ") ||
                "Valores DHCP não confirmados. Escrita desativada."
            );
        }

        document.getElementById(
            "advancedDhcpEnabled"
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
            "advancedDhcpDns1"
        ).value = basic.DNSServer1 || "";

        document.getElementById(
            "advancedDhcpDns2"
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
        advancedState.networkLoaded.dhcp = true;
        syncAdvancedNetworkForms();
        return true;
    } catch (error) {
        advancedState.networkLoaded.dhcp = false;
        syncAdvancedNetworkForms();
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
        return false;
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
            "advancedDhcpEnabled"
        ).checked,
        min_address: document.getElementById(
            "dhcpMinAddress"
        ).value.trim(),
        max_address: document.getElementById(
            "dhcpMaxAddress"
        ).value.trim(),
        dns1: document.getElementById(
            "advancedDhcpDns1"
        ).value.trim(),
        dns2: document.getElementById(
            "advancedDhcpDns2"
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
    const forwarding = await loadPortForwarding();
    const dmz = await loadDmz();
    return forwarding && dmz;
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
        advancedState.networkLoaded.portForwarding = true;
        syncAdvancedNetworkForms();
        return true;
    } catch (error) {
        advancedState.networkLoaded.portForwarding = false;
        syncAdvancedNetworkForms();
        container.innerHTML = featureUnavailable(
            "Port Forwarding",
            error.message
        );
        return false;
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
        advancedState.networkLoaded.dmz = true;
        syncAdvancedNetworkForms();
        return true;
    } catch (error) {
        advancedState.networkLoaded.dmz = false;
        syncAdvancedNetworkForms();
        container.innerHTML = featureUnavailable(
            "DMZ",
            error.message
        );
        return false;
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
    const feature = event.currentTarget?.dataset?.featureRead ||
        document.getElementById("firmwareFeatureSelect")?.value || "";
    if (!feature || !ontConnected) {
        showToast("Conecte-se e selecione uma funcionalidade.");
        return;
    }
    const button = document.getElementById("firmwareInspectButton");
    const output = document.getElementById("featureInspectorOutput");
    const catalog = advancedState.capabilities?.features || {};
    if (!Object.prototype.hasOwnProperty.call(catalog, feature)) {
        if (output) output.textContent = "Este recurso não consta do catálogo confirmado nesta sessão.";
        return;
    }
    if (button) {
        button.disabled = true;
        button.setAttribute("aria-busy", "true");
    }
    setBusy(true, "Consultando funcionalidade...");
    if (output) output.textContent = "Aguardando resposta do equipamento...";
    try {
        const data = await apiRequest(
            "/features/read?feature=" + encodeURIComponent(feature),
            {expected:"object"}
        );
        if (!globalThis.AccessManagerInspector) {
            throw new Error("O componente de inspeção não foi carregado.");
        }
        globalThis.AccessManagerInspector.render(feature, data, output);
    } catch (error) {
        if (output) {
            output.replaceChildren();
            const note = document.createElement("p");
            note.className = "am-inspector-alert";
            note.textContent = "Não foi possível confirmar a funcionalidade: " +
                normalizeApiErrorMessage(error);
            output.appendChild(note);
        }
    } finally {
        setBusy(false);
        if (button) {
            button.disabled = false;
            button.setAttribute("aria-busy", "false");
        }
    }
}

// History actions live in a separate presentation module. Keep these
// public function names to preserve all legacy event listener contracts.
async function backupConfiguration() {
    return window.AccessManagerHistory.backup();
}


// =========================================================
// HISTÓRICO / SNAPSHOT
// =========================================================

// History and snapshot share one sanitized timeline, not separate renderers.
async function captureSnapshot() {
    return window.AccessManagerHistory.snapshot();
}

async function loadHistory() {
    return window.AccessManagerHistory.load();
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
    setBusy(true, busyText);
    try {
        const result = await apiRequest(endpoint, {
            method: "POST", body: JSON.stringify(payload), expected:"object"
        });
        // Accepted != verified: the service annotates post-write readback.
        // A response without proof must never trigger a success notice.
        const outcome = result.audit_outcome ||
            (result.verified === true ? "verified" :
             result.uncertain || result.partial ? "uncertain" : "accepted");
        let refreshed = true;
        if (after) {
            try {
                const latest = await after();
                refreshed = latest !== false;
            } catch (_error) { refreshed = false; }
        }
        if (outcome === "verified") {
            showToast(successText);
        } else if (outcome === "failed") {
            showToast("O equipamento não confirmou a operação. Revise os dados e tente novamente.");
        } else if (outcome === "uncertain") {
            showToast("O equipamento pode ter aplicado parte da alteração. Consulte o estado atual antes de repetir.");
        } else {
            showToast("Solicitação recebida. A confirmação da alteração ainda está pendente.");
        }
        if (!refreshed) showToast(
            "Não foi possível atualizar o estado do equipamento; evite repetir a alteração sem conferir a configuração."
        );
        try { await loadHistory(); }
        catch (_error) { /* history must not change the actual write result */ }
    } catch (error) {
        showToast(error.message);
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
            <p>${escapeHtml(normalizeApiErrorMessage(message || "O firmware ou login não oferece este recurso."))}</p>
        </div>
    `;
}


// =========================================================
// HUAWEI • IPV4 FILTERING
// =========================================================

const huaweiIpv4FilterState = {
    rules: [],
    capability: null,
    loading: false
};

function syncHuaweiAdvancedMode() {
    const huawei = (
        ontConnected
        && currentVendor === "huawei"
    );
    const filterTab = document.getElementById(
        "advanced-tab-ipv4-filter"
    );
    filterTab?.classList.toggle(
        "hidden",
        !huawei
    );

    for (const id of [
        "advanced-tab-dhcp",
        "advanced-tab-nat"
    ]) {
        document.getElementById(id)?.classList.toggle(
            "hidden",
            huawei
        );
    }

    for (const id of [
        "refreshAdvancedNetworkButton",
        "multimodelProbeButton",
        "multimodelDiagnosticButton",
        "multimodelMeshButton",
        "backupConfigurationButton"
    ]) {
        document.getElementById(id)?.classList.toggle(
            "hidden",
            huawei
        );
    }

    if (huawei && filterTab) {
        queueMicrotask(() => {
            if (currentVendor === "huawei") {
                filterTab.click();
            }
        });
    }
}

function resetHuaweiIpv4FilterForm() {
    const form = document.getElementById(
        "huaweiIpv4FilterForm"
    );
    if (!form) return;

    form.reset();
    document.getElementById(
        "huaweiIpv4FilterDomain"
    ).value = "";
    document.getElementById(
        "huaweiIpv4FilterFormTitle"
    ).textContent = "Nova regra";
    document.getElementById(
        "huaweiIpv4FilterCancel"
    )?.classList.add("hidden");
    document.getElementById(
        "huaweiIpv4FilterProtocol"
    ).value = "TCP";
    syncHuaweiPortFields();
}

function syncHuaweiPortFields() {
    const protocol = String(
        document.getElementById(
            "huaweiIpv4FilterProtocol"
        )?.value || ""
    ).toUpperCase();

    const showTcp = (
        protocol === "TCP"
        || protocol.includes("TCP")
    );
    const showUdp = (
        protocol === "UDP"
        || protocol.includes("UDP")
    );

    document.querySelectorAll(
        ".huawei-ipv4-tcp-field"
    ).forEach(
        field => field.classList.toggle(
            "hidden",
            !showTcp
        )
    );
    document.querySelectorAll(
        ".huawei-ipv4-udp-field"
    ).forEach(
        field => field.classList.toggle(
            "hidden",
            !showUdp
        )
    );
}

function ensureSelectOption(
    select,
    value
) {
    if (!select || !value) return;
    const exists = Array.from(
        select.options
    ).some(
        option => option.value === value
    );
    if (!exists) {
        select.add(
            new Option(
                value,
                value
            )
        );
    }
}

function hydrateHuaweiFilterOptions(rules) {
    const protocol = document.getElementById(
        "huaweiIpv4FilterProtocol"
    );
    const direction = document.getElementById(
        "huaweiIpv4FilterDirection"
    );

    for (const rule of rules || []) {
        ensureSelectOption(
            protocol,
            rule.protocol
        );
        ensureSelectOption(
            direction,
            rule.direction
        );
    }
}

function huaweiRulePortSummary(rule) {
    const protocol = String(
        rule.protocol || ""
    ).toUpperCase();
    const parts = [];

    if (
        protocol.includes("TCP")
        && (
            rule.lan_tcp_port
            || rule.wan_tcp_port
        )
    ) {
        parts.push(
            "TCP "
            + (rule.lan_tcp_port || "—")
            + " → "
            + (rule.wan_tcp_port || "—")
        );
    }
    if (
        protocol.includes("UDP")
        && (
            rule.lan_udp_port
            || rule.wan_udp_port
        )
    ) {
        parts.push(
            "UDP "
            + (rule.lan_udp_port || "—")
            + " → "
            + (rule.wan_udp_port || "—")
        );
    }

    return parts.join(" · ") || "Sem portas";
}

function renderHuaweiIpv4Filters() {
    const list = document.getElementById(
        "huaweiIpv4FilterList"
    );
    const count = document.getElementById(
        "huaweiIpv4FilterCount"
    );
    const capabilityBadge = document.getElementById(
        "huaweiIpv4FilterCapability"
    );
    if (!list) return;

    const rules = huaweiIpv4FilterState.rules || [];
    if (count) {
        count.textContent = (
            rules.length
            + (rules.length === 1 ? " regra" : " regras")
        );
    }

    const capability = (
        huaweiIpv4FilterState.capability
        || {}
    );
    if (capabilityBadge) {
        capabilityBadge.textContent = capability.verified
            ? "CRUD validado"
            : (
                capability.read
                    ? "Leitura disponível"
                    : "Não confirmado"
            );
    }

    if (!rules.length) {
        list.innerHTML = (
            '<span class="muted">'
            + "Nenhuma regra IPv4 Filtering configurada."
            + "</span>"
        );
        return;
    }

    list.innerHTML = rules.map(
        (rule, index) => {
            const canUpdate = capability.update === true;
            const canDelete = capability.delete === true;
            return `
                <article class="capability-card huawei-ipv4-filter-rule"
                         data-huawei-filter-index="${index}">
                    <div class="capability-head">
                        <div>
                            <strong>${escapeHtml(rule.name || "Sem nome")}</strong>
                            <small>${escapeHtml(rule.domain || "")}</small>
                        </div>
                        <span class="badge">${escapeHtml(rule.protocol || "—")}</span>
                    </div>
                    <p>
                        <strong>Direção:</strong>
                        ${escapeHtml(rule.direction || "—")}
                    </p>
                    <p>
                        <strong>LAN:</strong>
                        ${escapeHtml(rule.lan_start_ip || "—")}
                        —
                        ${escapeHtml(rule.lan_end_ip || "—")}
                    </p>
                    <p>
                        <strong>WAN:</strong>
                        ${escapeHtml(rule.wan_start_ip || "—")}
                        —
                        ${escapeHtml(rule.wan_end_ip || "—")}
                    </p>
                    <p>
                        <strong>Portas:</strong>
                        ${escapeHtml(huaweiRulePortSummary(rule))}
                    </p>
                    <div class="advanced-actions with-top-space">
                        <button class="button ghost huawei-ipv4-filter-edit"
                                type="button"
                                data-index="${index}"
                                ${canUpdate ? "" : "disabled"}>
                            Editar
                        </button>
                        <button class="button danger huawei-ipv4-filter-delete"
                                type="button"
                                data-index="${index}"
                                ${canDelete ? "" : "disabled"}>
                            Excluir
                        </button>
                    </div>
                </article>
            `;
        }
    ).join("");

    list.querySelectorAll(
        ".huawei-ipv4-filter-edit"
    ).forEach(
        button => button.addEventListener(
            "click",
            () => editHuaweiIpv4Filter(
                Number(button.dataset.index)
            )
        )
    );
    list.querySelectorAll(
        ".huawei-ipv4-filter-delete"
    ).forEach(
        button => button.addEventListener(
            "click",
            () => deleteHuaweiIpv4Filter(
                Number(button.dataset.index)
            )
        )
    );
}

async function loadHuaweiIpv4Filters() {
    if (
        !ontConnected
        || currentVendor !== "huawei"
        || huaweiIpv4FilterState.loading
    ) {
        return;
    }

    huaweiIpv4FilterState.loading = true;
    const status = document.getElementById(
        "huaweiIpv4FilterStatus"
    );
    if (status) {
        status.innerHTML = (
            '<span class="muted">Consultando regras na ONT...</span>'
        );
    }

    try {
        const data = await apiRequest(
            "/huawei/ipv4-filters",
            { expected: "object" }
        );
        huaweiIpv4FilterState.rules = Array.isArray(
            data?.rules
        ) ? data.rules : [];
        huaweiIpv4FilterState.capability = (
            data?.capability || {}
        );
        hydrateHuaweiFilterOptions(
            huaweiIpv4FilterState.rules
        );
        renderHuaweiIpv4Filters();

        if (status) {
            status.textContent = (
                "Leitura concluída. "
                + huaweiIpv4FilterState.rules.length
                + " regra(s) encontrada(s)."
            );
        }

        const save = document.getElementById(
            "huaweiIpv4FilterSave"
        );
        if (save) {
            save.disabled = (
                huaweiIpv4FilterState.capability.create
                !== true
            );
        }
    } catch (error) {
        if (status) {
            status.textContent = error.message;
        }
        showToast(error.message);
        throw error;
    } finally {
        huaweiIpv4FilterState.loading = false;
    }
}

function collectHuaweiIpv4FilterPayload() {
    const value = id => String(
        document.getElementById(id)?.value || ""
    ).trim();

    const protocol = value(
        "huaweiIpv4FilterProtocol"
    );
    const payload = {
        name: value("huaweiIpv4FilterName"),
        protocol,
        direction: value("huaweiIpv4FilterDirection"),
        lan_start_ip: value("huaweiIpv4FilterLanStart"),
        lan_end_ip: value("huaweiIpv4FilterLanEnd"),
        wan_start_ip: value("huaweiIpv4FilterWanStart"),
        wan_end_ip: value("huaweiIpv4FilterWanEnd"),
        lan_tcp_port: value("huaweiIpv4FilterLanTcp"),
        lan_udp_port: value("huaweiIpv4FilterLanUdp"),
        wan_tcp_port: value("huaweiIpv4FilterWanTcp"),
        wan_udp_port: value("huaweiIpv4FilterWanUdp")
    };

    if (!protocol.toUpperCase().includes("TCP")) {
        payload.lan_tcp_port = "";
        payload.wan_tcp_port = "";
    }
    if (!protocol.toUpperCase().includes("UDP")) {
        payload.lan_udp_port = "";
        payload.wan_udp_port = "";
    }

    return payload;
}

async function saveHuaweiIpv4Filter(event) {
    event.preventDefault();
    if (
        currentVendor !== "huawei"
        || !ontConnected
    ) {
        showToast(
            "Conecte-se a uma ONT Huawei compatível."
        );
        return;
    }

    const domain = String(
        document.getElementById(
            "huaweiIpv4FilterDomain"
        )?.value || ""
    ).trim();
    const payload = collectHuaweiIpv4FilterPayload();
    const editing = Boolean(domain);
    const endpoint = editing
        ? "/huawei/ipv4-filters/update"
        : "/huawei/ipv4-filters/create";

    if (editing) {
        payload.instance_or_domain = domain;
    }

    setBusy(
        true,
        editing
            ? "Atualizando regra IPv4..."
            : "Criando regra IPv4..."
    );

    try {
        const result = await apiRequest(
            endpoint,
            {
                method: "POST",
                body: JSON.stringify(payload),
                expected: "object"
            }
        );
        if (result?.verified !== true) {
            throw new Error(
                result?.error
                || "A ONT não confirmou a alteração."
            );
        }
        resetHuaweiIpv4FilterForm();
        await loadHuaweiIpv4Filters();
        await loadHistory();
        showToast(
            editing
                ? "Regra IPv4 atualizada e confirmada."
                : "Regra IPv4 criada e confirmada."
        );
    } catch (error) {
        const status = document.getElementById(
            "huaweiIpv4FilterStatus"
        );
        if (status) {
            status.textContent = error.message;
        }
        showToast(error.message);
    } finally {
        setBusy(false);
    }
}

function editHuaweiIpv4Filter(index) {
    const rule = huaweiIpv4FilterState.rules[
        index
    ];
    if (!rule) return;

    const set = (id, value) => {
        const element = document.getElementById(id);
        if (element) {
            element.value = value ?? "";
        }
    };

    ensureSelectOption(
        document.getElementById(
            "huaweiIpv4FilterProtocol"
        ),
        rule.protocol
    );
    ensureSelectOption(
        document.getElementById(
            "huaweiIpv4FilterDirection"
        ),
        rule.direction
    );

    set("huaweiIpv4FilterDomain", rule.domain);
    set("huaweiIpv4FilterName", rule.name);
    set("huaweiIpv4FilterProtocol", rule.protocol);
    set("huaweiIpv4FilterDirection", rule.direction);
    set("huaweiIpv4FilterLanStart", rule.lan_start_ip);
    set("huaweiIpv4FilterLanEnd", rule.lan_end_ip);
    set("huaweiIpv4FilterWanStart", rule.wan_start_ip);
    set("huaweiIpv4FilterWanEnd", rule.wan_end_ip);
    set("huaweiIpv4FilterLanTcp", rule.lan_tcp_port);
    set("huaweiIpv4FilterLanUdp", rule.lan_udp_port);
    set("huaweiIpv4FilterWanTcp", rule.wan_tcp_port);
    set("huaweiIpv4FilterWanUdp", rule.wan_udp_port);

    document.getElementById(
        "huaweiIpv4FilterFormTitle"
    ).textContent = "Editar regra";
    document.getElementById(
        "huaweiIpv4FilterCancel"
    )?.classList.remove("hidden");
    syncHuaweiPortFields();
    document.getElementById(
        "huaweiIpv4FilterForm"
    )?.scrollIntoView({
        behavior: "smooth",
        block: "start"
    });
}

async function deleteHuaweiIpv4Filter(index) {
    const rule = huaweiIpv4FilterState.rules[
        index
    ];
    if (!rule) return;

    if (!window.confirm(
        "Excluir a regra "
        + (rule.name || rule.domain)
        + "?"
    )) {
        return;
    }

    setBusy(
        true,
        "Excluindo regra IPv4..."
    );
    try {
        const result = await apiRequest(
            "/huawei/ipv4-filters/delete",
            {
                method: "POST",
                body: JSON.stringify({
                    instance_or_domain: rule.domain
                }),
                expected: "object"
            }
        );
        if (result?.verified !== true) {
            throw new Error(
                result?.error
                || "A ONT não confirmou a exclusão."
            );
        }
        resetHuaweiIpv4FilterForm();
        await loadHuaweiIpv4Filters();
        await loadHistory();
        showToast(
            "Regra IPv4 excluída e confirmada."
        );
    } catch (error) {
        const status = document.getElementById(
            "huaweiIpv4FilterStatus"
        );
        if (status) {
            status.textContent = error.message;
        }
        showToast(error.message);
    } finally {
        setBusy(false);
    }
}

// =========================================================
// LOAD / EVENTS
// =========================================================

let operationsLoadPromise = null;

function loadOperationsConsole() {
    if (!ontConnected) return Promise.resolve();
    if (operationsLoadPromise) return operationsLoadPromise;
    operationsLoadPromise = loadOperationsConsoleInternal()
        .finally(() => { operationsLoadPromise = null; });
    return operationsLoadPromise;
}

async function loadOperationsConsoleInternal() {
    if (!ontConnected) return;

    syncHuaweiAdvancedMode();
    if (currentVendor === "huawei") {
        try {
            await loadCapabilityCatalog();
        } catch (error) {
            console.warn(
                "Capabilities Huawei:",
                error
            );
        }
        try {
            await loadHuaweiIpv4Filters();
        } catch (error) {
            console.warn(
                "IPv4 Filtering Huawei:",
                error
            );
        }
        try {
            await loadHistory();
        } catch (error) {
            console.warn(
                "Histórico local:",
                error
            );
        }
        advancedState.loaded = true;
        return;
    }

    // Bootstrap e catálogo nativo são exclusivamente locais e devem
    // aparecer ANTES das sondagens menuView/menuData, que podem levar
    // dezenas de segundos. Nenhuma GET pesada deve esconder o modelo.
    let bootstrap = null;
    try {
        bootstrap = await loadMultimodelCatalog();
    } catch (error) {
        console.warn("Bootstrap de descoberta:", error);
        const status = document.getElementById("trackerDiscoveryStatus");
        const grid = document.getElementById("trackerCapabilityGrid");
        if (status) status.textContent =
            "A identificação está indisponível: " + error.message;
        if (grid) grid.textContent =
            "Não foi possível consultar o catálogo. Tente Detectar modelo novamente.";
    }

    if (bootstrap?.native_diagnostics_available === true) {
        try {
            const native = await loadCapabilityCatalog();
            const grid = document.getElementById("trackerCapabilityGrid");
            // Quando o firmware não consta dos perfis documentados,
            // exibir o catálogo nativo sem declarar GETs não executados
            // como confirmados.
            if (grid && !grid.querySelector(".capability-card")) {
                renderTrackerDiscovery({
                    model: trackerDetectedModel || bootstrap.model,
                    family: "thinklua",
                    candidate_features: Object.entries(native.features).map(
                        ([feature, spec]) => ({
                            feature, label: spec.label || feature,
                            status: "not_tested"
                        })
                    ),
                    reason: "Modelo autenticado. Recursos disponíveis para verificação."
                });
            }
        } catch (error) {
            const grid = document.getElementById("capabilityGrid");
            if (grid) grid.textContent =
                "Não foi possível carregar os menus nativos: " + error.message;
        }
    }

    // Não iniciar sondagem nem coleta DHCP/NAT implicitamente:
    // esses GETs seguram o RLock da única sessão e atrasavam TODOS os botões.
    // O modelo vem do bootstrap local; os demais GETs são por ação do operador.
    const optionalLoaders = [loadHistory];

    // Rodar sequencialmente no equipamento, mas não atrasar a UI.
    // A falha de um módulo não interrompe os demais.
    for (const loader of optionalLoaders) {
        try {
            await loader();
        } catch (error) {
            console.warn("Módulo opcional:", loader.name, error);
            if (loader === loadCapabilityCatalog) {
                const grid = document.getElementById("capabilityGrid");
                if (grid) grid.textContent =
                    "Inspeção nativa indisponível: " + error.message;
            }
            if (loader === loadHistory) {
                const history = document.getElementById("historyOutput");
                if (history) history.textContent =
                    "Histórico não carregado: " + error.message;
            }
        }
    }
    advancedState.loaded = true;
}


async function loadAdvancedNetworkManually() {
    if (!ontConnected) {
        showToast("Conecte-se à ONT para consultar DHCP e NAT.");
        return;
    }
    if (advancedNetworkBusy || nativeProbeBusy || trackerProbeBusy ||
        modelDiagnosticRunning || meshProbeBusy) {
        showToast("Aguarde a leitura avançada atual.");
        return;
    }
    advancedNetworkBusy = true;
    const button = document.getElementById("refreshAdvancedNetworkButton");
    if (button) button.disabled = true;
    setBusy(true, "Consultando DHCP / LAN...");
    try {
        // A consulta de NAT é independente: erro em uma etapa não oculta a outra.
        const failures = [];
        for (const [name, loader] of [["DHCP/LAN", loadDhcpOperations], ["NAT", loadNatOperations]]) {
            setBusy(true, `Consultando ${name}...`);
            try {
                if ((await loader()) === false) failures.push(name);
            } catch (error) {
                failures.push(name);
                console.warn("Leitura avançada indisponível:", name, error?.name);
            }
        }
        showToast(failures.length
            ? "Leitura parcial. Indisponível: " + failures.join(", ")
            : "Informações DHCP e NAT atualizadas.");
    } finally {
        advancedNetworkBusy = false;
        if (button) button.disabled = false;
        setBusy(false);
    }
}

window.startQuickProbe = async function startQuickProbe() {
    if (!ontConnected) {
        showToast("Conecte-se ao equipamento antes de detectar recursos.");
        return;
    }
    try {
        // Não aguardar DHCP/NAT/histórico para executar o botão Probe.
        // O botão funciona mesmo quando outro módulo está demorando.
        await loadMultimodelCatalog();
        // A seleção entre GET nativo e catálogo familiar cabe ao bootstrap.
        // O estado de POST (routerWriteEnabled) é irrelevante nesta tela.
        await probeCapabilities();
    } catch (error) {
        console.error("Falha no atalho Probe:", error);
        const status = document.getElementById("trackerDiscoveryStatus");
        if (status) status.textContent =
            "Falha ao executar Probe: " + error.message;
        showToast(error.message);
    }
};


function initAdvancedOperations() {
    syncAdvancedNetworkForms();
    const info = document.getElementById("dhcpLeaseList");
    if (info) info.textContent = "Clique em Carregar DHCP / NAT para consultar o estado atual.";
    document.addEventListener("zte:page-open", event => {
        if (event.detail?.pageName === "advanced" && ontConnected) {
            syncHuaweiAdvancedMode();
            void loadOperationsConsole();
        }
    });

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
            "multimodelDiagnosticButton"
        )
        ?.addEventListener(
            "click",
            runMultimodelDiagnostic
        );

    document
        .getElementById(
            "multimodelMeshButton"
        )
        ?.addEventListener(
            "click",
            showMultimodelMesh
        );

    document
        .getElementById(
            "multimodelProbeButton"
        )
        ?.addEventListener(
            "click",
            detectConnectedModel
        );

    document.getElementById("refreshAdvancedNetworkButton")
        ?.addEventListener("click", loadAdvancedNetworkManually);

    document.getElementById("huaweiIpv4FilterForm")
        ?.addEventListener("submit", saveHuaweiIpv4Filter);
    document.getElementById("huaweiIpv4FilterRefresh")
        ?.addEventListener("click", loadHuaweiIpv4Filters);
    document.getElementById("huaweiIpv4FilterCancel")
        ?.addEventListener("click", resetHuaweiIpv4FilterForm);
    document.getElementById("huaweiIpv4FilterProtocol")
        ?.addEventListener("change", syncHuaweiPortFields);
    document.addEventListener(
        "huawei:ipv4-filter-refresh",
        () => {
            if (
                ontConnected
                && currentVendor === "huawei"
            ) {
                void loadHuaweiIpv4Filters();
            }
        }
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

    const featureSelect = document.getElementById("firmwareFeatureSelect");
    const inspectButton = document.getElementById("firmwareInspectButton");
    featureSelect?.addEventListener("change", () => {
        if (inspectButton) {
            inspectButton.disabled = !featureSelect.value;
            inspectButton.dataset.featureRead = featureSelect.value;
        }
    });
    inspectButton?.addEventListener("click", readFirmwareFeature);
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

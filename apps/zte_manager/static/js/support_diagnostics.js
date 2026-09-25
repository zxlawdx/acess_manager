// =========================================================
// ZTE AUTOMATIC • DIAGNÓSTICO DE ATENDIMENTO
// Motor visual separado do app.js/advanced.js para não duplicar renderers.
// =========================================================

const supportDiagnosticState = {
    lastDiagnostic: null,
    dashboardDiagnostic: null,
    running: false,
    lastConfig: null
};


pageInfo.supportDiagnostic = {
    title: "Diagnóstico automático",
    subtitle: "Localize gargalos, analise Wi-Fi e gere o atendimento sem digitação manual."
};


function supportEscape(value) {
    const node = document.createElement(
        "div"
    );

    node.textContent = (
        value === undefined
        || value === null
    )
        ? ""
        : String(value);

    return node.innerHTML;
}


function supportSeverityLabel(severity) {
    return {
        critical: "Crítico",
        warning: "Atenção",
        ok: "Normal",
        info: "Informação"
    }[severity] || severity || "Info";
}


function supportStatusClass(status) {
    return [
        "ok",
        "warning",
        "critical",
        "info"
    ].includes(status)
        ? status
        : "info";
}


function diagnosticPayload({
    full = true
} = {}) {
    const mode = document.getElementById(
        "supportDiagnosticMode"
    )?.value || "general";

    const selectedClient = document.getElementById(
        "supportAffectedClient"
    )?.value || "";

    const [
        affectedType,
        affectedValue
    ] = selectedClient.split(
        "|",
        2
    );

    const expectedDownload = Number(
        document.getElementById(
            "supportExpectedDownload"
        )?.value || 0
    );

    const expectedUpload = Number(
        document.getElementById(
            "supportExpectedUpload"
        )?.value || 0
    );

    const speedtestProvider = document.getElementById(
        "supportSpeedtestPreset"
    )?.value || "native_auto";

    const speedtestBaseUrl = [
        "auto",
        "librespeed"
    ].includes(
        speedtestProvider
    )
        ? (
            document.getElementById(
                "supportSpeedtestBaseUrl"
            )?.value.trim()
            || null
        )
        : null;

    return {
        mode,
        affected_mac: (
            affectedType === "mac"
                ? affectedValue
                : null
        ),
        affected_ip: (
            affectedType === "ip"
                ? affectedValue
                : null
        ),
        ping_host: (
            document.getElementById(
                "supportPingHost"
            )?.value.trim()
            || "1.1.1.1"
        ),
        dns_host: (
            document.getElementById(
                "supportDnsHost"
            )?.value.trim()
            || "cloudflare.com"
        ),
        include_traceroute: (
            full
            && Boolean(
                document.getElementById(
                    "supportIncludeTraceroute"
                )?.checked
            )
        ),
        include_speedtest: (
            full
            && Boolean(
                document.getElementById(
                    "supportIncludeSpeedtest"
                )?.checked
            )
        ),
        allow_speedtest_fallback: Boolean(
            document.getElementById(
                "supportAllowSpeedFallback"
            )?.checked ?? true
        ),
        speedtest_provider: speedtestProvider,
        speedtest_base_url: speedtestBaseUrl,
        auto_optimize_wifi: (
            full
            && Boolean(
                document.getElementById(
                    "supportAutoOptimizeWifi"
                )?.checked
            )
        ),
        expected_download_mbps: (
            expectedDownload > 0
                ? expectedDownload
                : null
        ),
        expected_upload_mbps: (
            expectedUpload > 0
                ? expectedUpload
                : null
        ),
        expected_lan_mbps: 1000,
        optical_rx_min: -27,
        optical_rx_max: -8,
        wifi_rssi_warning: -70,
        wifi_rssi_bad: -80,
        ping_warning_ms: 80
    };
}


async function runSupportDiagnostic({
    full = true,
    dashboard = false
} = {}) {
    if (
        !ontConnected
        || supportDiagnosticState.running
    ) {
        return;
    }

    if (!routerWriteEnabled) {
        // Diagnóstico por modelo permanece NA aba Diagnóstico Automático.
        // Nunca chamar o motor legado (ping/POST) num firmware experimental.
        await runSelectedFirmwareDiagnostic();
        return;
    }

    supportDiagnosticState.running = true;

    const payload = dashboard
        ? {
            mode: "general",
            ping_host: "1.1.1.1",
            dns_host: "cloudflare.com",
            include_traceroute: false,
            include_speedtest: false,
            allow_speedtest_fallback: false,
            auto_optimize_wifi: false,
            expected_lan_mbps: 1000,
            optical_rx_min: -27,
            optical_rx_max: -8,
            wifi_rssi_warning: -70,
            wifi_rssi_bad: -80,
            ping_warning_ms: 80
        }
        : diagnosticPayload({
            full
        });

    if (!dashboard) {
        supportDiagnosticState.lastConfig = {
            ...payload
        };

        setBusy(
            true,
            payload.include_speedtest
                ? "Executando diagnóstico completo e Speed Test..."
                : "Executando diagnóstico completo..."
        );

        const badge = document.getElementById(
            "supportDiagnosticBadge"
        );

        if (badge) {
            badge.className = "badge";
            badge.textContent = "Executando";
        }
    }

    try {
        const result = await apiRequest(
            "/diagnostics/support",
            {
                method: "POST",
                body: JSON.stringify(
                    payload
                )
            }
        );

        if (dashboard) {
            supportDiagnosticState.dashboardDiagnostic = result;
            renderDashboardHealth(
                result
            );

            seedAffectedClients(
                result
            );
        } else {
            supportDiagnosticState.lastDiagnostic = result;

            renderSupportDiagnostic(
                result
            );

            seedAffectedClients(
                result
            );

            const badge = document.getElementById(
                "supportDiagnosticBadge"
            );

            if (badge) {
                badge.className = (
                    "badge "
                    + supportStatusClass(
                        finalDiagnosticResult(
                            result
                        ).status
                    )
                );

                badge.textContent = supportSeverityLabel(
                    finalDiagnosticResult(
                        result
                    ).status
                );
            }

            showToast(
                "Diagnóstico automático concluído."
            );
        }

        return result;

    } catch (error) {
        if (dashboard) {
            renderDashboardHealthError(
                error
            );
        } else {
            showToast(
                error.message
            );

            const output = document.getElementById(
                "supportDiagnosticOutput"
            );

            if (output) {
                output.innerHTML = `
                    <div class="support-empty critical">
                        <strong>Falha no diagnóstico</strong>
                        <span>${supportEscape(error.message)}</span>
                    </div>
                `;
            }
        }
    } finally {
        supportDiagnosticState.running = false;

        if (!dashboard) {
            setBusy(
                false
            );
        }
    }
}


function finalDiagnosticResult(result) {
    return (
        result?.post_validation
        || result
        || {}
    );
}


function renderDashboardHealth(result) {
    const container = document.getElementById(
        "dashboardHealthResult"
    );

    const badge = document.getElementById(
        "dashboardHealthBadge"
    );

    if (
        !container
        || !badge
    ) {
        return;
    }

    const finalResult = finalDiagnosticResult(
        result
    );

    const status = finalResult.status || "info";

    badge.className = (
        "badge "
        + supportStatusClass(
            status
        )
    );

    badge.textContent = supportSeverityLabel(
        status
    );

    const findings = (
        finalResult.findings
        || []
    );

    const relevant = [
        ...findings.filter(
            item => [
                "critical",
                "warning"
            ].includes(
                item.severity
            )
        ),
        ...findings.filter(
            item => item.severity === "ok"
        )
    ].slice(
        0,
        5
    );

    container.innerHTML = relevant.length
        ? relevant.map(
            finding => `
                <div class="dashboard-health-line ${supportStatusClass(finding.severity)}">
                    <span class="health-dot"></span>
                    <span>${supportEscape(finding.message)}</span>
                </div>
            `
        ).join("")
        : `
            <div class="dashboard-health-line info">
                <span class="health-dot"></span>
                <span>Triagem concluída sem resultado resumível.</span>
            </div>
        `;
}


function renderDashboardHealthError(error) {
    const container = document.getElementById(
        "dashboardHealthResult"
    );

    const badge = document.getElementById(
        "dashboardHealthBadge"
    );

    if (badge) {
        badge.className = "badge warning";
        badge.textContent = "Parcial";
    }

    if (container) {
        container.innerHTML = `
            <div class="dashboard-health-line warning">
                <span class="health-dot"></span>
                <span>Triagem automática parcial: ${supportEscape(error.message)}</span>
            </div>
        `;
    }
}


function seedAffectedClients(result) {
    const select = document.getElementById(
        "supportAffectedClient"
    );

    if (!select) {
        return;
    }

    const previous = select.value;

    const finalResult = finalDiagnosticResult(
        result
    );

    const sections = (
        finalResult.sections
        || {}
    );

    const clients = [
        ...(
            sections.wifi_clients
            || []
        ).map(
            item => ({
                ...item,
                type: "Wi-Fi"
            })
        ),
        ...(
            sections.lan_clients
            || []
        ).map(
            item => ({
                ...item,
                type: "Ethernet"
            })
        )
    ];

    select.innerHTML = `
        <option value="">
            Todos / detectar automaticamente
        </option>
        ${clients.map(
            client => {
                const key = client.mac
                    ? `mac|${client.mac}`
                    : `ip|${client.ip || ""}`;

                const title = [
                    client.hostname || "Dispositivo",
                    client.type,
                    client.ip,
                    client.ssid,
                    client.rssi
                        ? `${client.rssi} dBm`
                        : null
                ].filter(Boolean).join(" • ");

                return `
                    <option value="${supportEscape(key)}">
                        ${supportEscape(title)}
                    </option>
                `;
            }
        ).join("")}
    `;

    if (
        previous
        && [
            ...select.options
        ].some(
            option => option.value === previous
        )
    ) {
        select.value = previous;
    }
}


function renderSupportDiagnostic(result) {
    const output = document.getElementById(
        "supportDiagnosticOutput"
    );

    if (!output) {
        return;
    }

    const finalResult = finalDiagnosticResult(
        result
    );

    output.innerHTML = `
        ${renderDiagnosticSummary(result, finalResult)}
        ${renderAffectedClient(finalResult)}
        ${renderFindings(finalResult)}
        ${renderWifiEnvironment(finalResult)}
        ${renderSpeedTest(finalResult)}
        ${renderDiagnosticErrors(finalResult)}
    `;

    bindRecommendationActions(
        output
    );

    const reportActions = document.getElementById(
        "supportReportActions"
    );

    if (reportActions) {
        reportActions.classList.remove(
            "hidden"
        );
    }
}


function renderDiagnosticSummary(original, result) {
    const remediations = (
        original.remediations
        || []
    );

    return `
        <article class="support-result-card support-summary ${supportStatusClass(result.status)}">
            <div>
                <span class="section-kicker">RESULTADO FINAL</span>
                <h3>${supportEscape(supportSeverityLabel(result.status))}</h3>
                <p>${supportEscape(result.summary || "Diagnóstico concluído.")}</p>
            </div>
            <div class="support-summary-metrics">
                <div>
                    <strong>${(result.findings || []).length}</strong>
                    <span>conclusões</span>
                </div>
                <div>
                    <strong>${(result.recommendations || []).length}</strong>
                    <span>recomendações</span>
                </div>
                <div>
                    <strong>${remediations.length}</strong>
                    <span>ajustes auto</span>
                </div>
            </div>
        </article>
    `;
}


function renderAffectedClient(result) {
    const client = result.affected_client;

    if (!client) {
        return "";
    }

    const band = inferClientBand(
        client
    );

    return `
        <article class="support-result-card">
            <div class="support-card-head">
                <div>
                    <span class="section-kicker">DISPOSITIVO AFETADO</span>
                    <h3>${supportEscape(client.hostname || client.mac || "Cliente")}</h3>
                </div>
                <span class="badge">${supportEscape(client.kind || "cliente")}</span>
            </div>
            <div class="support-metric-grid">
                ${metric("IP", client.ip)}
                ${metric("MAC", client.mac)}
                ${metric("SSID", client.ssid)}
                ${metric("Banda", band)}
                ${metric("RSSI", client.rssi ? `${client.rssi} dBm` : null)}
                ${metric("RX PHY", client.rx_rate)}
                ${metric("TX PHY", client.tx_rate)}
                ${metric("Modo", client.modo)}
            </div>
        </article>
    `;
}


function inferClientBand(client) {
    const ap = String(
        client.ap
        || client.interface
        || ""
    ).toUpperCase();

    if (
        ap.includes("AP1")
        || ap.includes("RD1")
        || ap.includes("2.4")
    ) {
        return "2.4 GHz";
    }

    if (
        ap.includes("AP5")
        || ap.includes("RD2")
        || ap.includes("5G")
    ) {
        return "5 GHz";
    }

    return "-";
}


function metric(label, value) {
    return `
        <div class="support-metric">
            <span>${supportEscape(label)}</span>
            <strong>${supportEscape(value ?? "-")}</strong>
        </div>
    `;
}


function renderFindings(result) {
    const findings = result.findings || [];

    if (!findings.length) {
        return "";
    }

    return `
        <article class="support-result-card">
            <div class="support-card-head">
                <div>
                    <span class="section-kicker">DIAGNÓSTICO</span>
                    <h3>Conclusões e ações</h3>
                </div>
            </div>
            <div class="finding-list">
                ${findings.map(
                    (finding, index) => {
                        const recommendation = finding.recommendation;
                        const action = recommendation?.action;

                        let actionButton = "";

                        if (
                            action?.type === "wifi_channel"
                            || action?.type === "wifi_auto_channel"
                        ) {
                            actionButton = `
                                <button
                                    class="button ghost compact"
                                    type="button"
                                    data-support-action="${supportEscape(action.type)}"
                                    data-band="${supportEscape(action.band || "")}"
                                    data-channel="${supportEscape(action.channel ?? "")}"
                                >
                                    Aplicar recomendado
                                </button>
                            `;
                        } else if (
                            action?.type === "inspect_band_steering"
                        ) {
                            actionButton = `
                                <button class="button ghost compact" type="button" data-jump="wifi">
                                    Ver Band Steering
                                </button>
                            `;
                        }

                        return `
                            <div class="finding-item ${supportStatusClass(finding.severity)}">
                                <span class="finding-index">${String(index + 1).padStart(2, "0")}</span>
                                <div class="finding-copy">
                                    <div class="finding-title-row">
                                        <strong>${supportEscape(supportSeverityLabel(finding.severity))}</strong>
                                        <span class="mono">${supportEscape(finding.code)}</span>
                                    </div>
                                    <p>${supportEscape(finding.message)}</p>
                                    ${recommendation?.title
                                        ? `<small>Recomendação: ${supportEscape(recommendation.title)}</small>`
                                        : ""}
                                </div>
                                ${actionButton}
                            </div>
                        `;
                    }
                ).join("")}
            </div>
        </article>
    `;
}


function renderWifiEnvironment(result) {
    const environment = result.sections?.wifi_environment;
    const bands = environment?.bands || {};

    if (!Object.keys(bands).length) {
        return "";
    }

    return `
        <article class="support-result-card">
            <div class="support-card-head">
                <div>
                    <span class="section-kicker">RF ENVIRONMENT</span>
                    <h3>Interferência e canais vizinhos</h3>
                </div>
            </div>
            <div class="wifi-environment-grid">
                ${Object.entries(bands).map(
                    ([band, data]) => renderWifiBandEnvironment(
                        band,
                        data
                    )
                ).join("")}
            </div>
        </article>
    `;
}


function renderWifiBandEnvironment(band, data) {
    const analysis = data.analysis || {};
    const networks = data.networks || [];
    const scoreEntries = Object.entries(
        analysis.scores || {}
    ).sort(
        (a, b) => Number(a[0]) - Number(b[0])
    );

    return `
        <div class="wifi-environment-band">
            <div class="wifi-band-heading">
                <div>
                    <strong>${supportEscape(band)}</strong>
                    <span>
                        atual ${supportEscape(analysis.current_channel ?? (analysis.auto_channel ? "Auto" : "-"))}
                        • melhor ${supportEscape(analysis.best_channel ?? "-")}
                    </span>
                </div>
                <span class="badge">${networks.length} APs</span>
            </div>

            <div class="channel-score-strip">
                ${scoreEntries.map(
                    ([channel, score]) => `
                        <div class="channel-score ${Number(channel) === Number(analysis.best_channel) ? "best" : ""}">
                            <span>CH ${supportEscape(channel)}</span>
                            <strong>${Number(score).toFixed(0)}</strong>
                        </div>
                    `
                ).join("")}
            </div>

            ${data.error
                ? `<p class="muted">Scan indisponível: ${supportEscape(data.error)}</p>`
                : ""}

            <div class="neighbor-table-wrap">
                <table class="neighbor-table">
                    <thead>
                        <tr>
                            <th>SSID</th>
                            <th>Canal</th>
                            <th>Sinal</th>
                            <th>Ruído</th>
                        </tr>
                    </thead>
                    <tbody>
                        ${networks.length
                            ? networks.slice(0, 20).map(
                                network => `
                                    <tr>
                                        <td>${supportEscape(network.ssid || "(oculto)")}</td>
                                        <td>${supportEscape(network.channel ?? "-")}</td>
                                        <td>${supportEscape(network.signal ?? network.signal_raw ?? "-")}</td>
                                        <td>${supportEscape(network.noise ?? network.noise_raw ?? "-")}</td>
                                    </tr>
                                `
                            ).join("")
                            : `
                                <tr>
                                    <td colspan="4" class="muted">Nenhuma rede vizinha retornada.</td>
                                </tr>
                            `
                        }
                    </tbody>
                </table>
            </div>
        </div>
    `;
}


function renderSpeedTest(result) {
    const speed = result.sections?.speedtest;

    if (!speed) {
        return "";
    }

    const providerLabels = {
        zte_native: "ONT ZTE",
        cloudflare: "Cloudflare",
        "fast.com": "FAST.com / Netflix",
        "speedtest.net": "Speedtest.net",
        librespeed: "LibreSpeed"
    };

    const source = speed.source === "ont_native"
        ? "Executado pela própria ONT"
        : "Executado pelo computador do atendente";

    const providerLabel = (
        providerLabels[speed.provider]
        || speed.provider
        || "Speed Test"
    );

    return `
        <article class="support-result-card speed-result-card">
            <div class="support-card-head">
                <div>
                    <span class="section-kicker">THROUGHPUT</span>
                    <h3>Teste de velocidade</h3>
                </div>
                <span class="badge ${speed.source === "ont_native" ? "ok" : "warning"}">
                    ${supportEscape(speed.source || "speedtest")}
                </span>
            </div>

            <div class="speed-hero-grid">
                <div>
                    <span>DOWNLOAD</span>
                    <strong>${supportEscape(formatNumber(speed.download_mbps))}</strong>
                    <small>Mbps</small>
                </div>
                <div>
                    <span>UPLOAD</span>
                    <strong>${supportEscape(formatNumber(speed.upload_mbps))}</strong>
                    <small>Mbps</small>
                </div>
                <div>
                    <span>LATÊNCIA</span>
                    <strong>${supportEscape(formatNumber(speed.latency_ms))}</strong>
                    <small>ms</small>
                </div>
                <div>
                    <span>JITTER</span>
                    <strong>${supportEscape(formatNumber(speed.jitter_ms))}</strong>
                    <small>ms</small>
                </div>
            </div>

            <p class="muted with-top-space">
                ${supportEscape(source)}
                • ${supportEscape(providerLabel)}
                ${speed.server?.name ? ` • ${supportEscape(speed.server.name)}` : ""}
            </p>

            ${(speed.attempts || []).length
                ? `
                    <details class="support-details">
                        <summary>Fallbacks utilizados</summary>
                        <pre>${supportEscape(JSON.stringify(speed.attempts, null, 2))}</pre>
                    </details>
                `
                : ""}
        </article>
    `;
}


function formatNumber(value) {
    const number = Number(
        value
    );

    return Number.isFinite(
        number
    )
        ? number.toFixed(1)
        : "-";
}


function renderDiagnosticErrors(result) {
    const entries = Object.entries(
        result.errors || {}
    );

    if (!entries.length) {
        return "";
    }

    return `
        <details class="support-result-card support-details">
            <summary>
                ${entries.length} coleta(s) indisponível(is) neste firmware/login
            </summary>
            <div class="error-list">
                ${entries.map(
                    ([name, message]) => `
                        <div>
                            <strong>${supportEscape(name)}</strong>
                            <span>${supportEscape(message)}</span>
                        </div>
                    `
                ).join("")}
            </div>
        </details>
    `;
}


function bindRecommendationActions(root) {
    root.querySelectorAll(
        "[data-support-action]"
    ).forEach(
        button => {
            button.addEventListener(
                "click",
                () => applySupportRecommendation(
                    button
                )
            );
        }
    );
}


async function applySupportRecommendation(button) {
    const action = button.dataset.supportAction;
    const band = button.dataset.band;
    const channel = button.dataset.channel;

    button.disabled = true;

    setBusy(
        true,
        "Aplicando e auditando a recomendação..."
    );

    try {
        await apiRequest(
            "/diagnostics/remediate",
            {
                method: "POST",
                body: JSON.stringify({
                    action,
                    band,
                    channel: (
                        channel
                            ? Number(channel)
                            : null
                    )
                })
            }
        );

        showToast(
            "Ajuste aplicado. Reexecutando a validação..."
        );

        const config = {
            ...(
                supportDiagnosticState.lastConfig
                || diagnosticPayload()
            ),
            include_speedtest: false,
            include_traceroute: false,
            auto_optimize_wifi: false
        };

        const result = await apiRequest(
            "/diagnostics/support",
            {
                method: "POST",
                body: JSON.stringify(
                    config
                )
            }
        );

        supportDiagnosticState.lastDiagnostic = result;
        supportDiagnosticState.lastConfig = config;

        renderSupportDiagnostic(
            result
        );

    } catch (error) {
        showToast(
            error.message
        );
    } finally {
        setBusy(
            false
        );

        button.disabled = false;
    }
}


async function generateSupportAttendance() {
    const diagnosticId = (
        supportDiagnosticState.lastDiagnostic?.history_id
        || null
    );

    if (!diagnosticId) {
        showToast(
            "Execute o diagnóstico completo primeiro."
        );

        return;
    }

    setBusy(
        true,
        "Gerando resumo do atendimento..."
    );

    try {
        const report = await apiRequest(
            "/diagnostics/attendance",
            {
                method: "POST",
                body: JSON.stringify({
                    diagnostic_id: diagnosticId
                })
            }
        );

        const textarea = document.getElementById(
            "supportAttendanceText"
        );

        textarea.value = report.text || "";

        document.getElementById(
            "supportAttendancePanel"
        )?.classList.remove(
            "hidden"
        );

        textarea.scrollIntoView({
            behavior: "smooth",
            block: "nearest"
        });

        showToast(
            "Atendimento gerado com o histórico da sessão."
        );

    } catch (error) {
        showToast(
            error.message
        );
    } finally {
        setBusy(
            false
        );
    }
}


async function copySupportAttendance() {
    const textarea = document.getElementById("supportAttendanceText");
    const text = textarea?.value || "";

    if (!text) {
        showToast("Gere o atendimento primeiro.");
        return;
    }

    try {
        // O botão no Windows NÃO chama as APIs do QtWebEngine: alguns builds
        // encerram o processo ao acessar navigator.clipboard/execCommand.
        if (/Windows/i.test(navigator.userAgent)) {
            await apiRequest("/desktop/clipboard", {
                method: "POST",
                body: JSON.stringify({ text })
            });
        } else if (navigator.clipboard && window.isSecureContext) {
            await navigator.clipboard.writeText(text);
        } else {
            textarea.focus();
            textarea.select();
            if (!document.execCommand("copy")) {
                throw new Error("Clipboard não disponível.");
            }
        }

        showToast("Atendimento copiado.");
    } catch (error) {
        // Evita crash/propagação de falha no botão; preserva a seleção
        // para cópia manual caso o desktop esteja sem permissão.
        textarea.focus();
        textarea.select();
        showToast(
            `Cópia automática indisponível: ${error.message}. Use Ctrl+C.`
        );
    }
}

async function runStandaloneSpeedTest() {
    setBusy(
        true,
        "Executando Speed Test..."
    );

    try {
        const result = await apiRequest(
            "/diagnostics/speedtest",
            {
                method: "POST",
                body: JSON.stringify({
                    allow_fallback: Boolean(
                        document.getElementById(
                            "supportAllowSpeedFallback"
                        )?.checked ?? true
                    ),
                    provider: (
                        document.getElementById(
                            "supportSpeedtestPreset"
                        )?.value
                        || "native_auto"
                    ),
                    fallback_base_url: (
                        [
                            "auto",
                            "librespeed"
                        ].includes(
                            document.getElementById(
                                "supportSpeedtestPreset"
                            )?.value
                        )
                            ? (
                                document.getElementById(
                                    "supportSpeedtestBaseUrl"
                                )?.value.trim()
                                || null
                            )
                            : null
                    )
                })
            }
        );

        const output = document.getElementById(
            "supportStandaloneSpeed"
        );

        if (output) {
            output.innerHTML = renderSpeedTest({
                sections: {
                    speedtest: result
                }
            });
        }

        showToast(
            "Speed Test concluído."
        );

    } catch (error) {
        showToast(
            error.message
        );
    } finally {
        setBusy(
            false
        );
    }
}


window.loadDashboardSupportHealth = async function () {
    const container = document.getElementById(
        "dashboardHealthResult"
    );

    if (!container || !ontConnected) {
        return;
    }

    container.innerHTML = `
        <div class="dashboard-health-line info">
            <span class="health-dot"></span>
            <span>Executando triagem de GPON, WAN, DNS, LAN e Wi-Fi...</span>
        </div>
    `;

    await runSupportDiagnostic({
        full: false,
        dashboard: true
    });
};


// O atalho do topo faz uma primeira triagem somente leitura.
window.runQuickSupportDiagnostic = async function runQuickSupportDiagnostic() {
    if (!ontConnected) {
        showToast("Conecte-se antes de iniciar o diagnóstico.");
        return;
    }
    if (supportDiagnosticState.running) {
        showToast("Um diagnóstico já está em andamento.");
        return;
    }
    // full=false desativa Speed Test, traceroute e otimização de Wi-Fi:
    // não aplicar mudanças implícitas ao clicar em um atalho.
    await runSupportDiagnostic({ full: false, dashboard: false });
};


document.getElementById(
    "supportDiagnosticForm"
)?.addEventListener(
    "submit",
    async event => {
        event.preventDefault();

        await runSupportDiagnostic({
            full: true
        });
    }
);


document.getElementById(
    "supportGenerateAttendance"
)?.addEventListener(
    "click",
    generateSupportAttendance
);


document.getElementById(
    "supportCopyAttendance"
)?.addEventListener(
    "click",
    copySupportAttendance
);


document.getElementById(
    "supportStandaloneSpeedButton"
)?.addEventListener(
    "click",
    runStandaloneSpeedTest
);


document.getElementById(
    "dashboardFullDiagnosticButton"
)?.addEventListener(
    "click",
    () => openPage(
        "supportDiagnostic"
    )
);


document.getElementById(
    "supportRepeatDiagnostic"
)?.addEventListener(
    "click",
    () => runSupportDiagnostic({
        full: true
    })
);



const SPEEDTEST_PROVIDER_STORAGE_KEY = "zteAutomatic.speedtestProvider";
const SPEEDTEST_URL_STORAGE_KEY = "zteAutomatic.speedtestUrl";


function syncSpeedtestServerField() {
    const preset = document.getElementById(
        "supportSpeedtestPreset"
    )?.value;

    const needsUrl = [
        "auto",
        "librespeed"
    ].includes(
        preset
    );

    document.getElementById(
        "supportSpeedtestCustomField"
    )?.classList.toggle(
        "hidden",
        !needsUrl
    );

    const help = document.getElementById(
        "supportSpeedtestHelp"
    );

    if (help) {
        help.textContent = preset === "librespeed"
            ? "Informe a URL raiz do LibreSpeed; o app descobre garbage.php e empty.php automaticamente."
            : "FAST.com, Speedtest.net e Cloudflare são detectados pela URL. Outras URLs são testadas como LibreSpeed.";
    }
}


function saveSpeedtestPreference() {
    try {
        localStorage.setItem(
            SPEEDTEST_PROVIDER_STORAGE_KEY,
            document.getElementById(
                "supportSpeedtestPreset"
            )?.value || "native_auto"
        );

        localStorage.setItem(
            SPEEDTEST_URL_STORAGE_KEY,
            document.getElementById(
                "supportSpeedtestBaseUrl"
            )?.value.trim() || ""
        );
    } catch (error) {
        console.warn(
            "Não foi possível salvar a preferência do Speed Test:",
            error
        );
    }
}


function loadSpeedtestPreference() {
    try {
        const provider = localStorage.getItem(
            SPEEDTEST_PROVIDER_STORAGE_KEY
        );

        const url = localStorage.getItem(
            SPEEDTEST_URL_STORAGE_KEY
        );

        const select = document.getElementById(
            "supportSpeedtestPreset"
        );

        if (
            provider
            && select
            && [
                ...select.options
            ].some(
                option => option.value === provider
            )
        ) {
            select.value = provider;
        }

        const input = document.getElementById(
            "supportSpeedtestBaseUrl"
        );

        if (
            input
            && url
        ) {
            input.value = url;
        }
    } catch (error) {
        console.warn(
            "Não foi possível restaurar a preferência do Speed Test:",
            error
        );
    }

    syncSpeedtestServerField();
}


document.getElementById(
    "supportSpeedtestPreset"
)?.addEventListener(
    "change",
    () => {
        syncSpeedtestServerField();
        saveSpeedtestPreference();
    }
);


document.getElementById(
    "supportSpeedtestBaseUrl"
)?.addEventListener(
    "change",
    saveSpeedtestPreference
);


loadSpeedtestPreference();


// =========================================================
// OPÇÕES DINÂMICAS POR FIRMWARE
// O catálogo indica apenas candidatos; a sondagem GET identifica quais
// rotas realmente responderam. Nenhuma ação de escrita é oferecida aqui.
// =========================================================

const firmwareDiagnosticState = {
    host: null,
    model: null,
    firmware: null,
    options: [],
    source: "multimodel",
    probeRunning: false,
    scanComplete: false
};

const FIRMWARE_DIAGNOSTIC_SECTIONS = Object.freeze({
    device_info: "device",
    wan: "wan",
    dsl: "dsl",
    wifi_ssids: "wifi_ssids",
    wifi_clients: "wifi_clients",
    lan_clients: "lan_clients",
    pon_optical: "optical"
});

const FIRMWARE_DIAGNOSTIC_LABELS = Object.freeze({
    device_info: "Identificação e recursos",
    wan: "Conexão WAN",
    dsl: "Sincronismo DSL",
    wifi_ssids: "Redes Wi-Fi",
    wifi_clients: "Dispositivos Wi-Fi",
    lan_clients: "Dispositivos cabeados",
    pon_optical: "Potência óptica"
});

function firmwareDiagnosticPanel() {
    const form = document.getElementById("supportDiagnosticForm");
    if (!form) return null;
    let panel = document.getElementById("firmwareDiagnosticPanel");
    if (panel) return panel;
    panel = document.createElement("section");
    panel.id = "firmwareDiagnosticPanel";
    panel.className = "panel";
    panel.style.marginBottom = "20px";
    panel.innerHTML = `
        <span class="section-kicker">RECURSOS DO EQUIPAMENTO</span>
        <h3>Diagnóstico dinâmico por firmware</h3>
        <p id="firmwareDiagnosticStatus" aria-live="polite">
            Conecte-se a uma ONT para consultar as opções.
        </p>
        <div id="firmwareDiagnosticChoices" class="advanced-switch-grid"></div>
        <div class="form-actions" style="margin-top: 14px; display: flex; gap: 8px; flex-wrap: wrap;">
            <button id="firmwareDiagnosticDetect" type="button" class="button ghost">
                Verificar recursos disponíveis
            </button>
            <button id="firmwareDiagnosticRun" type="button" class="button primary" disabled>
                Diagnosticar seções selecionadas
            </button>
        </div>
        <pre id="firmwareDiagnosticResult" style="white-space: pre-wrap; overflow-wrap: anywhere;"></pre>
    `;
    form.prepend(panel);
    panel.querySelector("#firmwareDiagnosticDetect")
        .addEventListener("click", () => void detectFirmwareDiagnosticOptions());
    panel.querySelector("#firmwareDiagnosticRun")
        .addEventListener("click", () => void runSelectedFirmwareDiagnostic());
    return panel;
}

function renderFirmwareDiagnosticOptions() {
    const panel = firmwareDiagnosticPanel();
    if (!panel) return;
    // Controles legados (incluindo POST de ping e otimização) não se aplicam
    // a firmwares experimentais. Não deixar opções visíveis que serão ignoradas.
    const form = document.getElementById("supportDiagnosticForm");
    for (const legacy of form.querySelectorAll(":scope > .support-form-grid, :scope > .support-check-grid, :scope > .support-action-row")) {
        legacy.classList.toggle("hidden", !routerWriteEnabled);
    }
    const grid = panel.querySelector("#firmwareDiagnosticChoices");
    const status = panel.querySelector("#firmwareDiagnosticStatus");
    const detected = firmwareDiagnosticState.options.filter(item => item.confirmed).length;
    const experimental = firmwareDiagnosticState.model?.toUpperCase().includes("F6201B");
    status.textContent = !ontConnected
        ? "Conecte-se antes de executar qualquer diagnóstico."
        : `${firmwareDiagnosticState.model || "Modelo desconhecido"}: ${detected} recurso(s) confirmado(s), ${firmwareDiagnosticState.options.length - detected} candidato(s) não confirmado(s).` +
          (experimental ? " F6201B: perfil experimental, sem garantia de compatibilidade." : "");
    const selected = new Set([...grid.querySelectorAll("input:checked")].map(input => input.value));
    grid.replaceChildren();
    for (const option of firmwareDiagnosticState.options) {
        const label = document.createElement("label");
        label.className = "advanced-switch";
        const input = document.createElement("input");
        input.type = "checkbox";
        input.value = option.name;
        input.disabled = !option.confirmed;
        input.checked = option.confirmed && (option.justConfirmed || selected.size === 0 || selected.has(option.name));
        option.justConfirmed = false;
        const text = document.createElement("span");
        text.textContent = `${option.label || FIRMWARE_DIAGNOSTIC_LABELS[option.name] || option.name} — ${option.confirmed ? "confirmado" : "candidato (não testado/indisponível)"}`;
        label.append(text, input);
        grid.append(label);
    }
    panel.querySelector("#firmwareDiagnosticRun").disabled = !detected || firmwareDiagnosticState.probeRunning;
    panel.querySelector("#firmwareDiagnosticDetect").disabled = !ontConnected || firmwareDiagnosticState.probeRunning;
}

async function loadFirmwareDiagnosticOptions() {
    const panel = firmwareDiagnosticPanel();
    if (!panel || !ontConnected) {
        renderFirmwareDiagnosticOptions();
        return;
    }
    try {
        // Bootstrap não consulta o roteador nem disputa o RLock do diagnóstico.
        const bootstrap = await apiRequest("/discovery/bootstrap");
        if (!bootstrap?.connected) {
            panel.querySelector("#firmwareDiagnosticStatus").textContent =
                "O backend não possui uma sessão autenticada.";
            return;
        }
        const model = bootstrap.model || bootstrap.detected_model || "";
        const sameDevice = firmwareDiagnosticState.host === currentHost
            && firmwareDiagnosticState.model === model;
        if (sameDevice && firmwareDiagnosticState.options.length) {
            renderFirmwareDiagnosticOptions();
            return;
        }
        const normalized = model.toUpperCase().replace(/[^A-Z0-9]/g, "");
        const entry = (bootstrap.catalog?.models || []).find(item =>
            normalized.includes(item.model.toUpperCase())
        );
        firmwareDiagnosticState.host = currentHost;
        firmwareDiagnosticState.model = model;
        firmwareDiagnosticState.firmware = bootstrap.firmware || null;
        firmwareDiagnosticState.scanComplete = false;
        firmwareDiagnosticState.source = "multimodel";
        firmwareDiagnosticState.options = (entry?.candidate_features || [])
            .filter(name => FIRMWARE_DIAGNOSTIC_SECTIONS[name])
            .map(name => ({ name, confirmed: false }));
        // Para a F670L, consultar o adaptador nativo; nunca declarar
        // operações perigosas como opções de diagnóstico.
        if (!entry && bootstrap.writes_enabled) {
            const nativeCatalog = await apiRequest("/device/capabilities");
            firmwareDiagnosticState.source = "native";
            firmwareDiagnosticState.options = Object.entries(nativeCatalog?.features || {})
                .filter(([name, meta]) => !meta.dangerous
                    && !["native_speedtest", "dns_lookup"].includes(name))
                .map(([name, meta]) => ({
                    name, label: meta.label || name, confirmed: false
                }));
        }
        renderFirmwareDiagnosticOptions();
        if (!entry) {
            panel.querySelector("#firmwareDiagnosticStatus").textContent =
                `O modelo ${model || "não identificado"} ainda não possui perfil. Não serão executadas consultas por suposição.`;
        }
    } catch (error) {
        panel.querySelector("#firmwareDiagnosticStatus").textContent =
            "Falha ao obter opções locais: " + error.message;
    }
}

async function detectFirmwareDiagnosticOptions() {
    const panel = firmwareDiagnosticPanel();
    if (!panel || firmwareDiagnosticState.probeRunning || !ontConnected) return;
    await loadFirmwareDiagnosticOptions();
    if (!firmwareDiagnosticState.options.length) {
        showToast("Não há perfil de endpoints candidato para esta ONT.");
        return;
    }
    firmwareDiagnosticState.probeRunning = true;
    renderFirmwareDiagnosticOptions();
    const status = panel.querySelector("#firmwareDiagnosticStatus");
    const result = panel.querySelector("#firmwareDiagnosticResult");
    const model = firmwareDiagnosticState.model;
    const host = firmwareDiagnosticState.host;
    let offset = 0;
    let total = 0;
    let stopped = false;
    const results = {};
    setBusy(true, "Validando recursos disponíveis (somente GET)...");
    try {
        if (firmwareDiagnosticState.source === "native") {
            // O adaptador nativo oferece recursos próprios da F670L.
            // Limitar a 12 consultas por ação, em lotes de dois.
            const features = firmwareDiagnosticState.options.slice(0, 12);
            for (let index = 0; index < features.length; index += 2) {
                const batch = await discoveryRequest("/device/capabilities/probe", {
                    method: "POST",
                    body: JSON.stringify({
                        features: features.slice(index, index + 2).map(item => item.name)
                    }),
                    timeoutMs: 55000
                });
                for (const item of batch.features || []) {
                    const option = firmwareDiagnosticState.options.find(
                        entry => entry.name === item.feature
                    );
                    if (option) {
                        option.justConfirmed = !option.confirmed && item.available;
                        option.confirmed = item.available === true;
                    }
                }
                renderFirmwareDiagnosticOptions();
            }
            firmwareDiagnosticState.scanComplete = true;
            const confirmed = features.filter(item => item.confirmed).length;
            status.textContent = "Adaptador nativo: " + confirmed + " recursos confirmados."; 
            result.textContent = "Selecione os recursos confirmados para consultar sua estrutura.";
            return;
        }
        do {
            // Um lote por vez: o firmware compartilha contexto menuView/menuData.
            const batch = await discoveryRequest("/multimodel/probe", {
                method: "POST",
                body: JSON.stringify({ model, start: offset, max_endpoints: 2 }),
                timeoutMs: 55000
            });
            if (host !== currentHost || model !== firmwareDiagnosticState.model) return;
            total = Number(batch.total_candidates || 0);
            for (const item of batch.capabilities || []) {
                results[item.feature] = {
                    available: item.available,
                    reason: item.reason || null
                };
            }
            for (const capability of batch.capabilities || []) {
                const option = firmwareDiagnosticState.options.find(
                    item => item.name === capability.feature
                );
                if (option) {
                    option.justConfirmed = !option.confirmed && capability.available === true;
                    option.confirmed = capability.available === true;
                }
            }
            offset = Number(batch.next_offset ?? (offset + 2));
            status.textContent =
                `Verificando ${model}: ${Math.min(offset, total)}/${total} endpoints avaliados...`;
            result.textContent = JSON.stringify({
                model,
                evaluated: Math.min(offset, total),
                total,
                firmware: firmwareDiagnosticState.firmware,
                experimental: model.toUpperCase().includes("F6201B"),
                results
            }, null, 2);
            renderFirmwareDiagnosticOptions();
            if (batch.session_expired) {
                stopped = true;
                showToast("Sessão expirada durante a detecção. Reconecte a ONT.");
                break;
            }
        } while (total && offset < total);
        firmwareDiagnosticState.scanComplete = !stopped;
        renderFirmwareDiagnosticOptions();
        if (!firmwareDiagnosticState.options.some(item => item.confirmed)) {
            status.textContent = "Nenhum endpoint confirmado neste firmware. Não será gerado diagnóstico fictício.";
        }
    } catch (error) {
        status.textContent = "Falha na detecção: " + error.message;
        showToast(error.message);
    } finally {
        firmwareDiagnosticState.probeRunning = false;
        renderFirmwareDiagnosticOptions();
        setBusy(false);
    }
}

async function runSelectedFirmwareDiagnostic() {
    const panel = firmwareDiagnosticPanel();
    if (!panel || !ontConnected || firmwareDiagnosticState.probeRunning) return;
    await loadFirmwareDiagnosticOptions();
    let choices = [...panel.querySelectorAll("#firmwareDiagnosticChoices input:checked")]
        .filter(input => !input.disabled).map(input => input.value);
    if (!choices.length && !firmwareDiagnosticState.scanComplete) {
        await detectFirmwareDiagnosticOptions();
        choices = [...panel.querySelectorAll("#firmwareDiagnosticChoices input:checked")]
            .filter(input => !input.disabled).map(input => input.value);
    }
    if (!choices.length) {
        showToast("Nenhuma seção validada. Verifique recursos antes de diagnosticar.");
        return;
    }
    const report = {
        model: firmwareDiagnosticState.model,
        read_only: true,
        sections: {}, errors: {},
        evidence: "Somente endpoints confirmados pela detecção GET"
    };
    const result = panel.querySelector("#firmwareDiagnosticResult");
    const host = currentHost;
    setBusy(true, "Consultando as seções verificadas...");
    try {
        for (const [index, feature] of choices.entries()) {
            if (host !== currentHost) break;
            const section = FIRMWARE_DIAGNOSTIC_SECTIONS[feature];
            try {
                if (firmwareDiagnosticState.source === "native") {
                    // Shape não retorna valores de clientes ou credenciais.
                    const data = await apiRequest(
                        "/features/shape?feature=" + encodeURIComponent(feature)
                    );
                    report.sections[feature] = {
                        available: data.available === true,
                        objects: data.objects || {}
                    };
                } else {
                    const data = await discoveryRequest("/multimodel/diagnostic", {
                        method: "POST",
                        body: JSON.stringify({ model: firmwareDiagnosticState.model, section }),
                        timeoutMs: 48000
                    });
                    Object.assign(report.sections, data.sections || {});
                    if (data.reason) report.errors[section] = data.reason;
                }
            } catch (error) {
                report.errors[section] = error.message;
                if (String(error.message).includes("passou de")) break;
            }
            result.textContent = `DIAGNÓSTICO POR FIRMWARE — ${index + 1}/${choices.length}\n` +
                JSON.stringify(report, null, 2);
        }
        showToast(Object.values(report.sections).some(item => item.available)
            ? "Diagnóstico por firmware concluído."
            : "O firmware não retornou dados nas seções selecionadas.");
    } finally {
        setBusy(false);
    }
}

document.addEventListener("zte:page-open", event => {
    if (event.detail?.pageName === "supportDiagnostic") {
        void loadFirmwareDiagnosticOptions();
    }
});

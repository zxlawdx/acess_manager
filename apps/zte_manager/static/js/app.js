const API_BASE = "/api";

// Indicador independente do overlay: a operação continua visível quando
// uma consulta demora ou quando o handler original não usava setBusy().
let pendingApiRequests = 0;
let requestStatusTimer = null;

function updateRequestStatus(errorMessage = null) {
    const indicator = document.getElementById("requestStatusIndicator");
    if (!indicator) return;
    clearTimeout(requestStatusTimer);
    if (errorMessage) {
        indicator.textContent = "Falha na operação: " + errorMessage;
        indicator.classList.add("is-error");
        indicator.classList.remove("hidden");
        requestStatusTimer = setTimeout(() => {
            if (!pendingApiRequests) indicator.classList.add("hidden");
        }, 5500);
        return;
    }
    indicator.classList.remove("is-error");
    if (pendingApiRequests) {
        indicator.textContent = `Carregando... ${pendingApiRequests} requisição(ões)`;
        indicator.classList.remove("hidden");
    } else {
        indicator.textContent = "Operação finalizada";
        requestStatusTimer = setTimeout(
            () => indicator.classList.add("hidden"), 1350
        );
    }
}


let ontConnected = false;
let routerWriteEnabled = true;
let currentHost = null;
let currentAttendant = null;
let currentProfile = null;
let cachedWan = [];
let cachedRadios = [];
let cachedNetworks = [];
let cachedWps = [];
let cachedBandSteering = null;
let cachedUpnp = null;
let pppoeRevealed = false;
let wifiPasswordsRevealed = false;


// =========================================================
// API
// =========================================================

async function apiRequest(
    endpoint,
    options = {}
) {
    pendingApiRequests++;
    const slowTimer = setTimeout(updateRequestStatus, 180);
    try {
    const config = {
        method: "GET",
        headers: {
            "Content-Type": "application/json",
            ...(options.headers || {})
        },
        ...options
    };

    const response = await fetch(
        `${API_BASE}${endpoint}`,
        config
    );

    let data = null;
    const contentType = response.headers.get(
        "content-type"
    );

    try {
        if (
            contentType
            && contentType.includes("application/json")
        ) {
            data = await response.json();
        } else {
            data = await response.text();
        }
    } catch {
        data = null;
    }

    if (
        response.ok
        && data
        && typeof data === "object"
        && data.error
    ) {
        throw new Error(
            data.error
        );
    }

    if (!response.ok) {
        let message = `Erro HTTP ${response.status}`;

        if (
            data
            && typeof data === "object"
        ) {
            message = (
                data.detail
                || data.message
                || message
            );
        } else if (
            typeof data === "string"
            && data.trim()
        ) {
            message = data;
        }

        throw new Error(
            message
        );
    }

    return data;
    } catch (error) {
        updateRequestStatus(error?.message || "Erro desconhecido");
        throw error;
    } finally {
        clearTimeout(slowTimer);
        pendingApiRequests = Math.max(0, pendingApiRequests - 1);
        // Preserve a mensagem de falha até expirar, mesmo após finalizar.
        if (!pendingApiRequests) {
            const badge = document.getElementById("requestStatusIndicator");
            if (!badge?.classList.contains("is-error")) {
                updateRequestStatus();
            }
        }
    }
}


// =========================================================
// CONEXÃO
// =========================================================

async function connectONT(
    ip,
    username,
    password,
    https,
    attendant,
    modelHint = null
) {
    return apiRequest(
        "/connect",
        {
            method: "POST",
            body: JSON.stringify({
                ip,
                username,
                password,
                https,
                attendant,
                model_hint: modelHint
            })
        }
    );
}


async function disconnectONT() {
    try {
        await apiRequest(
            "/disconnect",
            {
                method: "POST"
            }
        );
    } catch (error) {
        console.error(
            "Erro ao desconectar:",
            error
        );
    }
}


// =========================================================
// UI HELPERS
// =========================================================

function showToast(message) {
    const toast = document.getElementById(
        "toast"
    );

    toast.textContent = message;
    toast.classList.add(
        "show"
    );

    clearTimeout(
        toast._timeout
    );

    toast._timeout = setTimeout(
        () => {
            toast.classList.remove(
                "show"
            );
        },
        3200
    );
}


function setBusy(
    busy,
    text = "Processando..."
) {
    const overlay = document.getElementById(
        "busyOverlay"
    );

    const label = document.getElementById(
        "busyText"
    );

    label.textContent = text;

    overlay.classList.toggle(
        "hidden",
        !busy
    );
}


function setConnectionStatus(connected) {
    ontConnected = connected;

    const dot = document.getElementById(
        "connectionDot"
    );

    const text = document.getElementById(
        "connectionStatus"
    );

    const disconnectButton = document.getElementById(
        "disconnectButton"
    );

    const refreshButton = document.getElementById(
        "refreshButton"
    );

    const connectedDevice = document.getElementById(
        "connectedDevice"
    );

    dot.classList.remove(
        "online",
        "offline"
    );

    const consoleDot = document.getElementById(
        "consoleSessionDot"
    );

    const consoleState = document.getElementById(
        "consoleSessionState"
    );

    const consoleHost = document.getElementById(
        "consoleHostText"
    );

    if (consoleDot) {
        consoleDot.classList.remove(
            "online",
            "offline"
        );

        consoleDot.classList.add(
            connected
                ? "online"
                : "offline"
        );
    }

    if (consoleState) {
        consoleState.textContent = connected
            ? "SESSION ACTIVE"
            : "SESSION OFFLINE";
    }

    if (consoleHost) {
        consoleHost.textContent = connected
            ? (
                currentHost
                || "TARGET CONNECTED"
            )
            : "NO TARGET";
    }

    document.body.classList.toggle(
        "ont-connected",
        connected
    );

    if (connected) {
        dot.classList.add(
            "online"
        );

        text.textContent = "Conectado";

        disconnectButton.classList.remove(
            "hidden"
        );

        refreshButton.classList.remove(
            "hidden"
        );

        connectedDevice.classList.remove(
            "hidden"
        );

        document
            .querySelectorAll(
                ".protected-page"
            )
            .forEach(
                item => item.classList.remove(
                    "locked"
                )
            );
    } else {
        dot.classList.add(
            "offline"
        );

        text.textContent = "Desconectado";

        disconnectButton.classList.add(
            "hidden"
        );

        refreshButton.classList.add(
            "hidden"
        );

        connectedDevice.classList.add(
            "hidden"
        );

        document.getElementById(
            "topDeviceChip"
        ).classList.add(
            "hidden"
        );

        document
            .querySelectorAll(
                ".protected-page"
            )
            .forEach(
                item => item.classList.add(
                    "locked"
                )
            );
    }
}


// =========================================================
// NAVEGAÇÃO
// =========================================================

const pageInfo = {
    connection: {
        title: "Conexão",
        subtitle: "Entre na ONT para iniciar o atendimento."
    },
    dashboard: {
        title: "Dashboard",
        subtitle: "Visão geral do equipamento e do atendimento."
    },
    wifi: {
        title: "Wi-Fi",
        subtitle: "Redes, canal, largura, modo e potência."
    },
    wan: {
        title: "WAN / PPPoE",
        subtitle: "Status, VLAN e credenciais PPPoE."
    },
    diagnostics: {
        title: "Diagnóstico",
        subtitle: "Ping e traceroute executados pela própria ONT."
    },
    profiles: {
        title: "Configuração padrão",
        subtitle: "Perfil persistente de cada atendente."
    },
    clients: {
        title: "Clientes",
        subtitle: "Dispositivos Wi-Fi e Ethernet encontrados."
    },
    device: {
        title: "Equipamento",
        subtitle: "PON, conta administrativa e controle da ONT."
    }
};


function openPage(pageName) {
    if (
        ![
            "connection",
            "management"
        ].includes(pageName)
        && !ontConnected
    ) {
        showToast(
            "Conecte-se à ONT primeiro."
        );

        pageName = "connection";
    }

    document
        .querySelectorAll(
            ".page"
        )
        .forEach(
            page => page.classList.remove(
                "active"
            )
        );

    document
        .querySelectorAll(
            ".menu-item"
        )
        .forEach(
            item => item.classList.remove(
                "active"
            )
        );

    const targetPage = document.getElementById(
        `page-${pageName}`
    );

    if (targetPage) {
        targetPage.classList.add(
            "active"
        );
    }

    const menuButton = document.querySelector(
        `[data-page="${pageName}"]`
    );

    if (menuButton) {
        menuButton.classList.add(
            "active"
        );
    }

    const info = pageInfo[
        pageName
    ];

    if (info) {
        document.getElementById(
            "pageTitle"
        ).textContent = info.title;

        document.getElementById(
            "pageSubtitle"
        ).textContent = info.subtitle;
    }

    // Todas as entradas (sidebar, cartões, topo e restore) carregam dados.
    document.dispatchEvent(new CustomEvent(
        "zte:page-open", { detail: { pageName } }
    ));
}


// =========================================================
// CONNECTION FORM
// =========================================================

document
    .getElementById(
        "connectionForm"
    )
    .addEventListener(
        "submit",
        async event => {
            event.preventDefault();

            const ip = document.getElementById(
                "zteIp"
            ).value.trim();

            const username = document.getElementById(
                "zteUsername"
            ).value.trim();

            const password = document.getElementById(
                "ztePassword"
            ).value;

            const https = document.getElementById(
                "zteHttps"
            ).checked;

            const attendant = document.getElementById(
                "attendantName"
            ).value.trim();

            const modelHint = document.getElementById(
                "zteModelHint"
            )?.value || null;

            const button = document.getElementById(
                "connectButton"
            );

            const result = document.getElementById(
                "connectionResult"
            );

            button.disabled = true;
            button.textContent = "Conectando...";
            result.classList.add(
                "hidden"
            );

            setBusy(
                true,
                "Autenticando na ONT..."
            );

            try {
                const response = await connectONT(
                    ip,
                    username,
                    password,
                    https,
                    attendant,
                    modelHint
                );

                routerWriteEnabled = response.writes_enabled !== false;
                currentHost = response.host || ip;
                currentAttendant = response.attendant || attendant || "default";

                setConnectionStatus(
                    true
                );

                document.getElementById(
                    "connectedHost"
                ).textContent = currentHost;

                document.getElementById(
                    "connectedAttendant"
                ).textContent = `Atendente: ${currentAttendant}`;

                document.getElementById(
                    "dashboardProfileName"
                ).textContent = currentAttendant;

                document.getElementById(
                    "profileAttendant"
                ).textContent = currentAttendant;

                result.className = (
                    "connection-result connection-success"
                );

                result.textContent = response.writes_enabled === false
                    ? "Conectado no modo somente leitura. Diagnóstico por firmware disponível em Avançado."
                    : "Conectado com sucesso.";

                // Não disparar rotinas de configuração/dashboard da F670L
                // contra firmwares cujo perfil ainda está em descoberta.
                if (response.writes_enabled === false) {
                    showToast("Modelo experimental: escrita desativada. Use Avançado para detectar endpoints.");
                    openPage("advanced");
                    return;
                }

                await loadProfile();
                await loadAll();

                showToast(
                    "ONT conectada com sucesso."
                );

                openPage(
                    "dashboard"
                );
            } catch (error) {
                console.error(
                    error
                );

                setConnectionStatus(
                    false
                );

                result.className = (
                    "connection-result connection-error"
                );

                result.textContent = error.message;
            } finally {
                setBusy(
                    false
                );

                button.disabled = false;
                button.textContent = "Conectar";
            }
        }
    );


// =========================================================
// PASSWORD DA TELA DE LOGIN
// =========================================================

document
    .getElementById(
        "togglePassword"
    )
    .addEventListener(
        "click",
        () => {
            const input = document.getElementById(
                "ztePassword"
            );

            const button = document.getElementById(
                "togglePassword"
            );

            const visible = input.type === "text";

            input.type = visible
                ? "password"
                : "text";

            button.textContent = visible
                ? "Mostrar"
                : "Ocultar";
        }
    );


// =========================================================
// DISCONNECT
// =========================================================

document
    .getElementById(
        "disconnectButton"
    )
    .addEventListener(
        "click",
        async () => {
            setBusy(
                true,
                "Encerrando sessão..."
            );

            await disconnectONT();

            routerWriteEnabled = true;
            currentHost = null;
            currentAttendant = null;
            currentProfile = null;
            cachedWan = [];
            cachedRadios = [];
            cachedNetworks = [];
            cachedWps = [];
            cachedUpnp = null;
            pppoeRevealed = false;
            wifiPasswordsRevealed = false;

            setConnectionStatus(
                false
            );

            document.getElementById(
                "connectedModel"
            ).textContent = "-";

            document.getElementById(
                "connectedHost"
            ).textContent = "-";

            document.getElementById(
                "connectedAttendant"
            ).textContent = "-";

            setBusy(
                false
            );

            showToast(
                "ONT desconectada."
            );

            openPage(
                "connection"
            );
        }
    );


// =========================================================
// DEVICE
// =========================================================

async function loadDevice() {
    const data = await apiRequest(
        "/device/status"
    );

    document.getElementById(
        "deviceModel"
    ).textContent = data.modelo ?? "-";

    document.getElementById(
        "connectedModel"
    ).textContent = data.modelo ?? "ZTE";

    document.getElementById(
        "deviceFirmware"
    ).textContent = `Firmware: ${data.firmware ?? "-"}`;

    let memory = data.memoria_percent;

    if (
        memory !== undefined
        && memory !== null
        && memory !== ""
        && !String(memory).includes("%")
    ) {
        memory = `${memory}%`;
    }

    document.getElementById(
        "deviceMemory"
    ).textContent = memory ?? "-";

    const cpuValues = Object.values(
        data.cpu || {}
    )
        .map(
            value => Number(
                String(value ?? "")
                    .replace("%", "")
            )
        )
        .filter(
            value => !Number.isNaN(value)
        );

    let cpuText = "-";

    if (cpuValues.length) {
        const average = cpuValues.reduce(
            (a, b) => a + b,
            0
        ) / cpuValues.length;

        cpuText = `${average.toFixed(0)}%`;
    }

    document.getElementById(
        "deviceCpu"
    ).textContent = cpuText;

    document.getElementById(
        "deviceUptime"
    ).textContent = (
        data.uptime_dias !== undefined
            ? `${data.uptime_dias} dias`
            : "-"
    );

    document.getElementById(
        "dashboardSerial"
    ).textContent = data.serial ?? "-";

    document.getElementById(
        "topDeviceModel"
    ).textContent = data.modelo ?? "ZTE";

    document.getElementById(
        "topDeviceMeta"
    ).textContent = `${currentHost ?? "-"} • ${data.firmware ?? "-"}`;

    document.getElementById(
        "topDeviceChip"
    ).classList.remove(
        "hidden"
    );

    document.getElementById(
        "deviceDetails"
    ).innerHTML = `
        <div class="detail-grid">
            ${detailTile("Fabricante", data.fabricante, "factory")}
            ${detailTile("Modelo", data.modelo, "router")}
            ${detailTile("Firmware", data.firmware, "deployed_code")}
            ${detailTile("Hardware", data.hardware, "memory")}
            ${detailTile("Boot", data.boot, "power_settings_new")}
            ${detailTile("Serial", data.serial, "tag")}
            ${detailTile("Temp. CPU", data.temperatura_cpu ? `${data.temperatura_cpu} °C` : "-", "thermostat")}
            ${detailTile("Flash usada", data.flash_usado_percent ? `${data.flash_usado_percent}%` : "-", "storage")}
        </div>
    `;

    return data;
}


async function loadOptical() {
    const container = document.getElementById(
        "opticalDetails"
    );

    try {
        const data = await apiRequest(
            "/device/optical"
        );

        const rx = normalizeOpticalPower(
            data.rx_power_dbm
        );

        const tx = normalizeOpticalPower(
            data.tx_power_dbm
        );

        document.getElementById(
            "opticalRxKpi"
        ).textContent = rx !== "-"
            ? `${rx} dBm`
            : "-";

        document.getElementById(
            "opticalStatusKpi"
        ).textContent = [
            data.registration_status,
            data.los ? `LOS ${data.los}` : null
        ].filter(Boolean).join(" • ") || "PON lida";

        container.innerHTML = `
            <div class="optical-hero">
                <div class="optical-gauge">
                    <span class="material-symbols-outlined">cell_tower</span>
                    <strong>${escapeHtml(rx)}</strong>
                    <small>dBm RX</small>
                </div>
                <div class="optical-copy">
                    <span class="section-kicker">GPON LINK</span>
                    <h3>${escapeHtml(data.registration_status ?? "Status não informado")}</h3>
                    <p>ONU ${escapeHtml(data.onu_id ?? "-")} • LOS ${escapeHtml(data.los ?? "-")}</p>
                </div>
            </div>

            <div class="detail-grid compact">
                ${detailTile("RX", rx !== "-" ? `${rx} dBm` : "-", "south_west")}
                ${detailTile("TX", tx !== "-" ? `${tx} dBm` : "-", "north_east")}
                ${detailTile("Temperatura", data.temperature_c ? `${data.temperature_c} °C` : "-", "device_thermostat")}
                ${detailTile("Tensão", data.voltage, "bolt")}
                ${detailTile("Corrente", data.current_ma ? `${data.current_ma} mA` : "-", "electric_meter")}
                ${detailTile("PON uptime", formatSeconds(data.pon_uptime), "schedule")}
            </div>
        `;

        return data;
    } catch (error) {
        document.getElementById(
            "opticalStatusKpi"
        ).textContent = "Leitura óptica indisponível";

        container.innerHTML = `
            <div class="feature-unavailable inline">
                <span class="material-symbols-outlined">signal_cellular_off</span>
                <div>
                    <strong>Telemetria óptica indisponível</strong>
                    <p>${escapeHtml(error.message)}</p>
                </div>
            </div>
        `;

        throw error;
    }
}


// =========================================================
// WAN / PPPOE
// =========================================================

async function loadWan() {
    cachedWan = await apiRequest(
        "/wan/status"
    );

    const connections = Array.isArray(
        cachedWan
    )
        ? cachedWan
        : [];

    const summary = document.getElementById(
        "wanSummary"
    );

    const page = document.getElementById(
        "wanConnections"
    );

    if (!connections.length) {
        summary.innerHTML = (
            '<div class="loading">Nenhuma WAN encontrada.</div>'
        );

        page.innerHTML = (
            '<div class="card">Nenhuma WAN encontrada.</div>'
        );

        populateDiagnosticInterfaces(
            []
        );

        return;
    }

    const wan = connections.find(
        item => isWanConnected(
            item.status
        )
    ) || connections[0];

    summary.innerHTML = `
        <div class="info-row">
            <span class="info-label">Status</span>
            ${statusBadge(wan.status)}
        </div>
        ${infoRow("Nome", wan.nome)}
        ${infoRow("IPv4", wan.ip)}
        ${infoRow("Gateway", wan.gateway)}
        ${infoRow("VLAN", wan.vlan)}
    `;

    page.innerHTML = connections
        .map(
            renderWanCard
        )
        .join("");

    populateDiagnosticInterfaces(
        connections
    );
}


function renderWanCard(wan) {
    const connected = isWanConnected(
        wan.status
    );

    return `
        <article class="panel wan-card ${connected ? "connected" : "disconnected"}">
            <div class="wan-card-head">
                <div class="wan-title-group">
                    <span class="wan-icon ${connected ? "online" : "offline"}">
                        <span class="material-symbols-outlined">public</span>
                    </span>
                    <div>
                        <span class="section-kicker">${escapeHtml(wan.wan_type ?? wan.tipo ?? "WAN")}</span>
                        <h3>${escapeHtml(wan.nome ?? "WAN")}</h3>
                        <p>${escapeHtml(wan.id ?? "-")}</p>
                    </div>
                </div>
                ${statusBadge(wan.status)}
            </div>

            <div class="wan-address">
                <span>IPv4</span>
                <strong class="mono">${escapeHtml(wan.ip ?? "-")}</strong>
                <small>GW ${escapeHtml(wan.gateway ?? "-")}</small>
            </div>

            <div class="detail-grid compact">
                ${detailTile("VLAN", wan.vlan, "sell")}
                ${detailTile("MTU", wan.mtu, "straighten")}
                ${detailTile("DNS 1", wan.dns1, "dns")}
                ${detailTile("DNS 2", wan.dns2, "dns")}
                ${detailTile("NAT", wan.nat, "swap_horiz")}
                ${detailTile("Uptime", wan.uptime, "schedule")}
            </div>

            ${wan.ipv6 ? `<div class="wan-ipv6 mono">${escapeHtml(wan.ipv6)}</div>` : ""}
            ${wan.erro ? `<div class="wan-error">${escapeHtml(wan.erro)}</div>` : ""}
        </article>
    `;
}


async function loadPppoe(
    reveal = false
) {
    const query = new URLSearchParams({
        reveal_password: reveal
    });

    const data = await apiRequest(
        `/wan/pppoe?${query.toString()}`
    );

    const pppoe = Array.isArray(data)
        ? data
        : [];

    renderPppoe(
        document.getElementById(
            "dashboardPppoe"
        ),
        pppoe,
        false
    );

    renderPppoe(
        document.getElementById(
            "pppoeDetails"
        ),
        pppoe,
        true
    );

    pppoeRevealed = reveal;

    document.getElementById(
        "revealPppoeButton"
    ).textContent = reveal
        ? "Ocultar senha"
        : "Revelar senha";
}


function renderPppoe(
    container,
    items,
    detailed
) {
    if (!items.length) {
        container.innerHTML = (
            '<div class="loading">Nenhuma WAN PPPoE encontrada.</div>'
        );

        return;
    }

    container.innerHTML = items
        .map(
            item => `
                <div class="credential-card">
                    <div class="credential-head">
                        <div>
                            <span class="section-kicker">${escapeHtml(item.nome ?? "PPPoE")}</span>
                            <strong>${escapeHtml(item.username ?? "-")}</strong>
                        </div>
                        <span class="material-symbols-outlined">vpn_key</span>
                    </div>

                    <div class="secret-line">
                        <span>SENHA</span>
                        <strong class="mono">${escapeHtml(item.password ?? "-")}</strong>
                    </div>

                    ${detailed ? `
                        <div class="credential-meta">
                            <span>AUTH <strong>${escapeHtml(item.auth_type ?? "-")}</strong></span>
                            <span>VLAN <strong>${escapeHtml(item.vlan ?? "-")}</strong></span>
                            <span>MTU <strong>${escapeHtml(item.mtu ?? "-")}</strong></span>
                        </div>
                    ` : ""}
                </div>
            `
        )
        .join("");
}


// =========================================================
// LAN PORTS / UPNP
// =========================================================

async function loadLanPorts() {
    const container = document.getElementById(
        "lanPorts"
    );

    try {
        const data = await apiRequest(
            "/lan/ports"
        );

        const ports = Array.isArray(data)
            ? data
            : [];

        if (!ports.length) {
            container.innerHTML = (
                '<div class="loading">Nenhuma porta retornada.</div>'
            );

            return [];
        }

        container.innerHTML = ports
            .map(
                port => {
                    const active = isPortUp(
                        port.status
                    );

                    return `
                        <div class="port-card ${active ? "active" : ""}">
                            <div class="port-head">
                                <span class="port-number">LAN ${escapeHtml(port.port)}</span>
                                <span class="status-led ${active ? "on" : "off"}"></span>
                            </div>
                            <strong>${escapeHtml(port.speed ?? "-")}</strong>
                            <small>${escapeHtml(port.duplex ?? "-")} • ${escapeHtml(port.status ?? "-")}</small>
                            <div class="port-metrics">
                                <div><span>RX</span><strong>${formatBytes(port.rx_bytes)}</strong></div>
                                <div><span>TX</span><strong>${formatBytes(port.tx_bytes)}</strong></div>
                            </div>
                        </div>
                    `;
                }
            )
            .join("");

        return ports;
    } catch (error) {
        container.innerHTML = `
            <div class="feature-unavailable inline">
                <span class="material-symbols-outlined">lan</span>
                <div>
                    <strong>Portas LAN indisponíveis</strong>
                    <p>${escapeHtml(error.message)}</p>
                </div>
            </div>
        `;

        throw error;
    }
}


async function loadUpnp() {
    const container = document.getElementById(
        "upnpDetails"
    );

    const badge = document.getElementById(
        "upnpBadge"
    );

    try {
        cachedUpnp = await apiRequest(
            "/upnp"
        );

        if (!cachedUpnp?.available) {
            badge.className = "badge badge-danger";
            badge.textContent = "Indisponível";

            container.innerHTML = `
                <div class="feature-unavailable inline">
                    <span class="material-symbols-outlined">block</span>
                    <div>
                        <strong>UPnP não disponível</strong>
                        <p>A conta ou o firmware não expôs OBJ_UPNPCONFIG_ID.</p>
                    </div>
                </div>
            `;

            return cachedUpnp;
        }

        badge.className = (
            `badge ${cachedUpnp.enabled ? "badge-warning" : "badge-success"}`
        );

        badge.textContent = cachedUpnp.enabled
            ? "Ativo"
            : "Desativado";

        container.innerHTML = `
            <div class="upnp-copy">
                <span class="feature-icon large"><span class="material-symbols-outlined">device_hub</span></span>
                <div>
                    <h4>Descoberta automática de portas</h4>
                    <p>Controle o serviço exposto pelo firmware sem alterar os parâmetros que não foram solicitados.</p>
                </div>
            </div>

            <form id="upnpForm" class="upnp-form">
                <label class="switch-field upnp-switch">
                    <span>UPnP IGD</span>
                    <span class="switch">
                        <input
                            data-field="enabled"
                            type="checkbox"
                            ${cachedUpnp.enabled ? "checked" : ""}
                        >
                        <span class="switch-slider"></span>
                    </span>
                </label>

                <div class="form-grid four-fields">
                    <div class="form-group">
                        <label>WAN IPv4</label>
                        <input data-field="wan" type="text" value="${escapeHtml(cachedUpnp.wan ?? "")}">
                    </div>
                    <div class="form-group">
                        <label>WAN IPv6</label>
                        <input data-field="wan_ipv6" type="text" value="${escapeHtml(cachedUpnp.wan_ipv6 ?? "")}">
                    </div>
                    <div class="form-group">
                        <label>Advertisement</label>
                        <input data-field="advertisement_period" type="number" min="4" max="1440" value="${escapeHtml(cachedUpnp.advertisement_period ?? 30)}">
                    </div>
                    <div class="form-group">
                        <label>TTL</label>
                        <input data-field="ttl" type="number" min="1" max="255" value="${escapeHtml(cachedUpnp.ttl ?? 4)}">
                    </div>
                </div>

                <div class="form-footer">
                    <span class="radio-id">${escapeHtml(cachedUpnp.id ?? "OBJ_UPNPCONFIG_ID")}</span>
                    <button class="button ghost" type="submit">
                        <span class="material-symbols-outlined">save</span>
                        Aplicar UPnP
                    </button>
                </div>
            </form>
        `;

        document.getElementById(
            "upnpForm"
        ).addEventListener(
            "submit",
            applyUpnp
        );

        return cachedUpnp;
    } catch (error) {
        badge.className = "badge badge-danger";
        badge.textContent = "Sem acesso";

        container.innerHTML = `
            <div class="feature-unavailable inline">
                <span class="material-symbols-outlined">lock</span>
                <div>
                    <strong>UPnP não pôde ser lido</strong>
                    <p>${escapeHtml(error.message)}</p>
                </div>
            </div>
        `;

        throw error;
    }
}


async function applyUpnp(event) {
    event.preventDefault();

    const form = event.currentTarget;

    const payload = {
        enabled: form.querySelector('[data-field="enabled"]').checked,
        wan: form.querySelector('[data-field="wan"]').value.trim(),
        wan_ipv6: form.querySelector('[data-field="wan_ipv6"]').value.trim(),
        advertisement_period: Number(
            form.querySelector('[data-field="advertisement_period"]').value
        ),
        ttl: Number(
            form.querySelector('[data-field="ttl"]').value
        )
    };

    setBusy(
        true,
        "Aplicando UPnP..."
    );

    try {
        await apiRequest(
            "/upnp/update",
            {
                method: "POST",
                body: JSON.stringify(payload)
            }
        );

        showToast(
            "UPnP atualizado."
        );

        await loadUpnp();
    } catch (error) {
        showToast(
            error.message
        );
    } finally {
        setBusy(false);
    }
}


// =========================================================
// WIFI
// =========================================================

async function loadWifi() {
    const query = new URLSearchParams({
        reveal_password: wifiPasswordsRevealed
    });

    cachedNetworks = await apiRequest(
        `/wifi/networks?${query.toString()}`
    );

    cachedRadios = await apiRequest(
        "/wifi/radios"
    );

    renderWifiNetworks(
        Array.isArray(cachedNetworks)
            ? cachedNetworks
            : []
    );

    await renderWifiRadios(
        Array.isArray(cachedRadios)
            ? cachedRadios
            : []
    );

    // WPS depende do nível de permissão do login. Falhar aqui não deve
    // impedir o atendente de usar as funções principais de Wi-Fi.
    try {
        cachedWps = await apiRequest(
            "/wifi/wps"
        );

        renderWpsControls(
            Array.isArray(cachedWps)
                ? cachedWps
                : []
        );
    } catch (error) {
        console.warn(
            "WPS indisponível:",
            error
        );

        document.getElementById(
            "wpsControls"
        ).innerHTML = `
            <article class="panel feature-unavailable">
                <span class="material-symbols-outlined">lock</span>
                <div>
                    <strong>WPS indisponível para esta conta</strong>
                    <p>${escapeHtml(error.message)}</p>
                </div>
            </article>
        `;
    }

    await loadBandSteering();
}


async function loadBandSteering() {
    const container = document.getElementById(
        "bandSteeringControl"
    );

    try {
        cachedBandSteering = await apiRequest(
            "/wifi/band-steering"
        );

        if (!cachedBandSteering?.available) {
            container.innerHTML = `
                <article class="panel feature-unavailable">
                    <span class="material-symbols-outlined">hub</span>
                    <div>
                        <strong>Band Steering não disponível</strong>
                        <p>Este login ou firmware não expôs o recurso.</p>
                    </div>
                </article>
            `;
            return;
        }

        const params = cachedBandSteering.parameters || {};

        container.innerHTML = `
            <article class="panel feature-control-card">
                <div class="feature-control-main">
                    <div class="feature-control-icon">
                        <span class="material-symbols-outlined">hub</span>
                    </div>
                    <div>
                        <span class="section-kicker">SMART CONNECT</span>
                        <h3>Band Steering</h3>
                        <p>Direcionamento automático entre rádios, preservando os parâmetros internos de RSSI e airtime.</p>
                    </div>
                </div>

                <div class="feature-control-side">
                    <span class="badge ${cachedBandSteering.enabled ? "badge-success" : "badge-danger"}">
                        ${cachedBandSteering.enabled ? "ATIVO" : "DESATIVADO"}
                    </span>
                    <label class="switch-field compact">
                        <span>Ativar</span>
                        <span class="switch">
                            <input id="bandSteeringToggle" type="checkbox" ${cachedBandSteering.enabled ? "checked" : ""}>
                            <span class="switch-slider"></span>
                        </span>
                    </label>
                </div>

                <div class="band-steering-metrics">
                    <span>RSSI 2.4G <strong>${escapeHtml(params.rssi_limit_24g ?? "-")}</strong></span>
                    <span>RSSI 5G <strong>${escapeHtml(params.rssi_limit_5g ?? "-")}</strong></span>
                    <span>Util. 2.4G <strong>${escapeHtml(params.bandwidth_util_24g ?? "-")}%</strong></span>
                    <span>Util. 5G <strong>${escapeHtml(params.bandwidth_util_5g ?? "-")}%</strong></span>
                </div>

                ${renderBandSteeringAdvanced(params)}
            </article>
        `;

        document.getElementById(
            "bandSteeringToggle"
        ).addEventListener(
            "change",
            applyBandSteering
        );

        bindBandSteeringAdvanced(
            params
        );
    } catch (error) {
        console.warn(
            "Band Steering indisponível:",
            error
        );

        container.innerHTML = `
            <article class="panel feature-unavailable">
                <span class="material-symbols-outlined">lock</span>
                <div>
                    <strong>Band Steering indisponível para esta conta</strong>
                    <p>${escapeHtml(error.message)}</p>
                </div>
            </article>
        `;
    }
}


async function applyBandSteering(event) {
    const toggle = event.currentTarget;
    const enabled = toggle.checked;

    setBusy(
        true,
        enabled
            ? "Ativando Band Steering..."
            : "Desativando Band Steering..."
    );

    try {
        await apiRequest(
            "/wifi/band-steering/update",
            {
                method: "POST",
                body: JSON.stringify({
                    enabled
                })
            }
        );

        showToast(
            `Band Steering ${enabled ? "ativado" : "desativado"}.`
        );

        await loadBandSteering();
    } catch (error) {
        toggle.checked = !enabled;
        showToast(
            error.message
        );
    } finally {
        setBusy(
            false
        );
    }
}


function renderWifiNetworks(networks) {
    const dashboard = document.getElementById(
        "dashboardNetworks"
    );

    const page = document.getElementById(
        "wifiNetworks"
    );

    if (!networks.length) {
        dashboard.innerHTML = (
            '<div class="loading">Nenhuma rede encontrada.</div>'
        );

        page.innerHTML = (
            '<div class="panel">Nenhuma rede encontrada.</div>'
        );

        return;
    }

    dashboard.innerHTML = networks
        .map(
            network => `
                <button
                    class="network-overview-item"
                    data-jump="wifi"
                    type="button"
                >
                    <span class="network-overview-icon ${network.ativo ? "online" : "offline"}">
                        <span class="material-symbols-outlined">wifi</span>
                    </span>
                    <span class="network-overview-copy">
                        <strong>${escapeHtml(network.ssid ?? "Sem nome")}</strong>
                        <small>${escapeHtml(network.banda ?? "-")} • ${escapeHtml(network.seguranca ?? network.beacon_type ?? "-")}</small>
                    </span>
                    <span class="badge ${network.ativo ? "badge-success" : "badge-danger"}">
                        ${network.ativo ? "Ativa" : "Off"}
                    </span>
                </button>
            `
        )
        .join("");

    page.innerHTML = networks
        .map(
            renderSsidEditor
        )
        .join("");

    document
        .querySelectorAll(
            ".ssid-form"
        )
        .forEach(
            form => {
                form.addEventListener(
                    "submit",
                    applySsidForm
                );
            }
        );
}


function renderSsidEditor(network) {
    const passwordValue = (
        wifiPasswordsRevealed
        && !network.password_hidden
            ? network.password || ""
            : ""
    );

    const security = (
        network.seguranca
        || "WPA2-PSK-AES"
    );

    return `
        <article class="panel ssid-card ${network.ativo ? "ssid-online" : "ssid-offline"}">
            <div class="ssid-card-head">
                <div class="ssid-title">
                    <span class="ssid-icon">
                        <span class="material-symbols-outlined">wifi</span>
                    </span>
                    <div>
                        <strong>${escapeHtml(network.ssid ?? "Sem nome")}</strong>
                        <small>${escapeHtml(network.id ?? "-")} • ${escapeHtml(network.banda ?? "-")}</small>
                    </div>
                </div>

                <span class="badge ${network.ativo ? "badge-success" : "badge-danger"}">
                    ${network.ativo ? "ATIVA" : "DESATIVADA"}
                </span>
            </div>

            <form
                class="ssid-form"
                data-ssid-id="${escapeHtml(network.id ?? "")}"
                data-original-password="${escapeHtml(passwordValue)}"
            >
                <div class="ssid-meta">
                    <span class="meta-pill">${escapeHtml(network.banda ?? "-")}</span>
                    <span class="meta-pill">${escapeHtml(security)}</span>
                    <span class="meta-pill">MAX ${escapeHtml(network.max_clientes ?? "-")}</span>
                </div>

                <div class="form-grid two-fields">
                    <div class="form-group">
                        <label>Nome da rede</label>
                        <input
                            data-field="ssid"
                            type="text"
                            maxlength="32"
                            value="${escapeHtml(network.ssid ?? "")}"
                            required
                        >
                    </div>

                    <div class="form-group">
                        <label>Segurança</label>
                        ${securitySelect(security)}
                    </div>

                    <div class="form-group">
                        <label>Senha Wi-Fi</label>
                        <div class="ssid-password-wrap">
                            <input
                                data-field="password"
                                type="${wifiPasswordsRevealed ? "text" : "password"}"
                                value="${escapeHtml(passwordValue)}"
                                placeholder="${wifiPasswordsRevealed ? "Senha atual" : "Deixe vazio para manter"}"
                                autocomplete="new-password"
                            >
                            <span class="password-state">
                                ${wifiPasswordsRevealed ? "visível" : "protegida"}
                            </span>
                        </div>
                    </div>

                    <div class="form-group">
                        <label>Máx. clientes</label>
                        <input
                            data-field="max_clients"
                            type="number"
                            min="1"
                            max="64"
                            value="${escapeHtml(network.max_clientes ?? 32)}"
                        >
                    </div>
                </div>

                <div class="switch-row">
                    ${switchField(
                        "SSID ativo",
                        "enabled",
                        network.ativo
                    )}

                    ${switchField(
                        "Broadcast",
                        "broadcast",
                        network.broadcast !== false
                    )}

                    ${switchField(
                        "Isolamento",
                        "isolation",
                        network.isolamento
                    )}
                </div>

                <div class="form-footer">
                    <div class="ssid-footnote">
                        <span class="material-symbols-outlined">shield_lock</span>
                        <span>Read → modify → write, preservando os demais campos.</span>
                    </div>

                    <button class="button primary" type="submit">
                        <span class="material-symbols-outlined">save</span>
                        Aplicar SSID
                    </button>
                </div>
            </form>
        </article>
    `;
}


async function applySsidForm(event) {
    event.preventDefault();

    const form = event.currentTarget;
    const ssidId = form.dataset.ssidId;

    const passwordInput = form.querySelector(
        '[data-field="password"]'
    );

    const password = passwordInput.value;
    const originalPassword = form.dataset.originalPassword || "";

    const payload = {
        enabled: form.querySelector('[data-field="enabled"]').checked,
        ssid: form.querySelector('[data-field="ssid"]').value.trim(),
        broadcast: form.querySelector('[data-field="broadcast"]').checked,
        isolation: form.querySelector('[data-field="isolation"]').checked,
        max_clients: Number(
            form.querySelector('[data-field="max_clients"]').value
        ),
        encryption: form.querySelector('[data-field="encryption"]').value
    };

    // Senha mascarada nunca é reenviada como se fosse senha real. Quando a
    // senha está oculta, input vazio = manter a atual. Quando está revelada,
    // só mandamos se o atendente realmente alterou o valor.
    if (
        password
        && (
            !wifiPasswordsRevealed
            || password !== originalPassword
        )
    ) {
        payload.password = password;
    }

    setBusy(
        true,
        `Aplicando ${payload.ssid || ssidId}...`
    );

    try {
        await apiRequest(
            "/wifi/network/update",
            {
                method: "POST",
                body: JSON.stringify({
                    ssid_id: ssidId,
                    ...payload
                })
            }
        );

        showToast(
            "SSID atualizado e confirmado pela ONT."
        );

        await loadWifi();
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


async function renderWifiRadios(radios) {
    const page = document.getElementById(
        "wifiRadios"
    );

    if (!radios.length) {
        page.innerHTML = (
            '<div class="panel">Nenhum rádio encontrado.</div>'
        );

        return;
    }

    page.innerHTML = radios
        .map(
            renderRadioEditor
        )
        .join("");

    for (const radio of radios) {
        await fillChannelSelect(
            radio.banda,
            radio.largura,
            radio.canal_automatico
                ? "Auto"
                : radio.canal,
            radio.pais || "BRI",
            "radio"
        );
    }

    document
        .querySelectorAll(
            ".radio-form"
        )
        .forEach(
            form => {
                form.addEventListener(
                    "submit",
                    applyRadioForm
                );

                const bandwidth = form.querySelector(
                    '[data-field="bandwidth"]'
                );

                bandwidth.addEventListener(
                    "change",
                    async () => {
                        await fillChannelSelect(
                            form.dataset.band,
                            bandwidth.value,
                            "Auto",
                            form.querySelector('[data-field="country"]').value,
                            "radio"
                        );
                    }
                );
            }
        );

    document
        .querySelectorAll(
            ".radio-power-switch"
        )
        .forEach(
            input => {
                input.addEventListener(
                    "change",
                    changeRadioPower
                );
            }
        );
}


// Hooks de extensão: advanced.js adiciona controles sem duplicar o renderer
// base nem o fluxo de submit do console principal.
function renderRadioAdvancedFields(radio) {
    return "";
}


function collectRadioFormPayload(
    form,
    channelValue
) {
    return {
        auto_channel: channelValue === "Auto",
        channel: channelValue === "Auto"
            ? null
            : Number(channelValue),
        bandwidth: form.querySelector('[data-field="bandwidth"]').value,
        standard: form.querySelector('[data-field="standard"]').value,
        country: form.querySelector('[data-field="country"]').value.trim(),
        tx_power: form.querySelector('[data-field="tx_power"]').value,
        beacon_interval: Number(
            form.querySelector('[data-field="beacon_interval"]').value
        ),
        sgi: form.querySelector('[data-field="sgi"]').checked
    };
}


function renderBandSteeringAdvanced(params) {
    return "";
}


function bindBandSteeringAdvanced(params) {
    return undefined;
}


function renderRadioEditor(radio) {
    const key = bandKey(
        radio.banda
    );

    return `
        <article class="panel radio-card">
            <div class="radio-card-hero">
                <div>
                    <span class="section-kicker">RF ${escapeHtml(radio.banda)}</span>
                    <h3>${escapeHtml(radio.id ?? "Rádio")}</h3>
                    <p>
                        Canal <strong>${escapeHtml(radio.canal_automatico ? "Auto" : radio.canal)}</strong>
                        • ${escapeHtml(radio.largura ?? "-")}
                        • ${escapeHtml(radio.padrao ?? "-")}
                    </p>
                </div>

                <label class="power-toggle" title="Liga/desliga o rádio">
                    <span>${radio.radio_ativo ? "ON" : "OFF"}</span>
                    <span class="switch">
                        <input
                            class="radio-power-switch"
                            data-band="${escapeHtml(radio.banda)}"
                            type="checkbox"
                            ${radio.radio_ativo ? "checked" : ""}
                        >
                        <span class="switch-slider"></span>
                    </span>
                </label>
            </div>

            <form class="radio-form" data-band="${escapeHtml(radio.banda)}">
                <div class="form-grid two-fields">
                    <div class="form-group">
                        <label>Canal</label>
                        <select id="radioChannel-${key}" data-field="channel"></select>
                    </div>

                    <div class="form-group">
                        <label>Largura</label>
                        ${bandwidthSelect(radio.banda, radio.largura, "bandwidth")}
                    </div>

                    <div class="form-group">
                        <label>Modo</label>
                        ${standardSelect(radio.banda, radio.padrao, "standard")}
                    </div>

                    <div class="form-group">
                        <label>Região</label>
                        <input data-field="country" type="text" value="${escapeHtml(radio.pais ?? "BRI")}">
                    </div>

                    <div class="form-group">
                        <label>Potência</label>
                        ${powerSelect(radio.potencia, "tx_power")}
                    </div>

                    <div class="form-group">
                        <label>Beacon interval</label>
                        <input
                            data-field="beacon_interval"
                            type="number"
                            min="100"
                            max="1000"
                            value="${escapeHtml(radio.beacon_interval ?? 100)}"
                        >
                    </div>
                </div>

                <div class="radio-capabilities">
                    ${capabilityPill("SGI", radio.sgi)}
                    ${capabilityPill("MU-MIMO", radio.mu_mimo)}
                    ${capabilityPill("DL OFDMA", radio.downlink_ofdma)}
                    ${capabilityPill("TWT", radio.twt)}
                </div>

                <label class="check-row">
                    <input
                        data-field="sgi"
                        type="checkbox"
                        ${radio.sgi ? "checked" : ""}
                    >
                    <span>SGI habilitado</span>
                </label>

                ${renderRadioAdvancedFields(radio)}

                <div class="radio-form-footer">
                    <span class="radio-id">
                        ${escapeHtml(radio.sideband ?? "-")} • TX ${escapeHtml(radio.potencia ?? "-")}
                    </span>

                    <button class="button primary" type="submit">
                        <span class="material-symbols-outlined">tune</span>
                        Aplicar RF
                    </button>
                </div>
            </form>
        </article>
    `;
}


async function changeRadioPower(event) {
    const input = event.currentTarget;
    const band = input.dataset.band;
    const enabled = input.checked;

    input.disabled = true;

    setBusy(
        true,
        `${enabled ? "Ativando" : "Desativando"} rádio ${band}...`
    );

    try {
        await apiRequest(
            "/wifi/power/update",
            {
                method: "POST",
                body: JSON.stringify({
                    band,
                    enabled
                })
            }
        );

        showToast(
            `Rádio ${band} ${enabled ? "ativado" : "desativado"}.`
        );

        await loadWifi();
    } catch (error) {
        input.checked = !enabled;

        showToast(
            error.message
        );
    } finally {
        input.disabled = false;
        setBusy(false);
    }
}


async function applyRadioForm(event) {
    event.preventDefault();

    const form = event.currentTarget;
    const band = form.dataset.band;

    const channelValue = form.querySelector(
        '[data-field="channel"]'
    ).value;

    const payload = collectRadioFormPayload(
        form,
        channelValue
    );

    setBusy(
        true,
        `Aplicando Wi-Fi ${band}...`
    );

    try {
        await apiRequest(
            "/wifi/radio/update",
            {
                method: "POST",
                body: JSON.stringify({
                    band,
                    ...payload
                })
            }
        );

        showToast(
            `Wi-Fi ${band} atualizado.`
        );

        await loadWifi();
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


function renderWpsControls(items) {
    const container = document.getElementById(
        "wpsControls"
    );

    if (!items.length) {
        container.innerHTML = `
            <article class="panel feature-unavailable">
                <span class="material-symbols-outlined">lock</span>
                <div>
                    <strong>WPS não retornado pelo firmware</strong>
                    <p>Esta conta pode não ter permissão para o menu.</p>
                </div>
            </article>
        `;

        return;
    }

    container.innerHTML = items
        .map(
            item => `
                <article class="panel wps-card">
                    <div class="feature-card-title">
                        <span class="feature-icon"><span class="material-symbols-outlined">lock_reset</span></span>
                        <div>
                            <span class="section-kicker">${escapeHtml(item.band ?? "WIFI")}</span>
                            <h3>WPS ${escapeHtml(item.band ?? "")}</h3>
                        </div>
                        <span class="badge ${item.enabled ? "badge-warning" : "badge-success"}">
                            ${escapeHtml(item.mode ?? "Disabled")}
                        </span>
                    </div>

                    <p class="feature-description">
                        PBC inicia pareamento sem precisar expor PIN. Para atendimento, mantenha desativado quando não estiver em uso.
                    </p>

                    <div class="segmented-actions">
                        <button
                            class="button ${item.mode === "Disabled" ? "primary" : "ghost"} wps-action"
                            data-band="${escapeHtml(item.band ?? "")}"
                            data-mode="Disabled"
                            type="button"
                        >
                            Desativar
                        </button>
                        <button
                            class="button ${item.mode === "PBC" ? "primary" : "ghost"} wps-action"
                            data-band="${escapeHtml(item.band ?? "")}"
                            data-mode="PBC"
                            type="button"
                        >
                            Iniciar PBC
                        </button>
                    </div>
                </article>
            `
        )
        .join("");

    document
        .querySelectorAll(
            ".wps-action"
        )
        .forEach(
            button => {
                button.addEventListener(
                    "click",
                    applyWpsMode
                );
            }
        );
}


async function applyWpsMode(event) {
    const button = event.currentTarget;
    const band = button.dataset.band;
    const mode = button.dataset.mode;

    setBusy(
        true,
        mode === "PBC"
            ? `Iniciando WPS PBC em ${band}...`
            : `Desativando WPS em ${band}...`
    );

    try {
        await apiRequest(
            "/wifi/wps/update",
            {
                method: "POST",
                body: JSON.stringify({
                    band,
                    mode
                })
            }
        );

        showToast(
            mode === "PBC"
                ? `WPS PBC iniciado em ${band}.`
                : `WPS desativado em ${band}.`
        );

        cachedWps = await apiRequest(
            "/wifi/wps"
        );

        renderWpsControls(
            cachedWps
        );
    } catch (error) {
        showToast(
            error.message
        );
    } finally {
        setBusy(false);
    }
}


async function fillChannelSelect(
    band,
    bandwidth,
    selected,
    country,
    mode
) {
    const prefix = mode === "profile"
        ? "profileChannel"
        : "radioChannel";

    const select = document.getElementById(
        `${prefix}-${bandKey(band)}`
    );

    if (!select) {
        return;
    }

    select.innerHTML = '<option value="Auto">Auto</option>';

    try {
        const query = new URLSearchParams({
            band,
            bandwidth,
            country: country || "BRI"
        });

        const data = await apiRequest(
            `/wifi/channels?${query.toString()}`
        );

        const channels = [];

        for (const config of data || []) {
            for (const channel of config.canais || []) {
                if (!channels.includes(channel)) {
                    channels.push(channel);
                }
            }
        }

        channels.sort(
            (a, b) => Number(a) - Number(b)
        );

        for (const channel of channels) {
            const option = document.createElement(
                "option"
            );

            option.value = channel;
            option.textContent = channel;
            select.appendChild(
                option
            );
        }

        const desired = String(
            selected ?? "Auto"
        );

        if (
            [...select.options].some(
                option => option.value === desired
            )
        ) {
            select.value = desired;
        } else {
            select.value = "Auto";
        }
    } catch (error) {
        console.error(
            "Falha ao carregar canais:",
            error
        );

        select.value = "Auto";
    }
}


function securitySelect(selected) {
    const options = [
        "WPA2-PSK-AES",
        "WPA2/WPA3-SAE",
        "WPA2-PSK-AES/WPA3-SAE-AES",
        "WPA3-SAE",
        "WPA/WPA2-PSK-AES",
        "WPA/WPA2-PSK-TKIP/AES",
        "WPA-PSK-AES",
        "No Security"
    ];

    if (
        selected
        && !options.includes(selected)
    ) {
        options.unshift(
            selected
        );
    }

    return `
        <select data-field="encryption">
            ${options.map(
                option => `
                    <option
                        value="${escapeHtml(option)}"
                        ${option === selected ? "selected" : ""}
                    >
                        ${escapeHtml(option)}
                    </option>
                `
            ).join("")}
        </select>
    `;
}


function switchField(
    label,
    field,
    checked
) {
    return `
        <label class="switch-field">
            <span>${escapeHtml(label)}</span>
            <span class="switch">
                <input
                    data-field="${escapeHtml(field)}"
                    type="checkbox"
                    ${checked ? "checked" : ""}
                >
                <span class="switch-slider"></span>
            </span>
        </label>
    `;
}


function capabilityPill(
    label,
    enabled
) {
    return `
        <span class="capability-pill ${enabled ? "enabled" : ""}">
            <i></i>
            ${escapeHtml(label)}
        </span>
    `;
}


// =========================================================
// DNS
// =========================================================

async function loadDns() {
    const data = await apiRequest(
        "/dns/status"
    );

    const hosts = Array.isArray(
        data.hosts
    )
        ? data.hosts
        : [];

    const hostsHtml = hosts.length
        ? hosts
            .map(
                host => infoRow(
                    host.nome || "Nome",
                    host.ip
                )
            )
            .join("")
        : infoRow(
            "Nomes estáticos",
            "Nenhum"
        );

    document.getElementById(
        "dashboardDns"
    ).innerHTML = `
        ${infoRow("Domínio", data.domain_name)}
        ${infoRow("IPv4 1", data.ipv4_1)}
        ${infoRow("IPv4 2", data.ipv4_2)}
        ${infoRow("IPv6 1", data.ipv6_1)}
        ${infoRow("IPv6 2", data.ipv6_2)}
        ${hostsHtml}
    `;

    return data;
}


// =========================================================
// DIAGNÓSTICOS
// =========================================================

function populateDiagnosticInterfaces(connections) {
    for (const id of [
        "pingInterface",
        "traceInterface"
    ]) {
        const select = document.getElementById(
            id
        );

        select.innerHTML = (
            '<option value="">Rota padrão</option>'
        );

        for (const wan of connections) {
            if (!wan.id) {
                continue;
            }

            const option = document.createElement(
                "option"
            );

            option.value = wan.id;
            option.textContent = (
                `${wan.nome || wan.id} ${wan.ip ? `(${wan.ip})` : ""}`
            );

            select.appendChild(
                option
            );
        }
    }
}


document
    .getElementById(
        "pingForm"
    )
    .addEventListener(
        "submit",
        async event => {
            event.preventDefault();

            const output = document.getElementById(
                "pingOutput"
            );

            const payload = {
                host: document.getElementById("pingHost").value.trim(),
                interface: document.getElementById("pingInterface").value,
                ip_version: document.getElementById("pingIpVersion").value
            };

            output.textContent = "Executando ping pela ONT...";
            setBusy(
                true,
                "Executando ping..."
            );

            try {
                const data = await apiRequest(
                    "/diagnostics/ping",
                    {
                        method: "POST",
                        body: JSON.stringify(payload)
                    }
                );

                output.textContent = formatDiagnosticResult(
                    data
                );
            } catch (error) {
                output.textContent = `ERRO: ${error.message}`;
            } finally {
                setBusy(
                    false
                );
            }
        }
    );


document
    .getElementById(
        "tracerouteForm"
    )
    .addEventListener(
        "submit",
        async event => {
            event.preventDefault();

            const output = document.getElementById(
                "tracerouteOutput"
            );

            const payload = {
                host: document.getElementById("traceHost").value.trim(),
                interface: document.getElementById("traceInterface").value,
                protocol: document.getElementById("traceProtocol").value,
                max_hops: Number(document.getElementById("traceHops").value),
                timeout: Number(document.getElementById("traceTimeout").value),
                ip_version: "IPv4"
            };

            output.textContent = "Executando traceroute pela ONT...";
            setBusy(
                true,
                "Executando traceroute..."
            );

            try {
                const data = await apiRequest(
                    "/diagnostics/traceroute",
                    {
                        method: "POST",
                        body: JSON.stringify(payload)
                    }
                );

                output.textContent = formatDiagnosticResult(
                    data
                );
            } catch (error) {
                output.textContent = `ERRO: ${error.message}`;
            } finally {
                setBusy(
                    false
                );
            }
        }
    );


function formatDiagnosticResult(data) {
    const lines = [];

    if (data.host) {
        lines.push(`Host: ${data.host}`);
    }

    if (data.interface) {
        lines.push(`Interface: ${data.interface}`);
    }

    if (data.ip_version) {
        lines.push(`IP: ${data.ip_version}`);
    }

    if (data.protocol) {
        lines.push(`Protocolo: ${data.protocol}`);
    }

    if (data.minimo_ms !== undefined) {
        lines.push(`Mínimo: ${data.minimo_ms ?? "-"} ms`);
        lines.push(`Médio: ${data.medio_ms ?? "-"} ms`);
        lines.push(`Máximo: ${data.maximo_ms ?? "-"} ms`);
        lines.push(`Sucesso: ${data.sucesso ?? "-"}`);
        lines.push(`Falha: ${data.falha ?? "-"}`);
    }

    if (data.hops !== undefined) {
        lines.push(`Hops: ${data.hops ?? "-"}`);
    }

    lines.push("");
    lines.push(data.resultado || "Sem resultado retornado.");

    return lines.join(
        "\n"
    );
}


// =========================================================
// PERFIS DO ATENDENTE
// =========================================================

async function loadProfile() {
    if (!currentAttendant) {
        return;
    }

    currentProfile = await apiRequest(
        "/profiles/get",
        {
            method: "POST",
            body: JSON.stringify({
                attendant: currentAttendant
            })
        }
    );

    document.getElementById(
        "profileAttendant"
    ).textContent = currentAttendant;

    document.getElementById(
        "dashboardProfileName"
    ).textContent = currentAttendant;

    await renderProfileForm(
        currentProfile
    );
}


async function renderProfileForm(profile) {
    const wifi = profile.wifi || {};

    // O container de perfil começa vazio no template. No Vela a página é
    // injetada no shell e, por isso, não podemos assumir que os cards de rádio
    // já existem no DOM. Primeiro criamos a estrutura e só depois buscamos os
    // campos internos com querySelector().
    const radiosContainer = document.getElementById(
        "profileRadios"
    );

    if (!radiosContainer) {
        throw new Error(
            "Área de configuração padrão não encontrada na interface."
        );
    }

    const bands = [
        "2.4GHz",
        "5GHz"
    ];

    radiosContainer.innerHTML = bands
        .map(
            band => `
                <article
                    class="panel radio-card profile-radio-card"
                    data-profile-band="${escapeHtml(band)}"
                >
                    <div class="radio-card-hero">
                        <div>
                            <span class="section-kicker">PERFIL WI-FI</span>
                            <h3>${escapeHtml(band)}</h3>
                            <p>Configuração padrão aplicada por este atendente.</p>
                        </div>

                        <span class="badge badge-neutral">
                            Padrão
                        </span>
                    </div>

                    <div class="profile-fields"></div>
                </article>
            `
        )
        .join("");

    for (const band of bands) {
        const card = radiosContainer.querySelector(
            `[data-profile-band="${band}"]`
        );

        if (!card) {
            throw new Error(
                `Card do perfil ${band} não foi criado.`
            );
        }

        const container = card.querySelector(
            ".profile-fields"
        );

        if (!container) {
            throw new Error(
                `Campos do perfil ${band} não foram criados.`
            );
        }

        const config = wifi[band] || {};

        container.innerHTML = profileRadioFields(
            band,
            config
        );

        await fillChannelSelect(
            band,
            config.bandwidth || defaultBandwidth(band),
            config.auto_channel
                ? "Auto"
                : config.channel,
            config.country || "BRI",
            "profile"
        );

        const bandwidth = container.querySelector(
            '[data-field="bandwidth"]'
        );

        bandwidth.addEventListener(
            "change",
            async () => {
                await fillChannelSelect(
                    band,
                    bandwidth.value,
                    "Auto",
                    container.querySelector('[data-field="country"]').value,
                    "profile"
                );
            }
        );
    }

    const dns = profile.dns || {};

    document.getElementById(
        "profileDomainName"
    ).value = dns.domain_name || "";

    document.getElementById(
        "profileDns4_1"
    ).value = dns.ipv4_1 || "";

    document.getElementById(
        "profileDns4_2"
    ).value = dns.ipv4_2 || "";

    document.getElementById(
        "profileDns6_1"
    ).value = dns.ipv6_1 || "";

    document.getElementById(
        "profileDns6_2"
    ).value = dns.ipv6_2 || "";

    renderProfileHosts(
        Array.isArray(dns.hosts)
            ? dns.hosts
            : []
    );
}


function renderProfileHosts(hosts) {
    const container = document.getElementById(
        "profileHosts"
    );

    container.innerHTML = "";

    if (!hosts.length) {
        addProfileHostRow();
        return;
    }

    for (const host of hosts) {
        addProfileHostRow(
            host
        );
    }
}


function addProfileHostRow(
    host = {}
) {
    const container = document.getElementById(
        "profileHosts"
    );

    const row = document.createElement(
        "div"
    );

    row.className = "profile-host-row";

    row.innerHTML = `
        <div class="form-group">
            <label>Nome</label>
            <input
                data-host-field="name"
                type="text"
                placeholder="cloudflare"
                value="${escapeHtml(host.nome || "")}"
            >
        </div>

        <div class="form-group">
            <label>Endereço IP</label>
            <input
                data-host-field="ip"
                type="text"
                placeholder="1.1.1.1"
                value="${escapeHtml(host.ip || "")}"
            >
        </div>

        <button
            class="button button-danger button-small profile-host-remove"
            type="button"
            title="Remover entrada"
        >
            Remover
        </button>
    `;

    row.querySelector(
        ".profile-host-remove"
    ).addEventListener(
        "click",
        () => row.remove()
    );

    container.appendChild(
        row
    );
}


function collectProfileHosts() {
    const hosts = [];

    document
        .querySelectorAll(
            "#profileHosts .profile-host-row"
        )
        .forEach(
            row => {
                const nome = row.querySelector(
                    '[data-host-field="name"]'
                ).value.trim();

                const ip = row.querySelector(
                    '[data-host-field="ip"]'
                ).value.trim();

                // Linha totalmente vazia é apenas um espaço para novo cadastro.
                if (!nome && !ip) {
                    return;
                }

                hosts.push({
                    nome,
                    ip
                });
            }
        );

    return hosts;
}


function profileRadioFields(
    band,
    config
) {
    const key = bandKey(
        band
    );

    return `
        <div class="form-grid two-fields">
            <div class="form-group">
                <label>Canal</label>
                <select id="profileChannel-${key}" data-field="channel"></select>
            </div>

            <div class="form-group">
                <label>Largura</label>
                ${bandwidthSelect(band, config.bandwidth || defaultBandwidth(band), "bandwidth")}
            </div>

            <div class="form-group">
                <label>Modo</label>
                ${standardSelect(band, config.standard || defaultStandard(band), "standard")}
            </div>

            <div class="form-group">
                <label>País</label>
                <input
                    data-field="country"
                    type="text"
                    value="${escapeHtml(config.country || "BRI")}"
                >
            </div>

            <div class="form-group">
                <label>Potência</label>
                ${powerSelect(config.tx_power || "100%", "tx_power")}
            </div>

            <div class="form-group">
                <label>Beacon interval</label>
                <input
                    data-field="beacon_interval"
                    type="number"
                    min="100"
                    max="1000"
                    value="${escapeHtml(config.beacon_interval ?? 100)}"
                >
            </div>
        </div>

        <label class="checkbox-container">
            <input
                data-field="sgi"
                type="checkbox"
                ${config.sgi ? "checked" : ""}
            >
            <span>SGI habilitado</span>
        </label>
    `;
}


function collectProfileForm() {
    const wifi = {};

    for (const band of [
        "2.4GHz",
        "5GHz"
    ]) {
        const card = document.querySelector(
            `[data-profile-band="${band}"]`
        );

        const channel = card.querySelector(
            '[data-field="channel"]'
        ).value;

        wifi[band] = {
            auto_channel: channel === "Auto",
            channel: channel === "Auto"
                ? null
                : Number(channel),
            standard: card.querySelector('[data-field="standard"]').value,
            country: card.querySelector('[data-field="country"]').value.trim(),
            bandwidth: card.querySelector('[data-field="bandwidth"]').value,
            sgi: card.querySelector('[data-field="sgi"]').checked,
            beacon_interval: Number(
                card.querySelector('[data-field="beacon_interval"]').value
            ),
            tx_power: card.querySelector('[data-field="tx_power"]').value
        };
    }

    return {
        wifi,
        dns: {
            domain_name: document.getElementById("profileDomainName").value.trim(),
            ipv4_1: document.getElementById("profileDns4_1").value.trim(),
            ipv4_2: document.getElementById("profileDns4_2").value.trim(),
            ipv6_1: document.getElementById("profileDns6_1").value.trim(),
            ipv6_2: document.getElementById("profileDns6_2").value.trim(),
            hosts: collectProfileHosts()
        }
    };
}


async function saveProfile(
    quiet = false
) {
    if (!currentAttendant) {
        return null;
    }

    const profile = collectProfileForm();

    setBusy(
        true,
        "Salvando perfil..."
    );

    try {
        currentProfile = await apiRequest(
            "/profiles/save",
            {
                method: "POST",
                body: JSON.stringify({
                    attendant: currentAttendant,
                    ...profile
                })
            }
        );

        if (!quiet) {
            showToast(
                `Perfil de ${currentAttendant} salvo.`
            );
        }

        return currentProfile;
    } catch (error) {
        if (!quiet) {
            showToast(
                error.message
            );
        }

        throw error;
    } finally {
        setBusy(
            false
        );
    }
}


async function captureCurrentConfiguration() {
    if (!currentAttendant) {
        return;
    }

    setBusy(
        true,
        "Lendo configuração atual..."
    );

    try {
        // O backend lê a ONT e persiste a captura pelo Repository Pattern.
        // Assim o botão realmente transforma a configuração atual no padrão
        // daquele atendente, sem depender de um segundo clique em Salvar.
        const config = await apiRequest(
            "/profiles/capture",
            {
                method: "POST",
                body: JSON.stringify({
                    attendant: currentAttendant
                })
            }
        );

        currentProfile = config;

        await renderProfileForm(
            config
        );

        showToast(
            "Configuração atual salva como padrão do atendente."
        );
    } finally {
        setBusy(
            false
        );
    }
}


async function applyProfile() {
    if (!currentAttendant) {
        return;
    }

    try {
        // Salva primeiro o conteúdo atual da tela para o botão sempre aplicar
        // exatamente o perfil que o atendente está vendo.
        await saveProfile(
            true
        );

        setBusy(
            true,
            "Aplicando configuração padrão..."
        );

        const result = await apiRequest(
            "/profiles/apply",
            {
                method: "POST",
                body: JSON.stringify({
                    attendant: currentAttendant
                })
            }
        );

        renderProfileApplyResult(
            result
        );

        if (result.success) {
            showToast(
                "Configuração padrão aplicada."
            );
        } else {
            showToast(
                "O perfil foi aplicado parcialmente. Veja o relatório."
            );
        }

        await loadWifi();
        await loadDns();
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


function renderProfileApplyResult(result) {
    const container = document.getElementById(
        "profileApplyResult"
    );

    const steps = result.steps || [];

    if (!steps.length) {
        container.innerHTML = (
            '<div class="loading">Nenhuma etapa executada.</div>'
        );

        return;
    }

    container.innerHTML = steps
        .map(
            step => `
                <div class="result-step">
                    <div>
                        <strong>${escapeHtml(step.name)}</strong>
                        <p>${escapeHtml(step.detail)}</p>
                    </div>

                    <span class="badge ${step.success ? "badge-success" : "badge-danger"}">
                        ${step.success ? "OK" : "Falhou"}
                    </span>
                </div>
            `
        )
        .join("");
}



// =========================================================
// DEVICE MANAGEMENT
// =========================================================

async function loadAccounts() {
    const container = document.getElementById(
        "accountDetails"
    );

    try {
        const accounts = await apiRequest(
            "/device/accounts"
        );

        if (!Array.isArray(accounts) || !accounts.length) {
            container.innerHTML = (
                '<div class="loading">Nenhuma conta visível.</div>'
            );

            return [];
        }

        container.innerHTML = accounts
            .map(
                account => `
                    <div class="account-row">
                        <span class="account-avatar">
                            <span class="material-symbols-outlined">person</span>
                        </span>
                        <div>
                            <strong>${escapeHtml(account.username ?? "-")}</strong>
                            <small>Right ${escapeHtml(account.right ?? "-")} • ${account.enabled ? "habilitada" : "desabilitada"}</small>
                        </div>
                        ${account.current ? '<span class="badge badge-success">SESSÃO ATUAL</span>' : ''}
                    </div>
                `
            )
            .join("");

        return accounts;
    } catch (error) {
        container.innerHTML = `
            <div class="feature-unavailable inline">
                <span class="material-symbols-outlined">manage_accounts</span>
                <div><strong>Account Manager indisponível</strong><p>${escapeHtml(error.message)}</p></div>
            </div>
        `;

        throw error;
    }
}


async function changeAdminPassword(event) {
    event.preventDefault();

    const password = document.getElementById(
        "newAdminPassword"
    ).value;

    const confirmation = document.getElementById(
        "confirmAdminPassword"
    ).value;

    if (password !== confirmation) {
        showToast(
            "As senhas não coincidem."
        );
        return;
    }

    setBusy(
        true,
        "Alterando senha administrativa..."
    );

    try {
        await apiRequest(
            "/device/password",
            {
                method: "POST",
                body: JSON.stringify({
                    new_password: password
                })
            }
        );

        // Mantém o formulário de conexão sincronizado para um novo login.
        document.getElementById(
            "ztePassword"
        ).value = password;

        document.getElementById(
            "adminPasswordForm"
        ).reset();

        showToast(
            "Senha administrativa alterada."
        );

        await loadAccounts();
    } catch (error) {
        showToast(
            error.message
        );
    } finally {
        setBusy(false);
    }
}


async function rebootDevice() {
    const confirmed = window.confirm(
        "Reiniciar a ONT agora? A conexão ficará indisponível durante o boot."
    );

    if (!confirmed) {
        return;
    }

    setBusy(
        true,
        "Enviando comando de reinicialização..."
    );

    try {
        await apiRequest(
            "/device/reboot",
            {
                method: "POST"
            }
        );

        showToast(
            "Reinicialização enviada. Aguarde a ONT voltar."
        );

        setConnectionStatus(
            false
        );

        openPage(
            "connection"
        );
    } catch (error) {
        showToast(
            error.message
        );
    } finally {
        setBusy(false);
    }
}


// =========================================================
// CLIENTES
// =========================================================

async function loadClients() {
    const wifi = await apiRequest(
        "/clients/wifi"
    );

    const lan = await apiRequest(
        "/clients/lan"
    );

    const wifiClients = Array.isArray(wifi)
        ? wifi
        : [];

    const lanClients = Array.isArray(lan)
        ? lan
        : [];

    document.getElementById(
        "wifiClientCount"
    ).textContent = wifiClients.length;

    document.getElementById(
        "lanClientCount"
    ).textContent = lanClients.length;

    document.getElementById(
        "clientTotalKpi"
    ).textContent = wifiClients.length + lanClients.length;

    renderWifiClients(
        wifiClients
    );

    renderLanClients(
        lanClients
    );
}


function renderWifiClients(clients) {
    const tbody = document.getElementById(
        "wifiClientsTable"
    );

    if (!clients.length) {
        tbody.innerHTML = `
            <tr>
                <td colspan="8" class="empty-table">
                    Nenhum cliente Wi-Fi conectado.
                </td>
            </tr>
        `;

        return;
    }

    tbody.innerHTML = clients
        .map(
            client => `
                <tr>
                    <td>${escapeHtml(client.hostname ?? "Desconhecido")}</td>
                    <td>${escapeHtml(client.ip ?? "-")}</td>
                    <td>${escapeHtml(client.mac ?? "-")}</td>
                    <td>${escapeHtml(client.ssid ?? "-")}</td>
                    <td>${client.rssi ? `${escapeHtml(client.rssi)} dBm` : "-"}</td>
                    <td>${escapeHtml(client.snr ?? "-")}</td>
                    <td>${escapeHtml(client.rx_rate ?? "-")}</td>
                    <td>${escapeHtml(client.tx_rate ?? "-")}</td>
                </tr>
            `
        )
        .join("");
}


function renderLanClients(clients) {
    const tbody = document.getElementById(
        "lanClientsTable"
    );

    if (!clients.length) {
        tbody.innerHTML = `
            <tr>
                <td colspan="3" class="empty-table">
                    Nenhum cliente LAN encontrado.
                </td>
            </tr>
        `;

        return;
    }

    tbody.innerHTML = clients
        .map(
            client => `
                <tr>
                    <td>${escapeHtml(client.hostname ?? "Desconhecido")}</td>
                    <td>${escapeHtml(client.ip ?? "-")}</td>
                    <td>${escapeHtml(client.mac ?? "-")}</td>
                </tr>
            `
        )
        .join("");
}


// =========================================================
// COMPONENTES
// =========================================================

function bandwidthSelect(
    band,
    value,
    field
) {
    const options = band === "5GHz"
        ? ["Auto", "20MHz", "40MHz", "80MHz", "160MHz"]
        : ["Auto", "20MHz", "40MHz"];

    return selectHtml(
        options,
        value,
        field
    );
}


function standardSelect(
    band,
    value,
    field
) {
    const options = band === "5GHz"
        ? ["a", "n", "a,n", "ac", "a,n,ac", "a,n,ac,ax"]
        : ["b", "g", "n", "b,g", "g,n", "b,g,n", "b,g,n,ax"];

    return selectHtml(
        options,
        value,
        field
    );
}


function powerSelect(
    value,
    field
) {
    return selectHtml(
        ["100%", "50%"],
        value,
        field
    );
}


function selectHtml(
    options,
    selected,
    field
) {
    return `
        <select data-field="${escapeHtml(field)}">
            ${options.map(
                option => `
                    <option
                        value="${escapeHtml(option)}"
                        ${String(option) === String(selected) ? "selected" : ""}
                    >
                        ${escapeHtml(option)}
                    </option>
                `
            ).join("")}
        </select>
    `;
}


function defaultBandwidth(band) {
    return band === "5GHz"
        ? "80MHz"
        : "20MHz";
}


function defaultStandard(band) {
    return band === "5GHz"
        ? "a,n,ac"
        : "b,g,n";
}


function bandKey(band) {
    return String(band)
        .replace(/\./g, "_")
        .replace(/ /g, "_");
}



function detailTile(
    label,
    value,
    icon = "info"
) {
    return `
        <div class="detail-tile">
            <span class="material-symbols-outlined">${escapeHtml(icon)}</span>
            <div>
                <small>${escapeHtml(label)}</small>
                <strong>${escapeHtml(normalizeValue(value))}</strong>
            </div>
        </div>
    `;
}


function normalizeOpticalPower(value) {
    if (
        value === undefined
        || value === null
        || value === ""
    ) {
        return "-";
    }

    const number = Number(value);

    if (Number.isNaN(number)) {
        return String(value);
    }

    return number.toFixed(2);
}


function formatSeconds(value) {
    if (value === null || value === undefined || value === "") {
        return "-";
    }

    const seconds = Number(value);

    if (Number.isNaN(seconds)) {
        return normalizeValue(value);
    }

    const days = Math.floor(
        seconds / 86400
    );

    const hours = Math.floor(
        (seconds % 86400) / 3600
    );

    if (days > 0) {
        return `${days}d ${hours}h`;
    }

    const minutes = Math.floor(
        (seconds % 3600) / 60
    );

    return `${hours}h ${minutes}m`;
}


function formatBytes(value) {
    if (value === null || value === undefined || value === "") {
        return "-";
    }

    const bytes = Number(value);

    if (
        Number.isNaN(bytes)
        || bytes < 0
    ) {
        return normalizeValue(value);
    }

    if (bytes < 1024) {
        return `${bytes} B`;
    }

    const units = [
        "KB",
        "MB",
        "GB",
        "TB"
    ];

    let current = bytes / 1024;
    let unit = units[0];

    for (let index = 0; index < units.length; index += 1) {
        unit = units[index];

        if (
            current < 1024
            || index === units.length - 1
        ) {
            break;
        }

        current /= 1024;
    }

    return `${current.toFixed(current >= 100 ? 0 : 1)} ${unit}`;
}


function isPortUp(status) {
    const value = String(
        status ?? ""
    ).toLowerCase();

    return [
        "up",
        "1",
        "connected",
        "linkup"
    ].includes(value);
}


function infoRow(
    label,
    value
) {
    return `
        <div class="info-row">
            <span class="info-label">${escapeHtml(label)}</span>
            <span class="info-value">${escapeHtml(normalizeValue(value))}</span>
        </div>
    `;
}


function normalizeValue(value) {
    if (
        value === undefined
        || value === null
        || value === ""
    ) {
        return "-";
    }

    return String(
        value
    );
}


function isWanConnected(status) {
    if (!status) {
        return false;
    }

    const normalized = String(status)
        .toLowerCase();

    return (
        normalized === "connected"
        || normalized === "up"
        || normalized === "1"
    );
}


function statusBadge(status) {
    const connected = isWanConnected(
        status
    );

    return `
        <span class="badge ${connected ? "badge-success" : "badge-danger"}">
            ${escapeHtml(status ?? "Desconectado")}
        </span>
    `;
}


function escapeHtml(value) {
    if (
        value === undefined
        || value === null
    ) {
        return "";
    }

    return String(value)
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;")
        .replace(/'/g, "&#039;");
}


// =========================================================
// UI ZOOM
// =========================================================

const UI_ZOOM_KEY = "zteAutomatic.uiZoom";
const UI_ZOOM_MIN = 0.8;
const UI_ZOOM_MAX = 1.6;
const UI_ZOOM_STEP = 0.1;

let uiZoom = 1;


function clampUiZoom(value) {
    return Math.min(
        UI_ZOOM_MAX,
        Math.max(
            UI_ZOOM_MIN,
            Number(value) || 1
        )
    );
}


function applyUiZoom(
    value,
    persist = true
) {
    uiZoom = clampUiZoom(
        value
    );

    // Não aplicar zoom ao elemento raiz: no QtWebEngine o viewport
    // também é ampliado e os botões da direita ficam fora da janela.
    // Compensar largura do body mantém a aparência do console intacta.
    document.documentElement.style.zoom = "";
    document.body.style.zoom = String(uiZoom);
    document.body.style.width = `${100 / uiZoom}%`;
    document.body.style.maxWidth = `${100 / uiZoom}%`;
    document.documentElement.style.setProperty("--app-zoom", String(uiZoom));

    const level = document.getElementById(
        "zoomLevel"
    );

    if (level) {
        level.textContent = `${Math.round(uiZoom * 100)}%`;
    }

    if (persist) {
        try {
            localStorage.setItem(
                UI_ZOOM_KEY,
                String(uiZoom)
            );
        } catch (error) {
            console.warn(
                "Não foi possível persistir o zoom:",
                error
            );
        }
    }
}


function changeUiZoom(delta) {
    applyUiZoom(
        Math.round(
            (uiZoom + delta) * 10
        ) / 10
    );
}


function loadUiZoom() {
    let saved = 1;

    try {
        saved = Number(
            localStorage.getItem(
                UI_ZOOM_KEY
            )
        ) || 1;
    } catch (error) {
        console.warn(
            "Não foi possível ler o zoom salvo:",
            error
        );
    }

    applyUiZoom(
        saved,
        false
    );
}


function setRefreshBusy(busy) {
    const button = document.getElementById(
        "refreshButton"
    );

    if (!button) {
        return;
    }

    button.disabled = busy;

    button.classList.toggle(
        "is-loading",
        busy
    );

    button.title = busy
        ? "Atualizando dados..."
        : "Atualizar dados";

    button.setAttribute(
        "aria-label",
        button.title
    );

    // Não trocamos mais o conteúdo do botão por texto. O botão tem largura
    // fixa e isso causava o 'Atualizar' sobrepor o chip do equipamento.
}


// =========================================================
// LOAD ALL
// =========================================================

async function loadAll() {
    if (!ontConnected) {
        return;
    }

    const refreshButton = document.getElementById(
        "refreshButton"
    );

    setRefreshBusy(
        true
    );

    try {
        // Não executamos em paralelo. O firmware guarda a view atual dentro
        // da sessão e cada leitura precisa manter seu fluxo menuView->menuData.
        const loaders = [
            ["equipamento", loadDevice],
            ["óptico", loadOptical],
            ["WAN", loadWan],
            ["PPPoE", () => loadPppoe(false)],
            ["portas LAN", loadLanPorts],
            ["UPnP", loadUpnp],
            ["Wi-Fi", loadWifi],
            ["DNS", loadDns],
            ["clientes", loadClients],
            ["contas", loadAccounts]
        ];

        const failed = [];

        for (const [name, loader] of loaders) {
            try {
                await loader();
            } catch (error) {
                failed.push({
                    name,
                    error
                });

                console.error(
                    `Falha ao carregar ${name}:`,
                    error
                );
            }
        }

        // Extensões carregadas depois do app.js podem registrar uma triagem
        // adicional sem duplicar o fluxo principal nem disputar a sessão
        // ThinkLua em paralelo.
        if (
            typeof window.loadDashboardSupportHealth === "function"
        ) {
            try {
                await window.loadDashboardSupportHealth();
            } catch (error) {
                console.warn(
                    "Triagem automática do Dashboard indisponível:",
                    error
                );
            }
        }

        if (!failed.length) {
            showToast(
                "Dados atualizados."
            );
        } else {
            showToast(
                `${failed.length} consulta(s) falharam. Veja o console.`
            );
        }
    } finally {
        setRefreshBusy(
            false
        );
    }
}


// =========================================================
// EVENTOS
// =========================================================

document
    .querySelectorAll(
        ".menu-item"
    )
    .forEach(
        button => {
            button.addEventListener(
                "click",
                () => openPage(
                    button.dataset.page
                )
            );
        }
    );


document
    .getElementById(
        "refreshButton"
    )
    .addEventListener(
        "click",
        loadAll
    );


document
    .getElementById(
        "revealPppoeButton"
    )
    .addEventListener(
        "click",
        async () => {
            setBusy(
                true,
                pppoeRevealed
                    ? "Ocultando senha PPPoE..."
                    : "Lendo senha PPPoE..."
            );

            try {
                await loadPppoe(
                    !pppoeRevealed
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
    );





document
    .getElementById(
        "revealWifiPasswordsButton"
    )
    .addEventListener(
        "click",
        async () => {
            setBusy(
                true,
                wifiPasswordsRevealed
                    ? "Ocultando senhas Wi-Fi..."
                    : "Lendo senhas Wi-Fi..."
            );

            try {
                wifiPasswordsRevealed = !wifiPasswordsRevealed;

                await loadWifi();

                const button = document.getElementById(
                    "revealWifiPasswordsButton"
                );

                button.innerHTML = `
                    <span class="material-symbols-outlined">
                        ${wifiPasswordsRevealed ? "visibility_off" : "visibility"}
                    </span>
                    ${wifiPasswordsRevealed ? "Ocultar senhas Wi-Fi" : "Revelar senhas Wi-Fi"}
                `;
            } catch (error) {
                wifiPasswordsRevealed = false;
                showToast(error.message);
            } finally {
                setBusy(false);
            }
        }
    );


document
    .getElementById(
        "adminPasswordForm"
    )
    .addEventListener(
        "submit",
        changeAdminPassword
    );


document
    .getElementById(
        "rebootDeviceButton"
    )
    .addEventListener(
        "click",
        rebootDevice
    );


// Navegação contextual de cards do dashboard. Event delegation também
// cobre os cards de SSID que são renderizados depois do carregamento.
document.addEventListener(
    "click",
    event => {
        const target = event.target.closest(
            "[data-jump]"
        );

        if (!target) {
            return;
        }

        const jump = target.dataset.jump;
        openPage(jump);

        // Os atalhos do topo são ações, não apenas links invisíveis.
        if (target.closest(".topbar-quick-actions")) {
            if (!ontConnected && jump !== "management") {
                showToast("Conecte-se ao equipamento primeiro.");
                return;
            }
            if (jump === "advanced") {
                // O loader da página inicia pelo evento zte:page-open.
                // A probe só começa após catálogo ter sido carregado.
                window.setTimeout(() => {
                    if (typeof window.startQuickProbe === "function") {
                        void window.startQuickProbe();
                    }
                }, 0);
            } else if (jump === "supportDiagnostic") {
                if (typeof window.runQuickSupportDiagnostic === "function") {
                    void window.runQuickSupportDiagnostic();
                }
            } else if (jump === "management") {
                showToast("Atualizando plataforma de gerenciamento...");
            }
        }
    }
);


document
    .getElementById(
        "addProfileHostButton"
    )
    .addEventListener(
        "click",
        () => addProfileHostRow()
    );


document
    .getElementById(
        "saveProfileButton"
    )
    .addEventListener(
        "click",
        saveProfile
    );


document
    .getElementById(
        "captureProfileButton"
    )
    .addEventListener(
        "click",
        captureCurrentConfiguration
    );


document
    .getElementById(
        "applyProfileButton"
    )
    .addEventListener(
        "click",
        applyProfile
    );


document
    .getElementById(
        "applyDefaultButton"
    )
    .addEventListener(
        "click",
        applyProfile
    );


document
    .getElementById(
        "zoomOutButton"
    )
    ?.addEventListener(
        "click",
        () => changeUiZoom(
            -UI_ZOOM_STEP
        )
    );


document
    .getElementById(
        "zoomInButton"
    )
    ?.addEventListener(
        "click",
        () => changeUiZoom(
            UI_ZOOM_STEP
        )
    );


document.addEventListener(
    "keydown",
    event => {
        if (
            !event.ctrlKey
            && !event.metaKey
        ) {
            return;
        }

        const key = event.key;

        if (
            key === "+"
            || key === "="
        ) {
            event.preventDefault();

            changeUiZoom(
                UI_ZOOM_STEP
            );

            return;
        }

        if (
            key === "-"
            || key === "_"
        ) {
            event.preventDefault();

            changeUiZoom(
                -UI_ZOOM_STEP
            );

            return;
        }

        if (key === "0") {
            event.preventDefault();

            applyUiZoom(
                1
            );
        }
    }
);


// =========================================================
// INIT
// =========================================================

async function restoreDesktopSession() {
    // Navegação inesperada do WebView recria o estado JS, mas o singleton
    // Python pode continuar conectado. Nunca pedir login novamente sem
    // consultar a sessão local; não armazenar senha no navegador.
    try {
        const status = await apiRequest("/connection/status");
        if (!status?.connected) {
            openPage("connection");
            return;
        }

        currentHost = status.host || null;
        currentAttendant = status.attendant || "default";
        routerWriteEnabled = status.writes_enabled !== false;

        document.getElementById("connectedHost").textContent =
            currentHost || "-";
        document.getElementById("connectedAttendant").textContent =
            `Atendente: ${currentAttendant}`;
        document.getElementById("connectedModel").textContent =
            status.model || "ZTE";
        document.getElementById("dashboardProfileName").textContent =
            currentAttendant;
        document.getElementById("profileAttendant").textContent =
            currentAttendant;

        const topChip = document.getElementById("topDeviceChip");
        if (topChip) {
            topChip.classList.remove("hidden");
        }

        setConnectionStatus(true);
        // Evitar novo loadAll() automático: 10+ consultas seguidas
        // disputavam a sessão com o diagnóstico anterior. O usuário
        // pode atualizar os dados depois do restabelecimento da UI.
        openPage(routerWriteEnabled ? "dashboard" : "advanced");
        showToast("Sessão local recuperada após atualização da interface.");
    } catch (error) {
        console.warn("Não foi possível consultar sessão local:", error);
        // Erro temporário da API não equivale a logout remoto.
        const message = document.getElementById("connectionResult");
        if (message) {
            message.className = "connection-result connection-error";
            message.textContent =
                "Servidor local indisponível. Aguarde e tente atualizar a interface.";
        }
        openPage("connection");
    }
}


function initZteAutomatic() {
    if (window.__zteAutomaticInitialized) {
        return;
    }

    window.__zteAutomaticInitialized = true;

    loadUiZoom();

    setConnectionStatus(false);
    openPage("connection");

    // O listener executa depois que todos os scripts foram avaliados:
    // outra aba/rota do Vela não deve zerar uma sessão Python ativa.
    void restoreDesktopSession();
}


if (document.readyState === "loading") {
    document.addEventListener(
        "DOMContentLoaded",
        initZteAutomatic,
        { once: true }
    );
} else {
    initZteAutomatic();
}

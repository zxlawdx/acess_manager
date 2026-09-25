/* ZTE Automatic: adaptive, read-only views for firmware-specific data.
   The API supplies already-whitelisted fields; never display raw CMAPI/XML.
   No configuration mutations are performed by this module. */
(() => {
    "use strict";
    const LABELS = {
        device: "Identificação e recursos", identity: "Identificação",
        resources: "CPU e memória", uptime: "Tempo de atividade",
        optical: "Potência óptica e GPON", loss_of_signal: "Perda de sinal",
        registration: "Registro GPON", wifi_clients: "Clientes Wi-Fi",
        lan_clients: "Clientes Ethernet", dhcp_leases: "Dispositivos com DHCP",
        wifi_ssids: "Redes Wi-Fi", wifi_radios: "Rádios 2,4 / 5 GHz",
        lan_ports: "Portas Ethernet", wan: "Conexões WAN",
        band_steering: "Band Steering", wps: "WPS",
        mesh: "Mesh / roaming", dns: "DNS", dhcp: "Servidor DHCP",
        route_table: "Rotas IPv4", arp: "Tabela ARP", firewall: "Firewall",
        voip_status: "Telefonia", tr069_status: "TR-069",
        upnp: "UPnP", wifi_schedule: "Agendamento Wi-Fi",
        ping_history: "Último ping", traceroute_history: "Último traceroute",
        model: "Modelo", hardware: "Hardware", firmware: "Firmware",
        rx_power_raw: "RX (valor informado pelo firmware)",
        tx_power_raw: "TX (valor informado pelo firmware)",
        temperature_raw: "Temperatura (valor original)",
        voltage_raw: "Tensão (valor original)",
        current_raw: "Corrente (valor original)",
        status: "Estado", connected: "Conectados", leases: "Leases DHCP",
        records: "Registros", ssid_total: "Redes configuradas",
        ssid_enabled: "Redes ativas", cpu1: "CPU 1", cpu2: "CPU 2",
        cpu3: "CPU 3", cpu4: "CPU 4", memory_percent: "Memória (%)",
        uptime_seconds: "Atividade (s)", speed: "Velocidade",
        port: "Porta", enabled: "Habilitado", mode: "Modo",
        radio_status: "Estado do rádio", band: "Banda",
        transport: "Transporte", name: "Nome da conexão",
        rx_errors: "Erros RX", tx_errors: "Erros TX",
        average_ms: "Ping médio (ms)", successes: "Respostas",
        failures: "Perdas", registration_status: "Registro"
    };
    const PAGE_SECTIONS = {
        dashboard: ["device", "optical", "wan", "wifi_clients"],
        wifi: ["wifi_ssids", "wifi_radios", "band_steering", "wps", "wifi_schedule"],
        wan: ["wan", "lan_ports", "dns", "dhcp"],
        clients: ["wifi_clients", "dhcp_leases", "arp"],
        device: ["device", "optical", "voip_status", "tr069_status"]
    };
    const SENSITIVE = /password|passwd|secret|token|private|authuser|session|credential|keypassphrase/i;
    let cache = new Map();
    let lastHost = null;

    const el = (tag, className, value) => {
        const node = document.createElement(tag);
        if (className) node.className = className;
        if (value !== undefined && value !== null) node.textContent = String(value);
        return node;
    };
    const pretty = name => LABELS[name] || String(name).replace(/_/g, " ");
    const scalar = value => typeof value === "boolean"
        ? (value ? "Sim" : "Não")
        : (value == null || value === "" ? "Não informado" : String(value));
    function renderFields(data, parent, level = 0) {
        if (level > 4) return;
        if (Array.isArray(data)) {
            if (!data.length) {
                parent.append(el("p", "adaptive-empty", "Nenhum registro nesta leitura."));
                return;
            }
            const list = el("div", "adaptive-records");
            data.forEach((item, index) => {
                const record = el("div", "adaptive-record");
                if (data.length > 1) record.append(el("span", "adaptive-record-index", "Registro " + (index + 1)));
                renderFields(item, record, level + 1);
                list.append(record);
            });
            parent.append(list);
            return;
        }
        if (data && typeof data === "object") {
            const grid = el("dl", "adaptive-fields");
            Object.entries(data).forEach(([key, value]) => {
                if (SENSITIVE.test(key)) return;
                if (value && typeof value === "object") {
                    const nested = el("div", "adaptive-nested");
                    nested.append(el("h4", "", pretty(key)));
                    renderFields(value, nested, level + 1);
                    parent.append(nested);
                } else {
                    const cell = el("div", "adaptive-field");
                    cell.append(el("dt", "", pretty(key)));
                    cell.append(el("dd", "", scalar(value)));
                    grid.append(cell);
                }
            });
            if (grid.childElementCount) parent.prepend(grid);
            return;
        }
        parent.append(el("strong", "adaptive-value", scalar(data)));
    }
    function makeCard(key, section) {
        const card = el("article", "adaptive-card");
        const head = el("div", "adaptive-card-head");
        head.append(el("h3", "", pretty(key)));
        const available = section && section.available === true;
        head.append(el("span", "adaptive-badge " + (available ? "is-ok" : "is-muted"),
            available ? "Lido" : "Indisponível"));
        card.append(head);
        if (available) renderFields(section.data, card);
        else card.append(el("p", "adaptive-empty",
            section?.reason === "no_data_from_firmware"
                ? "Menu disponível, mas sem dados nesta consulta."
                : "Este recurso não respondeu neste firmware ou neste login."));
        return card;
    }
    function renderReport(report, mount, options = {}) {
        if (!mount) return;
        mount.style.whiteSpace = "normal";
        mount.classList.add("adaptive-report");
        mount.replaceChildren();
        const sections = Object.entries(report.sections || {});
        const ok = sections.filter(([, section]) => section?.available === true).length;
        const hero = el("header", "adaptive-summary");
        const copy = el("div");
        copy.append(el("span", "adaptive-eyebrow", "DIAGNÓSTICO · SOMENTE LEITURA"));
        copy.append(el("h2", "", report.model || "ZTE"));
        copy.append(el("p", "", `${ok} de ${sections.length} seções com leitura confirmada`));
        hero.append(copy);
        const score = el("div", "adaptive-score");
        score.append(el("strong", "", String(ok)));
        score.append(el("small", "", "seções lidas"));
        hero.append(score);
        mount.append(hero);
        if (options.progress) mount.append(
            el("p", "adaptive-progress", options.progress)
        );
        const cards = el("div", "adaptive-grid");
        if (!sections.length) cards.append(el("p", "adaptive-empty",
            "Nenhuma leitura concluída. Selecione recursos e inicie o diagnóstico."));
        sections.forEach(([key, value]) => cards.append(makeCard(key, value)));
        mount.append(cards);
        const errors = Object.entries(report.errors || {});
        if (errors.length) {
            const details = el("details", "adaptive-errors");
            details.append(el("summary", "", errors.length + " avisos técnicos"));
            errors.forEach(([key, value]) =>
                details.append(el("p", "", pretty(key) + ": " + String(value).slice(0, 160))));
            mount.append(details);
        }
    }

    function attendance(report) {
        const lines = [
            "RELATÓRIO DE ATENDIMENTO — ZTE AUTOMATIC",
            "Modelo: " + (report.model || "Não informado"),
            "Firmware: " + (report.firmware || "Não informado"),
            "Modo: somente leitura",
            "Coleta: " + new Date().toLocaleString("pt-BR"),
            "",
            "LEITURAS"
        ];
        for (const [key, section] of Object.entries(report.sections || {})) {
            if (!section?.available) {
                lines.push("- " + pretty(key) + ": indisponível/não confirmado");
                continue;
            }
            const data = section.data;
            if (Array.isArray(data)) {
                lines.push("- " + pretty(key) + ": " + data.length + " registro(s)");
                continue;
            }
            if (data && typeof data === "object") {
                const summary = Object.entries(data)
                    .filter(([k, v]) => !SENSITIVE.test(k) && (
                        v == null || typeof v !== "object"))
                    .map(([k, v]) => pretty(k) + "=" + scalar(v)).join(", ");
                lines.push("- " + pretty(key) + ": " + (summary || "leitura confirmada"));
            } else lines.push("- " + pretty(key) + ": " + scalar(data));
        }
        lines.push("", "OBSERVAÇÃO: nenhuma alteração de configuração foi executada.");
        lines.push("Dados indisponíveis não representam falha comprovada do equipamento.");
        return lines.join("\n");
    }
    window.renderAdaptiveDiagnostic = renderReport;
    window.composeFirmwareAttendance = attendance;

    function ensurePagePanel(page) {
        const section = document.getElementById("page-" + page);
        if (!section) return null;
        let panel = section.querySelector(".adaptive-page-panel");
        if (panel) return panel;
        panel = el("div", "adaptive-page-panel");
        const button = el("button", "button ghost adaptive-refresh", "Atualizar leituras");
        button.type = "button";
        button.addEventListener("click", () => {
            cache.clear();
            void loadPage(page);
        });
        panel.append(button);
        const body = el("div", "adaptive-page-body");
        panel.append(body);
        // Mantém o título e oculta componentes legados de escrita/leitura
        // incompatíveis, inclusive os que ficavam em "Carregando".
        [...section.children].forEach(child => {
            if (!child.classList.contains("section-intro")) child.classList.add("adaptive-hide-legacy");
        });
        section.append(panel);
        return panel;
    }
    async function loadPage(page) {
        if (routerWriteEnabled || !ontConnected || !PAGE_SECTIONS[page]) return;
        const panel = ensurePagePanel(page);
        if (!panel) return;
        const body = panel.querySelector(".adaptive-page-body");
        const bootstrap = await apiRequest("/discovery/bootstrap");
        const host = currentHost || "";
        if (lastHost !== host) { cache = new Map(); lastHost = host; }
        if (!bootstrap?.connected) {
            body.replaceChildren(el("p", "adaptive-empty", "Sessão expirada. Reconecte à ONT."));
            return;
        }
        const report = { model: bootstrap.model, firmware: bootstrap.firmware,
            sections: {}, errors: {} };
        const ids = PAGE_SECTIONS[page];
        for (let index = 0; index < ids.length; index++) {
            if (!ontConnected || currentHost !== host) return;
            const name = ids[index];
            const key = host + ":" + name;
            try {
                let entry = cache.get(key);
                if (!entry || (Date.now() - entry.at > 60000)) {
                    const data = await apiRequest("/multimodel/diagnostic", {
                        method: "POST", body: JSON.stringify({
                            model: bootstrap.model, section: name
                        })
                    });
                    entry = { at: Date.now(), data: data.sections?.[name] };
                    cache.set(key, entry);
                }
                report.sections[name] = entry.data || { available: false };
            } catch (error) {
                report.errors[name] = "Falha na consulta";
                report.sections[name] = { available: false, reason: "read_failed" };
            }
            renderReport(report, body, {
                progress: `Leitura ${index + 1}/${ids.length} · ${pretty(name)}`
            });
        }
        if (page === "clients") {
            const notice = el("p", "adaptive-footnote",
                "Leases DHCP e entradas ARP são históricos de rede, não prova de clientes Ethernet conectados neste momento.");
            body.append(notice);
        }
    }
    document.addEventListener("zte:page-open", event => {
        const page = event.detail?.pageName;
        if (page && !routerWriteEnabled && PAGE_SECTIONS[page]) {
            void loadPage(page).catch(error => {
                const panel = ensurePagePanel(page);
                panel?.querySelector(".adaptive-page-body")?.replaceChildren(
                    el("p", "adaptive-empty", "Falha na leitura: " + error.message));
            });
        }
    });
})();

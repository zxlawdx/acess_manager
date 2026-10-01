/* ZTE Automatic: adaptive, read-only views for firmware-specific data.
   The API supplies already-whitelisted fields; never display raw CMAPI/XML.
   No configuration mutations are performed by this module. */
(() => {
    "use strict";
    const LABELS = {
        device: "Identificação e recursos", identity: "Identificação",
        wifi_devices: "Dispositivos Wi-Fi identificados",
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
        failures: "Perdas", registration_status: "Registro",
        wifi_advanced: "Configurações avançadas do Wi-Fi",
        wifi_neighbor_scan: "Redes próximas e interferência",
        wifi_interference_schedule: "Controle de interferência",
        dhcp_basic: "Servidor DHCP", dhcp_reservations: "Reservas DHCP",
        ddns: "DNS dinâmico", sntp: "Sincronização de horário",
        upnp_port_map: "Mapeamento automático de portas",
        qos_queue: "Priorização de tráfego",
        qos_shaper: "Limite de banda",
        service_control_ipv4: "Serviços IPv4",
        service_control_ipv6: "Serviços IPv6",
        firewall_filters: "Regras do firewall",
        channel: "Canal", auto_channel: "Seleção automática de canal"
    };
    const PAGE_SECTIONS = {
        dashboard: ["device", "optical", "wan", "wifi_clients"],
        wifi: ["wifi_ssids", "wifi_radios", "band_steering", "wps", "wifi_schedule"],
        wan: ["wan", "lan_ports", "dns", "dhcp"],
        clients: ["wifi_clients", "lan_ports", "dhcp_leases", "arp"],
        device: ["device", "optical", "voip_status", "tr069_status"]
    };
    const SENSITIVE = /password|passwd|secret|token|private|authuser|session|credential|keypassphrase/i;
    let cache = new Map();
    let lastHost = null;
    let lastRevision = null;
    let renderEpoch = 0;
    const nativeModels = new Set(["F6600P", "F670L"]);
    const requestedFeatures = {
        dashboard: ["device_info", "pon_optical", "wan", "wifi_clients"],
        wifi: ["wifi_ssids", "wifi_radios", "band_steering", "wps", "wifi_schedule"],
        wan: ["wan", "lan_ports", "dns", "dhcp"],
        clients: ["wifi_clients", "lan_ports", "dhcp_leases", "arp"],
        device: ["device_info", "pon_optical", "voip_status", "tr069_status"]
    };
    const remap = { device_info: "device", pon_optical: "optical" };
    const modelKey = value =>
        String(value || "").toUpperCase().replace(/[^A-Z0-9]/g, "");
    function teardownOldPanels() {
        renderEpoch++;
        cache.clear();
        lastHost = null;
        lastRevision = null;
        for (const page of Object.keys(PAGE_SECTIONS)) {
            const section = document.getElementById("page-" + page);
            if (!section) continue;
            section.querySelector(".adaptive-page-panel")?.remove();
            section.querySelectorAll(".adaptive-hide-legacy").forEach(
                node => node.classList.remove("adaptive-hide-legacy")
            );
        }
    }
    window.clearAdaptiveFirmwareState = teardownOldPanels;

    const el = (tag, className, value) => {
        const node = document.createElement(tag);
        if (className) node.className = className;
        if (value !== undefined && value !== null) node.textContent = String(value);
        return node;
    };
    // Public labels come from an explicit operator vocabulary, never a Lua
    // filename, undocumented route or a raw backend property key.
    const pretty = name => LABELS[name] ||
        window.AccessManagerInspector?.label?.(name) ||
        "Funcionalidade adicional";
    const scalar = value => {
        if (typeof value === "boolean") return value ? "Sim" : "Não";
        if (value == null || value === "") return "Não informado";
        const text = String(value);
        const lower = text.toLowerCase();
        // Raw firmware errors may contain secrets even under an innocent key.
        if (["password=", "password:", "token=", "token:", "cookie=",
             "secret=", "traceback", "<html", "<script", "<?xml"].some(
                 marker => lower.includes(marker)
             ) || (lower.startsWith("http") && lower.includes("@")) ||
             text.length > 250) return "Informação técnica reservada.";
        return text;
    };
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
        const absent = section?.reason === "confirmed_absence";
        head.append(el("span", "adaptive-badge " + (available ? "is-ok" : "is-muted"),
            available ? "Leitura confirmada" : absent ? "Ausência confirmada" : "Não confirmado"));
        card.append(head);
        if (available) {
            // Probe confirmation is evidence of a working reader, not useful
            // output by itself. Never render "GET confirmado" as a card.
            const data = section.data;
            const synthetic = !data ||
                (typeof data === "object" && data.status === "GET confirmado") ||
                (typeof data === "object" && !Object.keys(data).length);
            if (!synthetic) renderFields(data, card);
            else card.append(el("p", "adaptive-empty",
                "A leitura deste recurso foi confirmada. Abra o diagnóstico " +
                "direcionado para consultar informações operacionais."));
        } else {
            const messages = {
                no_data_from_firmware: "O menu respondeu, mas não trouxe dados nesta leitura.",
                session_expired: "A sessão do equipamento expirou. Reconecte para continuar.",
                unexpected_xml_object: "O firmware respondeu, mas não retornou o objeto esperado para esta função.",
                network_timeout: "Tempo de resposta esgotado. Confira a conexão com a ONT.",
                invalid_xml: "A resposta do equipamento não corresponde ao formato XML esperado.",
                read_failed: "A consulta foi recusada ou falhou. Verifique permissões e mapeamento.",
            };
            card.append(el("p", "adaptive-empty",
                messages[section?.reason] ||
                "Função ainda não confirmada nesta versão de firmware."));
            // Technical driver error types remain in private logs only.
        }
        return card;
    }
    function renderReport(report, mount, options = {}) {
        if (!mount) return;
        mount.style.whiteSpace = "normal";
        mount.classList.add("adaptive-report");
        mount.replaceChildren();
        const sections = Object.entries(report.sections || {});
        const confirmed = sections.filter(([, item]) => item?.available === true);
        const count = confirmed.length;
        if (report.probe_only) {
            // Probing identifies available readers, not data collection.
            // The selectable diagnostic options already show every resource:
            // do not duplicate 12–25 tall empty cards or claim a completed
            // diagnostic after a successful capability probe.
            const summary = el("section", "adaptive-probe-result");
            summary.setAttribute("role", "status");
            summary.append(
                el("span", "adaptive-eyebrow", "IDENTIFICAÇÃO CONCLUÍDA"),
                el("strong", "", count + " de " + sections.length +
                    " funcionalidades responderam nesta verificação."),
                el("p", "", "Selecione os recursos confirmados acima e execute " +
                    "a coleta para consultar dados reais. Uma resposta ausente " +
                    "não demonstra incompatibilidade do firmware.")
            );
            if (options.progress)
                summary.append(el("small", "adaptive-progress", options.progress));
            mount.append(summary);
            return;
        }
        const hero = el("header", "adaptive-summary");
        const copy = el("div");
        copy.append(el("span", "adaptive-eyebrow", "LEITURAS DO EQUIPAMENTO"));
        copy.append(el("h2", "", report.model || "Equipamento conectado"));
        copy.append(el("p", "", count + " de " + sections.length +
            " recursos consultados com resposta confirmada"));
        hero.append(copy);
        const score = el("div", "adaptive-score");
        score.append(el("strong", "", String(count)));
        score.append(el("small", "", "consultas confirmadas"));
        hero.append(score);
        mount.append(hero);
        if (options.progress)
            mount.append(el("p", "adaptive-progress", options.progress));
        const cards = el("div", "adaptive-grid");
        if (!sections.length) cards.append(el("p", "adaptive-empty",
            "Nenhuma leitura concluída. Selecione recursos e inicie a coleta."));
        sections.forEach(([key, value]) => cards.append(makeCard(key, value)));
        mount.append(cards);
        const errors = Object.entries(report.errors || {});
        if (errors.length) {
            const details = el("details", "adaptive-errors");
            details.append(el("summary", "", errors.length +
                " leitura(s) sem confirmação"));
            for (const [key, value] of errors) {
                // Internal URLs, parser errors and route names belong in
                // private logs, never in the field operator's view.
                const detail = el("p", "", pretty(key) +
                    ": consulta indisponível no momento.");
                details.append(detail);
            }
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
                lines.push("- " + pretty(key) + ": " +
                    (section?.reason === "confirmed_absence"
                        ? "ausência confirmada" : "leitura não confirmada"));
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
        if (!ontConnected || !PAGE_SECTIONS[page]) return;
        // Consultar a sessão AUTORITATIVA antes de ocultar painéis nativos.
        const bootstrap = await apiRequest("/discovery/bootstrap");
        const host = currentHost || "";
        const detected = modelKey(bootstrap?.detected_model);
        const selected = modelKey(bootstrap?.model);
        const model = detected && detected !== "ZTE" ? detected : selected;
        const profile = (bootstrap?.catalog?.models || []).find(
            item => modelKey(item.model) === model
        );
        const revision = bootstrap?.session_revision || "";
        if (!bootstrap?.connected || routerWriteEnabled || nativeModels.has(model)
            || (model === "F6201B" && bootstrap.model_verified !== true)
            || !profile || !profile.candidate_features?.length
            || (detected && selected && detected !== "ZTE" && detected !== selected)) {
            teardownOldPanels();
            return;
        }
        if (lastHost !== host || lastRevision !== revision) {
            teardownOldPanels();
            lastHost = host;
            lastRevision = revision;
        }
        const epoch = renderEpoch;
        const panel = ensurePagePanel(page);
        if (!panel) return;
        const body = panel.querySelector(".adaptive-page-body");
        if (!bootstrap?.connected) {
            body.replaceChildren(el("p", "adaptive-empty", "Sessão expirada. Reconecte à ONT."));
            return;
        }
        const report = { model: profile.model, firmware: bootstrap.firmware,
            sections: {}, errors: {} };
        const supported = new Set(profile.candidate_features);
        const ids = requestedFeatures[page]
            .filter(feature => supported.has(feature))
            .map(feature => remap[feature] || feature);
        if (!ids.length) {
            body.replaceChildren(el("p", "adaptive-empty",
                "Nenhum recurso cadastrado para esta aba neste modelo."));
            return;
        }
        for (let index = 0; index < ids.length; index++) {
            if (epoch !== renderEpoch || !ontConnected || currentHost !== host)
                return;
            const name = ids[index];
            const key = revision + ":" + host + ":" + name;
            try {
                let entry = cache.get(key);
                if (!entry || (Date.now() - entry.at > 60000)) {
                    const data = await apiRequest("/multimodel/diagnostic", {
                        method: "POST", body: JSON.stringify({
                            model: profile.model, section: name
                        })
                    });
                    entry = { at: Date.now(), data: data.sections?.[name] };
                    if (epoch !== renderEpoch || !ontConnected ||
                        currentHost !== host) return;
                    cache.set(key, entry);
                }
                report.sections[name] = entry.data || { available: false };
            } catch (error) {
                report.errors[name] = "Falha na consulta";
                report.sections[name] = { available: false, reason: "read_failed" };
            }
            if (epoch !== renderEpoch) return;
            renderReport(report, body, {
                progress: `Leitura ${index + 1}/${ids.length} · ${pretty(name)}`
            });
        }
        if (page === "clients" && epoch === renderEpoch) {
            // A página de clientes é local ao atendente autorizado: aqui
            // é útil exibir dispositivos individuais. Não enviar esses
            // identificadores ao relatório/OS sanitizado.
            try {
                const wifi = await apiRequest("/clients/wifi");
                report.sections.wifi_devices = {
                    available: Array.isArray(wifi),
                    data: Array.isArray(wifi) ? wifi : []
                };
                if (epoch !== renderEpoch) return;
                renderReport(report, body);
            } catch (error) {
                report.sections.wifi_devices = {
                    available: false, reason: "read_failed"
                };
                renderReport(report, body);
            }
            const notice = el("p", "adaptive-footnote",
                "Leases DHCP e entradas ARP são históricos de rede, não prova de clientes Ethernet conectados neste momento.");
            body.append(notice);
        }
    }
    document.addEventListener("device:session-changed", teardownOldPanels);
    document.addEventListener("device:page-open", event => {
        const page = event.detail?.pageName;
        // O painel original é o ÚNICO layout para todas as famílias.
        // Este módulo continua exportando renderAdaptiveDiagnostic somente
        // para o resultado de sondagem em Avançado/diagnóstico técnico.
        // Nunca substituir as páginas Visão geral, Wi-Fi, WAN ou Clientes.
        if (PAGE_SECTIONS[page]) teardownOldPanels();
    });
})();


/* Catalog explorer: the 92 GET routes observed in the supplied F6201B
   capture are available ON DEMAND. XML values never reach this interface. */
(() => {
    "use strict";
    let catalogLoaded = false;
    let activeHost = null;

    function make(tag, cls, value) {
        const node = document.createElement(tag);
        if (cls) node.className = cls;
        if (value != null) node.textContent = String(value);
        return node;
    }

    function humanCapturedRoute(route, index) {
        const tag = String(route?.tag || "").toLowerCase();
        const vocabulary = [
            [/optical|poninfo|loid/, "Potência óptica e fibra"],
            [/wlan.*ssid|wlanhome|wlan_home/, "Redes Wi-Fi"],
            [/wlan.*basic|channel/, "Configurações de rádio"],
            [/wlan.*wps/, "Conexão simplificada WPS"],
            [/bandsteer/, "Direcionamento entre bandas"],
            [/sta_wlan_profile/, "Redes Wi-Fi próximas"],
            [/dhcp.*host|dhcphost/, "Dispositivos com DHCP"],
            [/dhcp.*static/, "Reservas DHCP"],
            [/dhcp/, "Servidor DHCP"],
            [/dns/, "Configurações DNS"],
            [/route.*ipv6/, "Rotas IPv6"],
            [/route.*ipv4/, "Rotas IPv4"],
            [/wan.*internet/, "Conexão de Internet"],
            [/upnp/, "Abertura automática de portas"],
            [/firewall/, "Proteção da rede"],
            [/sntp/, "Sincronização de horário"],
            [/remotemgr/, "Gerenciamento remoto"],
            [/networkdiag_ping/, "Teste de conectividade"],
            [/networkdiag_traceroute/, "Caminho da conexão"],
            [/log_syslog/, "Registros do equipamento"],
            [/voip/, "Telefonia"],
        ];
        const matched = vocabulary.find(([pattern]) => pattern.test(tag));
        return (matched ? matched[1] : (route.category || "Equipamento")) +
            " · função " + (index + 1);
    }

    async function loadCapturedRoutes() {
        if (routerWriteEnabled || !ontConnected) return;
        const bootstrap = await apiRequest("/discovery/bootstrap");
        if (!String(bootstrap?.model || "").toUpperCase().includes("F6201B")) return;
        const parent = document.getElementById("page-advanced");
        if (!parent) return;
        if (activeHost !== currentHost) catalogLoaded = false;
        if (catalogLoaded) return;
        activeHost = currentHost;
        const data = await apiRequest("/multimodel/mapped-routes");
        if (!data?.routes?.length) return;

        let panel = document.getElementById("capturedRouteExplorer");
        if (!panel) {
            panel = make("section", "panel adaptive-route-explorer");
            panel.id = "capturedRouteExplorer";
            parent.append(panel);
        }
        panel.replaceChildren();
        const header = make("div", "adaptive-route-head");
        const copy = make("div");
        copy.append(make("span", "adaptive-eyebrow",
            "MAPEAMENTO CAPTURADO · SOMENTE LEITURA"));
        copy.append(make("h2", "", "Funcionalidades identificadas no F6201B"));
        copy.append(make("p", "adaptive-empty",
            data.total_get_routes + " funcionalidades catalogadas. " +
            "Consultas opcionais mostram somente estrutura e contagens; " +
            "a presença no catálogo não confirma disponibilidade atual."));
        header.append(copy);
        panel.append(header);
        const search = make("input", "adaptive-search");
        search.type = "search";
        search.placeholder = "Buscar funcionalidade ou categoria…";
        search.setAttribute("aria-label", "Buscar funcionalidades observadas");
        panel.append(search);
        const groups = make("div", "adaptive-route-groups");
        panel.append(groups);
        const result = make("div", "adaptive-route-result");
        panel.append(result);
        const rebuild = () => {
            groups.replaceChildren();
            const filtered = data.routes.filter(route => (
                humanCapturedRoute(route, data.routes.indexOf(route)) + " " + route.category).toLowerCase()
                .includes(search.value.toLowerCase().trim()));
            const categories = new Map();
            filtered.forEach(route => {
                if (!categories.has(route.category)) categories.set(route.category, []);
                categories.get(route.category).push(route);
            });
            categories.forEach((routes, category) => {
                const details = make("details", "adaptive-route-category");
                const summary = make("summary", "", category +
                    " · " + routes.length + " funcionalidad(es)");
                details.append(summary);
                const list = make("div", "adaptive-route-list");
                routes.forEach(route => {
                    const row = make("div", "adaptive-route-row");
                    const desc = make("div");
                    desc.append(make("strong", "",
                        humanCapturedRoute(route, data.routes.indexOf(route))));
                    desc.append(make("small", "", route.inspectable
                        ? "Consulta estrutural disponível"
                        : "Consulta ainda sem formato confirmado"));
                    const button = make("button", "button ghost compact",
                        route.inspectable ? "Consultar" : "Não disponível");
                    button.type = "button";
                    button.disabled = !route.inspectable;
                    button.addEventListener("click", async () => {
                        if (!ontConnected) return;
                        button.disabled = true;
                        setBusy(true, "Consultando a funcionalidade...");
                        try {
                            const response = await apiRequest(
                                "/multimodel/mapped-inspect", {
                                    method: "POST",
                                    body: JSON.stringify({ tag: route.tag })
                                });
                            window.renderAdaptiveDiagnostic({
                                model: "F6201B",
                                sections: { [humanCapturedRoute(route, data.routes.indexOf(route))]: {
                                    available: response.available === true,
                                    data: response.available
                                        ? { objects: response.structure } : null,
                                    reason: response.reason
                                }}
                            }, result);
                            result.scrollIntoView({
                                behavior: "smooth", block: "nearest"
                            });
                        } catch (error) {
                            result.replaceChildren(make("p", "adaptive-empty",
                                "A consulta não foi confirmada nesta sessão. " +
                                "Verifique a conexão e tente novamente."));
                        } finally {
                            button.disabled = false;
                            setBusy(false);
                        }
                    });
                    row.append(desc, button);
                    list.append(row);
                });
                details.append(list);
                groups.append(details);
            });
        };
        search.addEventListener("input", rebuild);
        rebuild();
        catalogLoaded = true;
    }
    document.addEventListener("device:page-open", event => {
        if (event.detail?.vendor === "huawei") return;
        if (event.detail?.pageName === "advanced") {
            void loadCapturedRoutes().catch(error =>
                console.warn("Catálogo capturado indisponível:", error));
        }
    });
})();

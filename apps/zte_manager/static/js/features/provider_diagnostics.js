/* ISP troubleshooting presets use only existing live diagnostic handlers.
 * The workstation comparison is explicitly separate from customer ONT tests.
 */
(() => {
    "use strict";
    const SCENARIOS = Object.freeze({
        no_internet: {
            mode: "no_internet", speed: false, trace: true,
            text: "Serão consultados GPON, WAN, DNS, interfaces e caminho. " +
                "Confirme também se outros dispositivos do cliente estão sem acesso.",
        },
        low_speed: {
            mode: "low_speed", speed: true, trace: false,
            text: "Compare WAN, negociação Ethernet, sinal e taxas Wi-Fi " +
                "com o teste de velocidade. Informe a velocidade contratada.",
        },
        drops: {
            mode: "drops", speed: false, trace: true,
            text: "Verifique potência óptica, estado WAN, perdas no ping " +
                "e rota. Uma coleta pontual não comprova intermitência.",
        },
        wifi: {
            mode: "wifi", speed: false, trace: false,
            text: "Compare RSSI e banda do cliente com o scan das redes " +
                "vizinhas. Alteração automática de canal permanece desligada.",
        },
        realtime: {
            mode: "drops", speed: true, trace: true,
            text: "Observe latência, caminho e jitter quando o teste " +
                "disponibilizar essa métrica. Para confirmar perda ou " +
                "variação no cliente, execute testes também no dispositivo afetado.",
        },
    });
    const make = (tag, css = "", value) => {
        const item = document.createElement(tag);
        if (css) item.className = css;
        if (value !== undefined) item.textContent = value;
        return item;
    };
    function applyPreset(id) {
        const entry = SCENARIOS[id];
        if (!entry) return false;
        const setValue = (id, value, key) => {
            const input = document.getElementById(id);
            if (input) input[key] = value;
        };
        setValue("supportDiagnosticMode", entry.mode, "value");
        setValue("supportIncludeSpeedtest", entry.speed, "checked");
        setValue("supportIncludeTraceroute", entry.trace, "checked");
        // The preset must never silently opt in to a write operation.
        setValue("supportAutoOptimizeWifi", false, "checked");
        const status = document.getElementById("providerPresetStatus");
        if (status) status.textContent = entry.text +
            " Confira os campos e clique em Iniciar diagnóstico completo.";
        document.querySelectorAll("[data-provider-preset]").forEach(button => {
            button.setAttribute("aria-pressed",
                String(button.dataset.providerPreset === id));
        });
        return true;
    }
    function field(root, name, value) {
        const item = make("div", "am-workstation-metric");
        item.append(make("dt", "", name), make("dd", "", value));
        root.append(item);
    }
    function renderWorkstation(result, target) {
        if (!target || !result || result.source !== "technician_workstation") {
            if (target) target.textContent =
                "Não foi possível validar a origem desta leitura.";
            return;
        }
        target.replaceChildren();
        const list = make("dl", "am-workstation-metrics");
        const dns = result.dns || {}, tcp = result.tcp || {};
        field(list, "DNS deste computador",
            dns.ok ? "Respondeu" : "Sem resposta confirmada");
        field(list, "Tempo da consulta DNS",
            dns.ok && Number.isFinite(dns.duration_ms)
                ? dns.duration_ms.toFixed(1) + " ms" : "Não informado");
        field(list, "Conectividade TCP (3 tentativas)",
            (Number(tcp.successful) || 0) + " de " +
            (Number(tcp.attempts) || 3) + " concluídas");
        field(list, "Tempo médio de conexão TCP",
            Number.isFinite(tcp.mean_connect_ms)
                ? tcp.mean_connect_ms.toFixed(1) + " ms" : "Indisponível");
        field(list, "Variação entre conexões TCP",
            Number.isFinite(tcp.variation_ms)
                ? tcp.variation_ms.toFixed(1) + " ms" : "Indisponível");
        target.append(list);
        target.append(make("p", "am-workstation-caution",
            "Resultados referentes apenas ao PC do técnico. " +
            "TCP não mede perda de pacotes ICMP nem jitter UDP. " +
            "Restrições de proxy e firewall também podem afetar este teste."));
    }
    async function runWorkstation() {
        const button = document.getElementById("providerWorkstationRun");
        const result = document.getElementById("providerWorkstationResult");
        if (!button || !result || button.disabled) return;
        button.disabled = true;
        button.setAttribute("aria-busy", "true");
        result.textContent = "Testando DNS e conectividade TCP do computador...";
        try {
            const response = await apiRequest(
                "/diagnostics/workstation", {expected:"object"}
            );
            renderWorkstation(response, result);
        } catch (_) {
            result.textContent = "O teste do PC não pôde ser concluído. " +
                "Os testes da ONT permanecem disponíveis.";
        } finally {
            button.disabled = false;
            button.setAttribute("aria-busy", "false");
        }
    }
    function init() {
        document.querySelectorAll("[data-provider-preset]").forEach(button =>
            button.addEventListener("click", () =>
                applyPreset(button.dataset.providerPreset)));
        document.getElementById("providerWorkstationRun")
            ?.addEventListener("click", runWorkstation);
    }
    if (document.readyState === "loading")
        document.addEventListener("DOMContentLoaded", init, {once:true});
    else init();
    if (typeof window !== "undefined") window.ProviderDiagnostics =
        Object.freeze({applyPreset, renderWorkstation});
})();

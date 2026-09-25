// F6201B: usa a interface ORIGINAL de Wi-Fi/WAN/Clientes/Dashboard.
// Nenhum painel experimental de largura total nem formulários diferentes.
// As APIs seguem somente leitura, exceto SSID com opt-in + prévia + nonce.
(() => {
    "use strict";
    let epoch = 0;
    let sessionKey = null;
    let capabilities = null;
    let ssids = [];
    const fetches = new Map();
    const safe = value => escapeHtml(String(value ?? "-"));
    const $ = id => document.getElementById(id);
    const set = (id, value) => { const node = $(id); if (node) node.textContent = value ?? "-"; };
    const failure = (name, text) =>
        '<article class="panel feature-unavailable"><span class="material-symbols-outlined">info</span>' +
        '<div><strong>' + safe(name) + '</strong><p>' + safe(text) + '</p></div></article>';
    const notTested = "Este recurso ainda não foi confirmado neste firmware/login.";
    const originalNodes = {
        wifi: ["wifiNetworks","wifiRadios","wifiScheduleControl","wpsControls","bandSteeringControl"],
        wan: ["wanConnections","pppoeDetails","lanPorts","upnpDetails"],
        dashboard: ["dashboardNetworks","wanSummary","dashboardPppoe","dashboardDns"],
        device: ["deviceDetails","opticalDetails","accountDetails"]
    };
    function reset() {
        epoch++;
        sessionKey = null;
        capabilities = null;
        ssids = [];
        fetches.clear();
        document.querySelectorAll(".f6201b-inline, .f6201b-dns-action, .f6201b-dns-feedback").forEach(node => node.remove());
        // Sem dados de uma ONT anterior nas mesmas caixas que o layout nativo usa.
        for (const ids of Object.values(originalNodes)) {
            for (const id of ids) {
                const node = $(id);
                if (node) node.replaceChildren();
            }
        }
        for (const id of ["wifiClientsTable","lanClientsTable"]) {
            const node = $(id);
            if (node) node.replaceChildren();
        }
        for (const id of ["wifiClientCount","lanClientCount","clientTotalKpi"]) set(id,"0");
        // As limitações de escrita são específicas da sessão experimental.
        // Ao voltar para a F6600P/F670L, restaurar todos os formulários.
        $("adminPasswordForm")?.classList.remove("hidden");
        for (const id of ["applyDefaultButton","rebootDeviceButton"]) {
            const control = $(id);
            if (control) control.disabled = false;
        }
        for (const id of ["deviceModel","deviceFirmware","deviceCpu","deviceMemory",
            "deviceUptime","opticalRxKpi","opticalStatusKpi"]) set(id,"-");
        // Native F6600P/F670L loadAll repopulates exactly these existing nodes.
    }
    const verifiedModel = info =>
        info?.connected === true &&
        String(info.detected_model || "").toUpperCase().replace(/[^A-Z0-9]/g,"") === "F6201B" &&
        info.model_verified === true &&
        info.writes_enabled === false;

    async function bootstrap() {
        const info = await apiRequest("/discovery/bootstrap");
        if (!verifiedModel(info)) return null;
        const key = (info.session_revision || "") + ":" + (currentHost || "");
        if (sessionKey !== key) {
            sessionKey = key;
            capabilities = null;
            ssids = [];
            fetches.clear();
        }
        return info;
    }
    async function diagnostic(name, runEpoch) {
        const key = name;
        if (!fetches.has(key)) {
            // One getter at a time: ThinkLua menuView is session-global.
            const next = apiRequest("/multimodel/diagnostic", {
                method: "POST",
                body: JSON.stringify({model:"F6201B",section:name})
            }).then(result => result?.sections?.[name] ||
                {available:false,reason:"not_returned"});
            fetches.set(key,next);
        }
        const response = await fetches.get(key);
        return runEpoch === epoch ? response : null;
    }
    function nativeInfo(title, section) {
        const code = section?.reason;
        const labels = {
            session_expired:"Sessão expirada. Reconecte à ONT.",
            unexpected_xml_object:"O firmware não retornou o objeto esperado.",
            invalid_xml:"A resposta não corresponde ao menu esperado.",
            network_timeout:"Tempo limite na consulta.",
            read_failed:notTested,
        };
        return failure(title,labels[code] || notTested);
    }

    async function readSsids(runEpoch) {
        // Esta rota retorna apenas SSIDs/id/banda/estado — nenhuma senha.
        const result = await apiRequest("/f6201b/write/ssids");
        if (runEpoch !== epoch) return [];
        ssids = Array.isArray(result) ? result : [];
        return ssids;
    }
    function renderSsidCards() {
        const root = $("wifiNetworks");
        if (!root) return;
        if (!ssids.length) {
            root.innerHTML = failure("Redes Wi-Fi",
                "Nenhuma rede foi retornada pelo firmware neste login.");
            return;
        }
        const canEdit = capabilities?.opted_in === true &&
            capabilities?.supported_firmware === true;
        root.innerHTML = ssids.map(network => `
            <article class="panel ssid-card ${network.enabled ? "ssid-online" : "ssid-offline"}"
                     data-f6201b-id="${safe(network.id)}">
                <div class="ssid-card-head">
                    <div class="ssid-title">
                        <span class="ssid-icon"><span class="material-symbols-outlined">wifi</span></span>
                        <div><strong>${safe(network.ssid || "Sem nome")}</strong>
                            <small>${safe(network.id)} ${network.band ? "• " + safe(network.band) : ""}</small>
                        </div>
                    </div>
                    <span class="badge ${network.enabled ? "badge-success" : "badge-danger"}">
                        ${network.enabled ? "ATIVA" : "DESATIVADA"}
                    </span>
                </div>
                <form class="ssid-form f6201b-ssid-form">
                    <div class="ssid-meta">
                        <span class="meta-pill">F6201B</span>
                        <span class="meta-pill">Segurança preservada</span>
                        <span class="meta-pill">${canEdit ? "EDIÇÃO EXPERIMENTAL" : "LEITURA"}</span>
                    </div>
                    <div class="form-grid two-fields">
                        <div class="form-group"><label>Nome da rede</label>
                            <input data-field="ssid" maxlength="32" value="${safe(network.ssid || "")}"
                                   ${canEdit ? "" : "readonly"} required></div>
                        <div class="form-group"><label>Segurança</label>
                            <input value="Preservada pelo firmware" disabled></div>
                    </div>
                    <div class="switch-row">
                        <label class="switch-field"><span>SSID ativo</span>
                            <span class="switch"><input data-field="enabled" type="checkbox"
                                ${network.enabled ? "checked" : ""} ${canEdit ? "" : "disabled"}>
                                <span class="switch-slider"></span></span></label>
                        <label class="switch-field"><span>Broadcast</span>
                            <span class="switch"><input data-field="broadcast" type="checkbox"
                                ${network.broadcast ? "checked" : ""} ${canEdit ? "" : "disabled"}>
                                <span class="switch-slider"></span></span></label>
                    </div>
                    <div class="f6201b-inline-result" aria-live="polite"></div>
                    <div class="form-footer">
                        <span class="ssid-footnote"><span class="material-symbols-outlined">shield_lock</span>
                            ${canEdit ? "Prévia e confirmação obrigatórias." : "Somente leitura; nenhuma alteração será enviada."}
                        </span>
                        ${canEdit ? '<button class="button primary" type="submit"><span class="material-symbols-outlined">save</span>Prévia / Aplicar SSID</button>' : ""}
                    </div>
                </form>
            </article>`).join("");
        root.querySelectorAll(".f6201b-ssid-form").forEach(form => {
            form.addEventListener("submit", event => void submitSsid(event,form));
        });
    }
    async function submitSsid(event, form) {
        event.preventDefault();
        const root = form.closest(".ssid-card");
        const id = root?.dataset.f6201bId;
        const original = ssids.find(item => item.id === id);
        if (!original || !capabilities?.opted_in) return;
        const message = form.querySelector(".f6201b-inline-result");
        const name = form.querySelector('[data-field="ssid"]').value;
        const enabled = form.querySelector('[data-field="enabled"]').checked;
        const broadcast = form.querySelector('[data-field="broadcast"]').checked;
        const config = {};
        if (name !== original.ssid) config.ssid = name;
        if (enabled !== original.enabled) config.enabled = enabled;
        if (broadcast !== original.broadcast) config.broadcast = broadcast;
        if (!Object.keys(config).length) {
            message.textContent = "Nenhuma alteração informada.";
            return;
        }
        setBusy(true,"Conferindo formulário da ONT...");
        try {
            const proposal = await apiRequest("/f6201b/write/preview", {
                method:"POST",body:JSON.stringify({ssid_id:id,config})
            });
            const actual = Object.entries(proposal.changes || {}).map(
                ([name,item]) => name + ": " + item.before + " → " + item.after
            ).join("\n");
            message.replaceChildren();
            const summary = document.createElement("p");
            summary.textContent = actual;
            const warning = document.createElement("p");
            warning.textContent = "A alteração pode interromper o Wi-Fi. Requer acesso local; sem rollback automático.";
            const confirm = document.createElement("input");
            confirm.type = "text";
            confirm.placeholder = "Digite APLICAR F6201B";
            confirm.autocomplete = "off";
            const button = document.createElement("button");
            button.type = "button";
            button.className = "button primary";
            button.textContent = "Confirmar alterações";
            button.addEventListener("click",async () => {
                if(confirm.value !== "APLICAR F6201B") {
                    showToast("Confirmação inválida.");
                    return;
                }
                button.disabled = true;
                setBusy(true,"Aplicando e verificando SSID...");
                try {
                    const result = await apiRequest("/f6201b/write/apply",{
                        method:"POST",body:JSON.stringify({
                            nonce:proposal.nonce,confirmation:confirm.value
                        })
                    });
                    message.textContent = result.verified
                        ? "Configuração confirmada por releitura."
                        : "A ONT não confirmou a aplicação; confira o painel original.";
                    if(result.verified) await renderWifi();
                }catch(error) {
                    message.textContent = "Aplicação não confirmada: " + error.message;
                }finally {setBusy(false);}
            },{once:true});
            message.append(summary,warning,confirm,button);
        }catch(error){
            message.textContent = "Não foi possível validar o comando: "+error.message;
        }finally{setBusy(false);}
    }
    async function renderWifi() {
        const run = epoch;
        const root = $("wifiNetworks");
        if (!root) return;
        try {
            capabilities = await apiRequest("/f6201b/write/status");
            await readSsids(run);
            if (run !== epoch) return;
            renderSsidCards();
        } catch(error) {
            if(run===epoch) root.innerHTML = failure("Redes Wi-Fi",
                "Leitura indisponível: "+error.message);
        }
        // Mantém os MESMOS containers do layout antigo, cada função
        // aparecendo exatamente na categoria correspondente.
        const radios = $("wifiRadios");
        if (radios) {
            // A nova captura expõe canal, largura, padrão e potência.
            // Só renderizar quando XML COMPLETO for confirmado na ONT.
            try {
                let section = await diagnostic("wifi_radio_advanced",run);
                if (run!==epoch) return;
                if (!section?.available) section=await diagnostic("wifi_radios",run);
                if (run!==epoch) return;
                if (!section?.available) radios.innerHTML=
                    nativeInfo("Rádios 2,4 / 5 GHz",section);
                else {
                    const rows=Array.isArray(section.data)?section.data:[section.data];
                    radios.innerHTML=rows.map(row=>`
                        <article class="panel radio-card">
                            <div class="radio-card-hero">
                                <div>
                                    <span class="section-kicker">RF ${safe(row.band)}</span>
                                    <h3>${safe(row.band || "Rádio")}</h3>
                                    <p>Canal <strong>${safe(
                                        String(row.auto_channel)==="1"?"Auto":row.channel
                                    )}</strong> • ${safe(row.bandwidth)} • ${safe(row.standard)}</p>
                                </div>
                                <span class="badge ${String(row.radio_status)==="1"?"badge-success":"badge-warning"}">
                                    LEITURA
                                </span>
                            </div>
                            <div class="form-grid two-fields">
                                ${[
                                  ["Canal",row.channel],["Largura",row.bandwidth],
                                  ["Padrão",row.standard],["Potência",row.tx_power],
                                  ["Canal automático",row.auto_channel],
                                  ["SGI",row.sgi]
                                ].map(([label,value])=>`
                                  <div class="form-group"><label>${safe(label)}</label>
                                  <input value="${safe(value)}" readonly></div>
                                `).join("")}
                            </div>
                        </article>`).join("");
                }
            } catch(error) {
                if(run===epoch)radios.innerHTML=failure(
                    "Rádios 2,4 / 5 GHz","Leitura RF não confirmada.");
            }
        }
        const specs=[
            ["wifi_schedule","wifiScheduleControl","Agendamento Wi-Fi","schedule"],
            ["wps","wpsControls","WPS","lock_reset"],
            ["band_steering","bandSteeringControl","Band Steering","hub"]
        ];
        for (const [name,container,title,icon] of specs) {
            if (run!==epoch) return;
            const root=$(container);if(!root)continue;
            try {
                const section=await diagnostic(name,run);
                if(run!==epoch)return;
                if (!section?.available) {root.innerHTML=nativeInfo(title,section);continue;}
                const rows=Array.isArray(section.data)?section.data:[section.data];
                root.innerHTML=rows.map(row=>`
                    <article class="panel feature-control-card">
                       <div class="feature-control-main">
                         <span class="feature-control-icon"><span class="material-symbols-outlined">${icon}</span></span>
                         <div><span class="section-kicker">F6201B · LEITURA</span><h3>${safe(title)}</h3>
                            <div class="credential-meta">
                              ${Object.entries(row||{}).map(([k,v])=>`
                                 <span>${safe(k.replace(/_/g," "))} <strong>${safe(v)}</strong></span>
                              `).join("")}
                            </div>
                         </div>
                       </div>
                    </article>`).join("");
            }catch(error){if(run===epoch)root.innerHTML=failure(title,"Consulta falhou.");}
        }
    }
    async function renderWan() {
        const run=epoch;
        for(const [name,id] of [["wan","wanConnections"],["lan_ports","lanPorts"],["upnp","upnpDetails"]]){
            try{
                const section=name==="wan"?
                    {available:true,data:await apiRequest("/f6201b/wan/summary")}:
                    await diagnostic(name,run);
                if(run!==epoch)return;
                const container=$(id);if(!container)continue;
                if(!section?.available){container.innerHTML=nativeInfo(name,section);continue;}
                const records=Array.isArray(section.data)?section.data:[section.data];
                if(name==="wan" && typeof renderWanCard==="function"){
                    container.innerHTML=records.map(item=>renderWanCard(item)).join("");
                }else if(name==="lan_ports"){
                    container.innerHTML=records.map(port=>`
                        <div class="port-card">
                          <div class="port-head"><span class="port-number">${safe(port.port)}</span>
                          <span class="status-led ${/up/i.test(String(port.status))?"on":"off"}"></span></div>
                          <strong>${safe(port.speed)}</strong><small>${safe(port.duplex)} · ${safe(port.status)}</small>
                        </div>`).join("");
                }else{
                    container.innerHTML=records.map(row=>`
                       <div class="credential-card"><span class="section-kicker">UPnP · LEITURA</span>
                        <div class="credential-meta">${Object.entries(row||{}).map(([k,v])=>
                         `<span>${safe(k)} <strong>${safe(v)}</strong></span>`).join("")}</div></div>`).join("");
                }
                if(name==="wan") {
                    const pppoe=$("pppoeDetails");if(pppoe)pppoe.innerHTML=failure(
                        "Credenciais PPPoE","Disponíveis apenas quando este firmware permitir leitura autenticada específica.");
                }
            }catch(error){
                const node=$(id);
                if(node&&run===epoch)node.innerHTML=failure(name,"Leitura falhou.");
            }
        }
    }
    async function renderClients() {
        const run=epoch;
        let wifi=[];
        try{
            const result=await apiRequest("/clients/wifi");
            if(run!==epoch)return;
            wifi=Array.isArray(result)?result:[];
        }catch(error){console.warn("Clientes Wi-Fi indisponíveis:",error);}
        if(run!==epoch)return;
        if(typeof renderWifiClients==="function")renderWifiClients(wifi);
        set("wifiClientCount",String(wifi.length));
        // O firmware fornece leases DHCP, mas não prova conexão Ethernet.
        const lan=$("lanClientsTable");
        if(lan)lan.innerHTML='<tr><td colspan="3" class="empty-table">Dispositivos Ethernet ativos ainda não confirmados neste firmware. Leases DHCP não indicam conexão atual.</td></tr>';
        set("lanClientCount","—");
    }
    async function renderDashboard() {
        const run=epoch;
        const model=$("deviceModel");if(model)model.textContent="F6201B";
        const details=await diagnostic("device",run).catch(()=>null);
        if(run!==epoch)return;
        const identity=details?.data?.identity?.[0]||{};
        const resources=details?.data?.resources?.[0]||{};
        set("deviceFirmware","Firmware: "+(identity.firmware||"-"));
        set("deviceCpu",resources.cpu1??"-");
        set("deviceMemory",resources.memory_percent??"-");
        set("deviceUptime",details?.data?.uptime?.[0]?.seconds??"-");
        const summary=$("wanSummary");
        const wan=await diagnostic("wan",run).catch(()=>null);
        if(run!==epoch)return;
        if(summary)summary.innerHTML=wan?.available&&wan.data?.length?
            '<div class="wan-mini"><strong>'+safe(wan.data[0].status||"-")+'</strong>'+
            '<small>'+safe(wan.data[0].name||"WAN")+'</small></div>':
            nativeInfo("WAN",wan);
        const nets=$("dashboardNetworks");
        if(nets){
            try{await readSsids(run);if(run===epoch)nets.innerHTML=ssids.map(net=>`
                <button class="network-overview-item" data-jump="wifi" type="button">
                    <span class="network-overview-icon ${net.enabled?"online":"offline"}">
                       <span class="material-symbols-outlined">wifi</span></span>
                    <span class="network-overview-copy"><strong>${safe(net.ssid||"Sem nome")}</strong>
                    <small>${safe(net.band||"F6201B")}</small></span>
                    <span class="badge ${net.enabled?"badge-success":"badge-danger"}">
                        ${net.enabled?"Ativa":"Off"}</span>
                </button>`).join("");}
            catch(error){nets.innerHTML=nativeInfo("Redes Wi-Fi",null);}
        }
        const optical=await diagnostic("optical",run).catch(()=>null);
        if(run===epoch){
            const optics=optical?.data?.optical?.[0]||{};
            set("opticalRxKpi",optics.rx_power_raw??"-");
            set("opticalStatusKpi",optical?.available?
                "Valor bruto do firmware (unidade não confirmada)":"Leitura não confirmada");
        }
        const pppoe=$("dashboardPppoe");
        if(pppoe)pppoe.innerHTML=
            '<div class="loading">Credenciais PPPoE não expostas por este perfil.</div>';
        const dns=$("dashboardDns");
        if(dns){
            const section=await diagnostic("dns",run).catch(()=>null);
            if(run!==epoch)return;
            const item=section?.data?.[0]||{};
            dns.innerHTML=section?.available?
                '<div class="mini-metrics">'+
                '<div><span>DNS 1</span><strong>'+safe(item.dns_ipv4_1||"-")+'</strong></div>'+
                '<div><span>DNS 2</span><strong>'+safe(item.dns_ipv4_2||"-")+'</strong></div></div>':
                nativeInfo("DNS",section);
        }
        const operations=$("applyDefaultButton");
        if(operations) {
            try {
                const flags = await apiRequest("/f6201b/write/status");
                if (run !== epoch) return;
                operations.disabled = !(flags.opted_in && flags.supported_firmware);
                operations.title = operations.disabled
                    ? "Ative a escrita experimental para testar o perfil F6201B."
                    : "Perfil experimental: abrir prévia e confirmar RF/DNS.";
            } catch(error) {
                operations.disabled = true;
            }
        }
    }
    async function renderDevice() {
        const run=epoch;
        for(const [name,id] of [["device","deviceDetails"],["optical","opticalDetails"]]){
            const node=$(id);if(!node)continue;
            try{
                const section=await diagnostic(name,run);
                if(run!==epoch)return;
                if(!section?.available){node.innerHTML=nativeInfo(name,section);continue;}
                const groups=Object.entries(section.data||{});
                node.innerHTML=groups.map(([k,entries])=>
                    '<div class="detail-grid compact">'+(Array.isArray(entries)?entries:[entries]).map(
                    row=>Object.entries(row||{}).map(([key,v])=>
                        '<div class="detail-tile"><div><small>'+safe(key.replace(/_/g," "))+
                        '</small><strong>'+safe(v)+'</strong></div></div>').join("")
                    ).join("")+'</div>').join("");
            }catch(error){if(run===epoch)node.innerHTML=failure(name,"Leitura falhou.");}
        }
        const account=$("accountDetails");
        if(account)account.innerHTML=failure("Conta administrativa","A edição geral permanece indisponível no perfil experimental.");
        const password=$("adminPasswordForm");if(password)password.classList.add("hidden");
        const reboot=$("rebootDeviceButton");if(reboot)reboot.disabled=true;
    }
    // DNS no próprio bloco antigo "Configuração padrão", sem telas extras.
    async function renderDnsProfile() {
        const run = epoch;
        const primary = $("profileDns4_1");
        const secondary = $("profileDns4_2");
        if (!primary || !secondary) return;
        const panel = primary.closest(".panel");
        if (!panel) return;
        const info = panel.querySelector(".panel-header");
        let action = panel.querySelector(".f6201b-dns-action");
        if (!action) {
            action = document.createElement("button");
            action.type = "button";
            action.className = "button ghost compact f6201b-dns-action";
            action.textContent = "Prévia / Aplicar DNS";
            info?.append(action);
        }
        let report = panel.querySelector(".f6201b-dns-feedback");
        if (!report) {
            report = document.createElement("div");
            report.className = "f6201b-inline-result f6201b-dns-feedback";
            report.setAttribute("aria-live","polite");
            panel.append(report);
        }
        try {
            const status = await apiRequest("/f6201b/write/status");
            const current = await apiRequest("/f6201b/dns/status");
            if(run !== epoch) return;
            primary.value = current.ipv4_1 || "";
            secondary.value = current.ipv4_2 || "";
            // O formulário legado possui DNS IPv6, mas este adaptador
            // deliberadamente preserva esses campos, sem alterá-los.
            $("profileDns6_1").value = current.ipv6_1 || "";
            $("profileDns6_2").value = current.ipv6_2 || "";
            action.disabled = !status.opted_in || !status.supported_firmware;
            report.textContent = action.disabled
                ? "DNS atual consultado. Alterações experimentais desativadas."
                : "DNS atual consultado. Para alterar, gere uma prévia.";
            action.onclick = async () => {
                const changes = {};
                if (primary.value !== current.ipv4_1)
                    changes.ipv4_1 = primary.value;
                if (secondary.value !== current.ipv4_2)
                    changes.ipv4_2 = secondary.value;
                if (!Object.keys(changes).length) {
                    report.textContent = "Nenhuma alteração de DNS.";
                    return;
                }
                setBusy(true,"Validando servidores DNS...");
                try {
                    const preview = await apiRequest("/f6201b/dns/preview",{
                        method:"POST", body:JSON.stringify({changes})
                    });
                    if (run !== epoch) return;
                    report.replaceChildren();
                    const diff = document.createElement("p");
                    diff.textContent = Object.entries(preview.changes)
                        .map(([field,item])=>field+": "+
                            item.before+" → "+item.after).join("\n");
                    const warn = document.createElement("p");
                    warn.textContent = "O DNS de clientes pode mudar. "
                        +"Prévia válida por 120 segundos; exige acesso local.";
                    const confirmation = document.createElement("input");
                    confirmation.type="text";
                    confirmation.placeholder="Digite APLICAR DNS F6201B";
                    confirmation.autocomplete="off";
                    const submit=document.createElement("button");
                    submit.type="button";
                    submit.className="button primary";
                    submit.textContent="Confirmar DNS";
                    submit.addEventListener("click",async()=>{
                        if(confirmation.value!=="APLICAR DNS F6201B"){
                            showToast("Confirmação de DNS incorreta.");
                            return;
                        }
                        submit.disabled=true;
                        setBusy(true,"Aplicando DNS e confirmando releitura...");
                        try{
                            const result=await apiRequest("/f6201b/dns/apply",{
                                method:"POST",body:JSON.stringify({
                                    nonce:preview.nonce,
                                    confirmation:confirmation.value
                                })
                            });
                            if(run!==epoch)return;
                            report.textContent=result.verified
                                ? "DNS confirmado pela releitura da ONT."
                                : "DNS não confirmado. Confira o painel original.";
                        }catch(error){
                            if(run===epoch)report.textContent=
                                "DNS não confirmado: "+error.message;
                        }finally{setBusy(false);}
                    });
                    report.append(diff,warn,confirmation,submit);
                }catch(error){
                    if(run===epoch)report.textContent=
                        "Falha na prévia: "+error.message;
                }finally{setBusy(false);}
            };
        } catch(error){
            if(run===epoch)report.textContent=
                "A leitura DNS não está disponível neste firmware/login.";
            action.disabled = true;
        }
    }
    async function open(page) {
        // F6600P/F670L continue usando integralmente os carregadores antigos.
        if (!ontConnected || routerWriteEnabled) return;
        if(!["wifi","wan","clients","dashboard","device","profiles"].includes(page))return;
        const info=await bootstrap();
        if(!info)return;
        const run=epoch;
        const tasks={
            wifi:renderWifi,wan:renderWan,clients:renderClients,
            dashboard:renderDashboard,device:renderDevice,
            profiles:renderDnsProfile
        };
        if(run===epoch)await tasks[page]();
    }
    document.addEventListener("zte:session-changed",reset);
    document.addEventListener("zte:page-open",event=>{
        const page=event.detail?.pageName;
        void open(page).catch(error=>
            console.warn("Leitura nativa F6201B indisponível:",error));
    });
})();

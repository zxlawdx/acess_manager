// =========================================================
// ZTE AUTOMATIC • CPE MANAGEMENT PLATFORM
// =========================================================

pageInfo.management = {
    title: "Gerenciamento",
    subtitle: "Frota, acesso remoto, rede, monitoramento e provisionamento."
};


const managementState = {
    devices: [],
    agents: [],
    profiles: [],
    incidents: [],
    backups: [],
    firmware: [],
    selectedDeviceId: null,
    monitorId: null,
    networkResult: null,
    meshResult: null
};


function managementEscape(value) {
    const node = document.createElement("div");
    node.textContent = value === undefined || value === null
        ? ""
        : String(value);

    return node.innerHTML;
}


function managementJson(value) {
    return JSON.stringify(
        value,
        null,
        2
    );
}


function managementParseJson(id) {
    const raw = document.getElementById(id)?.value.trim() || "{}";

    try {
        return JSON.parse(raw);
    } catch (error) {
        throw new Error(
            "JSON inválido: " + error.message
        );
    }
}


function managementOutput(id, value) {
    const element = document.getElementById(id);

    if (!element) {
        return;
    }

    element.textContent = typeof value === "string"
        ? value
        : managementJson(value);
}


async function managementCopyText(
    text,
    successMessage = "Conteúdo copiado."
) {
    const value = String(
        text ?? ""
    );

    if (!value) {
        showToast(
            "Não há conteúdo para copiar."
        );

        return false;
    }

    try {
        if (
            navigator.clipboard
            && window.isSecureContext
        ) {
            await navigator.clipboard.writeText(
                value
            );
        } else {
            throw new Error(
                "Clipboard API indisponível."
            );
        }
    } catch (error) {
        // Fallback importante para WebView/Qt e HTTP local, onde a
        // Clipboard API pode ser bloqueada mesmo com interação do usuário.
        const textarea = document.createElement(
            "textarea"
        );

        textarea.value = value;
        textarea.setAttribute(
            "readonly",
            ""
        );
        textarea.style.position = "fixed";
        textarea.style.left = "-9999px";
        textarea.style.top = "0";

        document.body.appendChild(
            textarea
        );

        textarea.focus();
        textarea.select();

        const copied = document.execCommand(
            "copy"
        );

        textarea.remove();

        if (!copied) {
            throw error;
        }
    }

    showToast(
        successMessage
    );

    return true;
}


function managementRelevantNetworkResult() {
    const result = managementState.networkResult;

    if (!result) {
        return null;
    }

    return {
        tr069: result.tr069 ?? null,
        wan: result.wan ?? null
    };
}


function selectedManagementDevice() {
    return managementState.devices.find(
        item => Number(item.id) === Number(
            managementState.selectedDeviceId
        )
    ) || null;
}


function checkedManagementDevices() {
    return [
        ...document.querySelectorAll(
            ".management-device-check:checked"
        )
    ].map(
        input => Number(
            input.value
        )
    );
}


function managementSelectedProfileId(selectId) {
    const value = document.getElementById(
        selectId
    )?.value;

    return value
        ? Number(value)
        : null;
}


function managementTags() {
    return (
        document.getElementById(
            "managementTags"
        )?.value || ""
    )
        .split(",")
        .map(item => item.trim())
        .filter(Boolean);
}


async function managementRequest(
    path,
    {
        method = "GET",
        body = null
    } = {}
) {
    return apiRequest(
        path,
        {
            method,
            ...(body !== null
                ? {
                    body: JSON.stringify(body)
                }
                : {})
        }
    );
}


function switchManagementTab(name) {
    document.querySelectorAll(
        ".management-tab"
    ).forEach(
        item => item.classList.toggle(
            "active",
            item.dataset.managementTab === name
        )
    );

    document.querySelectorAll(
        ".management-pane"
    ).forEach(
        item => item.classList.toggle(
            "active",
            item.dataset.managementPane === name
        )
    );
}


async function refreshManagement() {
    setBusy(
        true,
        "Atualizando plataforma de gerenciamento..."
    );

    try {
        const [
            inventory,
            profiles,
            agents,
            incidents,
            backups,
            firmware,
            acs
        ] = await Promise.all([
            managementRequest("/management/inventory"),
            managementRequest("/management/profiles"),
            managementRequest("/management/agents"),
            managementRequest("/management/incidents"),
            managementRequest("/management/backups"),
            managementRequest("/management/firmware"),
            managementRequest("/management/acs")
        ]);

        managementState.devices = inventory.devices || [];
        managementState.profiles = profiles.profiles || [];
        managementState.agents = agents.agents || [];
        managementState.incidents = incidents.incidents || [];
        managementState.backups = backups.backups || [];
        managementState.firmware = firmware.firmware || [];

        renderManagementInventory();
        renderManagementProfiles();
        renderManagementAgents();
        renderManagementIncidents();
        renderManagementBackups();
        renderManagementFirmware();
        renderManagementACS(acs);
        renderManagementCounters();

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


function renderManagementCounters() {
    document.getElementById(
        "managementDeviceCount"
    ).textContent = managementState.devices.length;

    document.getElementById(
        "managementOnlineCount"
    ).textContent = managementState.devices.filter(
        item => item.status === "online"
    ).length;

    document.getElementById(
        "managementIncidentCount"
    ).textContent = managementState.incidents.filter(
        item => item.status === "open"
    ).length;

    document.getElementById(
        "managementAgentCount"
    ).textContent = managementState.agents.filter(
        item => item.enabled
    ).length;
}


function relativeManagementTime(value) {
    if (!value) {
        return "-";
    }

    const date = new Date(value);
    const seconds = Math.max(
        0,
        Math.floor(
            (
                Date.now()
                - date.getTime()
            ) / 1000
        )
    );

    if (seconds < 60) {
        return seconds + "s";
    }

    if (seconds < 3600) {
        return Math.floor(
            seconds / 60
        ) + " min";
    }

    if (seconds < 86400) {
        return Math.floor(
            seconds / 3600
        ) + " h";
    }

    return Math.floor(
        seconds / 86400
    ) + " d";
}


function renderManagementInventory() {
    const body = document.getElementById(
        "managementInventoryBody"
    );

    if (!body) {
        return;
    }

    const search = (
        document.getElementById(
            "managementInventorySearch"
        )?.value || ""
    ).trim().toLowerCase();

    const visible = managementState.devices.filter(
        item => {
            if (!search) {
                return true;
            }

            return [
                item.customer_name,
                item.host,
                item.model,
                item.serial,
                item.mac,
                item.olt,
                item.cto,
                item.pop
            ].some(
                value => String(
                    value || ""
                ).toLowerCase().includes(
                    search
                )
            );
        }
    );

    body.innerHTML = visible.length
        ? visible.map(
            item => {
                const selected = Number(item.id) === Number(
                    managementState.selectedDeviceId
                );

                const topology = [
                    item.pop,
                    item.olt,
                    item.cto
                ].filter(Boolean).join(" / ") || "-";

                return `
                    <tr
                        data-device-id="${item.id}"
                        class="${selected ? "selected" : ""}"
                    >
                        <td>
                            <input
                                class="management-device-check"
                                type="checkbox"
                                value="${item.id}"
                                aria-label="Selecionar equipamento"
                            >
                        </td>
                        <td>
                            <strong>${managementEscape(item.model || "ZTE")}</strong>
                            <small>${managementEscape(item.serial || item.mac || item.key || "-")}</small>
                            <small>
                                FW ${managementEscape(item.firmware || "-")}
                                ${item.firmware_compliant === true
                                    ? " • homologado"
                                    : item.firmware_compliant === false
                                        ? " • fora do padrão"
                                        : ""}
                            </small>
                        </td>
                        <td>${managementEscape(item.customer_name || "-")}</td>
                        <td class="mono">${managementEscape(item.host || "-")}</td>
                        <td>${item.rx_power !== null && item.rx_power !== undefined ? managementEscape(item.rx_power + " dBm") : "-"}</td>
                        <td>${managementEscape(topology)}</td>
                        <td><span class="badge ${item.status === "online" ? "ok" : item.status === "offline" ? "critical" : ""}">${managementEscape(item.status || "unknown")}</span></td>
                        <td>há ${managementEscape(relativeManagementTime(item.last_seen))}</td>
                    </tr>
                `;
            }
        ).join("")
        : `
            <tr>
                <td colspan="8" class="muted">
                    Nenhuma ONT no inventário.
                </td>
            </tr>
        `;

    body.querySelectorAll(
        "tr[data-device-id]"
    ).forEach(
        row => {
            row.addEventListener(
                "click",
                event => {
                    if (
                        event.target.matches(
                            "input"
                        )
                    ) {
                        return;
                    }

                    managementState.selectedDeviceId = Number(
                        row.dataset.deviceId
                    );

                    renderManagementInventory();
                    showToast(
                        "ONT selecionada para gerenciamento."
                    );
                }
            );
        }
    );
}


function renderManagementProfiles() {
    const selects = [
        "managementDriftProfile",
        "managementZeroTouchProfile"
    ];

    const options = managementState.profiles.map(
        item => `
            <option value="${item.id}">
                ${managementEscape(item.name)}
                ${item.is_default ? " • padrão" : ""}
            </option>
        `
    ).join("");

    selects.forEach(
        id => {
            const select = document.getElementById(id);

            if (!select) {
                return;
            }

            const previous = select.value;
            select.innerHTML = options || '<option value="">Nenhum perfil</option>';

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
    );
}


function renderManagementAgents() {
    const list = document.getElementById(
        "managementAgentList"
    );

    const select = document.getElementById(
        "managementTerminalAgent"
    );

    if (select) {
        const previous = select.value;
        select.innerHTML = managementState.agents.map(
            item => `
                <option value="${item.id}">
                    ${managementEscape(item.name)} • ${managementEscape(item.host)}
                </option>
            `
        ).join("") || '<option value="">Nenhum Agent</option>';

        if (
            previous
            && [
                ...select.options
            ].some(
                item => item.value === previous
            )
        ) {
            select.value = previous;
        }
    }

    if (!list) {
        return;
    }

    list.innerHTML = managementState.agents.length
        ? managementState.agents.map(
            item => `
                <div class="management-list-item">
                    <div>
                        <strong>${managementEscape(item.name)}</strong>
                        <span>${managementEscape(item.ssh_user)}@${managementEscape(item.host)}:${managementEscape(item.ssh_port)}</span>
                        <small>${managementEscape(item.vpn_driver || "none")} • última leitura ${managementEscape(relativeManagementTime(item.last_seen))}</small>
                    </div>
                    <button class="button ghost compact" data-agent-test="${item.id}" type="button">Testar</button>
                </div>
            `
        ).join("")
        : '<div class="support-empty">Nenhum Agent cadastrado.</div>';

    list.querySelectorAll(
        "[data-agent-test]"
    ).forEach(
        button => button.addEventListener(
            "click",
            async () => {
                setBusy(
                    true,
                    "Testando Agent..."
                );

                try {
                    const result = await managementRequest(
                        "/management/agents/test",
                        {
                            method: "POST",
                            body: {
                                id: Number(
                                    button.dataset.agentTest
                                )
                            }
                        }
                    );

                    showToast(
                        result.success
                            ? "Agent acessível."
                            : "Agent respondeu com falha."
                    );

                    await refreshManagement();
                } catch (error) {
                    showToast(
                        error.message
                    );
                } finally {
                    setBusy(false);
                }
            }
        )
    );
}


function renderManagementIncidents() {
    const list = document.getElementById(
        "managementIncidentList"
    );

    if (!list) {
        return;
    }

    list.innerHTML = managementState.incidents.length
        ? managementState.incidents.map(
            item => `
                <div class="management-list-item incident ${managementEscape(item.severity)}">
                    <div>
                        <strong>${managementEscape(item.title)}</strong>
                        <span>${managementEscape(item.scope?.type || "")}: ${managementEscape(item.scope?.value || "")}</span>
                        <small>${managementEscape(item.device_ids?.length || 0)} equipamento(s) • ${managementEscape(item.status)}</small>
                    </div>
                    <span class="badge ${item.severity === "critical" ? "critical" : "warning"}">${managementEscape(item.severity)}</span>
                </div>
            `
        ).join("")
        : '<div class="support-empty">Nenhum incidente correlacionado.</div>';
}


function renderManagementBackups() {
    const list = document.getElementById(
        "managementBackupList"
    );

    if (!list) {
        return;
    }

    const selected = Number(
        managementState.selectedDeviceId
    );

    const items = managementState.backups.filter(
        item => (
            !selected
            || !item.device_id
            || Number(item.device_id) === selected
        )
    );

    list.innerHTML = items.length
        ? items.slice(0, 30).map(
            item => `
                <div class="management-list-item">
                    <div>
                        <strong>#${item.id} • ${managementEscape(item.reason || "backup")}</strong>
                        <span class="mono">${managementEscape(item.path)}</span>
                        <small>${managementEscape(item.created_at)}</small>
                    </div>
                    <button class="button danger compact" data-backup-restore="${item.id}" type="button">Restaurar</button>
                </div>
            `
        ).join("")
        : '<div class="support-empty">Nenhum backup registrado.</div>';

    list.querySelectorAll(
        "[data-backup-restore]"
    ).forEach(
        button => button.addEventListener(
            "click",
            async () => {
                if (!window.confirm(
                    "Restaurar este backup? A ONT pode reiniciar e a sessão será perdida."
                )) {
                    return;
                }

                setBusy(
                    true,
                    "Enviando backup para a ONT..."
                );

                try {
                    const result = await managementRequest(
                        "/management/backups/restore",
                        {
                            method: "POST",
                            body: {
                                backup_id: Number(
                                    button.dataset.backupRestore
                                ),
                                confirm: true
                            }
                        }
                    );

                    showToast(
                        result.message || "Restore enviado."
                    );
                } catch (error) {
                    showToast(
                        error.message
                    );
                } finally {
                    setBusy(false);
                }
            }
        )
    );
}


function renderManagementFirmware() {
    const list = document.getElementById(
        "managementFirmwareList"
    );

    if (!list) {
        return;
    }

    const device = selectedManagementDevice();

    list.innerHTML = managementState.firmware.length
        ? managementState.firmware.map(
            item => {
                const compatible = !device
                    || !device.model
                    || item.model === device.model;

                return `
                    <div class="management-list-item">
                        <div>
                            <strong>${managementEscape(item.model)} • ${managementEscape(item.version)}</strong>
                            <span class="mono">${managementEscape(item.file_path)}</span>
                            <small>${item.approved ? "APROVADO" : "não aprovado"} • SHA ${managementEscape((item.sha256 || "").slice(0, 12))}</small>
                        </div>
                        <button
                            class="button danger compact"
                            data-firmware-upgrade="${item.id}"
                            type="button"
                            ${compatible && item.approved && device ? "" : "disabled"}
                        >
                            Atualizar
                        </button>
                    </div>
                `;
            }
        ).join("")
        : '<div class="support-empty">Nenhum firmware cadastrado.</div>';

    list.querySelectorAll(
        "[data-firmware-upgrade]"
    ).forEach(
        button => button.addEventListener(
            "click",
            async () => {
                const deviceId = managementState.selectedDeviceId;

                if (!deviceId) {
                    showToast(
                        "Selecione uma ONT no inventário."
                    );

                    return;
                }

                if (!window.confirm(
                    "Confirmar upgrade? O sistema criará backup antes do upload e a ONT poderá reiniciar."
                )) {
                    return;
                }

                setBusy(
                    true,
                    "Validando e enviando firmware..."
                );

                try {
                    const result = await managementRequest(
                        "/management/firmware/upgrade",
                        {
                            method: "POST",
                            body: {
                                device_id: Number(deviceId),
                                firmware_id: Number(
                                    button.dataset.firmwareUpgrade
                                ),
                                confirm: true
                            }
                        }
                    );

                    showToast(
                        result.message || "Firmware enviado."
                    );

                    await refreshManagement();
                } catch (error) {
                    showToast(
                        error.message
                    );
                } finally {
                    setBusy(false);
                }
            }
        )
    );
}


function renderManagementACS(status) {
    const config = status?.config || {};

    if (
        config.provider
        && document.getElementById(
            "managementAcsProvider"
        )
    ) {
        document.getElementById(
            "managementAcsProvider"
        ).value = config.provider;
    }

    if (
        config.base_url
        && document.getElementById(
            "managementAcsUrl"
        )
    ) {
        document.getElementById(
            "managementAcsUrl"
        ).value = config.base_url;
    }

    managementOutput(
        "managementAcsOutput",
        status
    );
}


function renderManagementTopology(result) {
    const root = document.getElementById(
        "managementTopology"
    );

    if (!root) {
        return;
    }

    const nodes = new Map(
        (result.nodes || []).map(
            node => [
                node.id,
                node
            ]
        )
    );

    const order = [];
    const clientNodes = (
        result.nodes || []
    ).filter(
        node => node.kind.startsWith(
            "client_"
        )
    );

    if (clientNodes.length) {
        order.push({
            label: clientNodes.map(
                item => item.label
            ).join(", "),
            kind: "clients",
            status: clientNodes.some(
                item => item.status === "critical"
            )
                ? "critical"
                : clientNodes.some(
                    item => item.status === "warning"
                )
                    ? "warning"
                    : "ok"
        });
    }

    [
        "ont",
        "cto",
        "olt",
        "pop",
        "internet"
    ].forEach(
        id => {
            if (nodes.has(id)) {
                order.push(
                    nodes.get(id)
                );
            }
        }
    );

    root.innerHTML = order.length
        ? order.map(
            (node, index) => `
                ${index ? '<span class="topology-arrow">→</span>' : ""}
                <div class="topology-node ${managementEscape(node.status || "unknown")}">
                    <span>${managementEscape(node.kind)}</span>
                    <strong>${managementEscape(node.label)}</strong>
                </div>
            `
        ).join("")
        : '<div class="support-empty">Sem dados de topologia.</div>';
}


async function syncManagementInventory() {
    setBusy(
        true,
        "Sincronizando inventário da ONT..."
    );

    try {
        const agentRaw = document.getElementById(
            "managementAgentId"
        )?.value;

        const result = await managementRequest(
            "/management/inventory/sync",
            {
                method: "POST",
                body: {
                    customer_name: document.getElementById(
                        "managementCustomer"
                    )?.value.trim() || null,
                    pop: document.getElementById(
                        "managementPop"
                    )?.value.trim() || null,
                    olt: document.getElementById(
                        "managementOlt"
                    )?.value.trim() || null,
                    cto: document.getElementById(
                        "managementCto"
                    )?.value.trim() || null,
                    agent_id: agentRaw
                        ? Number(agentRaw)
                        : null,
                    tags: managementTags()
                }
            }
        );

        managementState.selectedDeviceId = result.device?.id || null;

        showToast(
            "Inventário atualizado."
        );

        await refreshManagement();
    } catch (error) {
        showToast(
            error.message
        );
    } finally {
        setBusy(false);
    }
}


async function saveManagementProfile() {
    try {
        const config = managementParseJson(
            "managementProfileJson"
        );

        await managementRequest(
            "/management/profiles/save",
            {
                method: "POST",
                body: {
                    name: document.getElementById(
                        "managementProfileName"
                    ).value.trim(),
                    config,
                    is_default: document.getElementById(
                        "managementProfileDefault"
                    ).checked
                }
            }
        );

        showToast(
            "Perfil corporativo salvo."
        );

        await refreshManagement();
    } catch (error) {
        showToast(
            error.message
        );
    }
}


async function checkManagementDrift(fix = false) {
    const profileId = managementSelectedProfileId(
        "managementDriftProfile"
    );

    if (!profileId) {
        showToast(
            "Cadastre/selecione um perfil."
        );

        return;
    }

    if (
        fix
        && !window.confirm(
            "Corrigir as divergências da ONT atual? Um backup será criado antes."
        )
    ) {
        return;
    }

    setBusy(
        true,
        fix
            ? "Corrigindo Config Drift..."
            : "Comparando perfil com a ONT..."
    );

    try {
        const result = await managementRequest(
            fix
                ? "/management/drift/remediate"
                : "/management/drift",
            {
                method: "POST",
                body: {
                    profile_id: profileId,
                    confirm: fix
                }
            }
        );

        const assessment = result.after || result;

        managementOutput(
            "managementDriftOutput",
            result
        );

        const badge = document.getElementById(
            "managementDriftBadge"
        );

        badge.className = "badge " + (
            assessment.compliant
                ? "ok"
                : "warning"
        );

        badge.textContent = assessment.compliant
            ? "Conforme"
            : (
                assessment.count
                + " divergência(s)"
            );

        showToast(
            fix
                ? "Correção de drift concluída."
                : "Comparação concluída."
        );
    } catch (error) {
        showToast(
            error.message
        );
    } finally {
        setBusy(false);
    }
}


async function runManagementBatch() {
    const deviceIds = checkedManagementDevices();

    if (!deviceIds.length) {
        showToast(
            "Marque pelo menos uma ONT no inventário."
        );

        return;
    }

    try {
        let payload = managementParseJson(
            "managementBatchPayload"
        );

        const operation = document.getElementById(
            "managementBatchOperation"
        ).value;

        if (
            [
                "profile_remediate",
                "profile_acs"
            ].includes(operation)
            && !payload.profile_id
        ) {
            payload = {
                ...payload,
                profile_id: managementSelectedProfileId(
                    "managementDriftProfile"
                )
            };
        }

        const result = await managementRequest(
            "/management/batch",
            {
                method: "POST",
                body: {
                    operation,
                    device_ids: deviceIds,
                    payload
                }
            }
        );

        managementOutput(
            "managementBatchOutput",
            result
        );

        showToast(
            "Job em lote iniciado."
        );
    } catch (error) {
        showToast(
            error.message
        );
    }
}


async function refreshManagementBatch() {
    try {
        const result = await managementRequest(
            "/management/batch"
        );

        managementOutput(
            "managementBatchOutput",
            result
        );
    } catch (error) {
        showToast(
            error.message
        );
    }
}


async function saveManagementAgent() {
    try {
        const result = await managementRequest(
            "/management/agents/save",
            {
                method: "POST",
                body: {
                    name: document.getElementById(
                        "managementAgentName"
                    ).value.trim(),
                    host: document.getElementById(
                        "managementAgentHost"
                    ).value.trim(),
                    ssh_user: document.getElementById(
                        "managementAgentUser"
                    ).value.trim(),
                    ssh_port: Number(
                        document.getElementById(
                            "managementAgentPort"
                        ).value || 22
                    ),
                    ssh_key_path: document.getElementById(
                        "managementAgentKey"
                    ).value.trim() || null,
                    vpn_driver: document.getElementById(
                        "managementAgentVpn"
                    ).value,
                    enabled: true,
                    vpn_config: {}
                }
            }
        );

        showToast(
            "Agent salvo."
        );

        if (result.id) {
            document.getElementById(
                "managementAgentId"
            ).value = result.id;
        }

        await refreshManagement();
    } catch (error) {
        showToast(
            error.message
        );
    }
}


async function runManagementBufferbloat() {
    const agentId = Number(
        document.getElementById(
            "managementTerminalAgent"
        )?.value || 0
    );

    const iperfHost = document.getElementById(
        "managementTerminalExtra"
    )?.value.trim();

    const pingHost = document.getElementById(
        "managementTerminalHost"
    )?.value.trim() || "1.1.1.1";

    if (!agentId) {
        showToast(
            "Cadastre/selecione um Agent."
        );
        return;
    }

    if (!iperfHost) {
        showToast(
            "Informe o servidor iperf3 no campo Interface / IPERF."
        );
        return;
    }

    setBusy(
        true,
        "Medindo latência em repouso e durante carga..."
    );

    try {
        const result = await managementRequest(
            "/management/gateway/bufferbloat",
            {
                method: "POST",
                body: {
                    agent_id: agentId,
                    ping_host: pingHost,
                    iperf_host: iperfHost,
                    direction: "download",
                    duration: 10,
                    streams: 4
                }
            }
        );

        managementOutput(
            "managementTerminalOutput",
            result
        );

        const delta = result.latency_delta_ms;

        showToast(
            delta === null || delta === undefined
                ? "Teste concluído sem delta de latência."
                : "Bufferbloat: +" + Number(delta).toFixed(1) + " ms sob carga."
        );
    } catch (error) {
        managementOutput(
            "managementTerminalOutput",
            {
                error: error.message
            }
        );
        showToast(
            error.message
        );
    } finally {
        setBusy(false);
    }
}


async function openManagementRemote() {
    const device = selectedManagementDevice();

    if (!device) {
        showToast(
            "Selecione uma ONT no inventário."
        );

        return;
    }

    setBusy(
        true,
        "Abrindo túnel remoto temporário..."
    );

    try {
        const result = await managementRequest(
            "/management/remote/open",
            {
                method: "POST",
                body: {
                    device_id: device.id,
                    ttl_minutes: Number(
                        document.getElementById(
                            "managementRemoteTtl"
                        ).value || 30
                    ),
                    remote_port: Number(
                        document.getElementById(
                            "managementRemotePort"
                        ).value || 80
                    )
                }
            }
        );

        managementOutput(
            "managementRemoteOutput",
            result
        );

        showToast(
            "Acesso remoto aberto em " + result.access_url
        );
    } catch (error) {
        managementOutput(
            "managementRemoteOutput",
            {
                error: error.message
            }
        );

        showToast(
            error.message
        );
    } finally {
        setBusy(false);
    }
}


async function refreshRemoteSessions() {
    try {
        const result = await managementRequest(
            "/management/remote/sessions"
        );

        managementOutput(
            "managementRemoteOutput",
            result
        );
    } catch (error) {
        showToast(
            error.message
        );
    }
}


async function runManagementTerminal() {
    const agentId = Number(
        document.getElementById(
            "managementTerminalAgent"
        )?.value || 0
    );

    if (!agentId) {
        showToast(
            "Cadastre/selecione um Agent."
        );

        return;
    }

    const command = document.getElementById(
        "managementTerminalCommand"
    ).value;

    const host = document.getElementById(
        "managementTerminalHost"
    ).value.trim();

    const extra = document.getElementById(
        "managementTerminalExtra"
    ).value.trim();

    const params = {};

    if (
        [
            "ping",
            "traceroute",
            "dns"
        ].includes(command)
    ) {
        params.host = host;
    }

    if (command === "iperf3") {
        params.host = extra || host;
        params.duration = 10;
        params.streams = 4;
    }

    if (command === "capture") {
        params.interface = extra || "eth0";
        params.host = host || null;
        params.duration = 10;
        params.count = 100;
    }

    setBusy(
        true,
        "Executando no gateway..."
    );

    try {
        const result = await managementRequest(
            "/management/gateway/command",
            {
                method: "POST",
                body: {
                    agent_id: agentId,
                    command,
                    params
                }
            }
        );

        managementOutput(
            "managementTerminalOutput",
            result
        );
    } catch (error) {
        managementOutput(
            "managementTerminalOutput",
            {
                error: error.message
            }
        );

        showToast(
            error.message
        );
    } finally {
        setBusy(false);
    }
}


function renderManagementMonitor(result) {
    managementOutput(
        "managementMonitorOutput",
        result
    );

    const chart = document.getElementById(
        "managementMonitorChart"
    );

    const events = document.getElementById(
        "managementMonitorEvents"
    );

    const samples = result?.samples || [];

    const points = samples.map(
        item => ({
            at: item.captured_at,
            value: Number(
                item.payload?.optical?.rx_power_dbm
            )
        })
    ).filter(
        item => Number.isFinite(
            item.value
        )
    );

    if (chart) {
        if (points.length < 2) {
            chart.innerHTML = '<div class="support-empty">Aguardando pelo menos duas leituras ópticas.</div>';
        } else {
            const width = 800;
            const height = 165;
            const padX = 46;
            const padY = 18;
            const values = points.map(
                item => item.value
            );
            const min = Math.min(
                -8,
                ...values
            );
            const max = Math.max(
                -27,
                ...values
            );
            const range = Math.max(
                1,
                max - min
            );

            const coords = points.map(
                (item, index) => {
                    const x = padX + (
                        index
                        / Math.max(
                            1,
                            points.length - 1
                        )
                    ) * (
                        width
                        - padX
                        - 12
                    );

                    const y = padY + (
                        (
                            max
                            - item.value
                        )
                        / range
                    ) * (
                        height
                        - padY * 2
                    );

                    return {
                        x,
                        y,
                        ...item
                    };
                }
            );

            const polyline = coords.map(
                item => (
                    item.x.toFixed(1)
                    + ","
                    + item.y.toFixed(1)
                )
            ).join(" ");

            chart.innerHTML = `
                <svg viewBox="0 0 ${width} ${height}" preserveAspectRatio="none" role="img" aria-label="Variação da potência óptica">
                    <line class="grid-line" x1="${padX}" y1="20" x2="${width - 10}" y2="20"></line>
                    <line class="grid-line" x1="${padX}" y1="${height / 2}" x2="${width - 10}" y2="${height / 2}"></line>
                    <line class="grid-line" x1="${padX}" y1="${height - 20}" x2="${width - 10}" y2="${height - 20}"></line>
                    <text class="axis-label" x="2" y="23">${managementEscape(max.toFixed(1))} dBm</text>
                    <text class="axis-label" x="2" y="${height - 17}">${managementEscape(min.toFixed(1))} dBm</text>
                    <polyline class="rx-line" points="${polyline}"></polyline>
                    ${coords.map(
                        point => `
                            <circle class="rx-point" cx="${point.x.toFixed(1)}" cy="${point.y.toFixed(1)}" r="2.8">
                                <title>${managementEscape(point.at)} • ${managementEscape(point.value.toFixed(1))} dBm</title>
                            </circle>
                        `
                    ).join("")}
                </svg>
            `;
        }
    }

    if (events) {
        const items = result?.events || [];

        events.innerHTML = items.length
            ? items.slice().reverse().map(
                item => `
                    <div class="management-list-item incident ${managementEscape(item.severity)}">
                        <div>
                            <strong>${managementEscape(item.message)}</strong>
                            <span class="mono">${managementEscape(item.code)}</span>
                            <small>${managementEscape(item.at)}</small>
                        </div>
                    </div>
                `
            ).join("")
            : '<div class="support-empty">Nenhum evento de intermitência detectado.</div>';
    }
}


async function startManagementMonitor() {
    setBusy(
        true,
        "Iniciando monitor temporal..."
    );

    try {
        const result = await managementRequest(
            "/management/monitor/start",
            {
                method: "POST",
                body: {
                    device_id: managementState.selectedDeviceId,
                    duration_seconds: Number(
                        document.getElementById(
                            "managementMonitorDuration"
                        ).value || 300
                    ),
                    interval_seconds: Number(
                        document.getElementById(
                            "managementMonitorInterval"
                        ).value || 10
                    ),
                    ping_host: document.getElementById(
                        "managementMonitorPing"
                    ).value.trim() || "1.1.1.1"
                }
            }
        );

        managementState.monitorId = result.id;

        renderManagementMonitor(
            result
        );

        showToast(
            "Monitor iniciado."
        );
    } catch (error) {
        showToast(
            error.message
        );
    } finally {
        setBusy(false);
    }
}


async function refreshManagementMonitor() {
    if (!managementState.monitorId) {
        showToast(
            "Nenhum monitor iniciado nesta tela."
        );

        return;
    }

    try {
        const result = await managementRequest(
            "/management/monitor/status?id="
            + encodeURIComponent(
                managementState.monitorId
            )
        );

        renderManagementMonitor(
            result
        );
    } catch (error) {
        showToast(
            error.message
        );
    }
}


async function stopManagementMonitor() {
    if (!managementState.monitorId) {
        return;
    }

    try {
        const result = await managementRequest(
            "/management/monitor/stop",
            {
                method: "POST",
                body: {
                    id: managementState.monitorId
                }
            }
        );

        renderManagementMonitor(
            result
        );

        showToast(
            "Monitor encerrado."
        );
    } catch (error) {
        showToast(
            error.message
        );
    }
}


async function correlateManagementIncidents() {
    try {
        await managementRequest(
            "/management/incidents/correlate",
            {
                method: "POST",
                body: {
                    minimum_devices: 5
                }
            }
        );

        const result = await managementRequest(
            "/management/incidents"
        );

        managementState.incidents = result.incidents || [];

        renderManagementIncidents();
        renderManagementCounters();

        showToast(
            "Correlação atualizada."
        );
    } catch (error) {
        showToast(
            error.message
        );
    }
}


async function loadManagementTopology() {
    const device = selectedManagementDevice();

    if (!device) {
        showToast(
            "Selecione uma ONT no inventário."
        );

        return;
    }

    try {
        const result = await managementRequest(
            "/management/topology?device_id="
            + encodeURIComponent(
                device.id
            )
        );

        renderManagementTopology(
            result
        );
    } catch (error) {
        showToast(
            error.message
        );
    }
}


function renderManagementMesh(result) {
    managementState.meshResult = result;

    managementOutput(
        "managementMeshOutput",
        result
    );

    const badge = document.getElementById(
        "managementMeshStatusBadge"
    );

    if (badge) {
        badge.className = "badge " + (
            result.available
                ? (
                    result.enabled
                        ? "ok"
                        : "warning"
                )
                : "critical"
        );

        badge.textContent = !result.available
            ? "Indisponível"
            : result.enabled
                ? "Mesh ativo"
                : "Mesh desligado";
    }

    const enabled = document.getElementById(
        "managementMeshEnabled"
    );

    if (enabled) {
        enabled.checked = Boolean(
            result.enabled
        );
    }

    const steering = document.getElementById(
        "managementMeshBandSteering"
    );

    if (
        steering
        && result.band_steering !== null
        && result.band_steering !== undefined
    ) {
        steering.checked = Boolean(
            result.band_steering
        );
    }

    const rssi24 = document.getElementById(
        "managementMeshRssi24"
    );

    if (
        rssi24
        && result.rssi_limit_24g !== null
        && result.rssi_limit_24g !== undefined
    ) {
        rssi24.value = result.rssi_limit_24g;
    }

    const rssi5 = document.getElementById(
        "managementMeshRssi5"
    );

    if (
        rssi5
        && result.rssi_limit_5g !== null
        && result.rssi_limit_5g !== undefined
    ) {
        rssi5.value = result.rssi_limit_5g;
    }

    const legacy = document.getElementById(
        "managementMeshLegacyRoaming"
    );

    if (
        legacy
        && result.legacy_station_roaming !== null
        && result.legacy_station_roaming !== undefined
    ) {
        legacy.checked = Boolean(
            result.legacy_station_roaming
        );
    }
}


async function readManagementMesh() {
    setBusy(
        true,
        "Detectando EasyMesh / NetSphere..."
    );

    try {
        const result = await managementRequest(
            "/management/mesh"
        );

        renderManagementMesh(
            result
        );

        showToast(
            result.available
                ? "Backend EasyMesh detectado."
                : "EasyMesh não foi detectado."
        );

        return result;
    } catch (error) {
        const result = {
            available: false,
            error: error.message
        };

        renderManagementMesh(
            result
        );

        showToast(
            error.message
        );

        return result;
    } finally {
        setBusy(
            false
        );
    }
}


async function applyManagementMesh() {
    if (!window.confirm(
        "Aplicar a configuração EasyMesh na ONT atual? A rede Wi-Fi pode reiniciar por alguns instantes."
    )) {
        return;
    }

    const rssi24Raw = document.getElementById(
        "managementMeshRssi24"
    )?.value;

    const rssi5Raw = document.getElementById(
        "managementMeshRssi5"
    )?.value;

    setBusy(
        true,
        "Aplicando EasyMesh..."
    );

    try {
        const result = await managementRequest(
            "/management/mesh/configure",
            {
                method: "POST",
                body: {
                    enabled: Boolean(
                        document.getElementById(
                            "managementMeshEnabled"
                        )?.checked
                    ),
                    band_steering: Boolean(
                        document.getElementById(
                            "managementMeshBandSteering"
                        )?.checked
                    ),
                    rssi_limit_24g: rssi24Raw
                        ? Number(rssi24Raw)
                        : null,
                    rssi_limit_5g: rssi5Raw
                        ? Number(rssi5Raw)
                        : null,
                    legacy_station_roaming: Boolean(
                        document.getElementById(
                            "managementMeshLegacyRoaming"
                        )?.checked
                    ),
                    confirm: true
                }
            }
        );

        renderManagementMesh(
            result.after || result
        );

        showToast(
            "Configuração EasyMesh aplicada."
        );
    } catch (error) {
        managementOutput(
            "managementMeshOutput",
            {
                error: error.message
            }
        );

        showToast(
            error.message
        );
    } finally {
        setBusy(
            false
        );
    }
}


async function pairManagementMesh() {
    if (!managementState.meshResult) {
        const status = await readManagementMesh();

        if (
            !status
            || !status.available
        ) {
            return;
        }
    }

    if (
        !managementState.meshResult?.enabled
    ) {
        showToast(
            "Ative o EasyMesh antes de parear o Agent."
        );

        return;
    }

    if (!window.confirm(
        "Abrir a janela WPS/EasyMesh do Controller agora? Depois acione WPS no equipamento Agent."
    )) {
        return;
    }

    setBusy(
        true,
        "Abrindo janela de pareamento EasyMesh..."
    );

    try {
        const result = await managementRequest(
            "/management/mesh/pair",
            {
                method: "POST",
                body: {
                    confirm: true
                }
            }
        );

        managementOutput(
            "managementMeshOutput",
            result
        );

        showToast(
            result.message
            || "Pareamento iniciado."
        );
    } catch (error) {
        managementOutput(
            "managementMeshOutput",
            {
                error: error.message
            }
        );

        showToast(
            error.message
        );
    } finally {
        setBusy(
            false
        );
    }
}


async function refreshManagementNetwork() {
    setBusy(
        true,
        "Lendo controles de rede da ONT..."
    );

    try {
        const result = await managementRequest(
            "/management/network"
        );

        managementState.networkResult = result;

        managementOutput(
            "managementNetworkOutput",
            result
        );

        const copyButton = document.getElementById(
            "managementNetworkCopy"
        );

        const relevantButton = document.getElementById(
            "managementNetworkCopyRelevant"
        );

        if (copyButton) {
            copyButton.disabled = false;
        }

        if (relevantButton) {
            relevantButton.disabled = false;
        }
    } catch (error) {
        managementState.networkResult = null;

        managementOutput(
            "managementNetworkOutput",
            {
                error: error.message
            }
        );

        const copyButton = document.getElementById(
            "managementNetworkCopy"
        );

        const relevantButton = document.getElementById(
            "managementNetworkCopyRelevant"
        );

        if (copyButton) {
            copyButton.disabled = true;
        }

        if (relevantButton) {
            relevantButton.disabled = true;
        }

        showToast(
            error.message
        );
    } finally {
        setBusy(false);
    }
}


async function saveManagementQos() {
    if (!window.confirm(
        "Aplicar esta configuração QoS na ONT atual?"
    )) {
        return;
    }

    try {
        const result = await managementRequest(
            "/management/qos/save",
            {
                method: "POST",
                body: {
                    kind: document.getElementById(
                        "managementQosKind"
                    ).value,
                    config: managementParseJson(
                        "managementQosJson"
                    ),
                    confirm: true
                }
            }
        );

        managementOutput(
            "managementNetworkOutput",
            result
        );

        showToast(
            "QoS atualizado."
        );
    } catch (error) {
        showToast(
            error.message
        );
    }
}


async function saveManagementFirewall() {
    if (!window.confirm(
        "Alterar o firewall da ONT atual?"
    )) {
        return;
    }

    try {
        const result = await managementRequest(
            "/management/firewall/update",
            {
                method: "POST",
                body: {
                    config: {
                        enabled: document.getElementById(
                            "managementFirewallEnabled"
                        ).checked,
                        level: document.getElementById(
                            "managementFirewallLevel"
                        ).value
                    },
                    confirm: true
                }
            }
        );

        managementOutput(
            "managementNetworkOutput",
            result
        );

        showToast(
            "Firewall atualizado."
        );
    } catch (error) {
        showToast(
            error.message
        );
    }
}


async function saveManagementFirewallRule() {
    if (!window.confirm(
        "Salvar este filtro no firewall da ONT atual?"
    )) {
        return;
    }

    try {
        const result = await managementRequest(
            "/management/firewall/rules/save",
            {
                method: "POST",
                body: {
                    kind: document.getElementById(
                        "managementFirewallRuleKind"
                    ).value,
                    config: managementParseJson(
                        "managementFirewallRuleJson"
                    ),
                    confirm: true
                }
            }
        );

        managementOutput(
            "managementNetworkOutput",
            result
        );

        showToast(
            "Filtro de firewall salvo."
        );
    } catch (error) {
        showToast(
            error.message
        );
    }
}


async function deleteManagementFirewallRule() {
    const id = document.getElementById(
        "managementFirewallRuleId"
    ).value.trim();

    if (!id) {
        showToast(
            "Informe o ID do filtro."
        );

        return;
    }

    if (!window.confirm(
        "Excluir este filtro do firewall?"
    )) {
        return;
    }

    try {
        const result = await managementRequest(
            "/management/firewall/rules/delete",
            {
                method: "POST",
                body: {
                    kind: document.getElementById(
                        "managementFirewallRuleKind"
                    ).value,
                    id,
                    config: {},
                    confirm: true
                }
            }
        );

        managementOutput(
            "managementNetworkOutput",
            result
        );

        showToast(
            "Filtro removido."
        );
    } catch (error) {
        showToast(
            error.message
        );
    }
}


async function saveManagementFilterGlobal() {
    if (!window.confirm(
        "Alterar a política global de filtros?"
    )) {
        return;
    }

    try {
        const result = await managementRequest(
            "/management/firewall/filter-global",
            {
                method: "POST",
                body: {
                    config: managementParseJson(
                        "managementFirewallGlobalJson"
                    ),
                    confirm: true
                }
            }
        );

        managementOutput(
            "managementNetworkOutput",
            result
        );

        showToast(
            "Política global atualizada."
        );
    } catch (error) {
        showToast(
            error.message
        );
    }
}


async function saveManagementSntp() {
    try {
        const result = await managementRequest(
            "/management/sntp/update",
            {
                method: "POST",
                body: {
                    config: managementParseJson(
                        "managementSntpJson"
                    )
                }
            }
        );

        managementOutput(
            "managementNetworkOutput",
            result
        );

        showToast(
            "SNTP atualizado."
        );
    } catch (error) {
        showToast(
            error.message
        );
    }
}


async function saveManagementTr069() {
    if (!window.confirm(
        "Alterar os parâmetros TR-069/ACS da ONT?"
    )) {
        return;
    }

    try {
        const result = await managementRequest(
            "/management/tr069/update",
            {
                method: "POST",
                body: {
                    config: managementParseJson(
                        "managementTr069Json"
                    ),
                    confirm: true
                }
            }
        );

        managementOutput(
            "managementNetworkOutput",
            result
        );

        showToast(
            "TR-069 atualizado."
        );
    } catch (error) {
        showToast(
            error.message
        );
    }
}


async function createManagementWan() {
    if (!window.confirm(
        "Criar uma nova WAN/VLAN/PPPoE? Um backup será criado antes."
    )) {
        return;
    }

    try {
        const result = await managementRequest(
            "/management/wan/create",
            {
                method: "POST",
                body: {
                    config: managementParseJson(
                        "managementWanJson"
                    ),
                    confirm: true
                }
            }
        );

        managementOutput(
            "managementNetworkOutput",
            result
        );

        showToast(
            "Nova WAN criada."
        );
    } catch (error) {
        showToast(
            error.message
        );
    }
}


async function updateManagementWan() {
    if (!window.confirm(
        "Aplicar alteração WAN/VLAN/PPPoE? Um backup será criado antes."
    )) {
        return;
    }

    try {
        const result = await managementRequest(
            "/management/wan/update",
            {
                method: "POST",
                body: {
                    id: document.getElementById(
                        "managementWanId"
                    ).value.trim(),
                    config: managementParseJson(
                        "managementWanJson"
                    ),
                    confirm: true
                }
            }
        );

        managementOutput(
            "managementNetworkOutput",
            result
        );

        showToast(
            "WAN atualizada."
        );
    } catch (error) {
        showToast(
            error.message
        );
    }
}


async function deleteManagementWan() {
    const id = document.getElementById(
        "managementWanId"
    ).value.trim();

    if (!id) {
        showToast(
            "Informe o ID da WAN."
        );
        return;
    }

    if (!window.confirm(
        "Excluir esta WAN? Um backup será criado antes e a conexão pode cair."
    )) {
        return;
    }

    try {
        const result = await managementRequest(
            "/management/wan/delete",
            {
                method: "POST",
                body: {
                    id,
                    confirm: true
                }
            }
        );

        managementOutput(
            "managementNetworkOutput",
            result
        );

        showToast(
            "WAN removida."
        );
    } catch (error) {
        showToast(
            error.message
        );
    }
}


async function runManagementWanAction() {
    try {
        const result = await managementRequest(
            "/management/wan/action",
            {
                method: "POST",
                body: {
                    id: document.getElementById(
                        "managementWanId"
                    ).value.trim(),
                    action: document.getElementById(
                        "managementWanAction"
                    ).value
                }
            }
        );

        managementOutput(
            "managementNetworkOutput",
            result
        );
    } catch (error) {
        showToast(
            error.message
        );
    }
}


async function runManagementBridge() {
    if (!window.confirm(
        "ATENÇÃO: colocar a WAN em bridge pode derrubar o acesso atual. Criar backup e continuar?"
    )) {
        return;
    }

    try {
        const result = await managementRequest(
            "/management/bridge",
            {
                method: "POST",
                body: {
                    id: document.getElementById(
                        "managementWanId"
                    ).value.trim(),
                    config: managementParseJson(
                        "managementWanJson"
                    ),
                    confirm: true
                }
            }
        );

        managementOutput(
            "managementNetworkOutput",
            result
        );

        showToast(
            "Bridge Mode processado."
        );
    } catch (error) {
        showToast(
            error.message
        );
    }
}


async function createManagementBackup() {
    try {
        const result = await managementRequest(
            "/management/backups/create",
            {
                method: "POST",
                body: {
                    device_id: managementState.selectedDeviceId,
                    reason: document.getElementById(
                        "managementBackupReason"
                    ).value.trim() || "manual"
                }
            }
        );

        showToast(
            "Backup criado: " + result.filename
        );

        await refreshManagement();
    } catch (error) {
        showToast(
            error.message
        );
    }
}


async function compareManagementBackups() {
    const leftId = Number(
        document.getElementById(
            "managementBackupLeft"
        ).value || 0
    );

    const rightId = Number(
        document.getElementById(
            "managementBackupRight"
        ).value || 0
    );

    if (!leftId || !rightId) {
        showToast(
            "Informe os dois IDs de backup."
        );

        return;
    }

    try {
        const result = await managementRequest(
            "/management/backups/compare",
            {
                method: "POST",
                body: {
                    left_id: leftId,
                    right_id: rightId
                }
            }
        );

        managementOutput(
            "managementBackupCompareOutput",
            result
        );
    } catch (error) {
        showToast(
            error.message
        );
    }
}


async function registerManagementFirmware() {
    try {
        const result = await managementRequest(
            "/management/firmware/register",
            {
                method: "POST",
                body: {
                    model: document.getElementById(
                        "managementFirmwareModel"
                    ).value.trim(),
                    version: document.getElementById(
                        "managementFirmwareVersion"
                    ).value.trim(),
                    file_path: document.getElementById(
                        "managementFirmwarePath"
                    ).value.trim(),
                    approved: document.getElementById(
                        "managementFirmwareApproved"
                    ).checked
                }
            }
        );

        showToast(
            "Firmware cadastrado: " + result.version
        );

        await refreshManagement();
    } catch (error) {
        showToast(
            error.message
        );
    }
}


async function saveManagementACS() {
    try {
        const result = await managementRequest(
            "/management/acs/configure",
            {
                method: "POST",
                body: {
                    provider: document.getElementById(
                        "managementAcsProvider"
                    ).value,
                    base_url: document.getElementById(
                        "managementAcsUrl"
                    ).value.trim(),
                    timeout: 20
                }
            }
        );

        renderManagementACS(
            result
        );

        showToast(
            "Integração ACS/USP salva."
        );
    } catch (error) {
        showToast(
            error.message
        );
    }
}


async function discoverManagementACS() {
    const device = selectedManagementDevice();

    if (!device) {
        showToast(
            "Selecione uma ONT no inventário."
        );

        return;
    }

    setBusy(
        true,
        "Consultando ACS/USP..."
    );

    try {
        const result = await managementRequest(
            "/management/acs/discover?device_id="
            + encodeURIComponent(
                device.id
            )
        );

        managementOutput(
            "managementAcsOutput",
            result
        );
    } catch (error) {
        managementOutput(
            "managementAcsOutput",
            {
                error: error.message
            }
        );

        showToast(
            error.message
        );
    } finally {
        setBusy(false);
    }
}


async function runManagementZeroTouch() {
    const profileId = managementSelectedProfileId(
        "managementZeroTouchProfile"
    );

    if (!profileId) {
        showToast(
            "Selecione um perfil."
        );

        return;
    }

    if (!window.confirm(
        "Executar Zero Touch na ONT atual? Será criado backup antes das alterações."
    )) {
        return;
    }

    setBusy(
        true,
        "Executando pipeline de provisionamento..."
    );

    try {
        const agentRaw = document.getElementById(
            "managementAgentId"
        )?.value;

        const result = await managementRequest(
            "/management/zero-touch",
            {
                method: "POST",
                body: {
                    profile_id: profileId,
                    customer_name: document.getElementById(
                        "managementCustomer"
                    )?.value.trim() || null,
                    pop: document.getElementById(
                        "managementPop"
                    )?.value.trim() || null,
                    olt: document.getElementById(
                        "managementOlt"
                    )?.value.trim() || null,
                    cto: document.getElementById(
                        "managementCto"
                    )?.value.trim() || null,
                    agent_id: agentRaw
                        ? Number(agentRaw)
                        : null,
                    tags: managementTags(),
                    confirm: true
                }
            }
        );

        managementOutput(
            "managementZeroTouchOutput",
            result
        );

        showToast(
            result.success
                ? "Provisionamento concluído."
                : "Provisionamento concluído com falhas parciais."
        );

        await refreshManagement();
    } catch (error) {
        managementOutput(
            "managementZeroTouchOutput",
            {
                error: error.message
            }
        );

        showToast(
            error.message
        );
    } finally {
        setBusy(false);
    }
}


// =========================================================
// BINDINGS
// =========================================================

document.querySelectorAll(
    ".management-tab"
).forEach(
    button => button.addEventListener(
        "click",
        () => switchManagementTab(
            button.dataset.managementTab
        )
    )
);


document.querySelector(
    '[data-page="management"]'
)?.addEventListener(
    "click",
    refreshManagement
);


document.getElementById(
    "managementRefreshButton"
)?.addEventListener(
    "click",
    refreshManagement
);


document.getElementById(
    "managementInventorySearch"
)?.addEventListener(
    "input",
    renderManagementInventory
);


document.getElementById(
    "managementInventorySync"
)?.addEventListener(
    "click",
    syncManagementInventory
);


document.getElementById(
    "managementProfileSave"
)?.addEventListener(
    "click",
    saveManagementProfile
);


document.getElementById(
    "managementDriftCheck"
)?.addEventListener(
    "click",
    () => checkManagementDrift(false)
);


document.getElementById(
    "managementDriftFix"
)?.addEventListener(
    "click",
    () => checkManagementDrift(true)
);


document.getElementById(
    "managementBatchRun"
)?.addEventListener(
    "click",
    runManagementBatch
);


document.getElementById(
    "managementBatchRefresh"
)?.addEventListener(
    "click",
    refreshManagementBatch
);


document.getElementById(
    "managementAgentSave"
)?.addEventListener(
    "click",
    saveManagementAgent
);


document.getElementById(
    "managementRemoteOpen"
)?.addEventListener(
    "click",
    openManagementRemote
);


document.getElementById(
    "managementRemoteRefresh"
)?.addEventListener(
    "click",
    refreshRemoteSessions
);


document.getElementById(
    "managementTerminalRun"
)?.addEventListener(
    "click",
    runManagementTerminal
);


document.getElementById(
    "managementBufferbloatRun"
)?.addEventListener(
    "click",
    runManagementBufferbloat
);


document.getElementById(
    "managementMonitorStart"
)?.addEventListener(
    "click",
    startManagementMonitor
);


document.getElementById(
    "managementMonitorRefresh"
)?.addEventListener(
    "click",
    refreshManagementMonitor
);


document.getElementById(
    "managementMonitorStop"
)?.addEventListener(
    "click",
    stopManagementMonitor
);


document.getElementById(
    "managementIncidentCorrelate"
)?.addEventListener(
    "click",
    correlateManagementIncidents
);


document.getElementById(
    "managementIncidentRefresh"
)?.addEventListener(
    "click",
    refreshManagement
);


document.getElementById(
    "managementTopologyLoad"
)?.addEventListener(
    "click",
    loadManagementTopology
);


document.getElementById(
    "managementMeshRead"
)?.addEventListener(
    "click",
    readManagementMesh
);


document.getElementById(
    "managementMeshApply"
)?.addEventListener(
    "click",
    applyManagementMesh
);


document.getElementById(
    "managementMeshPair"
)?.addEventListener(
    "click",
    pairManagementMesh
);


document.querySelector(
    '[data-management-tab="mesh"]'
)?.addEventListener(
    "click",
    readManagementMesh
);


document.getElementById(
    "managementNetworkRefresh"
)?.addEventListener(
    "click",
    refreshManagementNetwork
);


document.getElementById(
    "managementNetworkCopy"
)?.addEventListener(
    "click",
    async () => {
        if (!managementState.networkResult) {
            showToast(
                "Execute Ler tudo primeiro."
            );

            return;
        }

        await managementCopyText(
            managementJson(
                managementState.networkResult
            ),
            "JSON completo copiado."
        );
    }
);


document.getElementById(
    "managementNetworkCopyRelevant"
)?.addEventListener(
    "click",
    async () => {
        const relevant = managementRelevantNetworkResult();

        if (!relevant) {
            showToast(
                "Execute Ler tudo primeiro."
            );

            return;
        }

        await managementCopyText(
            managementJson(
                relevant
            ),
            "TR-069 e WAN copiados."
        );
    }
);


document.getElementById(
    "managementQosSave"
)?.addEventListener(
    "click",
    saveManagementQos
);


document.getElementById(
    "managementFirewallSave"
)?.addEventListener(
    "click",
    saveManagementFirewall
);


document.getElementById(
    "managementFirewallRuleSave"
)?.addEventListener(
    "click",
    saveManagementFirewallRule
);


document.getElementById(
    "managementFirewallRuleDelete"
)?.addEventListener(
    "click",
    deleteManagementFirewallRule
);


document.getElementById(
    "managementFirewallGlobalSave"
)?.addEventListener(
    "click",
    saveManagementFilterGlobal
);


document.getElementById(
    "managementSntpSave"
)?.addEventListener(
    "click",
    saveManagementSntp
);


document.getElementById(
    "managementTr069Save"
)?.addEventListener(
    "click",
    saveManagementTr069
);


document.getElementById(
    "managementWanCreate"
)?.addEventListener(
    "click",
    createManagementWan
);


document.getElementById(
    "managementWanUpdate"
)?.addEventListener(
    "click",
    updateManagementWan
);


document.getElementById(
    "managementWanActionRun"
)?.addEventListener(
    "click",
    runManagementWanAction
);


document.getElementById(
    "managementWanDelete"
)?.addEventListener(
    "click",
    deleteManagementWan
);


document.getElementById(
    "managementBridgeRun"
)?.addEventListener(
    "click",
    runManagementBridge
);


document.getElementById(
    "managementBackupCreate"
)?.addEventListener(
    "click",
    createManagementBackup
);


document.getElementById(
    "managementBackupRefresh"
)?.addEventListener(
    "click",
    refreshManagement
);


document.getElementById(
    "managementBackupCompare"
)?.addEventListener(
    "click",
    compareManagementBackups
);


document.getElementById(
    "managementFirmwareRegister"
)?.addEventListener(
    "click",
    registerManagementFirmware
);


document.getElementById(
    "managementAcsSave"
)?.addEventListener(
    "click",
    saveManagementACS
);


document.getElementById(
    "managementAcsDiscover"
)?.addEventListener(
    "click",
    discoverManagementACS
);


document.getElementById(
    "managementZeroTouchRun"
)?.addEventListener(
    "click",
    runManagementZeroTouch
);

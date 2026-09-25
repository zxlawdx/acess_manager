// F6201B: edição experimental SUPERVISIONADA de SSID.
// Nunca ativar atalhos de escrita genéricos de outro modelo.
(() => {
    "use strict";
    let currentPreview = null;
    let activeHost = null;
    let activeEpoch = -1;
    const make = (tag, className, textValue) => {
        const node = document.createElement(tag);
        if (className) node.className = className;
        if (textValue != null) node.textContent = String(textValue);
        return node;
    };
    function message(panel, messageText, type = "info") {
        const box = panel.querySelector(".f6201b-message");
        box.className = "f6201b-message " + type;
        box.textContent = messageText;
    }
    function render(panel, capability) {
        panel.replaceChildren();
        panel.className = "panel f6201b-editor";
        panel.append(make("span", "adaptive-eyebrow",
            "F6201B · EXPERIMENTAL · ALTERAÇÕES CONTROLADAS"));
        panel.append(make("h2", "", "Configuração de SSID"));
        panel.append(make("p", "adaptive-empty",
            "O mapeamento enviado confirma leitura, mas não contém um POST " +
            "Apply. A escrita abaixo reutiliza o adaptador ThinkLua existente " +
            "e exige verificação do formulário, firmware exato e confirmação."));
        const badge = make("p", capability.opted_in && capability.supported_firmware
            ? "f6201b-badge enabled" : "f6201b-badge",
            capability.opted_in && capability.supported_firmware
                ? "Modo experimental autorizado nesta instância"
                : "Modo experimental bloqueado");
        panel.append(badge);
        const alert = make("p", "f6201b-warning",
            "Risco: desligar ou renomear a rede Wi-Fi pode interromper " +
            "o acesso à ONT. Faça o primeiro teste com acesso local " +
            "preferencialmente por cabo. Não há rollback automático.");
        panel.append(alert);

        const form = make("div", "f6201b-form");
        const chooser = make("select", "");
        chooser.setAttribute("aria-label", "SSID para alterar");
        const name = make("input");
        name.type = "text";
        name.maxLength = 32;
        name.placeholder = "Novo nome da rede";
        name.setAttribute("aria-label", "Nome do SSID");
        const enabledLabel = make("label", "f6201b-check");
        const enabled = make("input");
        enabled.type = "checkbox";
        enabledLabel.append(enabled, make("span", "", "SSID habilitado"));
        const visibleLabel = make("label", "f6201b-check");
        const visible = make("input");
        visible.type = "checkbox";
        visibleLabel.append(visible, make("span", "", "Transmitir nome da rede"));
        const reload = make("button", "button ghost", "Consultar SSIDs");
        reload.type = "button";
        const preview = make("button", "button ghost", "Visualizar alterações");
        preview.type = "button";
        const confirm = make("input", "f6201b-confirm");
        confirm.placeholder = "Digite APLICAR F6201B";
        confirm.autocomplete = "off";
        confirm.setAttribute("aria-label", "Confirmação de risco");
        const apply = make("button", "button primary", "Aplicar alterações");
        apply.type = "button";
        apply.disabled = true;
        preview.disabled = true;
        const diff = make("div", "f6201b-diff");
        diff.setAttribute("aria-live", "polite");
        const feedback = make("div", "f6201b-message");
        feedback.setAttribute("aria-live", "polite");
        const row = make("div", "f6201b-actions");
        row.append(reload, preview);
        for (const [label, input] of [["Rede", chooser], ["Nome", name]]) {
            const field = make("label", "f6201b-field");
            field.append(make("span", "", label), input);
            form.append(field);
        }
        form.append(enabledLabel, visibleLabel, row, diff);
        const confirmation = make("div", "f6201b-apply");
        confirmation.append(confirm, apply);
        form.append(confirmation, feedback);
        panel.append(form);
        if (!capability.opted_in || !capability.supported_firmware) {
            preview.disabled = true;
            panel.append(make("p", "adaptive-footnote",
                "Para habilitar os testes, inicie o aplicativo com " +
                "ZTE_F6201B_EXPERIMENTAL_WRITES=1. " +
                "Isso não libera escritas dos demais módulos."));
        }
        let options = [];
        const reset = () => {
            currentPreview = null;
            apply.disabled = true;
            confirm.value = "";
            diff.replaceChildren();
        };
        const select = () => {
            reset();
            const selected = options.find(item => item.id === chooser.value);
            if (!selected) return;
            name.value = selected.ssid || "";
            enabled.checked = Boolean(selected.enabled);
            visible.checked = Boolean(selected.broadcast);
        };
        chooser.addEventListener("change", select);
        for (const control of [name, enabled, visible]) {
            control.addEventListener("input", reset);
            control.addEventListener("change", reset);
        }
        reload.addEventListener("click", async () => {
            reset();
            setBusy(true, "Lendo SSIDs sem revelar senhas...");
            try {
                options = await apiRequest("/f6201b/write/ssids");
                chooser.replaceChildren();
                if (!Array.isArray(options)) throw new Error("Lista inválida.");
                for (const option of options) {
                    const entry = make("option", "",
                        (option.ssid || "SSID sem nome") + " · " + option.id);
                    entry.value = option.id;
                    chooser.append(entry);
                }
                select();
                preview.disabled = !options.length || !capability.opted_in ||
                    !capability.supported_firmware;
                message(panel, options.length
                    ? options.length + " rede(s) lidas. Selecione uma e edite."
                    : "Nenhum SSID retornado.");
            } catch (error) {
                message(panel, "Falha na leitura: " + error.message, "error");
            } finally {
                setBusy(false);
            }
        });
        preview.addEventListener("click", async () => {
            reset();
            const selected = options.find(item => item.id === chooser.value);
            if (!selected) return;
            const changed = {};
            if (name.value !== selected.ssid) changed.ssid = name.value;
            if (enabled.checked !== selected.enabled)
                changed.enabled = enabled.checked;
            if (visible.checked !== selected.broadcast)
                changed.broadcast = visible.checked;
            if (!Object.keys(changed).length) {
                message(panel, "Nenhuma alteração informada.");
                return;
            }
            setBusy(true, "Validando o formulário e construindo a prévia...");
            try {
                const result = await apiRequest("/f6201b/write/preview", {
                    method: "POST", body: JSON.stringify({
                        ssid_id: selected.id, config: changed
                    })
                });
                currentPreview = result;
                diff.replaceChildren();
                diff.append(make("h3", "", "Prévia · nenhuma escrita executada"));
                for (const [key, value] of Object.entries(result.changes || {})) {
                    const item = make("div", "f6201b-diff-item");
                    item.append(make("strong", "", key));
                    item.append(make("span", "",
                        String(value.before) + " → " + String(value.after)));
                    diff.append(item);
                }
                apply.disabled = false;
                message(panel, "Prévia válida por 120 segundos. " +
                    "Confirme o risco para executar.");
            } catch (error) {
                message(panel, "Escrita recusada no preflight: " +
                    error.message, "error");
            } finally {
                setBusy(false);
            }
        });
        apply.addEventListener("click", async () => {
            if (!currentPreview || confirm.value !== "APLICAR F6201B") {
                message(panel, "Digite exatamente APLICAR F6201B.", "error");
                return;
            }
            const nonce = currentPreview.nonce;
            reset();
            setBusy(true, "Enviando Apply experimental e conferindo a releitura...");
            try {
                const result = await apiRequest("/f6201b/write/apply", {
                    method: "POST", body: JSON.stringify({
                        nonce, confirmation: "APLICAR F6201B"
                    })
                });
                message(panel, result.verified
                    ? "Alteração confirmada por releitura do equipamento."
                    : "Resposta recebida, mas verificação não concluída.",
                    result.verified ? "success" : "error");
                if (result.verified) reload.click();
            } catch (error) {
                message(panel, "Não foi possível confirmar a alteração: " +
                    error.message + ". Consulte a interface original " +
                    "antes de repetir.", "error");
            } finally {
                setBusy(false);
            }
        });
    }

    async function openEditor() {
        if (!ontConnected || routerWriteEnabled) return;
        const bootstrap = await apiRequest("/discovery/bootstrap");
        // A escolha anterior não autoriza exibir editor noutro modelo.
        const actual = String(bootstrap?.detected_model || "").toUpperCase();
        const selected = String(bootstrap?.model || "").toUpperCase();
        if (selected.replace(/[^A-Z0-9]/g, "") !== "F6201B" ||
            (actual && actual !== "ZTE" &&
             actual.replace(/[^A-Z0-9]/g, "") !== "F6201B")) {
            document.querySelectorAll(".f6201b-editor").forEach(
                node => node.remove()
            );
            return;
        }
        const page = document.getElementById("page-wifi");
        if (!page) return;
        let panel = page.querySelector(".f6201b-editor");
        if (!panel) {
            panel = make("section", "panel f6201b-editor");
            page.append(panel);
        }
        if (activeHost === currentHost && activeEpoch === sessionEpoch &&
                panel.hasChildNodes()) return;
        activeHost = currentHost;
        activeEpoch = sessionEpoch;
        currentPreview = null;
        try {
            const capability = await apiRequest("/f6201b/write/status");
            render(panel, capability);
        } catch (error) {
            panel.append(make("p", "f6201b-message error",
                "Editor indisponível: " + error.message));
        }
    }
    document.addEventListener("zte:session-changed", () => {
        currentPreview = null;
        activeHost = null;
        activeEpoch = -1;
        document.querySelectorAll(".f6201b-editor").forEach(
            node => node.remove()
        );
    });
    document.addEventListener("zte:page-open", event => {
        if (event.detail?.pageName === "wifi") {
            void openEditor().catch(error =>
                console.warn("Editor F6201B indisponível:", error));
        }
    });
})();

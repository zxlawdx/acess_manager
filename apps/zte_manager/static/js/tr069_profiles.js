/* Scoped provider profiles: operator secrets live only in password inputs. */
(() => {
  "use strict";
  const byId = id => document.getElementById(id);
  let profiles = [], busy = false, epoch = 0, setupSnapshot = null;
  let loadedEpoch = -1;
  const clearSecrets = () => {
    for (const id of ["tr069ProviderPassword", "tr069ProviderRequestPassword"]) {
      if (byId(id)) byId(id).value = "";
    }
  };
  function feedback(message, error = false) {
    const target = byId("tr069ProviderFeedback");
    if (!target) return;
    target.textContent = message;
    target.dataset.level = error ? "error" : "ok";
  }
  function fill(profile) {
    clearSecrets();
    byId("tr069ProviderName").value = profile?.name || "";
    byId("tr069ProviderUrl").value = profile?.url || "";
    byId("tr069ProviderUser").value = profile?.username || "";
    byId("tr069ProviderRequestUser").value =
      profile?.connection_request_username || "";
    byId("tr069ProviderPeriodic").checked =
      profile?.periodic_inform_enabled !== false;
    const interval = String(profile?.periodic_inform_interval || 1200);
    const select = byId("tr069ProviderInterval");
    if (![...select.options].some(item => item.value === interval)) {
      select.add(new Option(interval + " s", interval));
    }
    select.value = interval;
  }
  function collect() {
    return {
      name: byId("tr069ProviderName").value.trim(),
      url: byId("tr069ProviderUrl").value.trim(),
      username: byId("tr069ProviderUser").value.trim(),
      connection_request_username: byId("tr069ProviderRequestUser").value.trim(),
      periodic_inform_enabled: byId("tr069ProviderPeriodic").checked,
      periodic_inform_interval: Number(byId("tr069ProviderInterval").value)
    };
  }
  async function listProviders(selectName = null) {
    const response = await apiRequest("/tr069/providers");
    if (!Array.isArray(response.profiles)) {
      throw new Error("O servidor não devolveu a lista de perfis ACS.");
    }
    profiles = response.profiles;
    const select = byId("tr069ProviderSelect");
    const preferred = selectName || select.value || profiles[0]?.name;
    select.replaceChildren(new Option("Selecione um perfil", ""));
    for (const profile of profiles) {
      select.add(new Option(profile.name, profile.name));
    }
    const chosen = profiles.find(item => item.name === preferred) || profiles[0];
    select.value = chosen?.name || "";
    fill(chosen);
  }
  async function refreshWan(refresh = false) {
    const requestEpoch = epoch;
    const selection = byId("tr069EligibleWan");
    const button = byId("tr069ProviderApply");
    button.disabled = true;
    selection.replaceChildren(new Option("Consultando WANs...", ""));
    try {
      const response = await apiRequest(
        "/tr069/setup" + (refresh ? "?refresh=1" : "")
      );
      if (requestEpoch !== epoch) return;
      setupSnapshot = response;
      const candidates = response.wan_candidates || [];
      selection.replaceChildren(new Option("Selecione a WAN PPPoE TR069", ""));
      for (const wan of candidates) {
        selection.add(new Option(wan.name + " · " + wan.services, wan.name));
      }
      const original = response.current?.DefaultWan;
      // Require explicit selection if the router did not return an
      // unambiguous existing WAN, never auto-switch a contract.
      if (original && candidates.some(wan => wan.name === original)) {
        selection.value = original;
      }
      const needSecrets = [
        !response.acs_secret_exists ? "senha ACS" : "",
        !response.request_secret_exists ? "senha da solicitação de conexão" : ""
      ].filter(Boolean).join(" e ");
      byId("tr069WanStatus").textContent = candidates.length
        ? "Selecione a WAN PPPoE/TR069 existente e confirme antes de aplicar." +
          (needSecrets ? " Preencha " + needSecrets + " para a primeira ativação." : "")
        : "Não há WAN PPPoE com serviço TR069 comprovado. Crie ou ajuste " +
          "a WAN de contrato na tela de gerenciamento antes de continuar.";
      button.disabled = candidates.length === 0 || response.available !== true;
      if (!response.available) {
        byId("tr069WanStatus").textContent =
          "O firmware/login não disponibilizou o formulário TR-069.";
      }
    } catch (error) {
      if (requestEpoch !== epoch) return;
      selection.replaceChildren(new Option("Não foi possível ler WANs", ""));
      byId("tr069WanStatus").textContent = error?.message ||
        "Falha ao consultar WAN PPPoE/TR069.";
    }
  }
  async function guard(action) {
    if (busy) return;
    busy = true;
    try {
      await action();
    } catch (error) {
      feedback(error?.message || "Operação não concluída.", true);
    } finally {
      busy = false;
    }
  }
  function init() {
    byId("tr069ProviderSelect")?.addEventListener("change", event => {
      fill(profiles.find(item => item.name === event.target.value));
    });
    byId("tr069ProviderNew")?.addEventListener("click", () => {
      byId("tr069ProviderSelect").value = "";
      fill({
        name: "", url: "", username: "",
        connection_request_username: "",
        periodic_inform_enabled: true, periodic_inform_interval: 1200
      });
      byId("tr069ProviderName").focus();
      feedback("Preencha os parâmetros do novo provedor e salve o perfil.");
    });
    byId("tr069ProviderSave")?.addEventListener("click", () => guard(async () => {
      const profile = collect();
      // Keep password inputs ONLY in this still-active WebView session,
      // not in the profile POST or browser storage.
      const saveEpoch = epoch;
      const pwd = byId("tr069ProviderPassword").value;
      const requestPwd = byId("tr069ProviderRequestPassword").value;
      const result = await apiRequest("/tr069/providers/save", {
        method: "POST", body: JSON.stringify({profile})
      });
      await listProviders(result.name);
      if (epoch === saveEpoch) {
        byId("tr069ProviderPassword").value = pwd;
        byId("tr069ProviderRequestPassword").value = requestPwd;
      }
      feedback("Perfil salvo. As senhas continuam apenas nesta sessão.");
    }));
    byId("tr069ProviderDelete")?.addEventListener("click", () => guard(async () => {
      const name = byId("tr069ProviderSelect").value;
      if (!name || !window.confirm("Excluir o perfil ACS selecionado?")) return;
      await apiRequest("/tr069/providers/delete", {
        method:"POST", body:JSON.stringify({name})
      });
      await listProviders();
      feedback("Perfil excluído.");
    }));
    byId("tr069ProviderRefresh")?.addEventListener("click", () =>
      void guard(() => refreshWan(true)));
    byId("tr069ProviderApply")?.addEventListener("click", () => guard(async () => {
      if (!ontConnected) throw new Error("Conecte-se à ONT antes de aplicar.");
      const name = byId("tr069ProviderSelect").value;
      const wan_name = byId("tr069EligibleWan").value;
      const stored = profiles.find(item => item.name === name);
      const draft = collect();
      const unchanged = stored && Object.keys(draft).every(
        key => draft[key] === stored[key]
      );
      if (!name || !wan_name || !unchanged) {
        throw new Error(
          "Selecione uma WAN e salve quaisquer alterações do perfil antes de aplicar."
        );
      }
      if (!window.confirm(
        "Aplicar este ACS na WAN PPPoE TR069 selecionada? Confirme " +
        "que as credenciais informadas pertencem à ONT atual."
      )) return;
      const password = byId("tr069ProviderPassword").value || null;
      const connection_request_password =
        byId("tr069ProviderRequestPassword").value || null;
      if (setupSnapshot?.acs_secret_exists === false && !password) {
        throw new Error("Informe a senha ACS para configurar esta ONT.");
      }
      if (setupSnapshot?.request_secret_exists === false &&
          !connection_request_password) {
        throw new Error("Informe a senha de solicitação de conexão.");
      }
      const button = byId("tr069ProviderApply");
      button.disabled = true;
      setBusy(true, "Aplicando TR-069 e relendo os parâmetros...");
      try {
        const result = await apiRequest("/tr069/providers/apply", {
          method: "POST", body:JSON.stringify({
            name, wan_name, password, connection_request_password, confirm:true
          })
        });
        feedback(result?.verified === true
          ? "Configuração enviada e verificada pela releitura."
          : "Comando enviado. Confira no firmware e na plataforma ACS " +
            "se houve registro; a conexão remota não foi comprovada.");
        await refreshWan();
      } finally {
        clearSecrets();
        setBusy(false);
        button.disabled = false;
      }
    }));
    document.addEventListener("device:session-changed", () => {
      epoch++;
      loadedEpoch = -1;
      setupSnapshot = null;
      clearSecrets();
      if (byId("tr069EligibleWan")) {
        byId("tr069EligibleWan").replaceChildren(
          new Option("Reconecte e atualize as WANs", "")
        );
      }
      if (byId("tr069ProviderApply")) byId("tr069ProviderApply").disabled = true;
    });
    window.warmHuaweiTr069Snapshot = async function warmHuaweiTr069Snapshot() {
      if (!ontConnected || currentVendor !== "huawei") return;
      if (loadedEpoch === epoch && setupSnapshot) return;
      await guard(async () => {
        await listProviders();
        await refreshWan();
        loadedEpoch = epoch;
      });
    };

    document.addEventListener("device:page-open", event => {
      if (event.detail?.pageName !== "tr069") return;
      if (
        currentVendor === "huawei"
        && loadedEpoch === epoch
        && setupSnapshot
      ) {
        return;
      }
      void guard(async () => {
        await listProviders();
        if (ontConnected) await refreshWan();
        if (currentVendor === "huawei") loadedEpoch = epoch;
      });
    });
  }
  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init, {once:true});
  } else init();
})();

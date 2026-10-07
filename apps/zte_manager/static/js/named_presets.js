/* Named technician presets coexist with the provider-neutral primary profile flow. */
(() => {
  "use strict";
  const PRIMARY = "Configuração principal";
  const id = name => document.getElementById(name);
  const state = {name: PRIMARY, owner: null, pending: false, generation: 0};
  globalThis.activeNamedPreset = PRIMARY;
  const isHuawei = () => currentVendor === "huawei";
  function hint(message, error = false) {
    const element = id("namedPresetHint");
    if (!element) return;
    element.textContent = message;
    element.dataset.level = error ? "error" : "ok";
  }
  function legacyControls(named) {
    for (const key of ["captureProfileButton","saveProfileButton","applyProfileButton"]) {
      const button = id(key);
      if (!button) continue;
      if (named) {
        button.disabled = true;
        button.title = "Use os botões da configuração selecionada abaixo.";
      } else {
        button.disabled = key === "applyProfileButton" && !routerWriteEnabled;
        button.title = "";
      }
    }
    const remove = id("namedPresetDelete");
    if (remove) remove.disabled = !named;
  }
  function huaweiPrimaryControls() {
    state.name = PRIMARY;
    globalThis.activeNamedPreset = PRIMARY;
    const select = id("namedPresetSelect");
    if (select) {
      select.replaceChildren(new Option(PRIMARY, PRIMARY));
      select.value = PRIMARY;
    }
    const create = id("namedPresetCreate");
    const remove = id("namedPresetDelete");
    if (create) {
      create.disabled = true;
      create.title = "Variantes nomeadas ainda são específicas do provider ZTE.";
    }
    if (remove) remove.disabled = true;
    const apply = id("namedPresetApply");
    if (apply) {
      apply.disabled = !routerWriteEnabled;
      apply.title = routerWriteEnabled ? "" :
        "A sessão atual não confirmou gravações para este perfil.";
    }
    legacyControls(false);
  }
  const post = (url, payload) => apiRequest(url, {
    method:"POST", body:JSON.stringify(payload)
  });
  async function refreshNames(desired = state.name) {
    if (!currentAttendant) return;
    if (isHuawei()) {
      huaweiPrimaryControls();
      return;
    }
    const owner = currentAttendant;
    const response = await post("/profiles/named/list", {attendant: owner});
    if (currentAttendant !== owner) return;
    const names = Array.isArray(response.names) ? response.names : [PRIMARY];
    const select = id("namedPresetSelect");
    select.replaceChildren();
    for (const name of names) select.add(new Option(name, name));
    if (!names.includes(desired)) desired = PRIMARY;
    select.value = desired;
  }
  async function selectPreset(name) {
    if (!currentAttendant) return;
    if (isHuawei()) {
      huaweiPrimaryControls();
      profileLoadedFor = null;
      currentProfile = null;
      await ensureAttendantProfile();
      hint("Configuração principal Huawei ativa; aplicação usa releitura por etapa.");
      return;
    }
    const generation = ++state.generation;
    const owner = currentAttendant;
    const named = name !== PRIMARY;
    state.name = name;
    state.owner = owner;
    globalThis.activeNamedPreset = name;
    legacyControls(named);
    if (!named) {
      profileLoadedFor = null;
      currentProfile = null;
      await ensureAttendantProfile();
      if (generation !== state.generation || owner !== currentAttendant) return;
      hint("Configuração principal ativa para o provedor conectado.");
      return;
    }
    try {
      const profile = await post("/profiles/named/get", {
        attendant: owner, name
      });
      if (generation !== state.generation || owner !== currentAttendant) return;
      if (!profile?.wifi?.["2.4GHz"] || !profile?.wifi?.["5GHz"])
        throw Error("O backend devolveu um perfil incompleto.");
      currentProfile = profile;
      profileLoadedFor = null;
      await renderProfileForm(profile);
      if (generation !== state.generation || owner !== currentAttendant) return;
      hint(name + " carregada. Edite os rádios/DNS, salve e aplique.");
    } catch (error) {
      if (generation === state.generation) {
        hint("Falha ao carregar a configuração: " + error.message, true);
        id("namedPresetApply").disabled = true;
      }
    }
  }
  async function saveSelected() {
    if (!currentAttendant) throw Error("Conecte-se e informe o atendente.");
    if (isHuawei() || state.name === PRIMARY) {
      await saveProfile();
      return;
    }
    const owner = currentAttendant;
    const profile = collectProfileForm();
    const saved = await post("/profiles/named/save", {
      attendant: owner, name: state.name, ...profile
    });
    if (owner !== currentAttendant) return;
    currentProfile = saved;
    hint("Configuração " + state.name + " salva para " + owner + ".");
  }
  function verifiedProfileSummary(result) {
    const steps = Array.isArray(result?.steps) ? result.steps : [];
    const changed = steps.filter(step =>
      Array.isArray(step?.changed_fields) && step.changed_fields.length > 0
    );
    const failed = steps.filter(step => step?.verified !== true && step?.success !== true);
    if (result?.success === false || failed.length) {
      return {
        message: "Perfil não foi totalmente confirmado. Confira as etapas abaixo antes de repetir.",
        error: true
      };
    }
    if (changed.length && changed.every(step => step?.verified === true)) {
      return {
        message: `${changed.length} etapa(s) aplicada(s) e confirmada(s) pela releitura da ONT.`,
        error: false
      };
    }
    const unchanged = Array.isArray(result?.unchanged) ? result.unchanged : [];
    if (result?.success === true && !changed.length && (unchanged.length || steps.length)) {
      return {
        message: "A ONT já correspondia ao perfil; nenhuma alteração pendente foi encontrada.",
        error: false
      };
    }
    if (result?.verified === true) {
      return {message:"Configuração aplicada e confirmada por leitura.", error:false};
    }
    return {
      message:"Configuração processada; confira abaixo quais etapas tiveram releitura confirmada.",
      error:false
    };
  }
  async function applyPrimaryGeneric() {
    if (!currentAttendant) throw Error("Informe um atendente conectado.");
    if (!routerWriteEnabled) {
      throw Error("A sessão atual não confirmou gravações para o perfil solicitado.");
    }
    const owner = currentAttendant;
    await saveProfile(true);
    if (owner !== currentAttendant) return;
    if (!window.confirm(
      "Aplicar a configuração principal à ONT atual? O backend validará as capacidades antes de gravar."
    )) return;
    setBusy(true, "Validando capacidades, aplicando diferenças e relendo a ONT...");
    try {
      const result = await post("/profiles/apply", {attendant: owner});
      if (owner !== currentAttendant) return;
      if (id("profileApplyResult")) renderProfileApplyResult(result);
      if (result?.success === false && Array.isArray(result?.unsupported)) {
        hint(
          "Perfil não aplicado. Recursos não suportados: " +
          result.unsupported.join(", ") + ".",
          true
        );
        return;
      }
      const summary = verifiedProfileSummary(result);
      hint(summary.message, summary.error);
      await loadWifi();
      await loadDns();
    } finally {
      setBusy(false);
    }
  }
  async function applySelected() {
    if (!currentAttendant) throw Error("Informe um atendente conectado.");
    if (isHuawei()) {
      huaweiPrimaryControls();
      await applyPrimaryGeneric();
      return;
    }
    if (state.name === PRIMARY) {
      await applyPrimaryGeneric();
      return;
    }
    if (!routerWriteEnabled) {
      throw Error("Esta ONT exige um fluxo capturado específico; não aplicar um batch genérico.");
    }
    await saveSelected();
    if (!window.confirm(
      "Aplicar " + state.name + " à ONT atual? O Wi-Fi pode reiniciar."
    )) return;
    setBusy(true, "Aplicando " + state.name + "...");
    try {
      const result = await post("/profiles/named/apply", {
        attendant:currentAttendant,name:state.name
      });
      if (id("profileApplyResult")) renderProfileApplyResult(result);
      const summary = verifiedProfileSummary(result);
      hint(summary.message, summary.error);
      await loadWifi();
      await loadDns();
    } finally {
      setBusy(false);
    }
  }
  async function execute(callback) {
    if (state.pending) return;
    state.pending = true;
    try { await callback(); }
    catch(error) { hint(error?.message || "Operação não concluída.", true); }
    finally { state.pending = false; }
  }
  function init() {
    // app.js still contains the historical captured F6201B button handler.
    // Huawei must never reach that route. Capture both visible apply controls
    // before legacy listeners and force the provider-neutral API.
    document.addEventListener("click", event => {
      const button = event.target.closest("#applyProfileButton, #namedPresetApply");
      if (!button) return;
      if (isHuawei()) {
        event.preventDefault();
        event.stopImmediatePropagation();
        huaweiPrimaryControls();
        void execute(applyPrimaryGeneric);
        return;
      }
      if (button.id !== "applyProfileButton" || state.name !== PRIMARY) return;
      event.preventDefault();
      event.stopImmediatePropagation();
      void execute(applyPrimaryGeneric);
    }, true);
    id("namedPresetSelect")?.addEventListener("change", event =>
      void execute(() => selectPreset(event.target.value)));
    id("namedPresetCreate")?.addEventListener("click", () => execute(async () => {
      if (isHuawei()) throw Error("Variantes nomeadas ainda são específicas do provider ZTE.");
      const name = id("namedPresetName").value.trim();
      if (!name || name === PRIMARY) throw Error("Informe um nome diferente para a variante.");
      if (!currentAttendant) throw Error("Conecte-se e informe o atendente.");
      const draft = collectProfileForm();
      await post("/profiles/named/save", {
        attendant:currentAttendant,name,...draft
      });
      await refreshNames(name);
      await selectPreset(name);
      id("namedPresetName").value = "";
    }));
    id("namedPresetSave")?.addEventListener("click", () =>
      void execute(saveSelected));
    id("namedPresetApply")?.addEventListener("click", () =>
      void execute(applySelected));
    id("namedPresetDelete")?.addEventListener("click", () => execute(async () => {
      if (isHuawei()) throw Error("A configuração principal Huawei não pode ser excluída.");
      if (state.name === PRIMARY) throw Error("A configuração principal não pode ser excluída.");
      if (!window.confirm("Excluir a variante " + state.name + "?")) return;
      await post("/profiles/named/delete", {
        attendant:currentAttendant,name:state.name
      });
      await refreshNames(PRIMARY);
      await selectPreset(PRIMARY);
      hint("Variante excluída. Configuração principal restaurada.");
    }));
    document.addEventListener("device:session-changed", () => {
      ++state.generation;
      state.name = PRIMARY;
      state.owner = null;
      globalThis.activeNamedPreset = PRIMARY;
      if (id("namedPresetSelect")) id("namedPresetSelect").replaceChildren();
    });
    document.addEventListener("device:page-open", event => {
      if (event.detail?.pageName !== "profiles" || !currentAttendant) return;
      if (event.detail?.vendor === "huawei" || isHuawei()) {
        huaweiPrimaryControls();
        hint("Configuração principal Huawei ativa; alterações só contam como aplicadas após releitura.");
        return;
      }
      void execute(async () => {
        await refreshNames();
        if (state.name !== PRIMARY) await selectPreset(state.name);
        else legacyControls(false);
      });
    });
  }
  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init, {once:true});
  } else init();
})();

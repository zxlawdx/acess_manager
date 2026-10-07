/* Named technician presets coexist with the provider-neutral primary profile flow. */
(() => {
  "use strict";
  const PRIMARY = "Configuração principal";
  const id = name => document.getElementById(name);
  const state = {name: PRIMARY, owner: null, pending: false, generation: 0};
  globalThis.activeNamedPreset = PRIMARY;
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
    id("namedPresetDelete").disabled = !named;
  }
  const post = (url, payload) => apiRequest(url, {
    method:"POST", body:JSON.stringify(payload)
  });
  async function refreshNames(desired = state.name) {
    if (!currentAttendant) return;
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
    if (state.name === PRIMARY) {
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
  async function applyPrimaryGeneric() {
    if (!currentAttendant) throw Error("Informe um atendente conectado.");
    if (!routerWriteEnabled) {
      throw Error("A sessão atual não confirmou gravações para o perfil solicitado.");
    }
    const owner = currentAttendant;
    // Persist exactly what is visible before asking the active provider to
    // calculate requirements/capabilities and apply. The backend owns the
    // no-partial-apply preflight and each provider owns write/readback safety.
    await saveProfile(true);
    if (owner !== currentAttendant) return;
    if (!window.confirm(
      "Aplicar a configuração principal à ONT atual? O backend validará as capacidades antes de gravar."
    )) return;
    setBusy(true, "Validando capacidades e aplicando o perfil...");
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
      hint(result?.verified === true
        ? "Configuração aplicada e confirmada por leitura."
        : "Configuração processada pelo provedor ativo; confira o relatório de verificação.");
      await loadWifi();
      await loadDns();
    } finally {
      setBusy(false);
    }
  }
  async function applySelected() {
    if (!currentAttendant) throw Error("Informe um atendente conectado.");
    if (state.name === PRIMARY) {
      await applyPrimaryGeneric();
      return;
    }
    if (!routerWriteEnabled) {
      throw Error("Esta ONT exige um fluxo capturado específico; não aplicar um batch genérico.");
    }
    // Named presets are still provider-specific on the server. Save the visible
    // editor before applying, never an older database value.
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
      hint(result?.verified === true
        ? "Configuração aplicada e confirmada por leitura."
        : "Configuração enviada; confira o relatório e valide na ONT.");
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
    // app.js still carries the historical F6201B compatibility function. The
    // visible primary Profile button is provider-neutral; intercept it in the
    // capture phase so the legacy button listener cannot route Huawei through
    // `/f6201b/profile/apply-saved`.
    document.addEventListener("click", event => {
      const button = event.target.closest("#applyProfileButton");
      if (!button || state.name !== PRIMARY) return;
      event.preventDefault();
      event.stopImmediatePropagation();
      void execute(applyPrimaryGeneric);
    }, true);
    id("namedPresetSelect")?.addEventListener("change", event =>
      void execute(() => selectPreset(event.target.value)));
    id("namedPresetCreate")?.addEventListener("click", () => execute(async () => {
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
      // Named presets remain ZTE-specific. The primary profile is already
      // provider-neutral and is kept enabled for Huawei sessions.
      if (event.detail?.vendor === "huawei") {
        state.name = PRIMARY;
        globalThis.activeNamedPreset = PRIMARY;
        legacyControls(false);
        return;
      }
      void execute(async () => {
        await refreshNames();
        // Primary editor is loaded by app.js; alternate editor is ours.
        if (state.name !== PRIMARY) await selectPreset(state.name);
        else legacyControls(false);
      });
    });
  }
  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init, {once:true});
  } else init();
})();

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

  function presetControls(named) {
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

    // A restored desktop session may momentarily dispatch session-changed
    // before app.js restores currentAttendant. The local create/save controls
    // depend on the authenticated session, not on that transient assignment
    // order. Click handlers still require currentAttendant before persistence.
    const sessionReady = Boolean(ontConnected || currentAttendant);

    const create = id("namedPresetCreate");
    if (create) {
      create.disabled = !sessionReady;
      create.title = sessionReady ? "" : "Conecte-se antes de criar uma configuração.";
    }

    const remove = id("namedPresetDelete");
    if (remove) {
      remove.disabled = !named;
      remove.title = named ? "" : "A configuração principal não pode ser excluída.";
    }

    const save = id("namedPresetSave");
    if (save) {
      save.disabled = !sessionReady;
      save.title = sessionReady ? "" : "Conecte-se antes de salvar uma configuração.";
    }

    const apply = id("namedPresetApply");
    if (apply) {
      apply.disabled = !routerWriteEnabled;
      apply.title = routerWriteEnabled ? "" :
        "A sessão atual não confirmou gravações para este perfil.";
    }
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
    if (!select) return;
    select.replaceChildren();
    for (const name of names) select.add(new Option(name, name));
    if (!names.includes(desired)) desired = PRIMARY;
    select.value = desired;
    presetControls(desired !== PRIMARY);
  }

  async function selectPreset(name) {
    if (!currentAttendant) return;
    const generation = ++state.generation;
    const owner = currentAttendant;
    const named = name !== PRIMARY;
    state.name = name;
    state.owner = owner;
    globalThis.activeNamedPreset = name;
    presetControls(named);

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
        const apply = id("namedPresetApply");
        if (apply) apply.disabled = true;
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
    if (state.name === PRIMARY) {
      await applyPrimaryGeneric();
      return;
    }
    if (!routerWriteEnabled) {
      throw Error("A sessão atual não confirmou gravações para a configuração selecionada.");
    }

    const owner = currentAttendant;
    const selected = state.name;
    await saveSelected();
    if (owner !== currentAttendant || selected !== state.name) return;
    if (!window.confirm(
      "Aplicar " + selected + " à ONT atual? O Wi-Fi pode reiniciar."
    )) return;
    setBusy(true, "Aplicando " + selected + "...");
    try {
      const result = await post("/profiles/named/apply", {
        attendant: owner, name: selected
      });
      if (owner !== currentAttendant || selected !== state.name) return;
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
    // app.js still contains the historical captured F6201B handler for the
    // primary Apply button. Intercept that control and always use the generic
    // provider-dispatched profile endpoint. Named Apply has its own handler.
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
      presetControls(false);

      // restoreDesktopSession currently restores currentAttendant immediately
      // after this event. Re-evaluate controls on the next microtask so the
      // transient null attendant cannot leave Create/Save permanently disabled.
      Promise.resolve().then(() => {
        if (ontConnected || currentAttendant) {
          presetControls(state.name !== PRIMARY);
        }
      });
    });

    document.addEventListener("device:page-open", event => {
      if (event.detail?.pageName !== "profiles") return;
      presetControls(state.name !== PRIMARY);
      if (!currentAttendant) return;
      void execute(async () => {
        await refreshNames();
        await selectPreset(state.name);
      });
    });
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init, {once:true});
  } else init();
})();

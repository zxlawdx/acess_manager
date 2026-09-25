/* F6201B captured workbench — scoped DOM; existing F6600P/F670L UI untouched. */
(() => {
  "use strict";
  const ID = "f6201b-workbench";
  const BOOL_FIELDS = new Set([
    "BPDUEnable", "EnableUPnPIGD", "BsEnable", "Enable"
  ]);
  let generation = 0;
  let catalog = null;
  let selected = null;
  let liveInstances = [];
  let activeInstance = null;
  let proposal = null;
  let working = false;

  const el = (tag, cls, text) => {
    const node = document.createElement(tag);
    if (cls) node.className = cls;
    if (text !== undefined) node.textContent = String(text);
    return node;
  };
  function api(path, body) {
    return apiRequest(path, body === undefined ? undefined : {
      method: "POST", body: JSON.stringify(body)
    });
  }
  function reset() {
    generation++;
    catalog = null;
    selected = null;
    liveInstances = [];
    activeInstance = null;
    proposal = null;
    working = false;
    document.getElementById(ID)?.remove();
  }
  function status(root, message, tone = "") {
    const node = root.querySelector(".f6201b-wb-status");
    if (node) {
      node.textContent = message;
      node.dataset.tone = tone;
      node.setAttribute("role", tone === "error" ? "alert" : "status");
    }
  }
  function clear(node) { if (node) node.replaceChildren(); }
  function rowFor(tag) { return catalog?.routes?.find(row => row.tag === tag); }
  function stateLabel(state) {
    return ({
      supervised_lab: "Teste supervisionado",
      existing_adapter: "Adaptador existente",
      needs_form_adapter: "Captura complementar"
    })[state] || "Não verificado";
  }
  function checkedModel(info) {
    const norm = String(info?.detected_model || "").toUpperCase()
      .replace(/[^A-Z0-9]/g, "");
    return info?.connected === true && info?.model_verified === true &&
      info?.writes_enabled === false && norm === "F6201B";
  }
  function makeButton(label, callback, klass = "button ghost") {
    const button = el("button", klass, label);
    button.type = "button";
    button.addEventListener("click", callback);
    return button;
  }
  function header(body, text) { body.appendChild(el("h3", "", text)); }
  function renderList(root) {
    const list = root.querySelector(".f6201b-wb-routes");
    clear(list);
    for (const route of catalog.routes) {
      const button = el("button", "f6201b-wb-item");
      button.type = "button";
      button.classList.toggle("is-active", route.tag === selected);
      button.append(
        el("span", "f6201b-wb-route-name", route.tag.replace(/_lua\.lua$/, "")),
        el("span", "f6201b-wb-badge " + route.state, stateLabel(route.state))
      );
      button.addEventListener("click", () => {
        if (working) return;
        selected = route.tag;
        liveInstances = [];
        activeInstance = null;
        proposal = null;
        renderList(root);
        renderDetails(root);
      });
      list.append(button);
    }
    const totals = catalog.routes.reduce((acc, r) => {
      acc[r.state] = (acc[r.state] || 0) + 1;
      return acc;
    }, {});
    const count = root.querySelector(".f6201b-wb-count");
    count.textContent =
      catalog.total_observed_apply_routes + " rotas capturadas · " +
      (totals.supervised_lab || 0) + " em teste · " +
      (totals.existing_adapter || 0) + " integradas · " +
      (totals.needs_form_adapter || 0) + " dependem de captura";
  }
  async function fetchInspect(root) {
    const requestGeneration = generation;
    const tag = selected;
    if (working) return;
    working = true;
    status(root, "Consultando menuView e menuData atual da ONT…", "progress");
    try {
      const data = await api("/f6201b/workbench/inspect", {tag});
      if (requestGeneration !== generation || selected !== tag) return;
      liveInstances = data.available ? (data.instances || []) : [];
      activeInstance = liveInstances.length === 1 ? liveInstances[0].id : null;
      proposal = null;
      status(root, data.available ?
        "Leitura concluída. Selecione apenas os campos que deseja alterar." :
        (data.reason || "O firmware não confirmou esta leitura."),
        data.available ? "ok" : "error");
    } catch (e) {
      if (requestGeneration !== generation || selected !== tag) return;
      liveInstances = [];
      activeInstance = null;
      status(root, "Falha na etapa GET: " + e.message, "error");
    } finally {
      working = false;
      if (requestGeneration === generation && selected === tag)
        renderDetails(root, true);
    }
  }
  function drawFields(root, destination) {
    const row = rowFor(selected);
    const data = liveInstances.find(v => v.id === activeInstance);
    if (liveInstances.length > 1) {
      const field = el("label", "f6201b-wb-field");
      field.append(el("span", "", "Instância da ONT"));
      const select = el("select");
      select.append(new Option("Selecione", ""));
      for (const item of liveInstances) select.append(new Option(item.id, item.id));
      select.value = activeInstance || "";
      select.addEventListener("change", () => {
        activeInstance = select.value || null;
        proposal = null;
        renderDetails(root, true);
      });
      field.append(select);
      destination.append(field);
    }
    if (!data) return;
    const grid = el("div", "f6201b-wb-form-grid");
    const missing = new Set(data.missing || []);
    for (const key of row.editable) {
      const field = el("label", "f6201b-wb-field");
      field.append(el("span", "", key));
      let input;
      if (BOOL_FIELDS.has(key) || key.startsWith("Is") && key.endsWith("Alg")) {
        input = el("select");
        input.append(new Option("0 — Desativado", "0"),
          new Option("1 — Ativado", "1"));
      } else {
        input = el("input");
        input.type = "text";
        input.autocomplete = "off";
        input.spellcheck = false;
      }
      input.name = key;
      input.dataset.original = String(data.current?.[key] ?? "");
      input.value = input.dataset.original;
      input.disabled = missing.has(key);
      input.addEventListener("input", () => {
        proposal = null;
        clear(root.querySelector(".f6201b-wb-preview"));
      });
      field.append(input);
      if (missing.has(key))
        field.append(el("small", "f6201b-wb-alert", "Ausente no GET; edição bloqueada"));
      grid.append(field);
    }
    destination.append(grid);
    if (missing.size) {
      destination.append(el("p", "f6201b-wb-alert",
        "O XML não devolveu todos os campos exigidos: " +
        [...missing].join(", ") + ". Nenhuma escrita será permitida."));
    }
    const preButton = makeButton("Revisar alterações", () => {
      void requestPreview(root);
    }, "button primary");
    preButton.disabled = missing.size > 0 || !catalog.writes_opted_in;
    destination.append(preButton);
    if (!catalog.writes_opted_in) {
      destination.append(el("p", "f6201b-wb-hint",
        "Escrita experimental desativada no processo. Para testes autorizados, " +
        "defina ZTE_F6201B_EXPERIMENTAL_WRITES=1 antes de abrir o aplicativo."));
    }
  }
  async function requestPreview(root) {
    if (working || !activeInstance || !selected) return;
    const fields = root.querySelector(".f6201b-wb-fields");
    const changes = {};
    for (const input of fields.querySelectorAll("[name][data-original]")) {
      if (input.disabled) return;
      if (input.value !== input.dataset.original) changes[input.name] = input.value;
    }
    if (!Object.keys(changes).length) {
      status(root, "Nenhuma diferença: altere um campo antes da prévia.", "error");
      return;
    }
    const tag = selected, requestGeneration = generation;
    working = true;
    status(root, "Gerando prévia: releitura, preservação e comparação…", "progress");
    try {
      proposal = await api("/f6201b/workbench/preview", {
        tag, instance_id: activeInstance, changes
      });
      if (requestGeneration !== generation || tag !== selected) return;
      renderPreview(root);
      status(root, "Prévia pronta. Revise as diferenças e confirme explicitamente.", "ok");
    } catch (e) {
      if (requestGeneration !== generation || tag !== selected) return;
      proposal = null;
      clear(root.querySelector(".f6201b-wb-preview"));
      status(root, "Prévia rejeitada: " + e.message, "error");
    } finally { working = false; }
  }
  function renderPreview(root) {
    const area = root.querySelector(".f6201b-wb-preview");
    clear(area);
    if (!proposal) return;
    header(area, "Prévia sem aplicação");
    area.append(el("small", "", "Válida por até " +
      proposal.expires_in_seconds + " segundos · sem repetição automática"));
    const table = el("table", "f6201b-wb-table");
    const thead = el("thead"); const tr = el("tr");
    ["Campo", "Atual", "Proposto"].forEach(x => tr.append(el("th", "", x)));
    thead.append(tr); table.append(thead);
    const tbody = el("tbody");
    for (const [key, delta] of Object.entries(proposal.diff || {})) {
      const r = el("tr");
      [key, delta.before, delta.after].forEach(x => r.append(el("td", "", x)));
      tbody.append(r);
    }
    table.append(tbody); area.append(table);
    if (proposal.risk_ack_required) {
      const risk = el("label", "f6201b-wb-risk");
      const box = el("input"); box.type = "checkbox"; box.id = "f6201b-wb-risk";
      risk.append(box, el("span", "",
        "Há risco de perder conectividade. Confirmo backup e acesso físico/local."));
      area.append(risk);
    }
    const confirm = el("label", "f6201b-wb-field");
    confirm.append(el("span", "", "Digite " + proposal.confirmation));
    const typed = el("input"); typed.type = "text";
    typed.id = "f6201b-wb-confirm"; typed.autocomplete = "off";
    confirm.append(typed); area.append(confirm);
    area.append(makeButton("Aplicar esta prévia", () => {
      void requestApply(root);
    }, "button primary"));
  }
  async function requestApply(root) {
    if (working || !proposal) return;
    const riskAck = !proposal.risk_ack_required ||
      root.querySelector("#f6201b-wb-risk")?.checked === true;
    if (!riskAck) {
      status(root, "Confirme o risco operacional antes do POST.", "error");
      return;
    }
    if (root.querySelector("#f6201b-wb-confirm")?.value !== proposal.confirmation) {
      status(root, "A frase de confirmação está incorreta.", "error");
      return;
    }
    const current = proposal, tag = selected, requestGeneration = generation;
    proposal = null; // consume locally before network I/O
    working = true;
    root.querySelectorAll(".f6201b-wb-preview button").forEach(b => b.disabled = true);
    status(root, "Enviando comando único; aguardando releitura de verificação…", "progress");
    try {
      const result = await api("/f6201b/workbench/apply", {
        nonce: current.nonce, confirmation: current.confirmation,
        risk_ack: riskAck
      });
      if (requestGeneration !== generation || tag !== selected) return;
      clear(root.querySelector(".f6201b-wb-preview"));
      if (result.verified) {
        status(root, "Aplicado e confirmado por releitura: " +
          (result.changed_fields || []).join(", ") + ".", "ok");
        // GET again only after a positively verified POST.
        working = false;
        await fetchInspect(root);
      } else {
        status(root, "Resultado incerto na etapa " + (result.stage || "desconhecida") +
          ". Confira a ONT original antes de uma nova prévia. " +
          (result.detail || ""), "error");
      }
    } catch (e) {
      if (requestGeneration !== generation || tag !== selected) return;
      clear(root.querySelector(".f6201b-wb-preview"));
      status(root, "Comando interrompido: " + e.message +
        ". Verifique o estado da ONT antes de tentar novamente.", "error");
    } finally { working = false; }
  }
  function renderDetails(root, retainStatus = false) {
    const detail = root.querySelector(".f6201b-wb-details");
    clear(detail);
    if (!retainStatus) status(root, "", "");
    const row = rowFor(selected);
    if (!row) return;
    const title = el("div", "f6201b-wb-detail-title");
    title.append(el("h3", "", row.tag), el("span",
      "f6201b-wb-badge " + row.state, stateLabel(row.state)));
    detail.append(title);
    detail.append(el("p", "f6201b-wb-hint", row.reason));
    if (row.state !== "supervised_lab") {
      detail.append(el("p", "f6201b-wb-hint",
        "Esta rota não é elegível para POST neste editor. O catálogo descreve " +
        "exatamente o estado observado sem presumir compatibilidade."));
      return;
    }
    const toolbar = el("div", "f6201b-wb-toolbar");
    toolbar.append(makeButton("Ler dados atuais", () => void fetchInspect(root)));
    detail.append(toolbar);
    const fields = el("div", "f6201b-wb-fields");
    detail.append(fields);
    if (liveInstances.length) drawFields(root, fields);
    else detail.append(el("p", "f6201b-wb-hint",
      "Use a leitura GET para identificar a instância antes da prévia."));
    detail.append(el("div", "f6201b-wb-preview"));
    if (proposal) renderPreview(root);
  }
  async function open() {
    const requestGeneration = generation;
    const bootstrap = await api("/discovery/bootstrap");
    if (requestGeneration !== generation || !checkedModel(bootstrap)) {
      document.getElementById(ID)?.remove();
      return;
    }
    if (!document.getElementById(ID)) {
      const host = document.getElementById("featureInspectorOutput")?.parentElement;
      if (!host) return;
      const root = el("section", "f6201b-wb");
      root.id = ID;
      root.append(el("div", "f6201b-wb-head",
        "LABORATÓRIO F6201B · V9.3.10P7N7"));
      root.append(el("p", "f6201b-wb-count", "Carregando inventário…"));
      const layout = el("div", "f6201b-wb-layout");
      layout.append(el("nav", "f6201b-wb-routes"));
      const editor = el("div", "f6201b-wb-editor");
      editor.append(el("p", "f6201b-wb-status"));
      editor.append(el("div", "f6201b-wb-details"));
      layout.append(editor); root.append(layout);
      host.append(root);
    }
    const root = document.getElementById(ID);
    if (!catalog) {
      status(root, "Carregando catálogo de rotas capturadas…", "progress");
      const data = await api("/f6201b/workbench/catalog");
      if (requestGeneration !== generation) return;
      catalog = data;
      selected = data.routes[0]?.tag || null;
    }
    renderList(root);
    renderDetails(root);
  }
  document.addEventListener("zte:session-changed", reset);
  document.addEventListener("zte:page-open", event => {
    if (event.detail?.pageName === "advanced")
      void open().catch(error => {
        const root = document.getElementById(ID);
        if (root) status(root, "Falha ao abrir laboratório: " + error.message, "error");
      });
  });
})();
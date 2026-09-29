/* Tangerine shell behavior is deliberately separate from ONT session logic.
 * The existing app.js continues to own navigation and every backend action.
 */
(() => {
  "use strict";
  const STORAGE = "access-manager-sidebar-collapsed";
  function init() {
    const sidebar = document.querySelector(".sidebar");
    const toggle = document.getElementById("sidebarCollapseToggle");
    if (!sidebar || !toggle) return;
    let preferredCollapsed = false;
    let mobileOpen = false;
    try {
      preferredCollapsed = localStorage.getItem(STORAGE) === "true";
    } catch {}
    const compactMedia = typeof window !== "undefined" && window.matchMedia
      ? window.matchMedia("(max-width: 930px)") : null;
    const isCompact = () => Boolean(compactMedia?.matches);
    let backdrop = null;
    if (compactMedia && document.createElement && document.body?.appendChild) {
      backdrop = document.createElement("button");
      backdrop.id = "amSidebarBackdrop";
      backdrop.type = "button";
      backdrop.hidden = true;
      backdrop.setAttribute("aria-label", "Fechar menu lateral");
      backdrop.addEventListener("click", () => {
        mobileOpen = false;
        render();
      });
      document.body.appendChild(backdrop);
    }
    function render() {
      if (!isCompact()) mobileOpen = false;
      const collapsed = isCompact() ? !mobileOpen : preferredCollapsed;
      sidebar.classList.toggle("is-collapsed", collapsed);
      sidebar.classList.toggle("am-mobile-open", isCompact() && mobileOpen);
      const shell = sidebar.closest?.(".app-shell");
      shell?.classList.toggle("am-shell-collapsed", isCompact() || preferredCollapsed);
      document.documentElement.dataset.sidebarCollapsed = String(isCompact() || preferredCollapsed);
      if (backdrop) backdrop.hidden = !(isCompact() && mobileOpen);
      toggle.setAttribute("aria-expanded", String(!collapsed));
      toggle.setAttribute("aria-label", collapsed ? "Abrir menu lateral" : "Recolher menu lateral");
      toggle.title = collapsed ? "Abrir menu lateral" : "Recolher menu lateral";
      const glyph = toggle.querySelector(".material-symbols-outlined");
      if (glyph) glyph.textContent = collapsed ? "menu_open" : "menu";
      sidebar.querySelectorAll(".menu-item[data-page]").forEach(button => {
        const text = button.querySelector("span:not(.material-symbols-outlined)");
        if (text) button.title = text.textContent.trim();
      });
    }
    toggle.addEventListener("click", () => {
      if (isCompact()) {
        mobileOpen = !mobileOpen;
      } else {
        preferredCollapsed = !preferredCollapsed;
        try { localStorage.setItem(STORAGE, String(preferredCollapsed)); } catch {}
      }
      render();
    });
    sidebar.querySelectorAll(".menu-item[data-page]").forEach(button => {
      button.addEventListener?.("click", () => {
        if (isCompact() && mobileOpen) {
          mobileOpen = false;
          render();
        }
      });
    });
    compactMedia?.addEventListener?.("change", render);
    document.addEventListener?.("keydown", event => {
      if (event.key === "Escape" && mobileOpen) {
        mobileOpen = false;
        render();
        toggle.focus?.();
      }
    });
    document.getElementById("appearanceSidebarButton")?.addEventListener("click", () => {
      if (isCompact() && mobileOpen) {
        mobileOpen = false;
        render();
      }
      const control = document.getElementById("appearanceSelect");
      control?.focus();
    });
    render();

    // Mirror existing authenticated DOM values instead of duplicating the
    // login protocol, requesting expensive firmware GETs or inventing stats.
    function syncOverview() {
      const connected = Boolean(document.body?.classList?.contains("ont-connected"));
      const read = id => document.getElementById(id)?.textContent?.trim() || "";
      const model = document.getElementById("overviewModel");
      const host = document.getElementById("overviewHost");
      const status = document.getElementById("overviewConnectionStatus");
      if (model) model.textContent = connected
        ? (read("connectedModel") || "Modelo não identificado")
        : "Nenhum equipamento conectado";
      if (host) host.textContent = connected
        ? (read("connectedHost") || "Endereço indisponível")
        : "Aguardando conexão";
      if (status) status.textContent = connected ? "Sessão ativa" : "Desconectado";
      const deviceModel = document.getElementById("deviceIdentityModel");
      const deviceHost = document.getElementById("deviceIdentityHost");
      const deviceState = document.getElementById("deviceIdentityState");
      if (deviceModel) deviceModel.textContent = connected
        ? (read("connectedModel") || "Modelo não identificado")
        : "Nenhum equipamento conectado";
      if (deviceHost) deviceHost.textContent = connected
        ? (read("connectedHost") || "Endereço indisponível")
        : "Sem endereço confirmado";
      if (deviceState) deviceState.textContent = connected
        ? "Equipamento autenticado" : "Sem sessão ativa";
    }
    syncOverview();
    if (typeof MutationObserver === "function") {
      for (const id of ["connectionStatus", "connectedModel", "connectedHost"]) {
        const target = document.getElementById(id);
        if (target) new MutationObserver(syncOverview).observe(target, {
          childList:true, characterData:true, subtree:true
        });
      }
    }

    // The local /history endpoint returns REAL persisted operations, not
    // Figma's sample activity. Render via textContent; never show raw
    // messages, URLs, POST bodies, passwords or diagnostic payloads here.
    let historyGeneration = 0, historyBusy = false;
    function historyTitle(raw, fallback) {
      return typeof raw === "string" &&
        /^[\p{L}][\p{L}\p{N} _-]{0,54}$/u.test(raw)
          ? raw : fallback;
    }
    async function refreshOverviewHistory() {
      const list = document.getElementById("overviewHistory");
      const page = document.getElementById("page-dashboard");
      if (!list || !page?.classList?.contains("active") ||
          !document.body?.classList?.contains("ont-connected") ||
          historyBusy || typeof apiRequest !== "function") return;
      const generation = historyGeneration;
      const hostAtStart = document.getElementById("connectedHost")?.textContent || "";
      const button = document.getElementById("overviewHistoryRefresh");
      historyBusy = true;
      if (button) button.disabled = true;
      list.textContent = "Consultando operações registradas...";
      try {
        const data = await apiRequest("/history?limit=5");
        // Reject stale responses after logout or equipment change.
        if (generation !== historyGeneration ||
            !document.body?.classList?.contains("ont-connected") ||
            hostAtStart !== (document.getElementById("connectedHost")?.textContent || "")) return;
        const changes = Array.isArray(data?.changes) ? data.changes.map(item => ({
          date:String(item.created_at || ""),
          title:historyTitle(item.operation, "Alteração de configuração"),
          success:item.success === true
        })) : [];
        const diagnostics = Array.isArray(data?.diagnostics) ? data.diagnostics.map(item => ({
          date:String(item.created_at || ""),
          title:historyTitle(item.status, "Diagnóstico"),
          success:true
        })) : [];
        const rows = [...changes,...diagnostics].sort((a,b) =>
          b.date.localeCompare(a.date)).slice(0,5);
        list.replaceChildren();
        if (!rows.length) {
          const empty=document.createElement("p");
          empty.className="am-activity-empty";
          empty.textContent="Nenhuma operação registrada neste histórico.";
          list.appendChild(empty);
          return;
        }
        for (const row of rows) {
          const card=document.createElement("div");
          card.className="am-activity-item";
          const title=document.createElement("strong");
          title.textContent=row.title;
          const time=document.createElement("small");
          const safeTime=/^\d{4}-\d{2}-\d{2}/.test(row.date)
            ? row.date.slice(0,19).replace("T"," ") : "Horário indisponível";
          time.textContent=(row.success ? "Concluído" : "Verificar resultado")+
            " · "+safeTime;
          card.append(title,time);
          list.appendChild(card);
        }
      } catch (error) {
        if (generation === historyGeneration) {
          list.textContent="O histórico não está disponível agora. Tente atualizar.";
        }
      } finally {
        historyBusy=false;
        if (button) button.disabled=false;
      }
    }
    document.getElementById("overviewHistoryRefresh")?.addEventListener(
      "click",refreshOverviewHistory);
    if (typeof MutationObserver === "function") {
      const dashboard=document.getElementById("page-dashboard");
      if (dashboard) new MutationObserver(() => {
        if (dashboard.classList.contains("active")) {
          syncOverview();
          refreshOverviewHistory();
        }
      }).observe(dashboard,{attributes:true,attributeFilter:["class"]});
    }
    document.addEventListener?.("zte:session-changed", () => {
      historyGeneration++;
      syncOverview();
      const list=document.getElementById("overviewHistory");
      if (list) list.textContent="Abra esta página para consultar o histórico.";
    });
  }
  if (document.readyState === "loading")
    document.addEventListener("DOMContentLoaded", init, { once:true });
  else init();
})();

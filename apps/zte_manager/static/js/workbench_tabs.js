/* Access Manager workbench controller.
 * Only presentation concerns live here. Existing page actions, sessions and
 * backend handlers stay in their original modules.
 */
(() => {
  "use strict";
  function setupWorkbench(section) {
    if (!section) return;
    const tabs = [...section.querySelectorAll('[role="tab"][data-am-tab]')];
    const panels = [...section.querySelectorAll('[role="tabpanel"][data-am-panel]')];
    if (!tabs.length || tabs.length !== panels.length) return;
    const allowed = new Set(tabs.map(tab => tab.dataset.amTab));
    const key = "am-workbench:" + section.id;
    function activate(target, focus = false) {
      if (!allowed.has(target)) return false;
      for (const tab of tabs) {
        const active = tab.dataset.amTab === target;
        tab.setAttribute("aria-selected", String(active));
        tab.tabIndex = active ? 0 : -1;
        tab.classList.toggle("is-active", active);
        if (active && focus) tab.focus();
      }
      for (const panel of panels) {
        panel.hidden = panel.dataset.amPanel !== target;
      }
      try { sessionStorage.setItem(key, target); } catch {}
      return true;
    }
    const initial = (() => {
      try { return sessionStorage.getItem(key) || tabs[0].dataset.amTab; }
      catch { return tabs[0].dataset.amTab; }
    })();
    activate(allowed.has(initial) ? initial : tabs[0].dataset.amTab);
    tabs.forEach((tab, position) => {
      tab.addEventListener("click", () => activate(tab.dataset.amTab));
      tab.addEventListener("keydown", event => {
        let next = position;
        if (event.key === "ArrowRight" || event.key === "ArrowDown")
          next = (position + 1) % tabs.length;
        else if (event.key === "ArrowLeft" || event.key === "ArrowUp")
          next = (position - 1 + tabs.length) % tabs.length;
        else if (event.key === "Home") next = 0;
        else if (event.key === "End") next = tabs.length - 1;
        else return;
        event.preventDefault();
        activate(tabs[next].dataset.amTab, true);
      });
    });
    // Toolbar actions already have actual handlers. Select the corresponding
    // panel so results remain visible without intercepting network commands.
    const destinations = {
      probeCapabilitiesButton:"discovery",multimodelProbeButton:"discovery",
      refreshAdvancedNetworkButton:"dhcp",multimodelDiagnosticButton:"diagnostics",
      multimodelMeshButton:"diagnostics",exportFeatureShapesButton:"discovery",
      captureSnapshotButton:"diagnostics",backupConfigurationButton:"inspector",
      overviewHistoryRefresh:"diagnostics"
    };
    for (const [id, panel] of Object.entries(destinations)) {
      section.querySelector("#"+id)?.addEventListener("click", () => activate(panel), true);
    }
    section.addEventListener("am:show-panel", event => {
      const target = event.detail?.panel;
      if (allowed.has(target)) activate(target);
    });
    return { activate };
  }
  function init() {
    const advanced = document.getElementById("page-advanced");
    const api = setupWorkbench(advanced);
    if (typeof window !== "undefined") window.AccessManagerWorkbench = api;
  }
  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init, {once:true});
  } else init();
})();
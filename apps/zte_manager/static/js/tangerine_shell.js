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
    let collapsed = false;
    try { collapsed = localStorage.getItem(STORAGE) === "true"; } catch {}
    function render() {
      sidebar.classList.toggle("is-collapsed", collapsed);
      toggle.setAttribute("aria-expanded", String(!collapsed));
      toggle.setAttribute("aria-label", collapsed ? "Expandir menu lateral" : "Recolher menu lateral");
      toggle.title = collapsed ? "Expandir menu lateral" : "Recolher menu lateral";
      const glyph = toggle.querySelector(".material-symbols-outlined");
      if (glyph) glyph.textContent = collapsed ? "menu_open" : "menu";
      // Native browser tooltip keeps collapsed destinations understandable.
      sidebar.querySelectorAll(".menu-item[data-page]").forEach(button => {
        const text = button.querySelector("span:not(.material-symbols-outlined)");
        if (text) button.title = text.textContent.trim();
      });
    }
    toggle.addEventListener("click", () => {
      collapsed = !collapsed;
      try { localStorage.setItem(STORAGE, String(collapsed)); } catch {}
      render();
    });
    document.getElementById("appearanceSidebarButton")?.addEventListener("click", () => {
      const control = document.getElementById("appearanceSelect");
      control?.focus();
    });
    render();
  }
  if (document.readyState === "loading")
    document.addEventListener("DOMContentLoaded", init, { once:true });
  else init();
})();

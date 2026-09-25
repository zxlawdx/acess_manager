/* Neutral Console theme: persists user choice without affecting ONT data. */
(() => {
  "use strict";
  const STORAGE = "zte-automatic-theme";
  const html = document.documentElement;
  function chosen() {
    try {
      const saved = localStorage.getItem(STORAGE);
      return saved === "light" || saved === "dark" ? saved :
        (matchMedia("(prefers-color-scheme: light)").matches ? "light" : "dark");
    } catch {
      return "dark";
    }
  }
  function apply(theme) {
    html.dataset.theme = theme;
    const button = document.getElementById("themeToggle");
    if (!button) return;
    const next = theme === "dark" ? "light" : "dark";
    button.setAttribute("aria-label","Ativar modo " + (next==="light"?"claro":"escuro"));
    button.setAttribute("title","Mudar para modo " + (next==="light"?"claro":"escuro"));
    button.setAttribute("aria-pressed",String(theme==="dark"));
    button.innerHTML = '<span aria-hidden="true">' +
      (theme==="dark" ? "☀" : "☾") +
      '</span><span class="theme-label">Modo ' +
      (theme==="dark" ? "escuro" : "claro") +
      '</span>';
  }
  const initial=chosen();
  html.dataset.theme=initial;
  function init() {
    apply(html.dataset.theme || initial);
    document.getElementById("themeToggle")?.addEventListener("click", () => {
      const next=html.dataset.theme==="dark"?"light":"dark";
      try { localStorage.setItem(STORAGE,next); } catch {}
      apply(next);
    });
  }
  if(document.readyState==="loading")
    document.addEventListener("DOMContentLoaded",init,{once:true});
  else init();
})();

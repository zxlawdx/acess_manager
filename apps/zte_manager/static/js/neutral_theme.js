/* Tangerine appearance controller. Existing light/dark preferences migrate
 * unchanged; "auto" follows the operating system, including live changes.
 * No equipment calls or session changes occur in this module.
 */
(() => {
  "use strict";
  const STORAGE = "zte-automatic-theme"; // retain previous versions' key
  const root = document.documentElement;
  const media = typeof matchMedia === "function"
    ? matchMedia("(prefers-color-scheme: dark)") : null;
  const allowed = new Set(["light", "dark", "auto"]);
  let preference;
  try {
    const saved = localStorage.getItem(STORAGE);
    preference = allowed.has(saved) ? saved : "auto";
  } catch {
    preference = "auto";
  }
  function effective() {
    return preference === "auto" ? (media?.matches ? "dark" : "light") : preference;
  }
  function label(value) {
    return ({ light: "Claro", dark: "Escuro", auto: "Automático" })[value];
  }
  function apply() {
    const resolved = effective();
    root.dataset.appearance = preference;
    root.dataset.theme = resolved; // compatibility with all legacy CSS
    const select = document.getElementById("appearanceSelect");
    if (select && select.value !== preference) select.value = preference;
    const toggle = document.getElementById("themeToggle");
    if (toggle) {
      toggle.setAttribute("aria-label", "Aparência atual: " + label(preference));
      toggle.setAttribute("title", "Aparência atual: " + label(preference));
      toggle.setAttribute("aria-pressed", String(resolved === "dark"));
      // Keep a functional fallback for existing builds that show this button.
      const icon = resolved === "dark" ? "☾" : "☀";
      toggle.textContent = icon + " " + label(preference);
    }
  }
  function choose(value) {
    if (!allowed.has(value)) return;
    preference = value;
    try { localStorage.setItem(STORAGE, preference); } catch {}
    apply();
  }
  // This is also set by the inline bootstrap in index.html before CSS loads.
  apply();
  function init() {
    document.getElementById("appearanceSelect")?.addEventListener("change", event => {
      choose(event.target.value);
    });
    document.getElementById("themeToggle")?.addEventListener("click", () => {
      const choices = ["light", "dark", "auto"];
      choose(choices[(choices.indexOf(preference) + 1) % choices.length]);
    });
    apply();
  }
  if (media) {
    if (typeof media.addEventListener === "function") {
      media.addEventListener("change", () => { if (preference === "auto") apply(); });
    } else if (typeof media.addListener === "function") {
      media.addListener(() => { if (preference === "auto") apply(); });
    }
  }
  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init, { once:true });
  } else init();
})();

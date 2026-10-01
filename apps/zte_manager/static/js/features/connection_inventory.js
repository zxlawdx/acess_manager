/* Figma Connections composition, backed by the REAL local CPE inventory.
 * Display and selection only; credentials are never read/persisted here.
 * Submitting /connect stays the exclusive responsibility of app.js.
 */
(() => {
  "use strict";
  const LIMIT=100;
  const hostPattern=/^[A-Za-z0-9.:[\]-]{1,255}$/;
  const modelPattern=/^[A-Za-z0-9 _.-]{1,40}$/;
  let devices=[],pending=null,lastLoaded=0,generation=0;
  const $=id=>document.getElementById(id);
  const text=(tag,className,value)=>{
    const item=document.createElement(tag);
    if(className)item.className=className;
    if(value!==undefined)item.textContent=value;
    return item;
  };
  function safeDevice(raw) {
    if(!raw||typeof raw!=="object")return null;
    const host=String(raw.host||"").trim();
    if(!hostPattern.test(host)||host.includes("..")||host.includes("@")||
       !/[A-Za-z0-9]/.test(host))return null;
    const name=String(raw.model||raw.name||"Equipamento ZTE").trim();
    return {
      host,
      model:modelPattern.test(name)?name:"Equipamento ZTE",
      // Inventory status is NOT proof of an active connection. Avoid badges.
    };
  }
  function draw() {
    const mount=$("connectionInventoryList"),counter=$("connectionInventoryCount");
    if(!mount)return;
    const q=($("connectionInventorySearch")?.value||"").toLocaleLowerCase("pt-BR").trim();
    const filtered=devices.filter(item=>item.host.toLowerCase().includes(q)||
      item.model.toLocaleLowerCase("pt-BR").includes(q));
    mount.replaceChildren();
    if(counter)counter.textContent=devices.length+" equipamento(s) registrado(s)";
    if(!filtered.length) {
      mount.appendChild(text("p","am-inventory-empty",
        devices.length?"Nenhum equipamento corresponde à pesquisa.":
        "Nenhum equipamento registrado. Informe o IP para conectar."));
      return;
    }
    const current=typeof currentHost==="string"?currentHost:"";
    for(const item of filtered) {
      const card=text("button","am-inventory-entry");
      card.type="button";
      card.setAttribute("aria-label","Preencher endereço do equipamento "+item.model);
      if(item.host===current)card.classList.add("is-current");
      const icon=text("span","am-inventory-icon");
      icon.appendChild(text("span","material-symbols-outlined","router"));
      const details=text("span","am-inventory-meta");
      details.append(text("strong","",item.model),text("small","mono",item.host));
      const arrow=text("span","material-symbols-outlined am-inventory-arrow","chevron_right");
      card.append(icon,details,arrow);
      card.addEventListener("click",()=>{
        const host=$("zteIp");
        if(!host)return;
        host.value=item.host;
        host.dispatchEvent(new Event("input",{bubbles:true}));
        $("zteUsername")?.focus();
        mount.querySelectorAll(".am-inventory-entry").forEach(
          button=>button.classList.toggle("is-selected",button===card));
      });
      mount.appendChild(card);
    }
  }
  async function refresh({force=false}={}) {
    const mount=$("connectionInventoryList");
    if(!mount||typeof apiRequest!=="function")return;
    if(pending)return pending;
    if(!force && lastLoaded && Date.now()-lastLoaded<30000){draw();return;}
    const revision=++generation;
    mount.setAttribute("aria-busy","true");
    mount.textContent="Consultando equipamentos registrados...";
    pending=(async()=>{
      try {
        const result=await apiRequest("/management/inventory?limit="+LIMIT,{expected:"object",silent:true});
        if(revision!==generation)return;
        if(!Array.isArray(result.devices)) {
          throw new Error("Formato inesperado.");
        }
        const unique=new Set();
        devices=result.devices.map(safeDevice).filter(item=>{
          if(!item||unique.has(item.host))return false;
          unique.add(item.host);return true;
        });
        lastLoaded=Date.now();
        draw();
      } catch (_error) {
        if(revision!==generation)return;
        if(!lastLoaded) {
          devices=[];
          mount.replaceChildren(text("p","am-inventory-empty",
            "Inventário indisponível. A conexão manual continua disponível."));
          const counter=$("connectionInventoryCount");
          if(counter)counter.textContent="Inventário indisponível";
        }else draw();
      } finally {
        pending=null;
        mount.setAttribute("aria-busy","false");
      }
    })();
    return pending;
  }
  function init() {
    $("connectionInventorySearch")?.addEventListener("input",draw);
    $("connectionNewTarget")?.addEventListener("click",()=>{
      const host=$("zteIp");
      if(host){host.value="";host.dispatchEvent(new Event("input",{bubbles:true}));host.focus();}
      $("connectionInventorySearch").value="";
      draw();
    });
    document.addEventListener("device:page-open",event=>{
      if(event.detail?.pageName==="connection") void refresh();
    });
    document.addEventListener("device:session-changed",()=>{
      // Never misrepresent stale inventory as live session state.
      const visible=$("page-connection")?.classList.contains("active");
      if(visible)draw();
    });
    if($("page-connection")?.classList.contains("active"))void refresh();
  }
  if(typeof window!=="undefined")
    window.AccessManagerConnectionInventory=Object.freeze({refresh,safeDevice});
  if(document.readyState==="loading")
    document.addEventListener("DOMContentLoaded",init,{once:true});
  else init();
})();
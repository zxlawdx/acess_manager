/* Session history & backup actions.
 * This module owns operator-facing history presentation. It consumes the
 * canonical shared API and never handles ONT credentials or HTTP internals.
 */
(() => {
  "use strict";
  const safeLabel = (value, fallback) =>
    typeof value === "string" &&
      /^[\p{L}\p{N} _.,:()\-]{1,65}$/u.test(value)
        ? value : fallback;
  const safeTime = value =>
    typeof value === "string" && /^\d{4}-\d{2}-\d{2}/.test(value)
      ? value.slice(0,19).replace("T"," ") : "Horário indisponível";
  function make(tag, cls, label) {
    const el = document.createElement(tag);
    if (cls) el.className = cls;
    if (label !== undefined) el.textContent = label;
    return el;
  }
  function renderHistory(container, data) {
    if (!container) return;
    const changes = Array.isArray(data?.changes) ? data.changes : [];
    const diagnostics = Array.isArray(data?.diagnostics) ? data.diagnostics : [];
    const entries = [
      ...changes.map(item => ({
        title:safeLabel(item.operation,"Alteração de configuração"),
        status:item.success === true ? "Concluída" : "Verificar resultado",
        time:safeTime(item.created_at),order:String(item.created_at||"")
      })),
      ...diagnostics.map(item => ({
        title:safeLabel(item.status,"Diagnóstico"),
        status:"Diagnóstico registrado",
        time:safeTime(item.created_at),order:String(item.created_at||"")
      }))
    ].sort((a,b)=>b.order.localeCompare(a.order)).slice(0,20);
    container.replaceChildren();
    if (!entries.length) {
      container.appendChild(make("p","am-history-empty","Nenhuma operação registrada."));
      return;
    }
    const timeline = make("ol","am-history-timeline");
    for (const entry of entries) {
      const row = make("li","am-history-item");
      const label=make("strong","",entry.title);
      const status=make("span","am-history-state",entry.status);
      const time=make("time","mono",entry.time);
      row.append(label,status,time);
      timeline.appendChild(row);
    }
    container.appendChild(timeline);
  }
  let generation=0,loading=false;
  async function load() {
    const container=document.getElementById("historyOutput");
    if (!container || loading) return;
    const at=generation,host=typeof currentHost==="string"?currentHost:"";
    loading=true;
    container.setAttribute("aria-busy","true");
    container.textContent="Consultando histórico...";
    try {
      const payload=await apiRequest("/history?limit=20",{expected:"object"});
      if (at!==generation || host!==(typeof currentHost==="string"?currentHost:"")) return;
      renderHistory(container,payload);
    } catch (_error) {
      if (at===generation)
        container.textContent="Histórico temporariamente indisponível. Tente atualizar.";
    } finally {
      loading=false;
      container.setAttribute("aria-busy","false");
    }
  }
  async function snapshot() {
    if (!ontConnected) {
      showToast("Conecte-se à ONT antes de registrar uma captura.");return;
    }
    if (!routerWriteEnabled) {
      showToast("A captura não está habilitada nesta sessão. Use o diagnóstico disponível.");return;
    }
    setBusy(true,"Registrando captura de estado...");
    try {
      const data=await apiRequest("/history/snapshot",{
        method:"POST",body:JSON.stringify({reason:"manual-ui"}),expected:"object"
      });
      const id=Number.isSafeInteger(data.snapshot_id) && data.snapshot_id>0
        ? " #" + data.snapshot_id : "";
      if (data.partial === true) {
        showToast("Captura"+id+" parcial. Revise os dados atuais antes de repetir.");
      } else if (id) {
        showToast("Captura"+id+" registrada.");
      } else {
        showToast("A solicitação foi processada, mas a confirmação da captura não foi retornada.");
      }
      await load();
    } catch(error) { showToast(error.message); }
    finally {setBusy(false);}
  }
  async function backup() {
    if (!ontConnected) {
      showToast("Conecte-se à ONT antes de executar backup.");return;
    }
    if (!routerWriteEnabled) {
      showToast("Backup não autorizado nesta sessão. Utilize a inspeção disponível.");return;
    }
    if (!window.confirm("Exportar uma cópia local da configuração do equipamento?"))return;
    setBusy(true,"Exportando configuração...");
    try {
      const data=await apiRequest("/system/backup",{method:"POST",expected:"object"});
      const display=document.getElementById("backupResult");
      const file=typeof (data.filename||data.path)==="string"
        ? String(data.filename||data.path).split(/[\\/]/).pop() : "";
      const cleanName=/^[\w.\-]{1,100}$/.test(file)?file:"";
      const confirmed=Boolean(cleanName || (data.success===true&&data.size>0));
      if(display) {
        display.replaceChildren();
        display.appendChild(make("div","am-history-backup",
          confirmed ? "Backup confirmado"+(cleanName?": "+cleanName:"") :
            "O serviço não retornou a confirmação do arquivo."));
      }
      showToast(confirmed ? "Backup local concluído." :
        "A exportação não pôde ser confirmada. Verifique os registros.");
      if(confirmed) await load();
    } catch(error) {showToast(error.message);}
    finally {setBusy(false);}
  }
  if(typeof document.addEventListener==="function")
    document.addEventListener("device:session-changed",()=>{generation++;});
  if(typeof window!=="undefined") window.AccessManagerHistory=
    Object.freeze({renderHistory,load,snapshot,backup});
})();
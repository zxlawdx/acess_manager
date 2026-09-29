/* Tangerine structured configuration editors.
 * Progressive enhancement: legacy textarea IDs are preserved so every
 * existing Vela route and management.js handler receives unchanged JSON.
 * The JSON source is hidden only after a complete editor is built.
 */
(() => {
  "use strict";
  const SOURCES = [
    "managementProfileJson", "managementBatchPayload",
    "managementQosJson", "managementFirewallRuleJson",
    "managementFirewallGlobalJson", "managementSntpJson",
    "managementTr069Json", "managementWanJson"
  ];
  const NAMES = {
    wifi:"Redes Wi-Fi", dns:"Servidores DNS",
    band_steering:"Direcionamento entre bandas", auto_channel:"Canal automático",
    enabled:"Ativado", Enable:"Ativado", Alias:"Identificação",
    Name:"Nome", Protocol:"Protocolo", mac_enabled:"Filtro de MAC",
    mac_target:"Ação sobre MAC", server1:"Servidor principal",
    server2:"Servidor secundário", periodic_inform_enabled:"Informes periódicos",
    periodic_inform_interval:"Intervalo (segundos)",
    vlan_enabled:"Utilizar VLAN", vlan_id:"Identificador da VLAN",
    priority:"Prioridade", mtu:"MTU", profile_id:"Perfil",
    password:"Senha", username:"Usuário", host:"Endereço"
  };
  const isPlain = value => value !== null && typeof value === "object" &&
    !Array.isArray(value);
  function labelFor(key) {
    if (Object.prototype.hasOwnProperty.call(NAMES, key)) return NAMES[key];
    return String(key).replace(/_/g," ").replace(/([a-z])([A-Z])/g,"$1 $2")
      .replace(/^./, c => c.toLocaleUpperCase("pt-BR"));
  }
  function assignPath(obj, path, value) {
    if (!path.length) return;
    let current = obj;
    for (let i=0; i<path.length-1; i++) {
      const name = path[i];
      if (!isPlain(current[name])) current[name] = {};
      current = current[name];
    }
    current[path[path.length-1]] = value;
  }
  function coerce(value, kind) {
    if (kind === "boolean") return Boolean(value);
    if (kind === "number") {
      if (String(value).trim()==="") throw new Error("Informe um número.");
      const number = Number(value);
      if (!Number.isFinite(number)) throw new Error("Informe um número válido.");
      return number;
    }
    return String(value);
  }
  const API = Object.freeze({labelFor,assignPath,coerce,isPlain});
  if (typeof window !== "undefined") window.TangerineFormsCore = API;
  function node(tag, cls, text) {
    const el = document.createElement(tag);
    if (cls) el.className = cls;
    if (text !== undefined) el.textContent = text;
    return el;
  }
  function enhance(source) {
    const label = source.closest("label");
    if (!label || !label.parentNode) return false;
    let initial;
    try {
      initial = JSON.parse(source.value || "{}");
      if (!isPlain(initial)) throw Error("A configuração deve conter campos.");
    } catch {
      label.classList.add("am-source-invalid");
      return false;  // preserve the functional raw editor if initial data is invalid
    }
    const state = initial;
    const editor = node("section","am-form-editor");
    editor.setAttribute("aria-label", "Configuração por formulário");
    const head = node("div","am-form-editor-head");
    const title = label.querySelector("span");
    head.appendChild(node("strong","",(title?.textContent || "").replace(/JSON/gi,"").trim() || "Parâmetros"));
    head.appendChild(node("small","", "Preencha os campos; o aplicativo converterá os valores automaticamente."));
    editor.appendChild(head);
    const content = node("div","am-form-editor-content");
    const feedback = node("p","am-form-editor-feedback");
    feedback.setAttribute("role","status");
    feedback.setAttribute("aria-live","polite");
    let counter=0;
    function sync() {
      source.value=JSON.stringify(state,null,2);
      feedback.textContent="";
      source.dispatchEvent(new Event("input",{bubbles:true}));
    }
    function addDynamic(container,path) {
      const add=node("button","am-add-setting","Adicionar parâmetro");
      add.type="button";
      add.addEventListener("click",() => {
        const row=node("div","am-dynamic-field");
        const name=node("input");name.type="text";name.placeholder="Nome do parâmetro";
        name.setAttribute("aria-label","Nome do novo parâmetro");
        const type=node("select");
        for(const [value,text] of [["string","Texto"],["number","Número"],["boolean","Sim / não"]]){
          const opt=node("option","",text);opt.value=value;type.appendChild(opt);
        }
        type.setAttribute("aria-label","Tipo do novo parâmetro");
        const input=node("input");input.type="text";input.placeholder="Valor";
        input.setAttribute("aria-label","Valor do novo parâmetro");
        const remove=node("button","am-remove-setting","Remover");
        remove.type="button";
        let savedName="";
        function commit() {
          const nameValue=name.value.trim();
          const target=path.reduce((acc,key)=>acc[key],state);
          if (savedName && savedName!==nameValue) delete target[savedName];
          if (!/^[a-zA-Z][a-zA-Z0-9_.-]{0,63}$/.test(nameValue)) {
            feedback.textContent="Informe um nome de parâmetro válido antes de salvar.";
            return;
          }
          if (Object.prototype.hasOwnProperty.call(target,nameValue) && savedName!==nameValue) {
            feedback.textContent="Este parâmetro já existe.";return;
          }
          let val;
          try {val=type.value==="boolean"?(input.value==="true"):coerce(input.value,type.value);}
          catch(e){feedback.textContent=e.message;return;}
          target[nameValue]=val;savedName=nameValue;sync();
        }
        type.addEventListener("change",()=>{
          input.type=type.value==="number"?"number":"text";
          input.placeholder=type.value==="boolean"?"true ou false":"Valor";
          if (savedName) commit();
        });
        name.addEventListener("change",commit);
        input.addEventListener("change",commit);
        remove.addEventListener("click",()=>{
          if(savedName){const target=path.reduce((acc,key)=>acc[key],state);delete target[savedName];sync();}
          row.remove();
        });
        row.append(name,type,input,remove);
        container.insertBefore(row,add);
        name.focus();
      });
      container.appendChild(add);
    }
    function build(container, group, path) {
      const entries=Object.entries(group);
      for(const [key,value] of entries) {
        if (isPlain(value)) {
          const fieldset=node("fieldset","am-editor-group");
          const legend=node("legend","",labelFor(key));fieldset.appendChild(legend);
          build(fieldset,value,[...path,key]);
          container.appendChild(fieldset);
        } else {
          const wrap=node("label","am-editor-field");
          const caption=node("span","",labelFor(key));wrap.appendChild(caption);
          const kind=typeof value;
          let input;
          if (kind==="boolean") {
            input=node("input");input.type="checkbox";input.checked=value;wrap.classList.add("am-editor-toggle");
          } else if (Array.isArray(value)) {
            input=node("input");input.type="text";input.value=value.join(", ");
            input.placeholder="Itens separados por vírgula";
          } else {
            input=node("input");
            input.type=kind==="number"?"number":/pass(word)?|secret|token/i.test(key)?"password":"text";
            input.value=String(value ?? "");
            if (input.type==="password") input.autocomplete="new-password";
          }
          input.id="am-editor-"+source.id+"-"+(++counter);
          input.setAttribute("aria-label",labelFor(key));
          if (kind==="boolean") {
            input.addEventListener("change",()=>{
              assignPath(state,[...path,key],input.checked);sync();
            });
          } else {
            input.addEventListener("change",()=>{
              try {
                const next=Array.isArray(value)
                  ?input.value.split(",").map(item=>item.trim()).filter(Boolean)
                  :coerce(input.value,kind==="number"?"number":"string");
                assignPath(state,[...path,key],next);sync();
              } catch(error) {feedback.textContent=error.message;}
            });
          }
          wrap.appendChild(input);container.appendChild(wrap);
        }
      }
      if (entries.length===0 || path.length===0) addDynamic(container,path);
    }
    build(content,state,[]);
    editor.append(content,feedback);
    label.parentNode.insertBefore(editor,label);
    // Hide only after successful composition. Old backend handlers still read
    // the original textarea value, including unknown keys not edited by UI.
    label.classList.add("am-editor-mounted");
    sync();
    return true;
  }
  function init() {
    const elements=SOURCES.map(id=>document.getElementById(id)).filter(Boolean);
    elements.forEach(enhance);
    if(elements.length) document.body.classList.add("am-structured-ready");
  }
  if (document.readyState==="loading") document.addEventListener("DOMContentLoaded",init,{once:true});
  else init();
})();

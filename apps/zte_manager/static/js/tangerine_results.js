/* Human-readable management results: the default UI never prints JSON.
 * Keep technical data for explicit export actions and private internal logs.
 */
(() => {
 "use strict";
 const PRIVATE=/(?:pass(?:word|phrase|wd)?|secret|token|cookie|authorization|api[_-]?key|endpoint|request[_-]?(?:body|headers)|traceback|stack|querystring)/i;
 const LABELS={status:"Situação",success:"Resultado",error:"Erro",message:"Mensagem",
  model:"Modelo",firmware:"Firmware",host:"Equipamento",device_id:"Identificador",
  count:"Quantidade",name:"Nome",type:"Tipo",created_at:"Horário",
  wan:"WAN",dns:"DNS",wifi:"Wi-Fi",connected:"Conexão",available:"Disponível",
  operation:"Operação",verified:"Verificado",pending:"Pendente"};
 const label=name=>LABELS[name]||String(name).replace(/_/g," ").replace(/^./,x=>x.toUpperCase());
 function sanitize(value,depth=0) {
   if(value===null||value===undefined)return "Não informado";
   if(depth>3)return "Dados adicionais disponíveis.";
   if(Array.isArray(value))return value.slice(0,25).map(v=>sanitize(v,depth+1));
   if(typeof value==="object"){
      const safe={};
      for(const [key,val] of Object.entries(value).slice(0,50)){
       if(!PRIVATE.test(key))safe[key]=sanitize(val,depth+1);
      }
      return safe;
   }
   if(typeof value==="boolean")return value?"Sim":"Não";
   const text=String(value);
   if(/(?:\\b(?:GET|POST|PUT|PATCH|DELETE)\\s+\\/|https?:\\/\\/|\\b(?:password|token|secret|authorization)\\s*[:=]|traceback|<script)/i.test(text))
     return "Informação técnica reservada.";
   return text.length>220?text.slice(0,217)+"...":text;
 }
 function flatten(value,depth=0){
   if(depth>3)return ["Dados adicionais disponíveis."];
   if(Array.isArray(value))return value.length
     ?value.flatMap((entry,i)=>["Registro "+(i+1)].concat(flatten(entry,depth+1))).slice(0,90)
     :["Nenhum registro encontrado."];
   if(value&&typeof value==="object"){
     const entries=Object.entries(value);
     return entries.length?entries.flatMap(([key,item])=>
      item&&typeof item==="object"
       ?[label(key)+":"].concat(flatten(item,depth+1).map(line=>"  "+line))
       :[label(key)+": "+item]).slice(0,90)
       :["Nenhuma informação encontrada."];
   }
   return [String(value)];
 }
 function node(tag,cls,text){
   const el=document.createElement(tag);
   if(cls)el.className=cls;
   if(text!==undefined)el.textContent=text;
   return el;
 }
 function draw(parent,item,depth=0){
   if(depth>3){parent.appendChild(node("span","am-result-value","Dados adicionais."));return;}
   if(Array.isArray(item)){
     const items=node("div","am-result-items");
     for(const entry of item){
       const child=node("div","am-result-record");draw(child,entry,depth+1);items.appendChild(child);
     }
     if(!item.length)items.appendChild(node("p","am-result-empty","Nenhum registro encontrado."));
     parent.appendChild(items);return;
   }
   if(item&&typeof item==="object"){
     const list=node("dl","am-result-grid");
     for(const [key,value] of Object.entries(item)){
       const field=node("div","am-result-cell");
       field.appendChild(node("dt","",label(key)));
       const desc=node("dd");draw(desc,value,depth+1);
       field.appendChild(desc);list.appendChild(field);
     }
     if(!Object.keys(item).length)parent.appendChild(node("p","am-result-empty","Nenhuma informação encontrada."));
     else parent.appendChild(list);
     return;
   }
   parent.appendChild(node("span","am-result-value",String(item)));
 }
 function render(value,element){
    if(!element)return;
    if(element.tagName==="PRE"||element.tagName==="TEXTAREA"){
      element.textContent=flatten(sanitize(value)).join("\n");
      return;
    }
    const box=node("section","am-operator-result");
    box.setAttribute("aria-label","Resultado da operação");
    box.appendChild(node("h4","am-result-title",value?.error?"Operação não concluída":"Resultado da consulta"));
    if(value?.error){
      const safe=typeof window.normalizeApiErrorMessage==="function"
       ?window.normalizeApiErrorMessage(value.error,0,value.type||"")
       :"Não foi possível concluir a operação. Verifique a sessão e tente novamente.";
      box.appendChild(node("p","am-result-alert",String(safe)));
    }
    draw(box,sanitize(value));
    element.replaceChildren(box);
 }
 if(typeof window!=="undefined")window.TangerineResults=Object.freeze({sanitize,render});
})();

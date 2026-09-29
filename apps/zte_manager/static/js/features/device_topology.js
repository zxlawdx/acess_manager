/* Read-only connected-device topology. Consumes the real /clients readings from
 * app.js. Edges mean an observed Wi-Fi/LAN association, not physical position.
 * No credentials, geolocation, manufacturer guess or background probes.
 */
(() => {
  "use strict";
  const NS = "http://www.w3.org/2000/svg";
  const MAX_PER_GROUP = 28;
  const samples = new Map();
  let currentHost = "";
  let current = {wifi:[],lan:[]};
  let selectedKey = null;

  const clean = (value, fallback="Não informado", limit=72) => {
    if (value === null || value === undefined || String(value).trim()==="") return fallback;
    const str=String(value).replace(/[\x00-\x1F\x7F<>]/g,"").trim();
    if (/(?:https?:\/\/|password\s*[:=]|token\s*[:=]|secret\s*[:=]|cookie\s*[:=])/i.test(str)) return fallback;
    return str ? str.slice(0,limit) : fallback;
  };
  function clientType(hostname) {
    const h=String(hostname||"").toLowerCase();
    if (/\b(iphone|android|galaxy|redmi|pixel|smartphone|celular|moto[- ]?g)\b/.test(h))
      return "Possível celular (inferido pelo nome)";
    if (/\b(smart[- ]?tv|televis[aã]o|bravia|webos|tizen|chromecast|roku|fire[- ]?tv|android[- ]?tv)\b/.test(h))
      return "Possível televisão ou TV Box (inferido pelo nome)";
    if (/\b(notebook|laptop|desktop|thinkpad|macbook|imac|workstation|computer|computador)\b/.test(h))
      return "Possível computador (inferido pelo nome)";
    return "Tipo não identificado";
  }
  function rssiValue(value) {
    if(value===null||value===undefined||value==="")return null;
    // Accept -62, "-62 dBm", but reject unrelated firmware diagnostic text.
    if(!/^-?\d{1,3}(?:[.,]\d)?(?:\s*dBm)?$/i.test(String(value).trim()))return null;
    const n=Number(String(value).replace(/dBm/i,"").trim().replace(",","."));
    return n>=-110&&n<=-10?n:null;
  }
  function estimateDistance(meanRssi, atOneMeter, exponent) {
    if(!Number.isFinite(meanRssi)||!Number.isFinite(atOneMeter)||
       meanRssi < -110||meanRssi > -10||atOneMeter < -110||atOneMeter > -10||
       !Number.isFinite(exponent)||exponent<1.6||exponent>6)return null;
    const result=Math.pow(10,(atOneMeter-meanRssi)/(10*exponent));
    return Number.isFinite(result)&&result>=.01&&result<=10000?result:null;
  }
  function normalize(item, kind) {
    const name=clean(item.hostname ?? item.name ?? item.HostName ?? item.DeviceName,
      "Dispositivo sem nome",48);
    const mac=clean(item.mac ?? item.MACAddr ?? item.MAC ?? item.mac_address,"Não informado",48);
    const ip=clean(item.ip ?? item.IPAddr ?? item.IP ?? item.ip_address,"Não informado",48);
    return {
      name,mac,ip,kind,ssid:clean(item.ssid ?? item.SSID,"Não informado",48),
      rssi:rssiValue(item.rssi ?? item.RSSI ?? item.signal),
      snr:clean(item.snr ?? item.SNR,"Não informado",32),
      rx:clean(item.rx_rate ?? item.RxRate,"Não informado",32),
      tx:clean(item.tx_rate ?? item.TxRate,"Não informado",32),
      type:clientType(name)
    };
  }
  function node(tag,cls,value){
    const el=document.createElement(tag);
    if(cls)el.className=cls;
    if(value!==undefined)el.textContent=value;
    return el;
  }
  function svg(tag,attrs={},value){
    const el=document.createElementNS(NS,tag);
    for(const [key,val] of Object.entries(attrs))el.setAttribute(key,String(val));
    if(value!==undefined)el.textContent=value;
    return el;
  }
  function currentCalibration(){
    const a=String(document.getElementById("topologyRssiOneMeter")?.value||"").trim().replace(",",".");
    const b=String(document.getElementById("topologyPathLoss")?.value||"").trim().replace(",",".");
    if(!a||!b)return null;
    const rssi=Number(a),exponent=Number(b);
    if(rssi < -110||rssi > -10||exponent < 1.6||exponent > 6 ||
       !Number.isFinite(rssi)||!Number.isFinite(exponent))return null;
    return {rssi,exponent};
  }
  function details(device){
    const panel=document.getElementById("topologyDetails");
    if(!panel)return;
    panel.replaceChildren();
    panel.appendChild(node("span","am-topology-eyebrow","DISPOSITIVO SELECIONADO"));
    panel.appendChild(node("h3","",device.name));
    const fields=[
      ["Conexão",device.kind==="wifi"?"Wi-Fi":"Ethernet"],
      ["IP informado",device.ip],
      ["MAC informado",device.mac],
      ["Tipo",device.type]
    ];
    if(device.kind==="wifi"){
      const key=device.key;
      const list=samples.get(key)||[];
      const mean=list.length?list.reduce((acc,v)=>acc+v,0)/list.length:device.rssi;
      fields.push(["Rede",device.ssid]);
      fields.push(["RSSI",mean===null?"Não fornecido pela ONT":
        mean.toFixed(1)+" dBm"+(list.length>1?" (média de "+list.length+" leituras)":"")]);
      fields.push(["SNR",device.snr]);
      fields.push(["Recepção",device.rx],["Transmissão",device.tx]);
      const calibration=currentCalibration();
      const distance=calibration?estimateDistance(mean,calibration.rssi,calibration.exponent):null;
      fields.push(["Distância",
        distance===null?"Indeterminada sem calibração e RSSI confiável":
          "≈ "+(distance<10?distance.toFixed(1):distance.toFixed(0))+
          " m — estimativa experimental"]);
    }else fields.push(["RSSI / Distância","Não se aplica à conexão cabeada"]);
    const dl=node("dl","am-topology-details-grid");
    fields.forEach(([label,value])=>{
      const row=node("div","am-topology-detail");
      row.append(node("dt","",label),node("dd","",clean(value)));
      dl.appendChild(row);
    });
    panel.appendChild(dl);
    panel.appendChild(node("p","am-topology-hint",
      "O tipo é sugerido somente quando o nome identifica o aparelho. "+
      "A distância por RSSI não é uma medição: paredes, potência, orientação e interferência alteram o resultado."));
  }
  function withIdentity(item,kind,index){
    const device=normalize(item,kind);
    // Repeated or unknown addresses must never merge measurements from
    // different clients. Index is a fallback only when identity is absent.
    const anonymous=device.mac==="Não informado"&&device.ip==="Não informado";
    device.key=kind+":"+device.mac+":"+device.ip+(anonymous?":"+index:"");
    return device;
  }
  function readDevices(wifi,lan){
    const w=Array.isArray(wifi)?wifi.filter(v=>v&&typeof v==="object").map((v,i)=>withIdentity(v,"wifi",i)):[];
    const l=Array.isArray(lan)?lan.filter(v=>v&&typeof v==="object").map((v,i)=>withIdentity(v,"lan",i)):[];
    // No mixing snapshots from different equipment; no localStorage.
    const host=clean(document.getElementById("connectedHost")?.textContent||"","",100);
    if(currentHost!==host){currentHost=host;samples.clear();selectedKey=null;}
    for(const device of w){
      if(device.rssi===null)continue;
      const key=device.key;
      const previous=samples.get(key)||[];
      previous.push(device.rssi);
      samples.set(key,previous.slice(-5));
    }
    current={wifi:w,lan:l};
    return current;
  }
  function render(wifi,lan){
    const section=document.getElementById("topologySection");
    const graph=document.getElementById("topologyGraph");
    const count=document.getElementById("topologyDeviceCount");
    if(!section||!graph)return;
    const data=readDevices(wifi,lan);
    if(count)count.textContent=(data.wifi.length+data.lan.length)+" clientes da leitura atual";
    graph.replaceChildren();
    const w=data.wifi.slice(0,MAX_PER_GROUP);
    const l=data.lan.slice(0,MAX_PER_GROUP);
    const total=data.wifi.length+data.lan.length;
    if(total===0){
      graph.appendChild(node("p","am-topology-empty",
        "Nenhum cliente confirmado nesta leitura. Atualize os clientes para tentar novamente."));
      const detail=document.getElementById("topologyDetails");
      if(detail)detail.textContent="Selecione um dispositivo quando houver clientes identificados.";
      return;
    }
    const rows=Math.max(Math.ceil(w.length/2),Math.ceil(l.length/2),1);
    const height=300+rows*99;
    const picture=svg("svg",{viewBox:"0 0 1000 "+height,
      role:"group","aria-label":"Grafo dos clientes informados pelo equipamento"});
    picture.classList.add("am-topology-svg");
    picture.appendChild(svg("title",{},"Relações lógicas entre a ONT e os clientes Wi-Fi e Ethernet"));
    const rootX=500,rootY=55,hubY=172;
    const shape= (x,y,cls,label,secondary,icon) => {
      const g=svg("g",{class:"am-topology-node "+cls});
      g.appendChild(svg("rect",{x:x-94,y:y-35,width:188,height:70,rx:15}));
      g.appendChild(svg("circle",{cx:x-70,cy:y,r:16,class:"am-topology-icon"}));
      g.appendChild(svg("text",{x:x-70,y:y+5,"text-anchor":"middle",class:"am-topology-symbol"},icon));
      g.appendChild(svg("text",{x:x-44,y:y-4,class:"am-topology-name"},
        label.length>19?label.slice(0,17)+"…":label));
      g.appendChild(svg("text",{x:x-44,y:y+15,class:"am-topology-sub"},
        secondary.length>23?secondary.slice(0,21)+"…":secondary));
      g.appendChild(svg("title",{},label+" — "+secondary));
      return g;
    };
    for(const x of [250,750]){
      picture.appendChild(svg("path",{d:"M 500 90 V 120 H "+x+" V 135",
        class:"am-topology-line"}));
    }
    const model=clean(document.getElementById("connectedModel")?.textContent,"ONT conectada",30);
    picture.appendChild(shape(rootX,rootY,"am-topology-router",model,"Equipamento consultado","◆"));
    picture.appendChild(shape(250,hubY,"am-topology-hub","Wi-Fi",
      data.wifi.length+" clientes","◉"));
    picture.appendChild(shape(750,hubY,"am-topology-hub","Ethernet",
      data.lan.length+" clientes","▤"));
    const all=[];
    function group(items,kind,xs,hubX){
      items.forEach((device,index)=>{
        const x=xs[index%2],y=289+Math.floor(index/2)*99;
        picture.appendChild(svg("path",{d:"M "+hubX+" "+(hubY+35)+" V "+
          (y-54)+" H "+x+" V "+(y-35),class:"am-topology-line"}));
        const key=device.key;
        const chip=shape(x,y,"am-topology-client"+(selectedKey===key?" is-selected":""),
          device.name,device.ip==="Não informado"?"Endereço não informado":device.ip,
          kind==="wifi"?"◉":"▣");
        chip.setAttribute("role","button");
        chip.setAttribute("tabindex","0");
        chip.setAttribute("aria-label","Abrir detalhes: "+device.name);
        chip.setAttribute("aria-pressed",String(selectedKey===key));
        const choose=()=>{
          selectedKey=key;
          picture.querySelectorAll(".am-topology-client").forEach(el=>{
            el.classList.remove("is-selected");
            el.setAttribute("aria-pressed","false");
          });
          chip.classList.add("is-selected");
          chip.setAttribute("aria-pressed","true");
          details(device);
        };
        chip.addEventListener("click",choose);
        chip.addEventListener("keydown",event=>{
          if(event.key==="Enter"||event.key===" "){event.preventDefault();choose();}
        });
        all.push({key,device,choose});
        picture.appendChild(chip);
      });
    }
    group(w,"wifi",[120,380],250);
    group(l,"lan",[620,880],750);
    graph.appendChild(picture);
    const truncated=Math.max(0,total-w.length-l.length);
    if(truncated)graph.appendChild(node("p","am-topology-hint",
      "Exibindo os primeiros "+(w.length+l.length)+
      " clientes. A lista abaixo contém todos os registros recebidos."));
    const selected=all.find(entry=>entry.key===selectedKey);
    if(selected)selected.choose();
    else{
      const panel=document.getElementById("topologyDetails");
      if(panel)panel.textContent="Clique em um dispositivo no grafo para consultar IP, MAC, sinal e informações disponíveis.";
    }
  }
  function reset(){
    samples.clear();currentHost="";selectedKey=null;current={wifi:[],lan:[]};
    const graph=document.getElementById("topologyGraph");
    const panel=document.getElementById("topologyDetails");
    if(graph)graph.textContent="Aguardando leitura dos clientes conectados...";
    if(panel)panel.textContent="Selecione um dispositivo após carregar os clientes.";
    const count=document.getElementById("topologyDeviceCount");
    if(count)count.textContent="Nenhuma leitura";
  }
  function init(){
    document.addEventListener("am:clients-updated",event=>
      render(event.detail?.wifi,event.detail?.lan));
    document.addEventListener("zte:session-changed",reset);
    for(const id of ["topologyRssiOneMeter","topologyPathLoss"]){
      document.getElementById(id)?.addEventListener("input",()=>{
        const currentDevice=[...current.wifi,...current.lan].find(d=>
          d.key===selectedKey);
        if(currentDevice)details(currentDevice);
      });
    }
  }
  if(document.readyState==="loading")document.addEventListener("DOMContentLoaded",init,{once:true});
  else init();
  if(typeof window!=="undefined")window.AccessManagerTopology=
    Object.freeze({render,reset,clientType,rssiValue,estimateDistance});
})();

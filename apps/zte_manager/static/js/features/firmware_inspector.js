/* Operator-facing firmware inspection.
 * Runtime capability reads never become raw JSON, paths or driver structures.
 * Existing editors are reused; Huawei mapped writes receive generated forms
 * from backend schemas without exposing endpoint names or protocol internals.
 */
(() => {
  "use strict";
  const LABELS=Object.freeze({
    wifi_advanced:"Configurações avançadas de Wi-Fi",
    wifi_neighbor_scan:"Redes Wi-Fi próximas",
    wifi_interference_schedule:"Gerenciamento de interferência",
    native_speedtest:"Teste de velocidade do equipamento",
    dns_lookup:"Consulta de DNS",
    wifi_schedule:"Agendamento do Wi-Fi",
    band_steering:"Direcionamento entre bandas",
    dhcp_basic:"Servidor DHCP",
    dhcp_leases:"Endereços atribuídos",
    dhcp_reservations:"Reservas de IP",
    port_forwarding:"Redirecionamento de portas",
    dmz:"Zona desmilitarizada (DMZ)",
    upnp_port_map:"Mapeamentos automáticos de portas",
    service_control_ipv4:"Serviços de rede IPv4",
    service_control_ipv6:"Serviços de rede IPv6",
    firewall:"Proteção da rede",
    firewall_filters:"Políticas de filtragem",
    ip_filter:"Regras de bloqueio por IP",
    mac_filter:"Regras de bloqueio por dispositivo",
    parental_control:"Controle parental",
    ddns:"Endereço dinâmico (DDNS)",
    sntp:"Sincronização de horário",
    tr069:"Gerenciamento remoto TR-069",
    route_table:"Rotas de rede",
    qos_queue:"Priorização de tráfego",
    qos_speed:"Controle de velocidade",
    qos_shaper:"Limites de banda",
    syslog:"Registros do equipamento",
    firmware_management:"Versão e atualização",
    restore_config:"Restauração de configuração",
    factory_reset:"Redefinição de fábrica",
    backup_config:"Cópia de segurança",
    wifi_clients:"Clientes conectados ao Wi-Fi",
    lan_clients:"Clientes conectados por cabo",
    wan:"Conexão de Internet",
    device_info:"Informações do equipamento",
    pon_optical:"Sinal óptico",
    wifi_ssids:"Redes Wi-Fi configuradas",
    wifi_radios:"Rádios Wi-Fi",
    wifi_radio_advanced:"Configuração avançada dos rádios",
    lan_ports:"Portas de rede",
    wps:"Conexão simplificada WPS",
    mesh:"Rede Mesh",
    dns:"Resolução de nomes DNS",
    dhcp:"Servidor DHCP",
    arp:"Dispositivos identificados na rede",
    voip_status:"Telefonia",
    tr069_status:"Gerenciamento remoto",
    upnp:"Abertura automática de portas",
    ping_history:"Histórico de conectividade",
    traceroute_history:"Histórico de rotas",
    ipv4_filter:"Filtragem IPv4",
    optical:"Sinal óptico",
    layer3:"Portas LAN em camada 3",
    lan_ipv4:"Endereçamento IPv4 da LAN",
    ipv6_lan:"Endereçamento IPv6 da LAN",
    dhcp_static:"Reservas DHCP",
    dns_host:"Hosts DNS locais",
    wifi_basic:"Redes Wi-Fi",
    wifi_radio:"Rádios Wi-Fi",
    tr069_url:"Servidor de gerenciamento TR-069",
    firewall_level:"Nível do firewall",
    alg:"Gateways de aplicação (ALG)",
    igmp:"Multicast / IGMP",
    dos:"Proteção contra ataques",
    ipv6_firewall:"Firewall IPv6",
    internet_control:"Controle de acesso à Internet",
    wifi_cover:"Cobertura Wi-Fi",
    easymesh_topology:"Topologia EasyMesh",
    ethernet_info:"Interfaces Ethernet",
    ont_auth:"Autenticação da ONT",
    port_isolation:"Isolamento de portas",
    ipv6_filter:"Filtragem IPv6",
    ipv6_port_mapping:"Redirecionamento de portas IPv6",
    ipv6_default_route:"Rota padrão IPv6",
    ipv6_static_route:"Rotas estáticas IPv6",
    routing:"Rotas de rede",
    port_mapping:"Redirecionamento e gatilho de portas",
    lan_service:"Serviços da LAN",
    arp_ping:"Diagnóstico ARP/Ping",
    firewall_log:"Eventos do firewall",
    wan_config:"Configuração da Internet",
    user_devices:"Inventário de dispositivos",
    vlan:"Configuração VLAN",
    qos_smart:"Priorização inteligente de tráfego",
    dscp_to_pbit:"Mapeamento DSCP para P-bit",
    remote_packet_mirror:"Espelhamento remoto de pacotes",
    reboot:"Reinicialização do equipamento",
    firmware:"Atualização de firmware",
    config_backup:"Arquivo de configuração",
    security_check:"Verificação de segurança",
    led:"Indicadores luminosos",
    collect:"Coleta de suporte",
    speed_test:"Teste de velocidade da ONT",
    diagnostics_webui:"Diagnóstico interno da ONT",
    support_config:"Configuração de suporte e manutenção",
    software_notice:"Avisos de software",
    account:"Conta administrativa",
    logs:"Registros do equipamento",
    mirror_port:"Espelhamento de porta",
    voip_interface:"Interface de telefonia"
  });
  const DESCRIPTIONS=Object.freeze({
    tr069:"Consulte a ativação dos informes periódicos e o intervalo de comunicação. Endereços e credenciais permanecem ocultos.",
    firewall:"Visualize o estado de proteção. Alterações utilizam o formulário separado e dependem das permissões da sessão.",
    service_control_ipv4:"Identifica os serviços IPv4 apresentados pelo equipamento. Alterações nesses serviços podem interromper o gerenciamento.",
    service_control_ipv6:"Identifica os serviços IPv6 apresentados pelo equipamento. Alterações nesses serviços podem interromper o gerenciamento.",
    wifi_neighbor_scan:"Lista as redes vizinhas somente quando o equipamento oferece uma leitura confirmada.",
    syslog:"Apenas a disponibilidade da consulta é mostrada. Conteúdos técnicos devem permanecer nos registros internos.",
    firmware_management:"Identificação em modo de consulta. A atualização requer o procedimento validado para o modelo.",
    restore_config:"Identificação em modo de consulta. Uma restauração não é executada automaticamente.",
    factory_reset:"Identificação em modo de consulta. A redefinição não pode ser feita por um botão genérico."
  });
  // Tool destinations are existing real editors; this map does not claim
  // that a read-only firmware endpoint accepts write operations.
  const EDITORS=Object.freeze({
    wifi_advanced:["wifi","wifiRadios"],
    wifi_ssids:["wifi","wifiNetworks"],
    wifi_radios:["wifi","wifiRadios"],
    wifi_radio_advanced:["wifi","wifiRadios"],
    dns:["profiles","profileDns4_1"],
    wifi_schedule:["wifi","wifiScheduleControl"],
    band_steering:["wifi","bandSteeringControl"],
    dhcp_basic:["advanced","dhcp","dhcpBasicForm"],
    dhcp_reservations:["advanced","dhcp","dhcpReservationForm"],
    port_forwarding:["advanced","nat","portForwardForm"],
    dmz:["advanced","nat","dmzForm"],
    upnp_port_map:["wan","upnpDetails"],
    firewall:["management","network","managementFirewallSave"],
    firewall_filters:["management","network","managementFirewallGlobalSave"],
    ip_filter:["management","network","managementFirewallRuleSave","ip"],
    mac_filter:["management","network","managementFirewallRuleSave","mac"],
    sntp:["management","network","managementSntpSave"],
    tr069:["management","network","managementTr069Save"],
    qos_queue:["management","network","managementQosSave","queue"],
    qos_speed:["management","network","managementQosSave","policer"],
    qos_shaper:["management","network","managementQosSave","shaper"],
    backup_config:["advanced","inspector","backupConfigurationButton"],
    diagnostics_webui:["diagnostics","pingHost"],
    arp_ping:["diagnostics","pingHost"]
  });
  const SAFE_FIELDS=Object.freeze({
    enable:"Ativo",enabled:"Ativo",serverenable:"Servidor ativo",
    periodicinformenable:"Informes periódicos",
    periodicinformenabled:"Informes periódicos",
    periodicinforminterval:"Intervalo de comunicação",
    autodns:"DNS automático",dnsmode:"Modo DNS",
    ssid:"Nome da rede",ssidname:"Nome da rede",
    wlanname:"Nome da rede",channel:"Canal",autochannel:"Canal automático",
    bandwidth:"Largura do canal",wanmode:"Tipo da conexão",
    security:"Segurança",encryption:"Proteção",
    ipv4address:"Endereço IPv4",ipaddress:"Endereço IP",
    minaddress:"Início da faixa",maxaddress:"Fim da faixa",
    leasetime:"Tempo de concessão",txpower:"Potência de transmissão",
    level:"Nível de proteção",firewallenable:"Firewall ativo"
  });
  const DENY=/(?:password|passphrase|passwd|token|secret|private|credential|url|uri|acs|username|userid|user|cookie|authentication|auth|key|cert|serial|mac|endpoint|view|tag|https?:\/\/|thinklua|[<>])/i;
  function label(feature,fallback){
    if(Object.prototype.hasOwnProperty.call(LABELS,feature))return LABELS[feature];
    if(typeof fallback==="string" && /^[\p{L}\p{N} /+().-]{2,70}$/u.test(fallback) &&
       !DENY.test(fallback) && !/_/.test(fallback))return fallback;
    return "Funcionalidade do equipamento";
  }
  function safeScalar(value){
    if(value===null||value===undefined)return null;
    if(typeof value==="boolean")return value?"Sim":"Não";
    if(typeof value==="number")return Number.isFinite(value)?String(value):null;
    if(typeof value!=="string")return null;
    const s=value.trim();
    if(!s||s.length>72||DENY.test(s)||/[{}\[\]\n\r]/.test(s)||
       /^[A-Za-z0-9+/]{40,}={0,2}$/.test(s))return null;
    if(/^(true|1|enabled|on)$/i.test(s))return "Sim";
    if(/^(false|0|disabled|off)$/i.test(s))return "Não";
    return s;
  }
  function summary(data){
    if(!data||typeof data!=="object"||!data.objects||typeof data.objects!=="object")
      return [];
    const output=[],unique=new Set();
    for(const entries of Object.values(data.objects)){
      const records=Array.isArray(entries)?entries.slice(0,3):
        (entries&&typeof entries==="object"?[entries]:[]);
      for(const record of records){
        if(!record||typeof record!=="object")continue;
        for(const [key,value] of Object.entries(record)){
          const normalized=key.toLowerCase().replace(/[^a-z0-9]/g,"");
          if(DENY.test(key)||!Object.prototype.hasOwnProperty.call(SAFE_FIELDS,normalized))
            continue;
          let v=safeScalar(value);
          if(v===null)continue;
          const name=SAFE_FIELDS[normalized];
          if(/^(ativo|servidor ativo|informes periódicos|firewall ativo|canal automático)$/i.test(name)&&
             /^(?:0|1|on|off|true|false|enabled|disabled)$/i.test(String(value).trim())){
            v=/^(1|true|on|enabled)$/i.test(String(value).trim())?"Sim":"Não";
          }
          const identity=name+":"+v;
          if(unique.has(identity))continue;
          unique.add(identity);
          output.push({name,value:v});
          if(output.length>=12)return output;
        }
      }
    }
    return output;
  }
  const el=(tag,cls,value)=>{
    const item=document.createElement(tag);
    if(cls)item.className=cls;
    if(value!==undefined)item.textContent=value;
    return item;
  };
  function goToEditor(feature){
    const config=EDITORS[feature];
    if(!config||typeof openPage!=="function")return false;
    const [page,panel,target,choice]=config;
    openPage(page);
    if(page==="advanced"&&panel){
      document.getElementById("page-advanced")?.dispatchEvent(
        new CustomEvent("am:show-panel",{detail:{panel}}));
    }
    if(page==="management"&&panel&&typeof switchManagementTab==="function")
      switchManagementTab(panel);
    if(choice&&feature.startsWith("qos")){
      const kind=document.getElementById("managementQosKind");
      if(kind)kind.value=choice;
    }
    if(choice&&(feature==="ip_filter"||feature==="mac_filter")){
      const kind=document.getElementById("managementFirewallRuleKind");
      if(kind)kind.value=choice;
    }
    const field=document.getElementById(target||panel);
    field?.scrollIntoView?.({behavior:"smooth",block:"center"});
    if(field?.matches?.("button,input,select"))field.focus();
    return true;
  }
  function mappedWriteEditor(feature,data,card,confirmed,writeActive){
    const schema=data?.mapped_write;
    const operations=Array.isArray(schema?.operations)?schema.operations:[];
    if(!schema?.available||!operations.length)return false;
    const section=el("section","am-inspector-actions am-mapped-write");
    section.appendChild(el("h4","","Configuração"));
    if(!writeActive){
      section.appendChild(el("small","",
        "A sessão está em modo somente leitura. As informações continuam disponíveis."));
      card.appendChild(section);
      return true;
    }
    const operationSelect=document.createElement("select");
    operationSelect.className="am-mapped-write-operation";
    operationSelect.setAttribute("aria-label","Operação de configuração");
    for(const operation of operations){
      const option=document.createElement("option");
      option.value=operation.key;
      option.textContent=operation.label||"Aplicar configuração";
      operationSelect.appendChild(option);
    }
    if(operations.length>1){
      const field=document.createElement("label");
      field.className="field";
      field.append(el("span","","OPERAÇÃO"),operationSelect);
      section.appendChild(field);
    }
    const fieldsRoot=el("div","operations-form-grid with-top-space");
    const renderFields=()=>{
      fieldsRoot.replaceChildren();
      const operation=operations.find(item=>item.key===operationSelect.value)||operations[0];
      for(const spec of operation?.fields||[]){
        const field=document.createElement("label");
        field.className="field";
        field.appendChild(el("span","",spec.label||"Valor"));
        const input=document.createElement("input");
        input.type=spec.secret?"password":"text";
        input.autocomplete="off";
        input.value=spec.default??"";
        input.dataset.mappedField=spec.key;
        field.appendChild(input);
        fieldsRoot.appendChild(field);
      }
      if(!(operation?.fields||[]).length){
        fieldsRoot.appendChild(el("p","am-inspector-quiet",
          "Esta operação não exige parâmetros adicionais."));
      }
    };
    operationSelect.addEventListener("change",renderFields);
    renderFields();
    section.appendChild(fieldsRoot);
    const status=el("p","am-inspector-quiet","");
    const apply=el("button","button primary","Aplicar");
    apply.type="button";
    apply.disabled=!confirmed;
    apply.addEventListener("click",async()=>{
      const operation=operations.find(item=>item.key===operationSelect.value)||operations[0];
      const config={};
      for(const input of fieldsRoot.querySelectorAll("[data-mapped-field]")){
        config[input.dataset.mappedField]=input.value;
      }
      apply.disabled=true;
      apply.setAttribute("aria-busy","true");
      status.textContent="Aplicando configuração...";
      try{
        const result=await apiRequest("/huawei/mapped/write",{
          method:"POST",
          body:JSON.stringify({operation:operation.key,config}),
          timeoutMs:70000
        });
        if(result?.error)throw new Error(result.error);
        status.textContent=result?.verified?
          "Alteração aplicada e relida na ONT.":
          result?.uncertain?
            "A ONT não confirmou o resultado. Consulte novamente antes de repetir.":
            "Alteração enviada à ONT.";
        if(typeof showToast==="function")showToast(status.textContent);
      }catch(error){
        status.textContent="Não foi possível aplicar: "+
          (typeof normalizeApiErrorMessage==="function"?
            normalizeApiErrorMessage(error):String(error?.message||error));
      }finally{
        apply.disabled=false;
        apply.removeAttribute("aria-busy");
      }
    });
    section.append(apply,status);
    card.appendChild(section);
    return true;
  }

  function render(feature,data,root){
    if(!root)return;
    root.replaceChildren();
    const name=label(feature,data?.label);
    const confirmed=data?.available===true;
    const writeActive=typeof routerWriteEnabled==="boolean"&&routerWriteEnabled===true;
    const editor=Object.prototype.hasOwnProperty.call(EDITORS,feature);
    const mappedEditor=Boolean(data?.mapped_write?.available);
    const card=el("article","am-inspector-card");
    const header=el("div","am-inspector-header");
    const kicker=el("span","am-inspector-kicker","CONSULTA DO EQUIPAMENTO");
    const title=el("h3","",name);
    const status=el("span","am-inspector-status"+(confirmed?" is-confirmed":""),
      confirmed?"Leitura confirmada":"Leitura ainda não confirmada");
    const heading=el("div","am-inspector-heading");
    heading.append(kicker,title);
    header.append(heading,status);
    card.append(header);
    card.appendChild(el("p","am-inspector-description",
      DESCRIPTIONS[feature]||"A consulta informa se esta funcionalidade está presente na sessão atual. Nenhuma alteração é executada pela inspeção."));
    const mode=el("div","am-inspector-mode");
    mode.appendChild(el("strong","", "Modo de operação"));
    const modeLabel=(!confirmed)
      ?"Pendente de confirmação nesta sessão"
      :(editor||mappedEditor)&&writeActive
        ?"Leitura confirmada • Formulário de configuração disponível"
      :data?.writable?"Leitura confirmada • Configuração disponível no provider"
      :"Leitura confirmada • Consulta somente leitura";
    mode.appendChild(el("span","",modeLabel));
    card.appendChild(mode);
    const fields=confirmed&&feature!=="syslog"?summary(data):[];
    if(fields.length){
      const section=el("section","am-inspector-fields");
      section.appendChild(el("h4","","Informações operacionais"));
      const dl=el("dl","am-inspector-fields-grid");
      for(const {name:caption,value} of fields){
        const cell=el("div","am-inspector-field");
        cell.append(el("dt","",caption),el("dd","",value));
        dl.appendChild(cell);
      }
      section.appendChild(dl);card.appendChild(section);
    }else{
      card.appendChild(el("p","am-inspector-quiet",confirmed?
        "Consulta confirmada. Não há outros dados operacionais seguros para exibir nesta visão.":
        "Não foi possível confirmar o recurso. Revise a conexão e execute a leitura novamente."));
    }
    if(editor){
      const actions=el("div","am-inspector-actions");
      if(writeActive){
        const button=el("button","button primary","Abrir configuração");
        button.type="button";
        button.disabled=!confirmed;
        button.addEventListener("click",()=>goToEditor(feature));
        actions.appendChild(button);
        actions.appendChild(el("small","",
          "A edição é realizada no formulário existente do Access Manager."));
      }else actions.appendChild(el("small","",
        "O formulário existe, mas a sessão atual está em modo somente leitura."));
      card.appendChild(actions);
    }else if(mappedEditor){
      mappedWriteEditor(feature,data,card,confirmed,writeActive);
    }else if(data?.writable){
      card.appendChild(el("p","am-inspector-warning",
        "A capability aceita escrita pelo provider Huawei. Use a ação específica da funcionalidade quando disponível."));
    }else if(data?.dangerous){
      card.appendChild(el("p","am-inspector-warning",
        "Recurso sensível: o equipamento permanece protegido contra gravações não homologadas."));
    }
    root.appendChild(card);
  }
  function renderMap(report,root){
    if(!root)return;
    root.replaceChildren();
    const records=new Map();
    const insert=(entry)=>{
      if(!entry||typeof entry!=="object"||typeof entry.feature!=="string")return;
      const name=entry.feature;
      const state=entry.available===true||entry.status==="detected"?"confirmed":
        entry.status==="not_tested"?"untested":"unconfirmed";
      const before=records.get(name);
      if(!before||state==="confirmed"||
        (state==="unconfirmed"&&before.state==="untested"))
        records.set(name,{name:label(name,entry.label),feature:name,state});
    };
    for(const item of report?.tracker?.capabilities||[])insert(item);
    for(const item of report?.tracker?.candidate_features||[])insert(item);
    for(const item of report?.features||[])insert(item);
    const values=[...records.values()].sort((a,b)=>a.name.localeCompare(b.name,"pt-BR"));
    const counts={confirmed:0,unconfirmed:0,untested:0};
    values.forEach(item=>counts[item.state]++);
    root.appendChild(el("h4","am-inspector-map-heading",
      "Funcionalidades reconhecidas pela sessão"));
    root.appendChild(el("p","am-inspector-map-summary",
      counts.confirmed+" confirmadas · "+counts.unconfirmed+
      " sem confirmação · "+counts.untested+" ainda não testadas"));
    const list=el("ul","am-inspector-map-list");
    for(const item of values){
      const row=el("li","am-inspector-map-item");
      row.appendChild(el("strong","",item.name));
      row.appendChild(el("span","am-inspector-map-state "+item.state,
        item.state==="confirmed"?"Leitura confirmada":
        item.state==="untested"?"Não testado":"Não confirmado"));
      row.appendChild(el("small","",
        Object.prototype.hasOwnProperty.call(EDITORS,item.feature)?
        "Possui formulário separado, sujeito à autorização da sessão":
        "Consulta neste aplicativo"));
      list.appendChild(row);
    }
    if(!values.length)list.appendChild(el("li","am-inspector-quiet",
      "Ainda não há recursos identificados para apresentar."));
    root.appendChild(list);
  }
  if(typeof window!=="undefined")window.AccessManagerInspector=
    Object.freeze({render,label,summary,safeScalar,goToEditor,renderMap});
})();
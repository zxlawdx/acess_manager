# F6201B V9.3.10P7N7 — Laboratório de formulários capturados

Este documento registra o resultado **verificável em código e testes sintéticos**
da nova camada de comandos e não confunde HTTP 200, um Apply capturado e
homologação física. Branch original: main após PRs #34–#38. A nova camada não
substitui os adaptadores nem a interface legada do F6600P/F670L.

A captura original do proprietário continha **209 eventos HTTP** (179 GET,
30 POST, dos quais 28 Apply entre **25 endpoints distintos** e dois comandos
de diagnóstico). O JSON contém credenciais, senhas, tokens e informações
de provisionamento; **não deve ser versionado, anexado aos logs nem
redistribuído**. O catálogo de código usa somente nomes e ordem de campos.

## Inventário: 25 rotas distintas de Apply

- **Laboratório supervisionado**: implementado neste PR. GET do objeto XML,
  instância explícita, formulário dinâmico, read-modify-write conforme captura,
  nonce e autorização, um POST, releitura. Ainda não homologado fisicamente.
- **Adaptador existente**: código anterior de SSID/DNS/RF com suas próprias
  condições de prévia e confirmação, sem promessa de homologação física.
- **Aguardando formulário**: GET catalogado, mas um POST genérico poderia
  alterar campos condicionais ou credenciais que não podem ser preservados
  com confiança. Não expõe botão de escrita.

| # | Tag menuData | Situação | O que ainda exige validação |
|---|---|---|---|
| 01 | wlan_wlansssidconf_lua.lua | Adaptador existente | Homologar senha, SSID, isolamento, criptografia e múltiplos encode em ONT |
| 02 | dns_localdns_lua.lua | Adaptador existente | Testar separadamente servidores IPv4/IPv6 e formulário de domínio |
| 03 | wlan_BandSteering_lua.lua | Laboratório supervisionado | Band Steering, RSSI, transição Mesh e releitura física |
| 04 | wlan_wps_lua.lua | Aguardando formulário | Preservar SSID_InstID e WPSChoose do HTML atual |
| 05 | wlan_wlanbasicadconf_lua.lua | Adaptador existente | Respostas XML integrais de RF e aplicação física por banda |
| 06 | wan_internet_lua.lua | Aguardando formulário | Branches PPPoE/IP/VLAN/IPv6, senha codificada e instância WAN |
| 07 | upnp_upnp_lua.lua | Laboratório supervisionado | Testar política de acesso e propagação UPnP |
| 08 | firewall_config_lua.lua | Laboratório supervisionado | Efeitos de política firewall e recuperação de acesso |
| 09 | dns_hostname_lua.lua | Adaptador existente | Upsert de host; duplicações e preservação das entradas |
| 10 | bpdu_lua.lua | Laboratório supervisionado | Estado BPDU e interação com bridges |
| 11 | route_routedefault_lua.lua | Laboratório supervisionado | Verificar índice de interface e acesso via WAN/LAN |
| 12 | route_routestaticipv4_lua.lua | Aguardando formulário | Campo Type não exposto no GET; Add/Edit distintos |
| 13 | Localnet_LanMgrIpv4_DHCPBasicCfg_lua.lua | Aguardando formulário | Múltiplos objetos DHCP e campo codificado; proteger IP LAN |
| 14 | Localnet_LanDevDHCPSource_lua.lua | Aguardando formulário | Vetor completo de 12 posições ProcFlag e InstID |
| 15 | addr6_lanaddr_lua.lua | Laboratório supervisionado | Configuração IPv6 LAN e possível perda de acesso |
| 16 | dhcp6s_dhcpserver_lua.lua | Aguardando formulário | Combinar objetos DHCPv6 e DNS e botões condicionais |
| 17 | ra_raservice_lua.lua | Aguardando formulário | S_AdvLinkMTU e regras de prefixo/atualização |
| 18 | radhcp6s_portctrl_lua.lua | Aguardando formulário | Vetor de portas completo e seleção de instância |
| 19 | eth_interface_config_lua.lua | Aguardando formulário | ModType ausente no GET fornecido |
| 20 | wlan_wlanbasiconoff_lua.lua | Aguardando formulário | Dois rádios, timer e instâncias dependentes |
| 21 | wlan_macfilteraclpolicy_lua.lua | Aguardando formulário | Vetor por SSID e instâncias ACL de múltiplas bandas |
| 22 | Localnet_NetSphere_Mode_lua.lua | Aguardando formulário | CurrentMode, CurrentEnable e confirmação Mesh |
| 23 | tr069_remotemgr_lua.lua | Aguardando formulário | Criptografia de duas credenciais, certificados e ACS |
| 24 | firewall_alg_lua.lua | Laboratório supervisionado | Testar ALG/VoIP sem romper serviços |
| 25 | firewall_dmz_lua.lua | Aguardando formulário | Campos MAC temporários não preserváveis no GET |

**Totais:** 7 rotas novas com ciclo supervisionado implementado; 4 com
adaptadores já existentes; 14 com catalogação e lacunas documentadas,
sem implementação de escrita. Não foram fabricados formulários nem
POSTs para completar artificialmente a contagem de 25.

## Fluxo e responsabilidades

- **Strategy / catálogo:** services/f6201b_workbench.py define objetos XML
  de consulta, campos editáveis exatos, risco operacional e razões para
  desabilitar fluxos incompletos. f6201b_evidence.py conserva a ordem
  capturada do body, sem valores sensíveis.
- **Command:** CapturedFormWorkbench guarda uma única prévia por sessão
  e a consome em toda tentativa. O Apply aceita somente nonce,
  confirmação e reconhecimento do risco; ignora payload enviado pelo cliente.
- **Facade e injeção simples:** ZTEService injeta o cliente HTTP
  autenticado e seus identificadores de host/revisão no Command. O RLock
  original serializa o fluxo; a conexão/disconexão limpa a prévia.
- **Segurança:** firmware e modelo são revalidados antes do GET/POST;
  ZTE_F6201B_EXPERIMENTAL_WRITES=1 é obrigatório. O transporte
  permanece bloqueado fora do escopo de um POST autorizado. A
  menuView é reaberta antes de cada POST para obter novo token e
  cabeçalho Check; não há fallback sem assinatura.
- **Verificação:** um GET fresco compara o snapshot antes de escrever;
  releitura após escrita verifica os campos alterados. Resultado
  ambíguo **não é repetido** automaticamente; não existe rollback
  prometido para WAN/LAN/Wi-Fi.
- **Interface:** nova seção na aba **Avançado** apenas para
  F6201B identificado no firmware conhecido. Mostra inventário
  técnico de 25 linhas, formulários somente nas 7 estratégias,
  instâncias, prévias, progresso e estados de erro. CSS usa os tokens
  BRModelo, com navegação/lista compacta, inspiração no workspace
  DockerFlow, sem alterar os componentes dos demais modelos.

## Como testar

Testes automatizados tests/test_f6201b_workbench.py usam fake GET,
mock do post_menu, valores sintéticos, nenhum roteador físico.
Cobrem contagem 25, exclusão de rotas não homologadas, ordenação,
preservação de campos, confirmação de risco, TTL, nonce único,
concorrência de estado, bloqueio de permissões e restauração do
transporte após erro. Os testes não comprovam que o firmware aceita
todos os Apply em rede real.

Para testes físicos, usar **ONT própria/autorizada isolada** e conexão
Ethernet local com acesso de recuperação. Fazer backup externo antes.
Testar uma rota por vez, usando leitura e prévia; registrar somente
campos não sensíveis, resultado no painel original e comparação
pós-POST. Evitar alterar rota default, IP de gerenciamento, firewall
ou TR-069 de uma ONT em produção. Se o resultado indicar incerteza,
verificar diretamente na ONT antes de gerar outra prévia.

~~~powershell
git switch main
git pull --ff-only origin main
py -3.13 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python -m unittest discover -s tests -v

# Apenas em ambiente autorizado, com backup e acesso Ethernet local:
$env:ZTE_F6201B_EXPERIMENTAL_WRITES = "1"
python manage.py runapp
~~~

A integração na main depende do workflow de testes. Homologação em
equipamento físico permanece etapa separada.

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
- **Formulário capturado completo**: o conjunto das outras 14 rotas
  recebeu uma Strategy individual em f6201b_full_forms.py. A interface
  disponibiliza leitura, formulário, prévia, confirmação e um Apply
  completo com a ordenação da captura. Quando o firmware omitir campos
  condicionais no GET e na menuView atual, o POST é recusado com a lista
  exata de informações ausentes, em vez de inventar valores.

| # | Tag menuData | Situação | O que ainda exige validação |
|---|---|---|---|
| 01 | wlan_wlansssidconf_lua.lua | Adaptador existente | Homologar senha, SSID, isolamento, criptografia e múltiplos encode em ONT |
| 02 | dns_localdns_lua.lua | Adaptador existente | Testar separadamente servidores IPv4/IPv6 e formulário de domínio |
| 03 | wlan_BandSteering_lua.lua | Laboratório supervisionado | Band Steering, RSSI, transição Mesh e releitura física |
| 04 | wlan_wps_lua.lua | Formulário capturado | Preservar SSID_InstID e WPSChoose do HTML atual |
| 05 | wlan_wlanbasicadconf_lua.lua | Adaptador existente | Respostas XML integrais de RF e aplicação física por banda |
| 06 | wan_internet_lua.lua | Formulário capturado | Branches PPPoE/IP/VLAN/IPv6, senha codificada e instância WAN |
| 07 | upnp_upnp_lua.lua | Laboratório supervisionado | Testar política de acesso e propagação UPnP |
| 08 | firewall_config_lua.lua | Laboratório supervisionado | Efeitos de política firewall e recuperação de acesso |
| 09 | dns_hostname_lua.lua | Adaptador existente | Upsert de host; duplicações e preservação das entradas |
| 10 | bpdu_lua.lua | Laboratório supervisionado | Estado BPDU e interação com bridges |
| 11 | route_routedefault_lua.lua | Laboratório supervisionado | Verificar índice de interface e acesso via WAN/LAN |
| 12 | route_routestaticipv4_lua.lua | Formulário capturado | Campo Type não exposto no GET; Add/Edit distintos |
| 13 | Localnet_LanMgrIpv4_DHCPBasicCfg_lua.lua | Formulário capturado | Múltiplos objetos DHCP e campo codificado; proteger IP LAN |
| 14 | Localnet_LanDevDHCPSource_lua.lua | Formulário capturado | Vetor completo de 12 posições ProcFlag e InstID |
| 15 | addr6_lanaddr_lua.lua | Laboratório supervisionado | Configuração IPv6 LAN e possível perda de acesso |
| 16 | dhcp6s_dhcpserver_lua.lua | Formulário capturado | Combinar objetos DHCPv6 e DNS e botões condicionais |
| 17 | ra_raservice_lua.lua | Formulário capturado | S_AdvLinkMTU e regras de prefixo/atualização |
| 18 | radhcp6s_portctrl_lua.lua | Formulário capturado | Vetor de portas completo e seleção de instância |
| 19 | eth_interface_config_lua.lua | Formulário capturado | ModType ausente no GET fornecido |
| 20 | wlan_wlanbasiconoff_lua.lua | Formulário capturado | Dois rádios, timer e instâncias dependentes |
| 21 | wlan_macfilteraclpolicy_lua.lua | Formulário capturado | Vetor por SSID e instâncias ACL de múltiplas bandas |
| 22 | Localnet_NetSphere_Mode_lua.lua | Formulário capturado | CurrentMode, CurrentEnable e confirmação Mesh |
| 23 | tr069_remotemgr_lua.lua | Formulário capturado | Criptografia de duas credenciais, certificados e ACS |
| 24 | firewall_alg_lua.lua | Laboratório supervisionado | Testar ALG/VoIP sem romper serviços |
| 25 | firewall_dmz_lua.lua | Formulário capturado | Campos MAC temporários não preserváveis no GET |

**Totais atuais:** 21 rotas com comandos supervisionados próprios
(7 estratégias originais + 14 Strategies condicionais) e 4 adaptadores
existentes, totalizando 25 rotas com implementação em código. O
funcionamento de cada comando fica condicionado à leitura real e
completa dos campos correspondentes ao formulário original; ausência
de dados bloqueia a escrita, e não representa uma tentativa parcial.

## Fluxo e responsabilidades

- **Strategy / catálogo:** services/f6201b_full_forms.py implementa os
  14 formulários complexos usando os objetos XML efetivamente expostos,
  leitura dos controles HTML atuais, seleção de instância,
  transformação conservadora de arrays, senha/encode e preenchimento
  obrigatório antes de gerar o body.
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
  técnico de 25 linhas, formulários nas 21 estratégias,
  instâncias, prévias, progresso e estados de erro. CSS usa os tokens
  BRModelo, com navegação/lista compacta, inspiração no workspace
  DockerFlow, sem alterar os componentes dos demais modelos.

## Como testar

Os testes de tests/test_f6201b_full_forms.py cobrem as 14 novas
estratégias, ordenação exata de todos os campos, falha de prévia sem
metadados do formulário, vínculo WPS, vetores de rádio, transformação
de DHCP/RA, recodificação AES/RSA de WAN e ACS, máscaras de senhas,
verificação separada de credenciais, transporte bloqueado e
ausência de repetição em falhas ambíguas.

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

A captura original tem homologação física informada pelo operador.
Os testes automatizados acima verificam o **novo código**, mas uma
reprodução na ONT deve comparar a serialização do aplicativo com a
mesma tela, mesma instância e versão de firmware. Campos não
observáveis em determinado login são relatados e **não** postados.

Em mudanças de WAN, LAN, firewall ou ACS, conserve acesso local e backup;
um HTTP 200/IF_ERRORID=0 não comprova que a configuração persistiu.

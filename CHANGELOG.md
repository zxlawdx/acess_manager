# Changelog

## 0.6.2 — Speed Test Providers

- Corrige URLs como `https://fast.com` que antes eram tratadas incorretamente como endpoints Cloudflare `/__down` e `/__up`.
- Adiciona Factory/Strategy por provedor: ONT nativa, Cloudflare, FAST.com/Netflix, Speedtest.net e LibreSpeed.
- Adiciona modo **Detectar pela URL**: FAST.com, Speedtest.net e Cloudflare são reconhecidos automaticamente; outras URLs são verificadas como LibreSpeed.
- FAST.com passa a descobrir o token atual e os alvos CDN da Netflix antes de medir download, upload, latência e jitter.
- Speedtest.net passa a usar `speedtest-cli` empacotado com a aplicação.
- LibreSpeed descobre automaticamente `backend/garbage.php`/`backend/empty.php` ou `garbage.php`/`empty.php`.
- A seleção do provedor é compartilhada entre **Testar velocidade** e o Speed Test do **Diagnóstico completo**.
- A UI e o relatório da OS registram qual provedor realmente executou a medição.
- Minha Conexão não é tratado como Cloudflare/LibreSpeed: sem API pública estável, o sistema informa explicitamente que não há automação direta suportada.

## 0.6.1 — Selectable Speed Test Server

- Adiciona seletor de servidor do Speed Test na aba de diagnóstico.
- Mantém Cloudflare como padrão e permite URL personalizada para o fallback executado pelo computador do atendente.
- Propaga a URL escolhida pela UI → API → `SupportDiagnosticService` → `SpeedTestService`.
- O teste nativo da ONT continua usando os servidores descobertos pelo próprio firmware.

## 0.6.0 — Automatic Support Diagnostics

- Adiciona a aba **Diagnóstico automático** e triagem de saúde no Dashboard.
- Adiciona seleção de cenário: geral, banda baixa, quedas, sem Internet e Wi-Fi.
- Correlaciona dispositivo afetado com banda 2.4/5 GHz, RSSI, taxa PHY, Band Steering e porta Ethernet quando o firmware fornece a interface.
- Adiciona scan ThinkLua de APs vizinhos em 2.4/5 GHz, com sinal, ruído e canal.
- Adiciona `ChannelAnalyzer` que pontua interferência pelo peso do sinal/ruído e sobreposição, em vez de apenas contar SSIDs.
- Adiciona recomendação de canal manual ou Auto; a otimização automática opcional passa por auditoria `before -> action -> after` e revalidação.
- Adiciona DNS Lookup nativo e evita tratar DNS estático `0.0.0.0` como falha quando a resolução efetiva funciona via WAN/PPPoE.
- Adiciona Speed Test nativo do dashboard AIS/ThinkLua quando disponível, com fallback HTTP identificado como teste executado pelo computador do atendente.
- Adiciona análise de erros/descartes LAN, CPU/memória e normalização dos enums de velocidade Ethernet ZTE.
- Adiciona gerador de atendimento/OS usando diagnóstico final + todas as alterações auditadas da sessão.
- Adiciona capabilities para scan Wi-Fi, gerenciador de interferência, DNS Lookup e Speed Test nativo.
- Adiciona bundle `support_diagnostics.js/css`, testes das regras e validação JS no CI.

## 0.5.0 — Operations Suite / F670L

- Adiciona adapters para **F6600P**, **F670L** e fallback genérico ThinkLua.
- Adiciona catálogo e probe de capabilities por firmware/login.
- Libera controles WLAN já expostos pelo firmware: MU-MIMO, OFDMA, TWT, Spatial Reuse, DTIM, RTS/CTS, preâmbulo e isolamento global.
- Adiciona agendamento global de Wi-Fi com preservação do estado manual dos rádios.
- Adiciona configuração avançada de Band Steering com thresholds de RSSI, utilização, idle-rate e parâmetros correlatos.
- Adiciona diagnóstico automático composto de PON, WAN, PPPoE, LAN, Wi-Fi, ping e traceroute opcional.
- Adiciona histórico SQLite com sessões, snapshots, diagnósticos e alterações antes/depois.
- Todas as mutações principais passam pelo mesmo fluxo auditável `before -> action -> after`.
- Adiciona gerenciamento DHCP IPv4, leases e reservas estáticas.
- Adiciona port forwarding e DMZ com confirmação explícita.
- Adiciona inspector ThinkLua somente leitura para firewall, filtros IP/MAC, parental control, controles de serviços, DDNS, SNTP, TR-069, rotas, QoS, UPnP PortMap e syslog.
- Adiciona probe seguro de firmware upgrade, restore e factory reset sem expor POST destrutivo.
- Adiciona exportação local de backup de configuração pelo fluxo oficial `usrCfgMgr`.
- Adiciona página **Avançado** à SPA e bundle `advanced.js/advanced.css`.
- CI passa a validar também `advanced.js`.
- Novos testes cobrem adapters, histórico SQLite, diagnóstico automático, builders de operações e contrato UI/API.

## 0.4.1 — Correção do perfil no Vela

- Corrige erro `Cannot read properties of null (reading 'querySelector')` após login.
- `profileRadios` agora cria os cards 2.4 GHz e 5 GHz antes de preencher o formulário.
- Adicionadas validações explícitas do DOM para evitar falhas silenciosas no WebView.
- Login bem-sucedido não volta mais à tela de conexão por causa da renderização do perfil.

## 0.4.0 — Vela Desktop

- Migração de FastAPI/Uvicorn para Vela Framework + Bottle interno.
- Janela desktop via pywebview.
- UI preservada como SPA em rota Vela `layout=blank`.
- Controllers FastAPI substituídos por `apps/zte_manager/api.py`.
- Pydantic mantido como validação na borda da API.
- Rotas `PATCH`/path params convertidas para comandos POST compatíveis com o `ApiRouter` atual.
- `ZTEBridge` adicionado para impedir hot reload de serviços stateful e preservar a sessão da ONT.
- Estrutura reorganizada em `apps/zte_manager/services`, `repositories` e `model`.
- `start.bat`, `start.ps1`, `launcher.py` e `build.bat` adicionados.
- Correções anteriores de segundo DNS/read-after-write preservadas.
- 21 testes de domínio/protocolo preservados.

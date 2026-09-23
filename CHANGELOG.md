# Changelog

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

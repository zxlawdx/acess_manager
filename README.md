# ZTE Automatic — Vela Desktop

Aplicação desktop para atendimento, diagnóstico e provisionamento de ONTs ZTE **F6600P, F670L e firmwares ThinkLua compatíveis**, construída sobre o **Vela Framework**.

A versão web/FastAPI foi convertida para a arquitetura do Vela sem alterar a lógica de protocolo que já estava funcionando no equipamento. A janela é nativa via `pywebview`, a UI continua em HTML/CSS/JS e a comunicação com o Python passa pelo servidor Bottle interno do Vela.

## O que o app faz

- Login na ONT por IP/host, usuário e senha.
- Mantém uma única `requests.Session()` durante o atendimento.
- Status do equipamento, firmware, hardware, serial, CPU, memória e uptime.
- Telemetria óptica GPON: estado de registro, ONU ID, RX/TX, temperatura, tensão e corrente quando disponíveis.
- WAN e PPPoE, incluindo usuário e senha com revelação explícita.
- Clientes Wi-Fi e LAN.
- Portas Ethernet e velocidade negociada.
- Redes/SSIDs com:
  - nome;
  - senha;
  - ativar/desativar SSID;
  - broadcast/SSID oculto;
  - isolamento;
  - limite de clientes;
  - modo de segurança.
- Rádio 2.4 GHz / 5 GHz:
  - liga/desliga;
  - canal automático/manual;
  - largura;
  - standard;
  - país;
  - potência;
  - SGI;
  - beacon interval.
- WPS PBC/Disabled quando o firmware expõe a função.
- Band Steering quando o firmware/permissão expõe a função.
- UPnP.
- DNS IPv4/IPv6 e nomes estáticos.
- Retry/read-after-write para confirmar o segundo DNS/nome estático em firmwares que demoram para persistir.
- Ping e traceroute executados pela própria ONT.
- Alteração da senha administrativa usada no login.
- Reboot da ONT.
- Perfil padrão por atendente e botão **Aplicar configuração padrão**.
- Adapter/capability detection para F6600P, F670L e fallback ThinkLua.
- Wi-Fi avançado: MU-MIMO, OFDMA, TWT, Spatial Reuse, DTIM, RTS/CTS, preâmbulo e isolamento quando expostos pelo firmware.
- Agendamento global de Wi-Fi pelo timer nativo da ONT.
- Band Steering avançado com thresholds de RSSI, utilização e idle-rate.
- Diagnóstico automático composto (PON + WAN + PPPoE + LAN + Wi-Fi + ping + traceroute opcional).
- **Automatic Support Diagnostics** com modos de queixa, dispositivo afetado, DNS Lookup, scan RF, análise de canal, Band Steering, Speed Test e revalidação.
- Scan de APs vizinhos 2.4/5 GHz quando o firmware expõe `OBJ_WLANGETNEBAP_ID`; o score pondera sinal, ruído e sobreposição de canais.
- Otimização automática opcional de canal Wi-Fi, sempre registrada no audit trail antes da validação final.
- Speed Test nativo da ONT em firmwares AIS/ThinkLua compatíveis; fallback HTTP pelo computador fica explicitamente identificado para não confundir os dois caminhos.
- Botão **Gerar atendimento** produz texto de OS usando o diagnóstico e todas as alterações da sessão.
- Histórico local SQLite com sessões, snapshots, diagnósticos e alterações antes/depois.
- DHCP IPv4: pool, DNS, lease, leases ativos e reservas por MAC.
- NAT: port forwarding e DMZ com confirmação explícita.
- Inspector ThinkLua em modo leitura para firewall, filtros IP/MAC, controle parental, DDNS, SNTP, TR-069, rotas, QoS, UPnP PortMap e syslog.
- Backup local da configuração de usuário usando o fluxo oficial `usrCfgMgr`.

## Arquitetura Vela

```text
pywebview / Vela Shell
        |
        v
HTML + CSS + JS (SPA)
        |
        v
/api/*  (Bottle interno do Vela)
        |
        v
apps.zte_manager.api
        |
        v
ZTEService  --------------------> ProfileService
    |                                  |
    |                                  v
    |                             ProfileRepository
    v
ZTE Facade
    |
    +--> DeviceAdapter / CapabilityService
    |       +--> F6600PAdapter
    |       +--> F670LAdapter
    |       +--> ThinkLua fallback
    |
    +--> Login / sessão / Check / RSA
    +--> Wi-Fi / SSID
    +--> WLAN advanced
    +--> WAN / PPPoE
    +--> DNS
    +--> PON / LAN / UPnP
    +--> Ping / Traceroute / NsLookup
    +--> Wi-Fi neighbor scan
    +--> Native Speed Test
    |
    +--> SupportDiagnosticService
    |       +--> Collectors
    |       +--> DiagnosticRules
    |       +--> ChannelAnalyzer
    |       +--> SpeedTest Strategy
    |
    +--> AttendanceReportService
```

Padrões usados: **Facade**, **Service Layer**, **Repository**, **Command/Composite**, **Strategy**, **Adapter**, **Template Method** e builder por estado atual.

## Operations Suite e F670L

O app não assume que todo firmware ZTE possui os mesmos menus. Depois do login, o modelo/firmware seleciona um `DeviceAdapter`; o botão **Detectar recursos** faz probe real de cada `menuView/menuData` e a UI marca o que aquele login realmente consegue acessar.

O F670L usa o mesmo fluxo ThinkLua de login e WAN encontrado no projeto atual (`login_entry/login_token`, `ethWanStatus` e `wan_internetstatus_lua.lua`). Recursos avançados continuam sendo validados por probe porque operadoras podem ocultar menus por firmware ou nível da conta.

As operações foram separadas por risco:

- **Escrita validada**: Wi-Fi avançado, timer Wi-Fi, Band Steering, DHCP/reservas, port forwarding e DMZ.
- **Somente leitura**: firewall/filtros, controle parental, DDNS, SNTP, TR-069/ACS, rotas, QoS, UPnP PortMap e logs.
- **Proteção extra**: port forwarding e DMZ exigem `confirm=true`; TR-069 nunca devolve senhas em claro.
- **Backup**: exportação local é automatizada; restauração/factory reset permanecem manuais para não importar configuração incompatível ou derrubar provisionamento ACS.

## Estrutura

```text
zte-automatic-vela/
├── manage.py
├── launcher.py
├── build.bat
├── start.bat
├── start.ps1
├── requirements.txt
├── requirements-build.txt
│
├── config/
│   ├── settings.py
│   └── wsgi.py
│
├── apps/
│   └── zte_manager/
│       ├── api.py
│       ├── schemas.py
│       ├── bridge.py
│       ├── views/
│       ├── templates/
│       ├── static/
│       ├── services/
│       ├── repositories/
│       └── model/
│           └── zte_configuration/
│
├── data/
├── docs/
└── tests/
```

## Por que existe `ZTEBridge`

O Vela 0.1.0 atualmente recarrega módulos `apps.*` em cada `navigate()`. Isso é ótimo para hot reload de páginas stateless, mas uma aplicação que mantém uma sessão HTTP stateful com uma ONT não pode recriar `ZTEService` durante o atendimento.

Por isso `apps/zte_manager/bridge.py` herda de `BaseBridge` e desativa **somente** esse hot reload automático. A aplicação continua usando o Vela normalmente para janela, shell, roteamento, estáticos, bridge e API.

A UI é uma SPA dentro de uma única rota Vela (`/`), então Dashboard/Wi-Fi/WAN/etc não recriam a view Python.

Mais detalhes: `docs/VELA_FRAMEWORK_NOTES.md`.

## Interface desktop e zoom

O bundle Windows usa **PyQt6 + QtWebEngine**. A UI usa fontes de texto do próprio sistema para manter aparência consistente mesmo sem acesso ao Google Fonts.

Atalhos de zoom:

- `Ctrl + +` aumenta a interface;
- `Ctrl + -` diminui;
- `Ctrl + 0` retorna para 100%.

O nível escolhido fica salvo localmente no WebView.

## API interna do app

O `ApiRouter` atual do Vela suporta `GET`, `POST`, `PUT` e `DELETE`, mas não `PATCH`, e o wrapper atual não injeta parâmetros dinâmicos de rota no handler. Para manter o projeto compatível **sem exigir um fork do framework**, os comandos de alteração usam `POST` com o identificador no JSON.

Exemplos:

```text
POST /api/connect
GET  /api/device/status
GET  /api/device/optical
GET  /api/wan/status
GET  /api/wan/pppoe?reveal_password=true
GET  /api/wifi/networks
POST /api/wifi/network/update
GET  /api/wifi/radios
POST /api/wifi/radio/update
GET  /api/wifi/power
POST /api/wifi/power/update
GET  /api/wifi/wps
POST /api/wifi/wps/update
GET  /api/wifi/band-steering
POST /api/wifi/band-steering/update
GET  /api/dns/status
POST /api/dns/update
POST /api/diagnostics/ping
POST /api/diagnostics/traceroute
POST /api/profiles/get
POST /api/profiles/save
POST /api/profiles/capture
POST /api/profiles/apply
POST /api/device/password
POST /api/device/reboot

GET  /api/device/capabilities
POST /api/device/capabilities/probe
GET  /api/features/read?feature=tr069

GET  /api/wifi/schedule
POST /api/wifi/schedule/update
POST /api/wifi/band-steering/configure

POST /api/diagnostics/automatic
POST /api/diagnostics/support
POST /api/diagnostics/remediate
POST /api/diagnostics/speedtest
POST /api/diagnostics/attendance
GET  /api/history
POST /api/history/snapshot

GET  /api/network/dhcp
POST /api/network/dhcp/update
POST /api/network/dhcp/reservation/save
POST /api/network/dhcp/reservation/delete

GET  /api/network/port-forwarding
POST /api/network/port-forwarding/save
POST /api/network/port-forwarding/delete
GET  /api/network/dmz
POST /api/network/dmz/update

POST /api/system/backup
```

A API é local. A porta preferencial é `127.0.0.1:8765`; se ela estiver ocupada, o Vela seleciona outra porta livre automaticamente.

## Executar no Windows

### Mais rápido

```bat
start.bat
```

O script:

1. cria `.venv`;
2. instala o Vela Framework e as dependências;
3. roda `collectstatic --no-tailwind`;
4. abre a aplicação desktop.

### Manual

```powershell
py -3.13 -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python manage.py collectstatic --no-tailwind
python manage.py runapp
```

## Releases automáticas por tag

O workflow `.github/workflows/release.yml` segue o mesmo modelo validado no projeto **PIBIC LAB**:

1. executa os testes;
2. gera build **Linux x86_64**;
3. gera build **Windows x86_64**;
4. valida os assets do bundle;
5. publica os dois pacotes na GitHub Release da tag;
6. publica também os checksums SHA-256.

Exemplo:

```bash
git tag -a v0.4.4 -m "ZTE Automatic v0.4.4"
git push origin v0.4.4
```

Arquivos esperados na Release:

```text
ZTEAutomatic-Linux-x86_64-v0.4.4.zip
ZTEAutomatic-Linux-x86_64-v0.4.4.zip.sha256
ZTEAutomatic-Windows-x86_64-v0.4.4.zip
ZTEAutomatic-Windows-x86_64-v0.4.4.zip.sha256
```

O workflow também pode ser executado manualmente em **Actions → build-release → Run workflow**, informando uma tag já existente.

## Build Windows

```bat
build.bat
```

O executável/onedir será criado em:

```text
dist\ZTEAutomatic\
```

O build usa Qt/QtWebEngine, seguindo o launcher recomendado pelo Vela.

## Desenvolvimento

Para abrir DevTools, altere em `config/settings.py`:

```python
DEBUG = True
```

Rotas visuais:

```powershell
python manage.py routes
```

Estáticos:

```powershell
python manage.py collectstatic --no-tailwind
```

## Testes

Os testes de protocolo e regras de domínio não dependem de uma ONT conectada:

```powershell
python -m unittest discover -s tests -v
```

A suíte cobre protocolo, segurança, builders WLAN, Vela, adapters, histórico SQLite, diagnóstico automático, regras de suporte/OS e contrato entre UI/API. O GitHub Actions também executa `compileall` e valida a sintaxe de `app.js`, `advanced.js` e `support_diagnostics.js`.

## Persistência dos perfis

Em desenvolvimento, os perfis ficam em `data/attendant_profiles.json`. No executável Windows, ficam em `%LOCALAPPDATA%\ZTEAutomatic\attendant_profiles.json`, para sobreviver a atualização/substituição da pasta do app.

Para forçar outro local:

```text
ZTE_AUTOMATIC_DATA_DIR=C:\meu-diretorio
```

Além dos perfis, a Operations Suite cria `operations.sqlite3` nesse diretório e usa `backups/` para exportações locais da configuração da ONT.

## Sessão da ZTE

O app não chama `logout_entry` ao aplicar configuração nem ao fechar o console. Ao desconectar, fecha apenas a sessão HTTP local.

Isso evita enviar um logout explícito que possa derrubar outra aba administrativa. Alguns firmwares ZTE ainda aceitam apenas uma sessão administrativa por vez; nesse caso, o simples login do app pode substituir uma sessão anterior aberta no navegador.

## Segurança do POST ThinkLua

O app replica o fluxo real do firmware:

1. `menuView` correto;
2. captura `_sessionTmpToken`;
3. captura chave RSA/`IntegCheck` dinamicamente;
4. lê o estado atual;
5. monta o body na ordem esperada;
6. `_sessionTOKEN` por último;
7. `SHA256(body)`;
8. RSA PKCS#1 v1.5 para o header `Check` quando necessário.

A chave RSA não fica fixa no código.

## Referências de firmware usadas

- `zxlawdx/Vela-framework` — runtime desktop desta versão.
- `juacas/zte_tracker` — sessão/reboot/compatibilidade ZTE.
- `cmocan/HA_CustomComponents` — implementação comunitária F660/F6600R.
- `Blinko1987/F6107A-telnet-root-on-AIS-fiber` — fontes ThinkLua, WLAN, DNS, diagnóstico, DHCP, NAT, segurança e fluxo `Check`.
- `langit7/zte-f670L` — confirmação pública do fluxo ThinkLua de login/WAN em variantes F670L.

Os repositórios aparentados ajudam a reproduzir o protocolo, mas o F6600P e seu firmware continuam sendo a autoridade final. O código lê estado/tokens/chaves dinamicamente exatamente por isso.

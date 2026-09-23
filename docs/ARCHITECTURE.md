# Arquitetura

```text
Vela / pywebview
    |
    v
SPA HTML/CSS/JS
    |
    +--> app.js
    +--> advanced.js
    |
    v
Bottle API interna (/api)
    |
    v
apps.zte_manager.api
    |
    v
ZTEService  --------------------> ProfileService
    |                                  |
    |                                  v
    |                             ProfileRepository
    |
    +---------------------------> HistoryRepository (SQLite)
    |
    +---------------------------> CapabilityService
    |                                  |
    |                                  v
    |                           DeviceAdapter Strategy
    |                           +--> F6600PAdapter
    |                           +--> F670LAdapter
    |                           +--> ThinkLuaAdapter
    |
    v
ZTE Facade
    |
    +--> sessão/login/security
    +--> Wi-Fi / SSID / timer / Band Steering
    +--> WLAN advanced builder
    +--> WAN / PPPoE
    +--> DHCP / LAN / NAT
    +--> DNS
    +--> PON / UPnP
    +--> backup
    +--> DiagnosticStrategy
    |       +--> PingDiagnostic
    |       +--> TracerouteDiagnostic
    |
    +--> AutomaticDiagnosticService (Composite)
    |
    +--> SupportDiagnosticService
            +--> DiagnosticCollector Composite
            +--> DiagnosticRule Specifications
            +--> ChannelAnalyzer
            +--> SpeedTestService
                    +--> NativeOntSpeedTestStrategy
                    +--> HttpWorkstationSpeedTestStrategy

ZTEService ---------------------> AttendanceReportService
```

## Padrões usados

**Facade** — `ZTE` esconde a fragmentação dos módulos ThinkLua e oferece operações de alto nível.

**Service Layer** — `ZTEService` é a fronteira entre a API Vela e a ONT. O `RLock` serializa chamadas porque a navegação da ZTE mantém estado por sessão.

**Repository** — `ProfileRepository` isola os perfis JSON. `HistoryRepository` isola SQLite e persiste sessões, snapshots, diagnósticos e alterações.

**Command + Composite** — `ApplyProfileCommand` compõe as etapas de perfil. `AutomaticDiagnosticService` compõe várias leituras independentes e produz findings sem falhar inteiro quando um menu não existe.

**Strategy** — ping e traceroute usam o mesmo contrato de diagnóstico. `DeviceAdapter` seleciona comportamento/capabilities por família/modelo sem espalhar condicionais por `ZTEService`.

**Adapter** — `F6600PAdapter`, `F670LAdapter` e `ThinkLuaAdapter` transformam diferenças de firmware em um catálogo uniforme de recursos.

**Template Method** — `ThinkLuaCrudGateway` centraliza `menuView -> menuData -> POST -> releitura` para recursos ManagerOBJ. `ZTEService._run_change()` centraliza auditoria `before -> action -> after`.

**Builder por estado atual** — WLAN e outros formulários de configuração partem do estado retornado pela ONT e aplicam somente overrides. Campos não enviados permanecem preservados.

## Multi-firmware e capabilities

O adapter é selecionado uma vez após o login, usando modelo e firmware retornados pela ONT. O catálogo declara recursos possíveis, mas **não presume disponibilidade**.

O probe real é feito por `CapabilityService`:

```text
FeatureSpec
    -> EndpointSpec(menuView, menuData)
    -> ThinkLuaCapabilityGateway
    -> GET menuView
    -> GET menuData
    -> parse / sanitize
    -> available=true|false
```

Isso é importante porque duas ONTs do mesmo modelo podem expor menus diferentes conforme firmware e privilégio da conta.

Recursos sensíveis como TR-069, firewall, firmware, restore e factory reset ficam somente em leitura/probe. Campos cujo nome indica senha/segredo são mascarados pelo gateway.

## Escrita e auditoria

Toda escrita nova passa pelo mesmo fluxo em `ZTEService._run_change()`:

```text
captura estado anterior
    -> executa ação
    -> captura estado posterior
    -> grava configuration_change
```

Se a ação falhar, a tentativa também é registrada como falha.

Port forwarding e DMZ exigem confirmação explícita na API. Restore, firmware upgrade e factory reset não têm ação destrutiva exposta pela aplicação.

## Diagnóstico automático

`AutomaticDiagnosticService` coleta de forma independente:

- device/uptime;
- GPON/óptica;
- WAN;
- PPPoE sem revelar senha;
- portas LAN;
- clientes Wi-Fi e LAN;
- ping;
- traceroute opcional.

Os thresholds de potência óptica, RSSI, velocidade Ethernet e latência vêm da requisição/configuração, não são tratados como limites universais.

## Diagnóstico de atendimento

A versão completa usa um pipeline deliberadamente separado entre **coleta**, **conclusão** e **remediação**:

```text
AutomaticDiagnosticService
    -> seções base
    -> DiagnosticCollectors opcionais
         -> RF neighbor scan
         -> DNS health / NsLookup
         -> DHCP / Band Steering / firmware health
         -> Speed Test
    -> DiagnosticRules
         -> cliente afetado / PHY / banda
         -> DNS
         -> erros LAN
         -> recursos da ONT
         -> interferência/canal
         -> velocidade
    -> recommendations
```

`SupportDiagnosticService` é somente leitura. Escritas recomendadas voltam para `ZTEService`, passam por `_run_change()` e só depois são revalidadas. Isso evita que uma regra de diagnóstico altere a ONT por conta própria.

`SpeedTestService` usa Chain of Responsibility: tenta o teste nativo da ONT e, se permitido, usa o teste HTTP pelo computador do atendente como fallback. A origem fica gravada no resultado.

`AttendanceReportService` usa o último diagnóstico e `HistoryRepository.session_timeline()` para montar a OS somente com eventos da sessão atual e remove campos de segredo dos diffs.

## Integração com o Vela

A interface usa uma única rota visual Vela em `layout="blank"`. A navegação interna continua sendo feita pelo JavaScript da SPA.

`app.js` mantém o console principal. `advanced.js` usa hooks expostos pelo bundle base para adicionar controles WLAN e Operations Suite sem duplicar o renderer principal. `support_diagnostics.js` concentra a experiência de triagem/diagnóstico/OS e registra no bundle base apenas o hook sequencial de saúde do Dashboard.

A API fica em `apps/zte_manager/api.py`, registrada via `@api.get` e `@api.post`.

## Estado da sessão

O `BaseBridge` do Vela 0.1.0 recarrega módulos `apps.*` durante `navigate()`. Como `ZTEService` mantém uma sessão stateful com o roteador, o projeto usa `ZTEBridge`, uma subclasse que desativa esse hot reload automático.

Uma conexão inicia também uma `attendant_session` no histórico local e registra um snapshot inicial.

## Concorrência

Uma janela/processo mantém uma sessão ONT ativa.

O `RLock` protege sequências dependentes de contexto:

```text
menuView -> menuData -> POST -> menuData
```

Duas operações concorrentes na mesma `requests.Session()` poderiam mudar a view/token temporário do firmware no meio de outra operação.

## Persistência

`runtime.data_dir()` é o ponto único para dados persistentes:

```text
attendant_profiles.json
operations.sqlite3
backups/
```

Em desenvolvimento ele aponta para `data/`. No executável Windows, usa o diretório local da aplicação/usuário definido pelo runtime. `ZTE_AUTOMATIC_DATA_DIR` pode sobrescrever o destino.

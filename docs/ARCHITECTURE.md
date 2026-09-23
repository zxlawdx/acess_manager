# Arquitetura

```text
Vela / pywebview
    |
    v
SPA HTML/CSS/JS
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
    v
ZTE Facade
    |
    +--> sessão/login/security
    +--> Wi-Fi / SSID
    +--> WLAN advanced builder
    +--> WAN / PPPoE
    +--> DNS
    +--> PON / LAN / UPnP
    +--> DiagnosticStrategy
            +--> PingDiagnostic
            +--> TracerouteDiagnostic
```

## Padrões usados

**Facade** — `ZTE` esconde a fragmentação dos módulos ThinkLua e oferece operações de alto nível.

**Service Layer** — `ZTEService` é a fronteira entre a API Vela e a ONT. O `RLock` serializa chamadas porque a navegação da ZTE mantém estado por sessão.

**Repository** — `ProfileRepository` isola JSON da regra de negócio; trocar por SQLite/PostgreSQL não exige alterar o protocolo da ONT.

**Command + Composite** — `ApplyProfileCommand` compõe as etapas 2.4 GHz, 5 GHz e DNS e gera um relatório por etapa.

**Strategy** — ping e traceroute usam o mesmo contrato de diagnóstico.

**Builder por estado atual** — o WLAN não inventa um payload inteiro. Primeiro lê a instância atual e aplica somente os overrides desejados.

## Integração com o Vela

A interface usa uma única rota visual Vela em `layout="blank"`. A navegação interna da aplicação continua sendo feita pelo JavaScript da SPA, preservando a UI técnica já construída.

A API fica em `apps/zte_manager/api.py`, registrada via `@api.get` e `@api.post`.

## Estado da sessão

O `BaseBridge` do Vela 0.1.0 recarrega módulos `apps.*` durante `navigate()`. Como `ZTEService` mantém uma sessão stateful com o roteador, o projeto usa `ZTEBridge`, uma subclasse que desativa esse hot reload automático.

Isso evita recriar o singleton da sessão no meio do atendimento.

## Concorrência

Uma janela/processo mantém uma sessão ONT ativa. Isso combina com o uso em cada estação de suporte.

O `RLock` protege sequências dependentes de contexto, como:

```text
menuView -> menuData -> POST
```

Duas operações concorrentes na mesma `requests.Session()` poderiam mudar a view do firmware no meio de outra operação.

## Persistência

Perfis de atendente usam `runtime.data_dir()`: `data/attendant_profiles.json` em desenvolvimento e `%LOCALAPPDATA%\ZTEAutomatic\attendant_profiles.json` no executável Windows.

# Fase 2 — Driver real, sessão resiliente, inventário isolado e clipboard

**Base:** PR #46 já integrada à `main@751d04e`.
**Objetivo:** aplicar o novo contrato de runtime no fluxo existente sem trocar os
endereços `/api/*`, sem criar duas sessões na mesma ONT e sem mudar os
formulários capturados da F6201B.

## Arquivos novos e modificados

- `infrastructure/zte/firmware_policy.py`: reconhecimento de famílias
  ThinkLua e telemetria **não bloqueante** de compatibilidade de firmware.
  O catálogo de versões conhecidas não é uma permissão de escrita.
- `infrastructure/zte/adapters/thinklua_device.py`: suporta
  `attach_authenticated(existing_zte, ...)` que empresta a sessão aberta
  pelo `ZTEService` **sem outro login ou logout**; revalida firmware, modelo,
  serial e fabricante antes das escritas gerenciadas pelo driver.
- `services/zte_service.py`: seleciona esse driver somente quando um modelo
  ThinkLua F670L/F6600P foi identificado pela resposta real do dispositivo.
  Utiliza o driver para status, leitura/escrita SSID e DHCP, mantendo os
  mesmos envelopes/valores retornados ao frontend. As demais funcionalidades
  legadas continuam na mesma sessão HTTP. Modelos ThinkLua reconhecidos
  iniciam com escrita habilitada, independentemente do catálogo de firmware;
  erros reais de sessão/comunicação e troca de identidade continuam protegidos.
- `application/inventory/device_registrar.py`: inventário best-effort
  separado do login, com allowlist de campos planos, metadados mínimos e
  logs de *tipos* de exceção sem identificadores/segredos.
- `services/desktop_capabilities.py`, `api.py`: novo GET
  `/api/desktop/capabilities`; clipboard Win32 legado mantido.
- `static/js/desktop_clipboard.js`, `support_diagnostics.js`,
  `templates/index.html`: capacidades do host Python determinam o
  backend; Windows chama **somente** Win32 e em qualquer erro cai para
  seleção manual. JS não usa heurística `navigator.userAgent` nem
  `execCommand` no novo módulo.

## Política operacional de escrita (alinhamento após PR #47)

Modelos ThinkLua **realmente identificados pela ONT** (F670L/F6600P)
recebem `writes_enabled=true` por padrão na sessão técnica. A existência
ou ausência de uma versão no catálogo de firmware **não** autoriza nem
bloqueia POSTs; a escolha operacional é do usuário da ferramenta.

As proteções efetivas mantidas no driver são: autenticação, GET de
revalidação de identidade antes de mutações, correspondência do equipamento
(modelo/serial e versão *quando conhecida*), comunicação saudável e erro
real retornado pelo dispositivo. A aplicação não faz homologação de firmware
automática a partir de uma consulta de status.

`FirmwarePolicy.recognition_status(model, firmware)` fornece **telemetria**:
`reviewed`, `known_candidate`, `unreviewed` ou `unavailable`. O manifesto
opcional `ZTE_APPROVED_FIRMWARE_JSON` apenas anota versões revistas;
não altera `writes_enabled`, nem precisa existir para trabalhar. A
F6201B permanece **fora** do driver genérico: seus comandos capturados
exigem identificação da versão exata porque a forma do protocolo foi
capturada nessa versão. Não confundir essa proteção técnica com limitação
artificial por cargo/operador.

O endpoint `/api/discovery/bootstrap` mantém todos os campos existentes
e acrescenta o Boolean `native_diagnostics_available`. Os painéis nativos
F670L/F6600P usam essa capacidade de **leitura**, independentemente de
`writes_enabled`. Nenhum botão de diagnóstico GET deve ser escondido
apenas porque uma operação de alteração falhou.

## Invariantes de sessão

1. `ZTEService` autentica uma vez e fornece a sessão existente ao driver.
   O driver empresta o transporte: `driver.close()` limpa apenas seu estado.
   `disconnect()` e troca de ONT fecham o socket HTTP local; nenhum logout
   remoto é iniciado automaticamente.
2. O `RLock` da fachada continua abrangendo todo o ciclo
   `menuView → menuData → POST`; o bloqueio interno do driver é reentrante.
3. Reuso rejeita mudanças de modelo/firmware/serial e, em sessão gerenciada
   pelo driver, indisponibilidade de identificação. O driver revalida
   novamente identidade e sessão antes da escrita.
4. F6201B segue por `_f6201b_write_firmware()`,
   `_readonly_original_post` e seus comandos capturados: não passa pelo
   driver genérico.
5. Persistência de histórico e inventário é não essencial à autenticação.
   Falhas SQLite tornam o registro incompleto, mas não refazem o login ou
   repetem um POST. O estado de acompanhamento histórico pode ficar
   indisponível durante falhas da base de dados.
6. Fluxos legados que não usam ainda o driver não possuem todos os
   preflights por operação. Migração e ensaio por firmware seguem pendentes;
   não interpretar um firmware reconhecido como homologação física
   de todos os comandos expostos pela interface.

## Clipboard

`GET /api/desktop/capabilities` responde:

```json
{"platform":"win32","native_clipboard":true,
 "web_clipboard_allowed":false,"webview_transport":"http"}
```

O navegador não escolhe a plataforma. Quando a rota falha, a plataforma
não pode ser inferida com segurança: selecionar o textarea e instruir
`Ctrl+C` **sem tentar clipboard web**. Linux/macOS podem usar o
clipboard web somente se o host autorizou e `isSecureContext` e
`navigator.clipboard.writeText` estiverem presentes.

## Testes

```bash
python -m unittest tests.test_phase2_integration tests.test_runtime_device_contract tests.test_windows_compat -v
node tests/test_desktop_clipboard.cjs
node tests/test_native_readonly_diagnostics.cjs
python -m unittest discover -s tests -v
```

Testes sintéticos cobrem: um único login, sessão emprestada, reuso,
troca de identidade durante uma sessão, escrita de F670L/F6600P
com firmware não catalogado, F6201B capturada preservada, falha de inventário e de histórico, allowlist de dados,
contrato HTTP, ausência de fallback perigoso no Windows e cópia manual.
O workflow contém suíte completa Ubuntu/Python 3.13 e testes de contrato
Phase 2 no runner Windows/Python 3.12; um runner Windows headless **não**
comprova a abertura da GUI Qt. Uma GUI real Qt/Windows e WebKit/Linux e
mudanças físicas em ONT **ainda exigem validação antes do merge em produção**.

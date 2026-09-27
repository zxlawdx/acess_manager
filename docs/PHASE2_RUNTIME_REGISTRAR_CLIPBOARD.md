# Fase 2 — Driver real, sessão resiliente, inventário isolado e clipboard

**Base:** PR #46 já integrada à `main@751d04e`.
**Objetivo:** aplicar o novo contrato de runtime no fluxo existente sem trocar os
endereços `/api/*`, sem criar duas sessões na mesma ONT e sem mudar os
formulários capturados da F6201B.

## Arquivos novos e modificados

- `infrastructure/zte/firmware_policy.py`: catálogo fechado de **versões
  candidatas conhecidas** + allowlist de aprovações locais. Versões listadas
  no repositório não são evidência automática de homologação física.
- `infrastructure/zte/adapters/thinklua_device.py`: suporta
  `attach_authenticated(existing_zte, ...)` que empresta a sessão aberta
  pelo `ZTEService` **sem outro login ou logout**; revalida firmware, modelo,
  serial e fabricante antes das escritas gerenciadas pelo driver.
- `services/zte_service.py`: seleciona esse driver somente quando um modelo
  ThinkLua F670L/F6600P foi identificado pela resposta real do dispositivo.
  Utiliza o driver para status, leitura/escrita SSID e DHCP, mantendo os
  mesmos envelopes/valores retornados ao frontend. As demais funcionalidades
  legadas continuam na mesma sessão HTTP, com o bloqueio de POST para
  firmware não aprovado; migração incremental de cada operação continua
  necessária para guardas por comando e verificadores específicos.
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

## Aprovação de firmware — política de segurança

A verificação por nome de modelo da primeira fase foi removida como
mecanismo de concessão de escrita no **novo driver e seu vínculo no login**.
É preciso identificar modelo e versão reais, ambos exatamente iguais a uma
versão conhecida **e** explicitamente aprovada por instalação.

| Modelo do novo driver | Versões candidatas encontradas no repositório |
|---|---|
| F670L | `V9.0.11P1N9` (documentação), `V9.0.11P1N40` (fixture de teste) |
| F6600P | `V9.0.10P6N34` (fixture de teste) |
| F6201B | **Nunca** incluída no driver genérico. Sua via capturada usa `EXACT_FIRMWARE` próprio. |

**Por padrão todas as versões do driver genérico são somente leitura.**
As versões acima são candidatas documentadas, não foram homologadas
fisicamente nesta PR. Após testes de bancada autorizados, o operador pode
aprovar **apenas uma versão já presente no catálogo** com a variável local:

```bash
export ZTE_APPROVED_FIRMWARE_JSON='{"F670L":["V9.0.11P1N9"]}'
python manage.py runserver
```

Reinicie a aplicação para aplicar mudanças de política; não acrescente
versões desconhecidas à variável: a política rejeita modelos/versões que
não aparecem em `KNOWN_CANDIDATES`. A adição de versões futuras exige
revisão de código e homologação por operação. Não adicionar credenciais
ao manifesto ou a logs.

**Compatibilidade funcional:** a mudança deliberada é que instalações
sem aprovação explícita passarão a apresentar `writes_enabled=false`
no login para F670L/F6600P. As **chaves e tipos JSON** da API e os
demais endpoints são preservados. Isso evita que a migração reintroduza
o risco de POST em firmware ainda desconhecido.

## Invariantes de sessão

1. `ZTEService` autentica uma vez e fornece a sessão existente ao driver.
   O driver empresta o transporte: `driver.close()` limpa apenas seu estado.
   `disconnect()` e troca de ONT fecham o socket HTTP local; nenhum logout
   remoto é iniciado automaticamente.
2. O `RLock` da fachada continua abrangendo todo o ciclo
   `menuView → menuData → POST`; o bloqueio interno do driver é reentrante.
3. Reuso rejeita mudanças de modelo/firmware/serial e, em sessão gerenciada
   pelo driver, indisponibilidade de identificação. O driver revalida
   novamente identidade e aprovação antes da escrita.
4. F6201B segue por `_f6201b_write_firmware()`,
   `_readonly_original_post` e seus comandos capturados: não passa pelo
   driver genérico.
5. Persistência de histórico e inventário é não essencial à autenticação.
   Falhas SQLite tornam o registro incompleto, mas não refazem o login ou
   repetem um POST. O estado de acompanhamento histórico pode ficar
   indisponível durante falhas da base de dados.
6. Fluxos legados que não usam ainda o driver não possuem todos os
   preflights por operação. Migração e ensaio por firmware seguem pendentes;
   não interpretar uma aprovação de um firmware como homologação física
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
python -m unittest discover -s tests -v
```

Testes sintéticos cobrem: um único login, sessão emprestada, reuso,
troca de firmware, bloqueio de POST em versão desconhecida, F6201B
preservada, falha de inventário e de histórico, allowlist de dados,
contrato HTTP, ausência de fallback perigoso no Windows e cópia manual.
O workflow do repositório continua testando em Ubuntu; uma GUI real
Qt/Windows e WebKit/Linux e mudanças físicas em ONT **ainda exigem
validação antes do merge em produção**.

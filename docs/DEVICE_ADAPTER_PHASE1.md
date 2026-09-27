# Fase 1: contrato de hardware e auditoria de alterações (26/09/2026)

Base: `main@89a4ed6b54b186ebfbff7254ea60fab943e526b7`.
Esta entrega **não altera o bootstrap Vela nem remove o pipeline F6201B**.
Exige regressão de CI e homologação física antes do merge/deploy em atendimento.

## Fronteiras reais

- `application/contracts/device.py`: `DeviceAdapter` é o **contrato
  de runtime** independente do fabricante. `Credentials` esconde a senha
  do `repr`; `SessionContext` representa uma sessão local.
- `model/device_adapters/base.py`: o `DeviceAdapter` histórico permanece
  como **catálogo de capabilities e endpoints**, usado pelo `ZTEService`
  atual. Não substituir nem alterar seu import; os conceitos serão unificados
  quando o coordenador de sessão estiver isolado.
- `infrastructure/zte/adapters/thinklua_device.py`: implementação funcional
  do novo contrato sobre o cliente ZTE atual. Não duplica URLs ThinkLua:
  delega a `ZTE` e seus módulos `zte_configuration/`.
  A nova instância é independente e **ainda não** substitui a sessão global
  do `ZTEService` — não instanciar ambas para a mesma ONT num atendimento.
  O próximo passo é injetar o driver no futuro `ConnectionCoordinator`.
- Fabricantes novos implementam o `DeviceAdapter` de aplicação em
  `infrastructure/<vendor>/adapters/`, com seu próprio transporte,
  autenticação, leitura, escrita e verificadores.
  Uma leitura bem-sucedida não habilita novas escritas automaticamente.

`get_lan_config` / `set_lan_config` no ThinkLua inicial tratam apenas DHCP
(preservam IP da interface LAN). `set_wifi_config` recebe
`{"ssid_id": "AP1", "changes": {"ssid": "novo"}}`.
`verify_change("lan.dhcp", {"basic": {"ServerEnable": "0"}})` e
`verify_change("wifi.ssid", {"id": "AP1", "ssid": "novo"})` exigem
leituras novas do equipamento e alvo explícito. Senha não é comparável
ao valor mascarado de `wifi_networks(reveal_password=False)`: a escrita
legada confirma PSK por releitura privada dentro de `_verify_ssid`.

**Homologação:** o novo runtime só habilita escrita para modelos realmente
identificados pelas classes F6600P/F670L do catálogo existente. Outras
famílias, **inclusive F6201B neste novo caminho**, ficam em inspeção
somente leitura; a operação F6201B já existente continua no fluxo
capturado, isolado e condicionado ao firmware exato. Não significa que
o driver genérico da F6201B foi homologado.

## Alterações auditadas pela fachada em produção

`_run_change` agora delega ao `AuditedOperation` **dentro do RLock já
existente** e devolve o **mesmo objeto da ação**, preservando o shape HTTP
atual. Sempre faz captura prévia, um único envio e pós-leitura. Não repete
um POST por falha de auditoria, leitura ou persistência SQLite.

| Resultado | Condição | `success` no novo histórico |
|---|---|---|
| `verified` | pós-leitura válida e verificador específico retornou `True` | `true` |
| `accepted` | ação aceita e pós-leitura válida, mas sem verificador configurado | `false` |
| `uncertain` | pós-leitura falhou, pré-leitura indisponível para verificar, ou valor não corresponde ao esperado | `false` |
| `failed` | ação lançou erro ou retornou explicitamente `False`/`success:false` | `false` |

`ssid_update` e `dhcp_basic` foram conectados aos verificadores
específicos em `application/operations/verifiers.py`. As demais mutações
legadas que usam `_run_change` ficam `accepted` ou `uncertain`
até que os leitores equivalentes e campos esperados de cada firmware
sejam mapeados e testados; diferença genérica de snapshots nunca prova
alteração pretendida. O fluxo direto F6201B e comandos fora de
`_run_change` **ainda não migraram** para este executor.

`HistoryRepository` aplica migração não destrutiva `outcome TEXT`,
aplica redação recursiva a entradas JSON antes do SQLite e mantém
`save_change(..., success=...)` dos clientes legados. Histórico antigo com
`success=1` é classificado `legacy_success_unverified`: os dados não
permitem inventar uma prova de releitura retroativa. O relatório de
atendimento agora mostra a distinção sem misturar eventos de outras sessões.

Limite: a nova redação protege valores associados a chaves de segredo
(password/passphrase/token/cookie/psk etc.) em mapas aninhados. Conteúdo
livre como XML cru ou textos arbitrários contendo senhas exige política de
armazenamento separada; não introduzir captura de requisições brutas em
`save_change` sem um parser/redator especializado.

## Como testar

```bash
python -m unittest tests.test_verified_audit tests.test_runtime_device_contract -v
python -m unittest discover -s tests -v
python -m compileall -q apps config tests
```

Os testes de contrato usam **FakeZTE** sem conexões físicas e asseguram:
falta de prova não vira `verified`, falha de pós-leitura vira `uncertain`,
erro de banco não reenvia o POST, segredos não ficam no SQLite/log,
migração histórica conserva dados, sessões de identidade alterada
bloqueiam escrita e modelos desconhecidos permanecem read-only.

### Homologação física pendente (obrigatória)

Em bancada autorizada e com backup: executar DHCP e SSID num
F670L e F6600P, coletar estado antes/depois sem senhas, simular resposta
`SUCC` sem persistência, timeout pós-POST, troca do destino por VPN,
repetir na mesma sessão e registrar
`modelo × firmware × operação × POST × releitura × data`.
Não marcar novos fabricantes/versões como homologados só porque
o contrato Python ou a CI passa.

## Continuidade, não incluída neste PR

Fase 2: extrair `DeviceRegistrar`, depois `ConnectionCoordinator`;
implementar `/desktop/capabilities` e migrar clipboard sem usar
`navigator.userAgent`. CSS fica fora deste PR. Preservar a sessão HTTP
única e nunca quebrar `menuView → menuData → POST`.

# Descoberta ZTE Tracker — funcionamento e limites (2026-09)

## Por que a tela anterior aparecia como "Não detectado"?

Havia duas consultas independentes, mas só uma desenhava cards no painel:
o catálogo genérico de menus ThinkLua retornava **candidatos**, sem iniciar
leitura ao abrir Avançado. O botão **Detectar modelo** devolvia texto JSON no
`multimodelProbeOutput`, mas **não atualizava** `capabilityGrid`. Uma leitura
HTTP 200 com XML sem objeto esperado também podia ser indevidamente classificada
como disponível pelo gateway genérico.

A atualização separa os dados em **Recursos por firmware — zte_tracker** e
**Inspeção avançada ThinkLua**. Ao abrir Avançado a sessão é consultada para
obter o modelo real; os dois primeiros endpoints documentados são validados
automaticamente (somente GET). **Detectar modelo** testa até 10 candidatos,
**Detectar recursos** percorre os menus do adaptador nativo quando compatível.
Cards distinguem confirmado / não confirmado / ainda não testado e preservam
mensagens explícitas quando o login não expõe determinado menu.

## Inventário do zte_tracker consultado

O `zte_tracker/zteclient/zte_client.py` declara **16 nomes** organizados
em quatro perfis básicos e duas especializações:

| Perfil | Nomes da matriz upstream | Diferença comprovada em documentação upstream |
| --- | --- | --- |
| F6640 | F6640, F6645P, F680 | Clientes `wlan_client_stat_lua.lua`; LAN `accessdev_landevs_lua.lua`; WAN `wan_internetstatus_lua.lua` |
| F6640 | F6600P | Mesmo perfil, mais PON `optical_info_lua.lua`; topologia `topo_lua.lua` é candidata |
| F6640 | F8748 | WAN com contadores (unidade DIGI/PT citada no upstream) |
| H288A | H288A, H169A, H3600P, H3640, H6645P, H6745 | Clientes `accessdev_ssiddev_lua.lua`; WAN `wan_internetstatus_lua.lua` |
| H388X | H388X | Usa alternativa WAN `wan_internet_lua.lua` |
| H2640 | H2640 | DSL `dsl_interface_status_lua.lua`; requisito diferenciado de checksum de reboot **não implementado** |
| E2631/Vue | E2631 (AX3000), SR7410 (BE7200 Pro+), SR7110 | GET `vueData` com tags `vue_client_data`, `localnet_lan_info_lua`, `vue_mainwan_data` |

**F670L** é implementação pré-existente do Access Manager, não integra a
matriz oficial de modelos verificados do upstream consultado. Seus menus
podem variar por firmware e operadora.

## Implementado nesta alteração

- Acrescentado SR7110 e metadados de diferenças específicas.
- Perfis expõem SSIDs (F6640) e dados de identificação (ThinkLua), e somente
  F6600P tenta óptica GPON no detector.
- A tela consulta modelo real automaticamente sem troca silenciosa de família.
- Leitura inicial de dois endpoints; varredura expandida manual em até dez.
- Resposta válida exige XML ThinkLua, sucesso e objeto específico:
  HTTP 200 com HTML de login ou XML de outro menu **não** confirma recurso.
- Respostas da descoberta são estruturais (nomes de campos filtrados e
  contagens); não contêm valores de clientes.
- Rotinas de **escrita não foram copiadas** do tracker: mudanças de senha,
  WAN, Mesh, reinício e restauração são arriscadas quando os endpoints da
  operadora diferem. A existência de endpoint de leitura NÃO habilita escrita.
- Scripts de regressão e fluxo de CI verificam inventário, parsers, UI e
  identificação de HTTP 200 falsos.

## Homologação necessária

Os testes automatizados usam fixtures, não equipamentos reais.
Em bancada, anotar modelo exibido, firmware e operadora, botão selecionado,
tempo de execução e status de cada recurso. Para F6600P, testar inicialmente
clientes, WAN, SSIDs e PON; verificar se a página de login não substitui o XML.
Para Vue, testar login e `vueData` separadamente; para H2640, não interpretar
DSL sincronizada como Internet ativa. Antes de habilitar escrita para qualquer
modelo novo, realizar validação com aparelho de testes, snapshot e rollback.

Fonte técnica estudada: github.com/juacas/zte_tracker (GPL-3.0); perfis e
terminologia referenciados, implementação Python/UI escrita independentemente.
Nenhum módulo upstream GPL foi incorporado.

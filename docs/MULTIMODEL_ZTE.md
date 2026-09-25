# ZTE Automatic — Multi-model / Read-only discovery

Esta etapa incorpora à aplicação um catálogo de quinze modelos de ZTE
documentados no projeto independente **juacas/zte_tracker**:

- F6640, F6645P, F680, F6600P, F8748: família ThinkLua F6640.
- H169A, H288A, H3600P, H3640 V10, H6645P V2, H6745 V3: família H288A.
- H388X: família H388X, cujo menu WAN diverge do H288A.
- H2640: família H288A com estatísticas **DSL** separadas de conectividade à Internet.
- E2631 (AX3000) e SR7410 (BE7200 Pro+): família **Vue** (`_type=vueData`).

O F670L já possuía adaptador anterior e continua no projeto.

## Status REAL (não é certificação de firmware)

| Família / modelos | Implementado nesta etapa | Limitação |
| --- | --- | --- |
| F6640 / F6645P / F680 / F8748 | Seleção, probe estrutural, menus legados de clientes, WAN em modo leitura, resumo Mesh se houver endpoint | Configuração, backup, firmwares de operadoras e Mesh real exigem teste físico |
| F6600P | Recursos anteriores preservados; probe multi-modelo e resumo Mesh adicionados | Firmware específico e Mesh requerem validação |
| H169A / H288A / H3600P / H3640 / H6645P / H6745 | Seleção, leitura normalizada de clientes Wi-Fi/LAN, probe por família e inspeção de WAN | Escrita deliberadamente bloqueada |
| H388X | Leitura de clientes e candidato WAN alternativo `wan_internet_lua.lua` | Escrita deliberadamente bloqueada |
| H2640 | Leitura de clientes e inspeção separada da linha DSL | DSL sincronizada não implica Internet conectada; sem escrita |
| E2631 / SR7410 | Autenticação `loginData` existente com seleção e probe `vueData`, leitura de clientes em hipótese de XML compatível | Dependem de teste real Vue por firmware; não usar menus ThinkLua nem escrever |
| F670L | Implementação anterior preservada | Nem todas as versões de operadoras possuem mesmos recursos |

**Todos os endpoints são candidatos até retornarem resposta válida no equipamento.**
Ter o nome na lista não significa que login, serviços e manipulação do firmware
tenham sido testados em unidade real; tampouco significa que todo recurso esteja
disponível com credencial restrita.

## Segurança para atendimento

- Modelos recém-cadastrados entram em **modo somente leitura**. Após login,
  o transporte HTTP do cliente bloqueia quaisquer POSTs subsequentes,
  inclusive ações que ignorem o helper central `post_menu`.
- A F670L e a F6600P mantêm o comportamento de escrita anterior.
- Ao conectar em modelos não validados, o app abre a área **Avançado**,
  sem executar rotinas específicas de aplicação de perfil F670L.
- O probe estrutural retorna **contagens e nomes não sensíveis**; nunca retorna
  valores dos registros. Em relatórios públicos, ainda é preciso revisar
  metadados, tags e nomes dos campos do firmware.
- A consulta Mesh (família F6640) retorna **apenas contagens agregadas**:
  dispositivos, agentes e tipos de conexão; não inclui MAC, IP, SSID,
  hostname ou nome de nó.
- As leituras de clientes contendo MAC/IP/host são usadas na interface local
  do atendimento; não exportar dados de clientes para issues públicas.

## Como validar em bancada

1. Escolha um modelo na tela de conexão caso o status inicial não identifique
   automaticamente o equipamento. A URL pode precisar de HTTPS conforme o
   firmware; use apenas credenciais de laboratório autorizadas.
2. Para modelos fora F6600P/F670L, a sessão entra em modo leitura.
3. Na página **Avançado**, selecione o modelo e execute **Detectar modelo**.
   Inspecione quais endpoints responderam e quais retornaram erro tipado.
4. Execute **Detectar recursos** para os perfis ThinkLua; modelos Vue usam
   apenas o detector multi-modelo específico, sem tentar `menuView`.
5. Teste **Clientes** (Wi-Fi e LAN) para confirmar o parser real de cada
   operadora/firmware. A resposta XML vazia é válida se o objeto existir
   sem clientes.
6. Para a família F6640, execute **Resumo Mesh**, se o equipamento tiver
   nós configurados. Falha significa "não confirmado", não ausência física.
7. Registre modelo, versão de firmware, operadora, resultado por endpoint e
   mensagem de erro sem cookies, chaves, senhas, MACs ou IPs do cliente.

## Referência, licença e limites

Documentação consultada: https://github.com/juacas/zte_tracker (GPL-3.0),
especialmente seus perfis públicos de endpoints e formatos XML/JSON ThinkLua
e Vue. Esta implementação de testes, despacho e parsers foi escrita
independentemente: **não incorpora módulos GPL** do zte_tracker.

O projeto zte_tracker declara modelos em sua matriz, mas versões de firmware
e restrições da operadora diferem. O pipeline CI usa mocks, não roteadores reais.
A validação cruzada Windows/Linux requer equipamentos físicos por família.

# Auditoria de funcionalidades — ZTE Automatic (Windows / modelos ZTE)

Esta é uma **auditoria de código e testes com mocks**, não uma certificação
de que todas as ONTs/roteadores ou firmwares de operadoras estejam homologados.
As quinze referências vieram do catálogo público do projeto juacas/zte_tracker;
nenhum módulo GPL foi copiado.

## Varredura por área

| Área | Encontrado no aplicativo | Correção/estado desta alteração |
| --- | --- | --- |
| Sessão/login | `loginData`, estado local na camada de serviço, retomada de SPA após refresh | Evitar sondar status ThinkLua durante login Vue; exigir que o modelo pesquisado corresponda à sessão atual |
| Inventário | Modelo/firmware, serial, estado, agentes, perfis, incidentes | Fluxos preservados; registro não deve bloquear login |
| Diagnóstico | GPON/WAN, portas LAN, PPPoE, RF, DNS, ping, traceroute, Wi-Fi, clientes, teste de velocidade, relatório | Novo **Diagnóstico por modelo** sem nenhum POST na ONT para famílias ainda não homologadas; os erros por seção não invalidam o restante |
| Recursos | Catálogo, sondagem de menus, leitura estrutural sem valores | Perfil específico por família; UI informa quando menu ThinkLua não se aplica ao Vue |
| Backup/snapshot | Exportação, persistência, histórico, comparação, APIs de restauração | Mensagem explícita em perfil não homologado em vez de aparentar clique inerte; funções existentes permanecem para F670L/F6600P |
| Wi-Fi | SSIDs, RF, canais, WPS, potência, Band Steering, agendamento | Operações de escrita não são extrapoladas automaticamente a outras famílias |
| Gestão WAN/LAN | IPv4/IPv6, DHCP, DNS, reservas, NAT, UPnP, bridge, filtros, QoS, SNTP/TR-069 | Rota e telas existentes auditadas; escritas dependem de firmware e autorização explícita |
| Mesh | Status e pareamento F670L; JSON topo com contagens na família F6640 | Não atribuir suporte Mesh a outras famílias sem resposta real de endpoint |
| Windows | Clipboard, CSS zoom, atalhos, indicadores | Clipboard nativo também no Gerenciamento; zoom sem aplicar escala à raiz; status HTTP visível em qualquer operação, com erros; atalhos Probe/Auto diagnóstico passam a executar ações; páginas disparadas pelo topo carregam seus dados |

## Matriz de diferenças por família

| Modelos | Firmware / endpoint público candidato | Testável sem escrita | Ainda não homologado |
| --- | --- | --- | --- |
| F6640, F6645P, F680, F8748 | Família F6640: `wlan_client_stat_lua.lua`, `accessdev_landevs_lua.lua`, `wan_internetstatus_lua.lua` | Identificação, clientes, WAN, contagens Mesh quando `topo_lua.lua` responde | Backup, alteração Wi-Fi, firewall, WAN, gestão Mesh de cada operadora |
| F6600P | Família F6640 + adaptador legado | Rotas anteriores, leitura, probe e topologia | Validar cada firmware antes de usar escrita em produção |
| H169A, H288A, H3600P, H3640 V10, H6645P V2, H6745 V3 | Família H288A: `accessdev_ssiddev_lua.lua`, WAN status, LAN | Clientes, WAN e dados de equipamento | Escritas/backup por revisão |
| H388X | WAN alternativa `wan_internet_lua.lua` | Clientes, WAN alternativa | Operações de escrita e versão de operadora |
| H2640 | DSL `dsl_interface_status_lua.lua` | Métricas DSL **separadas** de WAN/Internet | Reboot/Check específico e escrita DSL |
| E2631 / AX3000, SR7410 / BE7200 Pro+ | `vueData`: `vue_client_data`, `localnet_lan_info_lua`, `vue_mainwan_data` | LoginData + leitura experimental Vue; identificadores no relatório público são excluídos | Configuração completa Vue, parser por revisão, backup, firmware |
| F670L (pré-existente) | ThinkLua F670L com exceções Oi Brasil | Rotas e escrita anteriores, sujeito a autenticação real | Comparar firmware real e validar hardware antes de afirmar suporte total |

`sucesso HTTP 200` **não** confirma disponibilidade de endpoint: parsers
verificam XML, objeto esperado e mensagens de erro. Para Vue, o teste real do
firmware é especialmente necessário.

## Interface e relatórios

- O topo **Probe** abre Avançado, carrega o catálogo e executa detecção.
- **Auto diagnóstico** executa uma triagem sem remediação/Speed Test pesado;
  o formulário continua disponível para o relatório completo.
- **Gerenciamento** abre e atualiza inventário/dados, mesmo quando usado pelo
  topo, não apenas pela sidebar.
- Cada chamada de API sinaliza carregamento e sucesso/erro no indicador de
  status, inclusive funcionalidades que antes não mostravam overlay.
- Zoom de 80% a 160% permanece salvo no navegador; corpo com largura
  compensada evita recortar topo sob QtWebEngine ao ampliar, com grades
  redimensionáveis e rolagem interna em saídas técnicas.
- Rejeitar recursos não homologados **com motivo**, sem enviar POST ao cliente.

## Homologação antes de publicar para atendimento

Executar no Windows com firmware real de cada família: login + acesso somente
leitura, abrir atalhos, detectar recursos, diagnóstico por modelo, clientes,
topologia quando documentada, zoom (80%, 100%, 125%, 150%, 160%), clipboard e
recuperação da SPA. Repetir pelo menos 2 vezes, confirmar que o equipamento
**não perde a sessão** e que nenhum POST de configuração ocorre na família
experimental. Para operações com mudança, usar laboratório e backup de
configuração válido antes da ativação em produção.

**Privacidade:** não subir logs que contenham session token, SSID de cliente,
MAC/IP, serial ou senhas; compartilhar apenas matriz de resultados e metadados
sanitizados.

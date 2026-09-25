# F6201B V9.3.10P7N7 — segunda captura e adaptadores específicos

## Evidência nova e proteção de segredos

O proprietário forneceu **209 eventos HTTP**, sendo **179 GETs** e
**30 POSTs**: **28 Apply**, 1 PingDiagnosis, 1 TraceRouteDiagnosis. As
respostas registradas dos 30 POSTs incluem `IF_ERRORID=0` além de
HTTP 200. Isso demonstra que o firmware reconheceu aqueles comandos
nas circunstâncias da captura; não garante que o código os reproduzirá
com sucesso em qualquer outra configuração.

**Nunca versionar o JSON de captura bruto**: ele pode conter senha de
Wi-Fi, credenciais PPPoE/ACS, cookies, tokens temporários, dados de
clientes e configuração administrativa. Este PR contém somente
`f6201b_evidence.py`, com tags, vistas, nomes e ordenação de campos,
sem os valores originais.

A segunda captura corrigiu detalhes concretos do mapeamento:
- MenuView obrigatória por rota, incluindo `ethWanConfig`,
  `ethWanStatus`, `wlanBasic`, `wifibandsteer`, `dns` etc.
- `wan_internetstatus_lua.lua`: `TypeUplink=2&pageType=1` e objeto
  `ID_WAN_COMFIG` validado; `wan_internet_lua.lua` configuração usa
  `pageType=0` em outra vista.
- `wlan_wlansssidconf_lua.lua`: o XML possui **três blocos
  `<encode>` separados**. O primeiro contém parâmetros administrativos;
  o último contém `KeyPassphrase`. O parser anterior descartava os
  últimos, impedindo descriptografia/preservação correta da senha.
- Dois `Apply` SSID observados; serialização segue a **ordem exata**
  de campos do formulário capturado e exclui botões sintéticos de
  outras versões do firmware.
- Respostas de RF avançado podem exceder o limite de coleta de 30 KB.
  Um XML truncado no arquivo de captura NÃO autoriza fabricar valores;
  as informações são lidas e validadas diretamente na ONT autenticada.

## Escopo integrado

### Leituras
- Catálogo complementar de rotas, menuView/GET com parâmetros corretos
  e identificação real de WAN status (inclusive cards antigos com
  VLAN, IP, MTU e DNS, somente na interface local, sem credenciais).
- Radio avançado: canal, largura, padrão, potência, SGI e AutoChannel
  apenas se resposta XML atual estiver completa.
- Mesmas telas antigas de Wi-Fi, WAN, Clientes, Dashboard e Diagnóstico;
  a interface não muda para outros modelos.

### Gravações controladas
O opt-in permanece **desligado por padrão**. Quando habilitado
(`ZTE_F6201B_EXPERIMENTAL_WRITES=1`), o F6201B com firmware e modelo
revalidados na sessão atual expõe:

1. **SSID**: nome, senha PSK quando verificável, habilitar, broadcast, isolamento e limite de clientes; prévia sem POST, nonce único
   de 120 segundos, confirmação `APLICAR F6201B`, replay bloqueado,
   leitura PSK com os 3 blocos `<encode>`, serialização igual à captura
   e verificação pós-POST.
2. **DNS IPv4/IPv6**: servidores principais/secundários; captura
   comprova um Apply com o body de 7 campos. A função preserva o DNS
   IPv6 atual, valida IP, exige prévia/nonce/confirmação específica
   `APLICAR DNS F6201B`, envia o body na ordem original e confirma
   releitura. Não repete automaticamente um POST cuja resposta foi
   ambígua.

As gravações permanecem protegidas pelo lock da sessão. Fora de um
Apply específico, `session.post` continua bloqueado. Falhas também
restauram o bloqueio.

Outros Apply foram **mapeados, não executados automaticamente**:
WAN/PPPoE, DHCP/IPv6, WPS, Band Steering, Mesh, RF completo,
firewall/DMZ, UPnP e TR-069. Exigem adaptadores e testes dedicados:
um corpo capturado não demonstra preservação segura de todos os
campos em qualquer estado da ONT.

## Testar sem alterar a ONT

```powershell
git switch main
git pull --ff-only origin main
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
Remove-Item Env:ZTE_F6201B_EXPERIMENTAL_WRITES -ErrorAction SilentlyContinue
python manage.py runserver
```

Confirme identificação do F6201B, leituras, cartões nativos, RF,
WAN e diagnóstico. Teste também F6600P após desconectar, garantindo
que nenhum card experimental persista.

## Primeiro teste de escrita, SOMENTE em ONT própria/autorizada

Com backup e acesso local **preferencialmente via cabo**:

```powershell
$env:ZTE_F6201B_EXPERIMENTAL_WRITES = "1"
python manage.py runserver
```

Na aba Wi-Fi, altere um SSID de laboratório com prévia e confirmação.
No formulário **Configuração padrão**, a ação específica de DNS aparece
somente no F6201B confirmado. Evite alterar SSID da própria conexão
usada para acessar a ONT; mudanças podem desconectar o atendente.

A validação automatizada usa fakes: **a aplicação física dos comandos
permanece pendente até confirmação no seu equipamento**. Em resposta
ambígua, consulte a interface original antes de reenviar; nunca
remova os bloqueios para contornar erros.


## Atualização do laboratório: perfil DNS completo e senha Wi-Fi

O perfil experimental do atendente agora prepara separadamente as
alterações de rádio, servidores DNS IPv4 e IPv6, domínio DNS e nomes
estáticos de DNS (somente inclusão/atualização, sem apagar entradas
externas). Cada formulário corresponde a uma requisição capturada
diferente. A prévia informa todas as diferenças; a execução confirma
a releitura de cada etapa e PARA após a primeira inconsistência.

Na aba Wi-Fi, o editor próprio de cada SSID passou a permitir também
trocar senha PSK, isolamento de clientes e limite de clientes. A senha
não é devolvida pelo preview nem impressa em logs. A troca exige que
o firmware exponha a PSK anterior com formato de criptografia
comprovado; redes abertas ou WEP exigem configuração manual prévia
do modo de segurança.

**Não existe botão seguro de "liberar todo e qualquer POST"**: as 25
rotas Apply registradas têm formatos, dependências e efeitos diferentes.
WAN/PPPoE, TR-069/ACS, DHCPv6, firewall/DMZ e outras rotas permanecem
disponíveis para inspeção via catálogo capturado, mas não são
executadas como parte do perfil de atendente; isso exigiria que o
usuário fornecesse um formulário de configuração próprio para cada
recurso, com backup e validação de todos os campos.

Antes de validar em hardware, fazer backup da ONT e conectar por
Ethernet. Mudanças de rádio, senha ou DNS podem perder a conexão.
Nenhum POST ambíguo é repetido automaticamente; **não há rollback
geral**. Se o relatório indicar aplicação parcial, confira o estado
atual no painel original antes de executar outra tentativa.

# Access Manager — revisão de acesso, comandos e compatibilidade

## Objetivo

O operador escolhe as configurações a aplicar na sessão autenticada do próprio
equipamento. O nome do atendente identifica somente o perfil salvo e o histórico
local: não constitui uma função de segurança nem limita DHCP, WAN, DNS, rádio ou
outras operações. Os serviços não exigem variável de ambiente, frase digitada
ou confirmação booleana adicional antes de executar uma operação solicitada.

## O que continua obrigatório por motivos técnicos

- O **roteador** precisa autenticar a sessão e aceitar o recurso no firmware.
  Permissões nativas rejeitadas pela ONT não podem ser substituídas pelo app.
- Para os comandos F6201B capturados, conferir o modelo retornado pela ONT,
  firmware V9.3.10P7N7, objeto XML, campos do menuView e identidade da
  instância. Modelos ainda não mapeados não recebem os POSTs de outra família.
- A assinatura RSA/Check, token efêmero e cookies continuam enviados pelo
  transporte original. O estado da sessão é serializado pelo RLock.
- A aplicação de SSIDs preserva a PSK existente, exige validação do formato
  criptografado e não devolve senhas em relatórios. Os formulários WAN/ACS
  também não expõem segredos na interface.
- Antes dos comandos a ONT é relida, apenas campos válidos/alterados seguem
  para POST e há verificação posterior. Respostas ambíguas não geram reenvio.
- O aviso de impacto operacional não é uma permissão adicional do aplicativo.

## Operações conectadas

1. **Perfil Wi-Fi/DNS** F6201B: um clique salva o padrão local e envia
   alterações em rádios/DNS com leitura anterior e posterior no mesmo lock.
   A seleção de perfil não está restrita ao nome do atendente.
2. **SSID, DNS e comandos avançados**: a UI usa rotas `/update` específicas
   por modelo; o backend mantém preflight e nonce *internamente*, sem pedir
   outra ação ou digitação do operador. O catálogo contém 25 capturas Apply;
   quatro aproveitam os adaptadores existentes e as demais possuem estratégias
   específicas, condicionadas ao formulário real recebido.
3. **DHCP IPv4**: leitura de configuração, faixa, concessões, DNS e gateway.
   A edição exige o formulário completo da ONT. Os cinco campos IPv4
   criptografados (IP LAN, início/fim do pool, DNS1/2) são descriptografados
   com o token vigente do GET e recodificados em AES/RSA no POST, conforme
   a captura original. Valida IP/máscara, intervalo e tipos; a gravação de
   gateway só é oferecida se o GET do próprio dispositivo expuser um campo
   verificável. As ações não são filtradas
   por atendente. Concessões e DHCPv6 são lidos independentemente. O painel
   DHCPv6 expõe alteração somente após receber todos os campos necessários
   do formulário capturado.
4. **Ping/Traceroute** F6201B: usam `networkDiag`, os POSTs capturados
   `PingDiagnosis` e `TraceRouteDiagnosis` (com Check/token reais) e polling
   por resultado novo. Retornam min/média/máx/perda e saltos estruturados.
   Não executam testes no computador como se fossem da ONT.
5. **DHCP dos modelos nativos já suportados**: valida intervalos e confere
   persistência por nova leitura antes de responder sucesso.

## Pontos não homologados por este conjunto de testes

- Os novos fluxos foram testados com ONTs sintéticas/mocks, não por acesso
  físico à rede privada de um cliente. A captura do operador documenta os
  métodos e parâmetros, mas os novos POSTs e readbacks precisam ser comparados
  no equipamento real.
- A captura do DHCP F6201B apresenta `IPRouters` vazio no POST e não
  retorna esse campo no GET; nesse formulário específico não se pode
  declarar persistência ou liberar edição de gateway sem nova evidência.
- O POST de *reserva DHCP F6201B* não foi comprovado na captura disponível;
  o painel não declara gravação de reservas nesse modelo, mas os adaptadores
  nativos de reservas dos modelos anteriores continuam existindo.
- A captura de Ping/Traceroute F6201B não descreve campos de interface nem
  seleção IPv6 no POST. Esses controles são rejeitados com explicação explícita
  nesse firmware, não ignorados silenciosamente. Outros modelos preservam
  o fluxo legado. Não inferir equivalência entre modelos/versões.
- WAN, TR-069 e demais formulários complexos exigem a *mesma* sequência
  menuView/menuData e os campos condicionais capturados. Se um login não
  disponibilizá-los, o equipamento não é alterado.
- A interface clara reutiliza os tokens centrais `--ui-*`, incluindo o
  novo painel DHCP. Auditoria visual em monitor real e testes de ONT
  continuam distintos dos testes automatizados.

## Verificações automatizadas

- Unitários Python: sessão/nonce, tradução de formulários, confirmação por
  releitura, falhas ambíguas e restauração do transporte, descoberta DHCP,
  valores inválidos e comandos Ping/Traceroute com HTTP sintético.
- Contratos Node: não remover componentes nativos, não recriar RBAC nem
  confirmações digitadas nos editores F6201B, sintaxe JS, campos DHCP/Ping,
  preservação das seções 2,4 e 5 GHz e modo claro/escuro.
- CI GitHub Actions roda o conjunto do projeto e os novos contratos.

Não são criados papéis internos de administrador, operador ou atendente
para autorizar funções. O campo atendente é metadado de perfil/histórico.

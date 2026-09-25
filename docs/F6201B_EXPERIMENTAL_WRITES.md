# F6201B — implementação experimental de configuração

## O que o mapeamento realmente demonstra

O mapeamento fornecido para F6201B V9.3.10P7N7 descreve 93 combinações de rota, mas uma única requisição POST, com IF_ACTION=Cancel em wan_internet_lua.lua. Não há POST Apply de Wi-Fi, WAN ou DNS. Portanto nenhuma alteração real nesses subsistemas está homologada para o firmware, e GETs bem-sucedidos não demonstram capacidade de escrita.

## O que foi implementado neste PR

- Adaptador experimental de edição supervisionada de SSID: renomear, habilitar/desabilitar e transmitir/ocultar nome.
- Modo desligado por padrão. A liberação exige ZTE_F6201B_EXPERIMENTAL_WRITES=1 definida antes de abrir o Vela.
- Bloqueio das demais operações: o transporte inteiro continua somente leitura fora do breve Apply autorizado, protegido pelo lock da sessão.
- Identificação e firmware exatos confirmados pelo equipamento, preflight do formulário, token, estrutura XML, criptografia de PSK e chave de assinatura quando exigida.
- Prévia de diferenças sem POST, nonce descartável com validade de 120 segundos e confirmação digitada APLICAR F6201B.
- Reutilização da rotina existente ThinkLua de read-modify-write, assinatura e verificação por releitura. Em caso de erro, bloqueio de transporte é restaurado mesmo quando o firmware recusa a operação.
- Interface na aba Wi-Fi e SSIDs; testes unitários com roteador simulado.

IMPORTANTE: isso é infraestrutura experimental para obter a primeira evidência controlada. O mecanismo POST Apply pode diferir do adaptador já suportado e falhar no preflight. Não remova as validações para fazê-lo passar. Faça o primeiro teste em ONT própria/autorizada com acesso local, preferencialmente conectado por cabo; renomear SSID pode derrubar o acesso remoto.

## Testar separadamente na branch

No Windows PowerShell, na raiz do repositório:

    git fetch origin
    git switch -c teste-f6201b-write --track origin/feat/f6201b-guarded-write-adapter
    .\.venv\Scripts\Activate.ps1
    pip install -r requirements.txt
    $env:ZTE_F6201B_EXPERIMENTAL_WRITES = "1"
    python manage.py runserver

Conecte ao F6201B e abra a aba Wi-Fi e SSIDs. A seção independente de edição experimental oferece Consultar SSIDs, Visualizar alterações e Aplicar alterações. Faça a prévia primeiro. Se ela recusar o firmware/menu/tokens/PSK, pare e confira o fluxo original.

## Obter evidência do Apply real sem divulgar dados pessoais

1. Abra no navegador a interface original de um F6201B sob sua autorização, com acesso local e backup.
2. No Console do navegador cole o conteúdo de tools/f6201b_apply_capture.js. Ele captura somente rota, ordem dos nomes de campos, presença de token/Check e nomes de objetos XML, nunca os valores.
3. No painel ORIGINAL da ONT, faça voluntariamente uma mudança pequena em um SSID de teste e clique no botão Aplicar.
4. Execute window.exportF6201BApplyMap() e revise o JSON gerado. Para parar, execute window.stopF6201BApplyMap().
5. Compare o mapa sanitizado com o adaptador experimental. A captura do Apply é necessária antes de declarar a funcionalidade compatível ou expandir escrita para DNS/WAN/radio.

NÃO COMPARTILHE HAR bruto, cookies, headers completos, tokens, valores dos formulários, credenciais PPPoE/ACS ou XML integral.

## Limites

Sem POST Apply validado ainda NÃO é possível afirmar que escrita foi comprovada. O inventário GET e diagnóstico do PR #28 são separados e permanecem operacionais. As áreas não cobertas por POST (WAN, GPON, DNS, gerenciamento etc.) continuam somente leitura.

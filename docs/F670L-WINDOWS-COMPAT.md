# F670L (Oi Brasil) — Windows / diagnóstico de compatibilidade

## Mudanças nesta branch

- O estado GPON `RegStatus=5` é interpretado como O5 operacional na triagem; `O5` textual já era reconhecido.
- O botão **Copiar atendimento** usa área de transferência nativa Win32 no Windows, evitando duas chamadas de clipboard do QtWebEngine envolvidas no encerramento reportado. Outros sistemas continuam com o caminho web/fallback.
- O workspace da interface limita sua largura à área disponível, com cabeçalho flexível em DPI/zoom altos.
- Probe de recursos ocorre em lotes de 3 e preserva recursos já detectados se outro lote falhar. Isso **não** significa que cada endpoint ThinkLua foi verificado para o firmware V9.
- **Mapa do firmware** executa leituras somente dos recursos detectados e mostra apenas nomes de campos, nomes dos objetos e contagens (não valores); inspirado no conceito de suporte estrutural do zte_tracker. Revise os nomes antes de compartilhar.
- Backup rejeita respostas HTML de sessão expirada com HTTP 200; o erro explica que um fluxo específico do firmware pode ser necessário. NÃO há restauração automática.
- Mensagens de backup e snapshot não passam a indicar falha apenas por problemas de atualização do histórico.

## Referência / limites

Projeto estudado: juacas/zte_tracker (GPL-3.0), especialmente README e documentação de integração ThinkLua. O ZTE Tracker documenta rastreamento Wi-Fi/LAN, malha Mesh, status WAN, cache, recuperação e exportação **de estrutura** do firmware. A lista de equipamentos verificados pelo projeto **não inclui F670L** na revisão consultada. Nenhum código GPL do projeto foi incorporado nesta branch e seus endpoints de modelos diferentes não devem ser assumidos como funcionais na F670L V9.

## Teste real necessário na F670L V9.0.11P1N9

1. No Windows, executar **Copiar atendimento** várias vezes e conferir se o executável continua aberto (e o texto chega ao clipboard).
2. Maximizar a janela, ajustar zoom para 110%, 125% e 150%; conferir topo, botões e painel de histórico.
3. Executar probe: anotar quais recursos são classificados como indisponíveis, sem forçar escrita em endpoints desconhecidos.
4. Capturar snapshot, depois consultar **Histórico**; conferir que o ID retornou e se as 7 seções foram preenchidas (cada seção pode conter `_error`).
5. Tentar backup: conferir arquivo binário e tamanho. Se retornar mensagem **HTML**, a ONT não enviou configuração; capturar somente formato/caminho/status HTTP e conteúdo estrutural sem credenciais para desenvolver adaptador específico.

**Nota de segurança:** backup binário e snapshots podem conter dados de clientes e de rede. Não anexar logs brutos ou backups ao GitHub. Para diagnóstico público, remova IPs externos, MACs, SSIDs, tokens, credenciais, serial e nomes.

## Por que ainda precisamos testar no aparelho?

Linux e Windows compartilham a camada HTTP de backend Python; firmware, sessão autenticada e privilégios de acesso costumam explicar divergências de endpoints melhor do que o sistema operacional em si. O protocolo específico de exportação de configuração da F670L V9 ainda não foi comprovado pelo zte_tracker, portanto não foi criado fallback inventado.

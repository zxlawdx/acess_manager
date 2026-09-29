# Diagnóstico operacional para suporte ISP — 29/09/2026

## Fluxos disponíveis no Access Manager

O menu **Diagnóstico completo** inclui roteiros opcionais para problemas comuns:
sem Internet, lentidão, quedas/intermitência, Wi-Fi instável e TV/chamadas.
Cada roteiro prepara *o formulário real existente*; não aciona diagnósticos
nem gravações sem o clique explícito do técnico em **Iniciar diagnóstico**.

As leituras existentes da ONT incluem, quando oferecidas pelo firmware,
registro e potência GPON, estado WAN/PPPoE, estado e negociação LAN, clientes
e RSSI Wi-Fi, consulta DNS nativa, ping, traceroute, bandas, vizinhança RF e
teste de velocidade. O relatório agora destaca ICMP perdido por tentativas
efetivamente reportadas pela ONT, latência média, rota e resultados de
otimização com releitura. Dados ausentes são mostrados como *não medidos*.

O botão separado **Testar conexão deste PC** efetivamente consulta DNS e
faz três conexões TCP com destino público fixo, sem utilizar a ONT. O tempo
médio de conexão TCP e a variação são métricas desse computador. **Não são
jitter UDP, perda ICMP ou evidência direta da conexão do cliente.** O botão
não depende das credenciais da ONT.

### Escolha de canal e segurança operacional

A análise usa canais *realmente retornados* pelo firmware da ONT e redes
vizinhas *realmente lidas*. Um canal com menor interferência relativa não é
necessariamente o de maior throughput, já que uma varredura pontual não
mede airtime, retries e tráfego não Wi-Fi. Apenas com uma diferença mínima
e dados suficientes o programa propõe uma troca de canal e só executa
alteração automática quando o técnico habilitar essa opção.
Releitura independente do estado do rádio confirma a mudança no histórico;
HTTP 200/POST aceito jamais equivale à mudança verificada.

Se a ONT já está em **Auto**, não forçamos um canal fixo pelo algoritmo.
Sem lista validada de canais ou sem scan, nada é gravado por esse diagnóstico.
Confirmação de interferência persistente deve incluir medições em horários
distintos ou vistoria presencial, especialmente no 2,4 GHz.

### Triagem operacional sugerida

| Queixa | Leituras iniciais | Quando continuar |
| --- | --- | --- |
| Sem Internet | GPON, WAN, PPPoE, DNS, ICMP e caminho | Se WAN ativa sem navegação: revisar DNS; se sem GPON: examinar fibra/OLT. |
| Lentidão | Negociação Ethernet, bandas, RSSI, PHY e velocidade | Comparar cabo e Wi-Fi no dispositivo do cliente; picos de CPU/carga não são provados por speedtest. |
| Quedas | Potência GPON, estado WAN, ping em diferentes momentos e histórico | Teste contínuo/OLT é necessário para confirmar intermitência; instantâneo não prova ausência. |
| Wi-Fi instável | RSSI, canal atual, redes vizinhas e banda do cliente | Se possível, verificar airtime, retransmissões e interferência não Wi-Fi com equipamento apropriado. |
| TV/chamadas | Ping, perda, rota, throughput e jitter quando servidor informa | Jitter e latência sob carga exigem métodos e amostras próprios; ainda não são inferidos de TCP. |

Para o técnico, as **medidas adicionais ainda não implementadas** (não
exibir como se estivessem sendo executadas): monitoramento contínuo de
flaps LOS/PPPoE em OLT/ACS, análise MTR longitudinal, latência sob carga e
retransmissões 802.11/airtime real nos firmwares que permitirem, testes
IPv6 ponta a ponta, e BGP/rota pela observabilidade do provedor.

## Referências técnicas

- Ubiquiti, Wi-Fi Troubleshooting Guide:
  https://help.ui.com/hc/en-us/articles/32064585817495-WiFi-Troubleshooting-Guide
  (RSSI de cliente, retransmissões, interferência, airtime e canais).
- Ubiquiti, Channel AI:
  https://help.ui.com/hc/en-us/articles/37367741854743-UniFi-Channel-AI-and-Automated-WiFi-Optimization
  (medição RF seguida de proposta e aplicação explícita).
- RIPE Atlas, Path Analysis:
  https://atlas.ripe.net/docs/tools-and-code/path-analysis
  (comparação longitudinal de rotas em vez de confiar num salto isolado).
- RIPE NCC, Atlas:
  https://www.ripe.net/analyse/internet-measurements/ripe-atlas/how-ripe-atlas-works/
  (ping, traceroute, DNS, TLS, HTTP a partir de pontos de observação).

**Validação pendente:** dispositivos físicos e builds Windows/Linux do novo
commit precisam passar por release CI e por testes reais antes de serem
declarados compatíveis com um firmware específico.

# Mapa do protocolo ZTE usado pelo projeto

Este arquivo separa o que foi observado diretamente no F6600P usado durante o desenvolvimento do que foi inferido a partir do framework ThinkLua público de modelos/firmwares aparentados.

## Fluxo de sessão

1. `GET /?_type=loginData&_tag=login_entry` para obter `sess_token`.
2. `GET /?_type=loginData&_tag=login_token` para obter o challenge.
3. `SHA256(password + login_token)`.
4. `POST /?_type=loginData&_tag=login_entry` com `Username`, hash e `_sessionTOKEN`.
5. Quando `login_need_refresh=true`, `GET /` antes das demais chamadas.

As páginas de configuração mantêm contexto. Por isso o projeto sempre abre o `menuView` correspondente antes do `menuData`.

## POST protegido

O `dataPost()` do firmware ThinkLua faz, em essência:

```text
menuView
  -> extrai _sessionTmpToken
  -> InitialPostData(IF_ACTION)
  -> adiciona &_sessionTOKEN=<token> por último
  -> SHA256(body exato)
  -> RSA PKCS#1 v1.5 do digest
  -> Base64
  -> header Check
  -> POST menuData
```

`apps/zte_manager/model/zte_configuration/zte_post.py` replica esse fluxo. A chave RSA é extraída de `asyEncode()` no HTML/JS da própria ONT para não assumir que firmwares diferentes compartilham a mesma chave.

## Wi-Fi global

Observado diretamente no F6600P V9.0.10P6N34:

```text
menuView: wlanBasic
menuData: wlan_wlanbasicadconf_lua.lua
```

O XML real retornou:

- `DEV.WIFI.RD1` -> `2.4GHz`
- `DEV.WIFI.RD2` -> `5GHz`
- `Channel`
- `AutoChannelEnabled`
- `Standard`
- `BandWidth`
- `CountryCode`
- `SGIEnabled`
- `BeaconInterval`
- `TxPower`
- `QosType`
- `WorkMode`
- `RtsCts`
- `DTIM`
- `MUMIMOEnable`
- `UPLinkMUMIMO` / `DownLinkMUMIMO`
- `UPLinkOFDMA` / `DownLinkOFDMA`
- `TWTSupport`
- `SpatialReuse`
- `OBJ_CHANNEL_ID` com os canais aceitos por país/banda/largura.

O JS público `wlan_wlanbasicadconf_js.lp` confirma que:

```text
UI_Channel = Auto
    AutoChannelEnabled = 1
    Channel = NULL

UI_Channel = manual
    AutoChannelEnabled = 0
    Channel = canal selecionado
```

Ele também recalcula `BasicDataRates`, `OpDataRates`, `11nMode` e `GreenField` quando o modo (`Standard`) é alterado. O builder Python faz o mesmo.

## SSIDs / nomes das redes

```text
menuView: wlanBasic
menuData: wlan_wlansssidconf_lua.lua
```

O projeto lê `OBJ_WLANAP_ID` e expõe SSID, banda, estado, ocultação, segurança, isolamento e limite de clientes em `/api/wifi/networks`.

## WAN / PPPoE

Status observado no F6600P:

```text
menuView: ethWanStatus
menuData: wan_internetstatus_lua.lua
query: TypeUplink=2&pageType=1
```

Configuração/credenciais, corroborada pelos fontes ThinkLua:

```text
menuView: ethWanConfig
menuData: wan_internet_lua.lua
query: TypeUplink=2&pageType=0
```

O backend público declara `UserName` e `Password` em `<encode>`. A UI oficial descriptografa esses campos com AES-CBC usando SHA256 de `_sessionTmpToken` como chave e SHA256 do token invertido como IV. A API mascara a senha por padrão e só retorna o valor revelado quando a UI solicita explicitamente.

## DNS

A mesma `menuView` contém três formulários independentes:

```text
menuView: dns

Nome do domínio:
    menuData: dns_localdns_lua.lua
    campos: DomainName

Servidores DNS:
    menuData: dns_localdns_lua.lua
    campos: SerIPAddress1, SerIPAddress2, SerIPv6Address1, SerIPv6Address2

Nome de servidor:
    menuData: dns_hostname_lua.lua
    campos: HostName, IPAddress
```

Nos fontes ThinkLua, o formulário de domínio e o formulário dos servidores usam o mesmo backend, mas são enviados separadamente. O projeto mantém essa divisão. IPv6 vazio é convertido para `::`, igual ao JavaScript original.

`dns_hostname_lua.lua` junta hosts manuais e entradas aprendidas via DHCP em `ALLDNSHOST`. O projeto filtra DHCP e trata os hosts do perfil como **upsert**: cria ou atualiza os nomes definidos pelo atendente e não apaga entradas extras existentes na ONT. Para uma nova entrada, a UI original usa `_InstID=-1`.

## Ping

```text
menuView: networkDiag
menuData: networkdiag_ping_lua.lua
IF_ACTION: PingDiagnosis
```

O firmware fixa quatro repetições, 56 bytes e timeout de 2000 ms. A interface oficial consulta o resultado a cada 3 segundos; o projeto reproduz esse polling.

## Traceroute

```text
menuView: networkDiag
menuData: networkdiag_traceroute_lua.lua
IF_ACTION: TraceRouteDiagnosis
```

Campos usados: `Host`, `Interface`, `MaxHopCount`, `Timeout`, `Protocol`, `IPVersion` e `Control`. O resultado também é obtido por polling.

## Referências públicas consultadas

- https://github.com/juacas/zte_tracker
- https://github.com/juacas/zte_tracker/issues/54
- https://github.com/juacas/zte_tracker/issues/57
- https://github.com/cmocan/HA_CustomComponents/blob/master/isp_routers/routers/zte_f660.py
- https://github.com/Blinko1987/F6107A-telnet-root-on-AIS-fiber/blob/main/home/httpd/thinklua/template/commpage_status_comm.lp
- https://github.com/Blinko1987/F6107A-telnet-root-on-AIS-fiber/blob/main/home/httpd/webmodules/modules/wlan_wlanbasicadconf_t.lp
- https://github.com/Blinko1987/F6107A-telnet-root-on-AIS-fiber/blob/main/home/httpd/webmodules/modules/wlan_wlanbasicadconf_js.lp
- https://github.com/Blinko1987/F6107A-telnet-root-on-AIS-fiber/blob/main/home/httpd/webmodules/modules/wlan_wlanbasicadconf_lua.lua
- https://github.com/Blinko1987/F6107A-telnet-root-on-AIS-fiber/blob/main/home/httpd/webmodules/modules/wan_eth_config_t.lp
- https://github.com/Blinko1987/F6107A-telnet-root-on-AIS-fiber/blob/main/home/httpd/webmodules/modules/wan_internet_lua.lua
- https://github.com/Blinko1987/F6107A-telnet-root-on-AIS-fiber/blob/main/home/httpd/webmodules/modules/dns_localdns_t.lp
- https://github.com/Blinko1987/F6107A-telnet-root-on-AIS-fiber/blob/main/home/httpd/webmodules/modules/dns_dnsserver_t.lp
- https://github.com/Blinko1987/F6107A-telnet-root-on-AIS-fiber/blob/main/home/httpd/webmodules/modules/dns_hostname_t.lp
- https://github.com/Blinko1987/F6107A-telnet-root-on-AIS-fiber/blob/main/home/httpd/webmodules/modules/dns_hostname_lua.lua
- https://github.com/Blinko1987/F6107A-telnet-root-on-AIS-fiber/blob/main/home/httpd/webmodules/modules/networkdiag_ping_lua.lua
- https://github.com/Blinko1987/F6107A-telnet-root-on-AIS-fiber/blob/main/home/httpd/webmodules/modules/networkdiag_traceroute_lua.lua

Os fontes Blinko1987 são de outro equipamento/firmware e foram usados como referência do framework ThinkLua. Para escrita, o F6600P P6N34 continua sendo a autoridade final.

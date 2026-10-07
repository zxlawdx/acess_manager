# Huawei endpoint provenance

This file records protocol evidence, not universal support. `LOCAL` means observed in an authorized local Access Manager device/capture. `EXTERNAL` means observed in an external source. `PROBED` means Access Manager can safely probe/read and only promotes support after a recognizable parsed response.

| Endpoint / surface | Evidence | Family / model reference | Access Manager status |
|---|---|---|---|
| HTTP `/` with `SSLPort` bootstrap | LOCAL + EXTERNAL | EG8041X6-10 local; EG8145X6-10 external | central transport detects the Huawei-style JS bootstrap and preserves the explicit TLS port (`https://host:80`) |
| `/asp/GetRandCount.asp` | LOCAL + EXTERNAL | EG8041X6-10/X7-10 local; HG8010H/EG8010H, HG8245X6, EG8145V5, EG8145X6-10 external | RandCount; POST preferred with safe GET fallback; trailing 32-hex challenge variant characterized |
| `/login.cgi` | LOCAL + EXTERNAL | multiple Huawei WebUIs | shared auth transport; auth strategy selected before credentials |
| `/html/ssmp/common/getRandString.asp` | EXTERNAL | EG8021V5 | RandString auth strategy implemented; physical validation pending |
| `/html/ssmp/common/GetRandToken.asp` | EXTERNAL | EG8021V5 | private post-login token acquisition implemented; physical validation pending |
| `/html/ssmp/deviceinfo/deviceinfo.asp` | LOCAL + EXTERNAL + PROBED | EG8041X6/X7 local; EG8021V5/EG8145V5 external | device reader + model/firmware/CfgMode evidence; parser success required |
| `/html/amp/opticinfo/opticinfo.asp` | LOCAL + EXTERNAL + PROBED | EG8041 family; HG8010H/EG8010H, EG8021V5, EG8145-class references | existing optical reader; normalized telemetry accepts only characterized signatures |
| `/html/status/opticinfo.asp` | EXTERNAL + PROBED | older HG8010H generation | read-only alternate optical endpoint; `stOpticInfo/6` characterized |
| `/html/bbsp/common/ontstate.asp` | EXTERNAL + PROBED | EG8021V5 and compatible generated WebUI references | read-only PON state reader; capability promoted only on parser success |
| `/html/bbsp/common/getwanlist.asp` | LOCAL + EXTERNAL + PROBED | EG8041 family and multiple AMP/BBSP references | WAN list/service discovery; object path is retained for diagnostics instead of hardcoding `WANPPPConnection.1` |
| WAN traffic-stat pages under `/html/bbsp/common/` | EXTERNAL | EG8021V5 / current OptiXstar integrations | read only when a recognizable counter surface exists; absent counters remain `None` |
| `/html/amp/ethinfo/ethinfo.asp` | LOCAL/EXTERNAL by firmware + PROBED | EG8041/EG8021 references | Ethernet capability promoted only after parsed reader succeeds |
| `/html/amp/wlanadv/WlanAdvance.asp?2G` | LOCAL + PROBED | EG8041X6-10 and existing X7 mapping | shared EG8041 2.4 GHz advanced read/object signature |
| `/html/amp/wlanadv/WlanAdvance.asp?5G` | LOCAL + PROBED | EG8041X6-10 and existing X7 mapping | shared EG8041 5 GHz advanced read/object signature |
| `/html/amp/common/WlanChannel.asp?1=1` | LOCAL + PROBED | EG8041X6/X7 | dynamic channel discovery; normalized `SUPPORTED.channel` uses firmware result when available |
| `/html/amp/wlanadv/set.cgi` | LOCAL captured + existing X7 validation | EG8041 family | shared mapped mutation surface; POST once + readback. X6 captured surface is not itself physical write validation |
| `/html/amp/wlaninfo/wlaninfo.asp` | EXTERNAL | EG8021V5 | Wi-Fi reference only; family mapping remains runtime-gated |
| `/html/bbsp/common/GetLanUserDhcpInfo.asp` | LOCAL/EXTERNAL by firmware | generated AMP/BBSP | LAN-client evidence; family runtime deduplicates conservatively by normalized MAC |
| `/html/bbsp/common/GetLanUserDevInfo.asp` | EXTERNAL | HG8245X6 / EG8145V5 references | alternate LAN-client surface; family-specific discovery required |
| `/html/bbsp/userdevinfo/getuserdevinfo.asp` | EXTERNAL | EG8145X6-10 / OptiXstar references | alternate client surface; not auto-enabled |
| `/html/bbsp/maintenance/diagnosecommon.asp` | LOCAL | EG8041X6/X7 | native ONT diagnostics page |
| `/html/bbsp/maintenance/complex.cgi?...IPPingDiagnostics...` | LOCAL + PHYSICAL | EG8041X6/X7 | native ping start; single mutation request, controlled polling |
| `/html/bbsp/maintenance/GetPingDnsResult.asp` | LOCAL + PHYSICAL | EG8041X6/X7 | read-only resolved-address polling/source |
| `/html/bbsp/maintenance/GetPingResult.asp` | LOCAL + PHYSICAL | EG8041X6/X7 | native ping result polling + normalized packet/latency parser |
| `/html/bbsp/maintenance/complex.cgi?...TraceRouteDiagnostics...` | LOCAL + PHYSICAL | EG8041X6/X7 | native traceroute start using discovered active WAN object path |
| `/html/bbsp/maintenance/GetRouteResult.asp` | LOCAL + PHYSICAL | EG8041X6/X7 | traceroute result polling + normalized hop parser |
| `/html/ssmp/testspeed/testspeed.asp` | LOCAL/PRESENT SURFACE | EG8041 WebUI | readable/present surface; start operation remains `UNKNOWN` |
| `/html/ssmp/testspeed/speedResult.asp` | LOCAL/PRESENT SURFACE | EG8041 WebUI | result surface only; no invented task creation endpoint |
| `/html/ssmp/Sectionspeed/Sectionspeed.asp` | LOCAL/PRESENT SURFACE | EG8041 WebUI | section-speed UI observed; START remains unsupported/unknown until characterized |
| `/CustomApp/mainpage.asp` | EXTERNAL | HG8245X6 MCP reference | firmware-specific WAN token/status helper; not generalized |
| `/asp/GetConfig.asp` | EXTERNAL DOCUMENTATION | HG8245H5 | `asp_config` family evidence only; runtime unconfirmed |
| `/asp/SetConfig.asp` | EXTERNAL DOCUMENTATION | HG8245H5 | `asp_config` family evidence only; no write support declared |
| `set.cgi` / `add.cgi` with `InternetGatewayDevice.*` | LOCAL + EXTERNAL | multiple generated Huawei WebUIs | only mapped operations with runtime/family evidence are enabled; object paths are not generalized universally |

## EG8041 Wi-Fi object signatures

The BREBG2-like family strategy requires matching object semantics, not only a model name:

- 2.4 GHz: `InternetGatewayDevice.LANDevice.1.WLANConfiguration.1` and `InternetGatewayDevice.LANDevice.1.WiFi.Radio.1`;
- 5 GHz: `InternetGatewayDevice.LANDevice.1.WLANConfiguration.5` and `InternetGatewayDevice.LANDevice.1.WiFi.Radio.2`;
- 5 GHz global options may also expose `InternetGatewayDevice.LANDevice.1.WiFi.X_HW_GlobalConfig`;
- mutation action object: `InternetGatewayDevice.X_HW_DEBUG.WLANConfigAction`.

Known physically observed width mappings are deliberately small: 2.4 GHz raw `X_HW_HT20=0` maps to `auto_20_40`, and 5 GHz raw `X_HW_HT20=4` maps to `auto_20_40_80_160`. Unknown raw mappings fail closed.

## CLI read surfaces

CLI is **not** enabled by Access Manager. These commands are available only if SSH/Telnet is already open, the operator explicitly enables CLI for the session and supplies their own credentials, and the transport probe succeeds.

| Command | Evidence | Normalized feature | Mutation |
|---|---|---|---|
| `display onu info` | HG8010H independent sources | `PonStatus` / `pon_status` | read only |
| `display optic` | HG8010H independent sources | `OpticalTelemetry` / `optical_telemetry` | read only |
| `display sysinfo` | HG8010H dump + MQTT exporter | `DeviceResourceTelemetry` / `resource_telemetry` | read only |
| `display pon statistics` | HG8010H MQTT/exporter sources | `PonStatistics` / `pon_statistics` | read only |

`clear pon statistics` appears in an external exporter but is intentionally not implemented and is rejected by the CLI allow-list because it mutates counters.

## Endpoint selection rules

1. Authentication/challenge probes are read-only and may be used before credentials are submitted.
2. Feature discovery uses GET/read-only POST only.
3. HTTP 200 is not endpoint success when the body is the Huawei HTTPS bootstrap; it is transport negotiation evidence.
4. A normal HTTP 200 is still not capability proof; the response must be recognizable and parsable.
5. Optical positional fallback is signature-gated (`stOpticInfo/6`, `/8`, `/16`); unknown argument counts remain unsupported.
6. `InternetGatewayDevice` object paths are not universal identifiers. WAN/SSID/reservation instances must be discovered or mapped for the actual family.
7. Reads may reauthenticate and retry once after a confirmed session expiry; mutation requests are never blindly replayed.
8. External/captured writes remain `PHYSICAL_VALIDATION_REQUIRED` unless the exact physical effect/readback was independently validated.
9. No frontend route exposes raw Huawei CGI endpoints; the API remains feature/domain oriented.
10. CLI feature readers do not open ports, alter firewall/config trees or enable SSH/Telnet remotely.

# Huawei endpoint provenance

This file records protocol evidence, not universal support. `LOCAL` means already present in the Access Manager implementation/captures before this multi-repo phase. `EXTERNAL` means observed in an external source. `PROBED` means Access Manager can safely probe/read and only promotes support after a recognizable parsed response.

| Endpoint / surface | Evidence | Family / model reference | Access Manager status |
|---|---|---|---|
| `/asp/GetRandCount.asp` | LOCAL + EXTERNAL | EG8041X7-10 local; HG8010H/EG8010H, HG8245X6, EG8145V5, EG8145X6-10 external | RandCount; POST preferred with safe GET fallback; trailing 32-hex challenge variant characterized |
| `/login.cgi` | LOCAL + EXTERNAL | multiple Huawei WebUIs | shared auth transport; auth strategy selected before credentials |
| `/html/ssmp/common/getRandString.asp` | EXTERNAL | EG8021V5 | RandString auth strategy implemented; physical validation pending |
| `/html/ssmp/common/GetRandToken.asp` | EXTERNAL | EG8021V5 | private post-login token acquisition implemented; physical validation pending |
| `/html/ssmp/deviceinfo/deviceinfo.asp` | LOCAL + EXTERNAL | EG8041X7 local; EG8021V5/EG8145V5 external | existing device reader; also safe auth proof/family evidence |
| `/html/amp/opticinfo/opticinfo.asp` | LOCAL + EXTERNAL + PROBED | EG8041X7 local; HG8010H/EG8010H, EG8021V5, EG8145-class references | existing optical reader remains; normalized telemetry accepts only characterized `stOpticInfo` signatures |
| `/html/status/opticinfo.asp` | EXTERNAL + PROBED | older HG8010H generation and older Huawei status WebUI | read-only alternate optical endpoint; `stOpticInfo/6` characterized |
| `/html/bbsp/common/ontstate.asp` | EXTERNAL + PROBED | EG8021V5 reference | read-only PON state reader; capability promoted only on parser success |
| `/html/bbsp/common/getwanlist.asp` | LOCAL + EXTERNAL | multiple AMP/BBSP references | existing WAN reader; do not assume identical constructor fields |
| WAN traffic-stat pages under `/html/bbsp/common/` | EXTERNAL | EG8021V5 / current OptiXstar integrations | scheduled telemetry expansion |
| `/html/amp/ethinfo/ethinfo.asp` | EXTERNAL | EG8021V5 / current OptiXstar integrations | scheduled Ethernet normalization |
| `/html/amp/wlaninfo/wlaninfo.asp` | EXTERNAL | EG8021V5 | Wi-Fi reference only; local Wi-Fi mapping remains authoritative |
| `/html/bbsp/common/GetLanUserDhcpInfo.asp` | EXTERNAL | EG8021V5 | LAN-client reference; dedup/normalization scheduled |
| `/html/bbsp/common/GetLanUserDevInfo.asp` | EXTERNAL | HG8245X6 / EG8145V5 references | alternate LAN-client surface; family-specific discovery required |
| `/html/bbsp/userdevinfo/getuserdevinfo.asp` | EXTERNAL | EG8145X6-10 / OptiXstar references | alternate client surface; not auto-enabled |
| `/CustomApp/mainpage.asp` | EXTERNAL | HG8245X6 MCP reference | firmware-specific WAN token/status helper; not generalized |
| `/asp/GetConfig.asp` | EXTERNAL DOCUMENTATION | HG8245H5 | `asp_config` family evidence only; runtime unconfirmed |
| `/asp/SetConfig.asp` | EXTERNAL DOCUMENTATION | HG8245H5 | `asp_config` family evidence only; no write support declared |
| `set.cgi` / `add.cgi` with `InternetGatewayDevice.*` | LOCAL + EXTERNAL | multiple generated Huawei WebUIs | only existing locally mapped writes are enabled; external domains are not copied universally |

## CLI read surfaces

CLI is **not** enabled by Access Manager. These commands are available only if
SSH/Telnet is already open, the operator explicitly enables CLI for the session
and supplies their own credentials, and the transport probe succeeds.

| Command | Evidence | Normalized feature | Mutation |
|---|---|---|---|
| `display onu info` | HG8010H independent sources | `PonStatus` / `pon_status` | read only |
| `display optic` | HG8010H independent sources | `OpticalTelemetry` / `optical_telemetry` | read only |
| `display sysinfo` | HG8010H dump + MQTT exporter | `DeviceResourceTelemetry` / `resource_telemetry` | read only |
| `display pon statistics` | HG8010H MQTT/exporter sources | `PonStatistics` / `pon_statistics` | read only |

`clear pon statistics` appears in an external exporter but is intentionally not
implemented and is rejected by the CLI allow-list because it mutates counters.

## Endpoint selection rules

1. Authentication/challenge probes are read-only and may be used before credentials are submitted.
2. Feature discovery uses GET/read-only POST only.
3. A HTTP 200 alone is not capability proof; the response must be recognizable and parsable.
4. Optical parser positional fallback is signature-gated (`stOpticInfo/6`, `/8`, `/16`); unknown argument counts remain unsupported.
5. `InternetGatewayDevice` object paths are not universal identifiers. WAN/SSID/reservation instances must be discovered or mapped for the actual family.
6. External write endpoints remain `PHYSICAL_VALIDATION_REQUIRED` unless Access Manager already has independent local validation for the exact semantics.
7. No frontend route exposes raw Huawei CGI endpoints; the API remains feature/domain oriented.
8. CLI feature readers do not open ports, alter firewall/config trees or enable SSH/Telnet remotely.

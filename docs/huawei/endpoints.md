# Huawei endpoint provenance

This file records protocol evidence, not universal support. `LOCAL` means already present in the Access Manager implementation/captures before this multi-repo phase. `EXTERNAL` means observed in an external source. `PROBED` means this PR can safely probe/read and only promotes support after a recognizable parsed response.

| Endpoint / surface | Evidence | Family / model reference | Access Manager status |
|---|---|---|---|
| `/asp/GetRandCount.asp` | LOCAL + EXTERNAL | EG8041X7-10 local; HG8245X6, EG8145V5, EG8145X6-10 external | auth supported by RandCount strategy |
| `/login.cgi` | LOCAL + EXTERNAL | multiple Huawei WebUIs | shared auth transport |
| `/html/ssmp/common/getRandString.asp` | EXTERNAL | EG8021V5 | RandString auth strategy implemented; physical validation pending |
| `/html/ssmp/common/GetRandToken.asp` | EXTERNAL | EG8021V5 | private post-login token acquisition implemented; physical validation pending |
| `/html/ssmp/deviceinfo/deviceinfo.asp` | LOCAL + EXTERNAL | EG8041X7 local; EG8021V5/EG8145V5 external | existing device reader; also safe auth proof/family evidence |
| `/html/amp/opticinfo/opticinfo.asp` | LOCAL + EXTERNAL | EG8041X7 local; EG8021V5 and HN8010 reference | existing optical reader; family-specific field normalization remains separate |
| `/html/bbsp/common/ontstate.asp` | EXTERNAL + PROBED | EG8021V5 reference | new read-only PON reader; capability promoted only on parser success |
| `/html/bbsp/common/getwanlist.asp` | LOCAL + EXTERNAL | multiple AMP/BBSP references | existing WAN reader; do not assume identical constructor fields |
| WAN traffic-stat pages under `/html/bbsp/common/` | EXTERNAL | EG8021V5 | scheduled telemetry PR |
| `/html/amp/ethinfo/ethinfo.asp` | EXTERNAL (and related local Ethernet surfaces) | EG8021V5 | scheduled telemetry normalization |
| `/html/amp/wlaninfo/wlaninfo.asp` | EXTERNAL | EG8021V5 | Wi-Fi reference only; local Wi-Fi mapping remains authoritative |
| `/html/bbsp/common/GetLanUserDhcpInfo.asp` | EXTERNAL | EG8021V5 | LAN-client reference; dedup/normalization scheduled |
| `/html/bbsp/common/GetLanUserDevInfo.asp` | EXTERNAL | HG8245X6 / EG8145V5 references | alternate LAN-client surface; family-specific discovery required |
| `/html/bbsp/userdevinfo/getuserdevinfo.asp` | EXTERNAL | EG8145X6-10 example | alternate client surface; not auto-enabled |
| `/CustomApp/mainpage.asp` | EXTERNAL | HG8245X6 MCP reference | firmware-specific WAN token/status helper; not generalized |
| `/asp/GetConfig.asp` | EXTERNAL DOCUMENTATION | HG8245H5 | `asp_config` family evidence only; runtime unconfirmed |
| `/asp/SetConfig.asp` | EXTERNAL DOCUMENTATION | HG8245H5 | `asp_config` family evidence only; no write support declared |
| `set.cgi` / `add.cgi` with `InternetGatewayDevice.*` | LOCAL + EXTERNAL | multiple generated Huawei WebUIs | only existing locally mapped writes are enabled; external domains are not copied universally |

## Endpoint selection rules

1. Authentication/challenge probes are read-only and may be used before credentials are submitted.
2. Feature discovery uses GET/read-only POST only.
3. A HTTP 200 alone is not capability proof; the response must be recognizable and parsable.
4. `InternetGatewayDevice` object paths are not universal identifiers. WAN/SSID/reservation instances must be discovered or mapped for the actual family.
5. External write endpoints remain `PHYSICAL_VALIDATION_REQUIRED` unless Access Manager already has independent local validation for the exact semantics.
6. No frontend route exposes raw Huawei CGI endpoints; the API remains feature/domain oriented.

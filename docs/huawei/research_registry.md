# Huawei research registry

This registry separates external knowledge from Access Manager runtime truth.
A source can raise confidence, but only runtime probes and local/physical tests
can promote actual device capabilities.

Evidence vocabulary:

- `SOURCE_MENTIONED`
- `SOURCE_CODE_OBSERVED`
- `FIXTURE_OBSERVED`
- `MULTIPLE_SOURCES_AGREE`
- `LOCAL_FIRMWARE_OBSERVED`
- `TESTED_AUTOMATICALLY`
- `PHYSICALLY_VALIDATED`

## Sources reviewed

| Source | Type | License | Models / family | Useful protocol evidence | Status in Access Manager |
|---|---|---|---|---|---|
| Access Manager local EG8041X7-10 capture | authorized local device | local sanitized evidence | EG8041X7-10 | broad AMP/BBSP/SSMP surface, writes + readback | existing physically validated operational profile |
| Access Manager local EG8041X6-10 evidence | authorized local device | local sanitized evidence | EG8041X6-10 | RandCount, BREBG2, HTTP->HTTPS:80 bootstrap, 2G/5G object graph, channel discovery, WAN, native ping/traceroute | sanitized fixtures + family runtime; write effects remain per-operation gated |
| Huawei EG8041X6-10 product documentation | vendor documentation | Huawei copyright | EG8041X6-10 | Web UI/TR-069/OMCI management positioning and dual-band Wi-Fi context | corroborating model/O&M evidence only |
| `siedgustavo/huawei-ont-stats` | Python monitoring/API | MIT | EG8021V5 | RandString/RandToken, AMP/BBSP, PON/optic/WAN/client reads | behavior incorporated in #84; fixtures remain external-reference |
| `Erenn0989/huawei-ont-mcp` | MCP/automation | MIT | HG8245X6-family | RandCount, read reauth, same-TCP warning | characterized; same-TCP still pending fixture/device |
| `minzique/huawei-hg8245h5` | firmware/reverse-engineering docs | MIT | HG8245H5 | ASP GetConfig/SetConfig, IGD tree, WAP/CLI | research only until reader characterization |
| `chickenzord/go-huawei-client` | Go client/exporter | MIT | EG8145V5, HN8010TS draft | shared session/HTTP architecture, AMP reads | EG8145/HN follow-up |
| `logon84/Huawei-Optistar-EG8145X6-10-remote-login-example` | Python example | no LICENSE found | EG8145X6-10 | HTTPS:80, RandCount/login/client-list behavior | factual behavior only; no credentials/code copied |
| `kevinantoniowiyonolauw/netcut` router package | Go implementation/docs | public source; license checked at source level before code reuse | EG8145V5 | independent RandCount/login flow and topology/Ethernet behavior | protocol corroboration only; no source transplanted |
| EletrônicaBR EG8145V5-V2 R020/R021 research | forum technical report | N/A | EG8145V5-V2 | GetRandCount/login, SSMP resources, `CfgMode=BREBG2` | **candidate family evidence only**; no capability promoted by name/CfgMode alone |
| IXC ACS EG8145V5-V2 guidance | vendor/operator documentation | site copyright | EG8145V5-V2 | TR-069/WAN operational semantics | semantic reference only |
| `loiklo/huawei-onu-to-graphite` | HTTP/Telnet exporter | GPL-3.0 | HG8010H-like | POST GetRandCount, trailing 32-char token observation, AMP optic page, WAP optic | behavior only; clean-room implementation |
| `sirjeannot/huawei-ont-2-mqtt` | Telnet/MQTT exporter | GPL-3.0 | HG8010H | WAP `display optic`, `display sysinfo`, `display pon statistics`; units/counters | behavior only; clean-room parsers/fixtures |
| `jasperf/huawei-echolife-eg8145V5` | operational notes | no LICENSE found | EG8145V5 | Web/SSH/WAP operational evidence | factual behavior only; internet/default credentials are not imported |
| `DictumMortuum/servus-extapi` | Go exporter | no repository LICENSE | HG8010H | independent WAP reads for ONU state, optic and selected PON counters | cross-source confirmation only |
| `PayungsakCNR/ais-fibre-huawei-hg8010h-hacking` | firmware/system dump | no LICENSE found | HG8010H | ProductClass, CLI/system fields including CPU/memory | factual dump evidence only; no bypass/tampering adopted |
| `lilmayofuksu/huawei-gpon-thing` | Python WebUI monitor | MIT | HG8010H-family | RandCount WebUI and 16-argument `stOpticInfo`; LAN counters | optical signature corroboration; code not copied |
| `TheIcelandicguy/huawei_ont` | Home Assistant integration | MIT | Huawei OptiXstar family | current AMP/BBSP endpoints, constructor parsing, optical positional shape | cross-source family evidence; not treated as local fixture |
| `kalagxw/MA5671-205` | extracted WebUI files | unverified/no license relied upon | Huawei MA5671 firmware tree | `stOpticInfo` 6/8-argument function definitions | factual signature evidence only |
| Marco d'Itri — *Exploring the Huawei HG8010H GPON ONT* | technical article/PDF | document copyright | HG8010H older generation | `/html/status/opticinfo.asp`, 6-arg `stOpticInfo`, legacy hashed-cookie auth | old-firmware characterization; auth deliberately unsupported |
| CAPS forum — HG8010H/EG8010H research | forum/reverse-engineering thread | N/A | HG8010H, EG8010H | newer RandCount/login flow, AMP optic page, firmware variance | cross-source evidence for family variance |
| 0neday Huawei ONT/Home Assistant gist | Gist | no license relied upon | Huawei AMP WebUI | AMP optic/login cookie variants | factual behavior only |
| BroadbandForum/cwmp-data-models | official data-model source | project license applies | TR-069/TR-181 | standard object semantics vs vendor `X_HW_*` extensions | semantic reference; no Huawei capability inferred from standard alone |

## Security / licensing boundary

- GPL or unlicensed sources are used for factual protocol behavior only; Access
  Manager implementation is clean-room and follows the existing architecture.
- Internet credentials/default passwords are never imported into application
  code, docs or fixtures.
- Firmware/hacking repositories are not used for auth bypass, privilege
  escalation, firmware modification or credential recovery.
- External fixtures are named `*_reference`. Local authorized evidence is kept
  separately under `eg8041x7_10_local` and `eg8041x6_10_local` and is sanitized.
- A captured mutation request is not equivalent to a physically validated
  effect. New writes still require runtime readback and evidence metadata.

## Findings promoted in the EG8041 family PR

1. EG8041X6-10 and EG8041X7-10 have independent local evidence for the same
   AMP/BBSP object graph. The implementation is therefore owned by an EG8041
   family strategy rather than duplicated per model.
2. EG8041X6-10 HTTP port 80 can be a JavaScript TLS bootstrap advertising
   `SSLPort=80`; the central Huawei transport now preserves the explicit port
   while changing the scheme to HTTPS.
3. RFC6598 `100.64.0.0/10` is a management-probe network in addition to RFC1918.
   It is explicitly documented as shared address space, not RFC1918.
4. Wi-Fi channel support is read from `WlanChannel.asp` when available. Current,
   default and supported values remain separate normalized domains.
5. Native ping/traceroute already existed in Access Manager; this PR generalizes
   their family ownership and adds normalized result fields while preserving
   existing response keys.
6. EG8145V5-V2 has external `BREBG2` + RandCount/SSMP evidence, but remains a
   research candidate until the live object signatures and readers match. No
   write capability is inferred from `CfgMode` alone.
7. HG8010H remains a distinct multi-variant family; its WebUI/CLI telemetry work
   from #85 is preserved and is not forced into the EG8041 strategy.

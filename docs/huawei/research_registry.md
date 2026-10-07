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
| `siedgustavo/huawei-ont-stats` | Python monitoring/API | MIT | EG8021V5 | RandString/RandToken, AMP/BBSP, PON/optic/WAN/client reads | behavior incorporated in #84; fixtures remain external-reference |
| `Erenn0989/huawei-ont-mcp` | MCP/automation | MIT | HG8245X6-family | RandCount, read reauth, same-TCP warning | characterized; same-TCP still pending fixture/device |
| `minzique/huawei-hg8245h5` | firmware/reverse-engineering docs | MIT | HG8245H5 | ASP GetConfig/SetConfig, IGD tree, WAP/CLI | research only until reader characterization |
| `chickenzord/go-huawei-client` | Go client/exporter | MIT | EG8145V5, HN8010TS draft | shared session/HTTP architecture, AMP reads | EG8145/HN follow-up |
| `logon84/Huawei-Optistar-EG8145X6-10-remote-login-example` | Python example | no LICENSE found | EG8145X6-10 | RandCount/login/client-list behavior | factual behavior only; no code copied |
| `loiklo/huawei-onu-to-graphite` | HTTP/Telnet exporter | GPL-3.0 | HG8010H-like | POST GetRandCount, trailing 32-char token observation, AMP optic page, WAP optic | behavior only; clean-room implementation |
| `sirjeannot/huawei-ont-2-mqtt` | Telnet/MQTT exporter | GPL-3.0 | HG8010H | WAP `display optic`, `display sysinfo`, `display pon statistics`; units/counters | behavior only; clean-room parsers/fixtures in this PR |
| `jasperf/huawei-echolife-eg8145V5` | operational notes | no LICENSE found | EG8145V5 | model/CLI operational evidence | next PR; factual behavior only |
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
- External fixtures are always named `*_reference`; only the existing
  `eg8041x7_10_local` evidence may be described as local physical capture.

## Findings promoted in this PR

1. HG8010H is not one immutable protocol shape. Independent material shows at
   least an older `/html/status/opticinfo.asp` + derived-cookie generation and a
   newer RandCount/login + `/html/amp/opticinfo/opticinfo.asp` generation.
2. `stOpticInfo` has multiple real signatures. The new parser accepts only
   characterized argument counts (6, 8, 16) or named fields produced by those
   shapes; unknown counts remain unsupported.
3. WAP telemetry fields for HG8010H are corroborated by multiple independent
   sources: optical DOM values, CPU/memory and PON counters.
4. CLI access is optional evidence/transport. Access Manager never enables SSH
   or Telnet and never clears counters.
5. EG8010H shares enough external protocol evidence to be recognized, but not
   enough to be advertised at the same support level as HG8010H yet.

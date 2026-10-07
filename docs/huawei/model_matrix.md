# Huawei model support matrix

Support is a runtime/software claim, not a name match. `RECOGNIZED` means the model can be identified/routed but does not imply useful reads on every firmware. `READ_PARTIAL` means at least one meaningful read path is integrated while known variants remain uncovered. Family compatibility is promoted only after live protocol/object/parser evidence.

| Model | Evidence | Probable family | Auth / transport | Runtime status | Write / physical boundary |
|---|---|---|---|---|---|
| EG8041X6-10 | authorized local evidence + sanitized fixtures + tests | AMP_BBSP / BREBG2-like | RandCount; HTTP bootstrap -> HTTPS:80 | **READ_SUPPORTED / FAMILY_COMPATIBLE after runtime signature proof** | Wi-Fi mutation surface characterized + readback-gated; new write effects `PHYSICAL_VALIDATION_PENDING` |
| EG8041X7-10 | local capture + regression suite | AMP_BBSP / BREBG2-like | RandCount WebUI | **WRITE_SUPPORTED / PHYSICALLY_VALIDATED** | existing operational profile/write validation remains authoritative |
| HG8010H | multiple independent sources + reference fixtures | AMP_BBSP with firmware variants | RandCount newer; derived-cookie older; optional WAP | **READ_PARTIAL** | read only in new telemetry surface |
| EG8010H | CAPS/forum family evidence | AMP_BBSP probable | RandCount observed externally | **RECOGNIZED** | no inheritance from HG8010H |
| EG8021V5 | huawei-ont-stats + #84 tests | AMP_BBSP | RandString + RandToken | **READ_PARTIAL** | external/fixture evidence; physical validation pending |
| EG8145V5 | go-huawei-client + independent operational/source evidence | AMP_BBSP candidate | RandCount; WebUI + WAP/SSH evidence | **RECOGNIZED** | exact EG8041 object graph not proven; no family writes |
| EG8145V5-V2 | external firmware/SSMP research | AMP_BBSP / BREBG2 **candidate** | RandCount; SSMP; `CfgMode=BREBG2` reported | **RESEARCH_ONLY** | CfgMode alone does not grant family compatibility or writes |
| EG8145X6-10 | public login example + related OptiXstar material | AMP_BBSP candidate | RandCount; HTTPS:80 observed externally | **RESEARCH_ONLY** | client/optic evidence only; no EG8041 write inheritance |
| HG8245X6 | huawei-ont-mcp | AMP_BBSP candidate | RandCount with same-TCP constraint | **RESEARCH_ONLY** | strict same-TCP behavior still uncharacterized locally |
| HG8245H5 | firmware/docs | ASP_CONFIG candidate + WAP | RandCount; GetConfig/SetConfig documented | **RESEARCH_ONLY** | deliberately separate from EG8041 mutation strategy |
| HG8245H | gist/reverse-engineering material | AMP/ASP uncertain | token/RandCount variants | **RESEARCH_ONLY** | no automatic family assignment |
| HG8012H | firmware/reverse-engineering material | config-tree/WAP evidence only | insufficient | **RESEARCH_ONLY** | no support inferred |
| HG8240H5 | firmware/reverse-engineering material | WAP/config-tree candidate | insufficient | **RESEARCH_ONLY** | no support inferred |
| HN8010TS | go-huawei-client draft | EG8145-like WebUI candidate | shared-session draft | **RESEARCH_ONLY** | no support inferred |
| HN8010T-like | related external discussion | unknown | unknown | **RESEARCH_ONLY** | no support inferred |
| HG8245Q2 | source mentions | unknown | unknown | **UNKNOWN** | unknown |
| HG8546M | source mentions | unknown | unknown | **UNKNOWN** | unknown |
| HS8145V5 | source mentions | AMP_BBSP candidate | insufficient | **RESEARCH_ONLY** | no support inferred |
| EG8141A5 | source mentions | unknown | unknown | **UNKNOWN** | unknown |
| HG8245U | source mentions | unknown | unknown | **UNKNOWN** | unknown |
| HG8245X6-8Ne | source mentions | X6 candidate, not proven | insufficient | **RESEARCH_ONLY** | no support inferred |

## EG8041 family compatibility rule

A registered EG8041 name is evidence, not the runtime contract. The family provider requires `AMP_BBSP` plus the characterized dual-band object signatures and successful feature readers. `CfgMode=BREBG2` strengthens the fingerprint but is not sufficient by itself.

For EG8041X6-10 the operator supplied physical evidence for model/family, HTTPS-on-port-80 negotiation, Wi-Fi object graph/channel discovery, WAN and native ping/traceroute. The implementation records that evidence separately from write verification. A captured POST payload is not labelled as a successful physical write effect.

## HG8010 / other-family boundary

HG8010 telemetry from #85 remains a separate multi-variant strategy, including optional read-only CLI. EG8021V5 keeps its RandString flow. HG8245X6 keeps its same-TCP warning. HG8245H5 keeps ASP_CONFIG separate. None are forced into BREBG2 merely because they expose `InternetGatewayDevice` objects.

## Physical-validation boundary

- EG8041X7-10: existing local physical validation, including mapped writes/readback.
- EG8041X6-10: local physical evidence supplied by the operator for the family/read/diagnostic surfaces listed above; the assistant did not re-exercise the hardware during this PR execution.
- HG8010H/EG8010H/EG8021V5/EG8145-family research remains external/fixture evidence unless separately stated.

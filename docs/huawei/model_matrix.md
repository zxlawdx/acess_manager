# Huawei model support matrix

Support is a runtime/software claim, not a name match. `RECOGNIZED` means the
model can be identified/routed but does not imply useful reads on every
firmware. `READ_PARTIAL` means at least one meaningful read path is integrated
with characterization tests while known firmware variants remain uncovered.

| Model | Evidence | Probable family | Web auth evidence | Web telemetry | CLI evidence | Support |
|---|---|---|---|---|---|---|
| EG8041X7-10 | local capture + tests | AMP_BBSP | RandCount | broad local mapped surface | not required | **WRITE_SUPPORTED / PHYSICALLY_VALIDATED** |
| HG8010H | multiple independent sources + reference fixtures | AMP_BBSP with firmware variants | RandCount newer; derived-cookie older | optic `/html/amp/...` and `/html/status/...` signatures | WAP optic/sysinfo/PON/ONU | **READ_PARTIAL** |
| EG8010H | CAPS/forum family evidence | AMP_BBSP probable | RandCount observed externally | AMP optic reported | WAP family reported | **RECOGNIZED** |
| EG8021V5 | huawei-ont-stats + #84 tests | AMP_BBSP | RandString + RandToken | PON state and AMP optic | not required | **READ_PARTIAL** |
| EG8145V5 | go-huawei-client + jasperf notes | AMP_BBSP | RandCount evidence | device/optic/client/resource references | WAP/SSH references | **RECOGNIZED**; next PR |
| EG8145V5-V2 | source mentions only | unknown/AMP_BBSP candidate | not characterized | not characterized | not characterized | **RESEARCH_ONLY** |
| EG8145X6-10 | login example + related family material | AMP_BBSP candidate | RandCount | client/optic family evidence | unconfirmed | **RESEARCH_ONLY** |
| HG8245X6 | huawei-ont-mcp | AMP_BBSP candidate | RandCount with same-TCP constraint | partial external reads | unconfirmed | **RESEARCH_ONLY** until same-TCP characterization |
| HG8245H5 | firmware/docs | ASP_CONFIG candidate + WAP | RandCount | GetConfig/IGD documentation | WAP | **RESEARCH_ONLY** |
| HG8245H | gist/reverse-engineering material | AMP/ASP generation uncertain | RandCount + page/write token evidence | read surfaces documented | WAP reports | **RESEARCH_ONLY** |
| HG8012H | firmware/reverse-engineering material | firmware/config-tree evidence only | insufficient safe characterization | insufficient | WAP family reported | **RESEARCH_ONLY** |
| HG8240H5 | firmware/reverse-engineering material | WAP/config-tree family evidence | insufficient | insufficient | WAP/AMP commands | **RESEARCH_ONLY** |
| HN8010TS | open go-huawei-client draft | EG8145-like WebUI candidate | shared session under investigation | optic draft | unconfirmed | **RESEARCH_ONLY** |
| HN8010T-like | related external discussion | unknown | unknown | unknown | unknown | **RESEARCH_ONLY** |
| HG8245Q2 | documentation/source mentions | unknown | unknown | unknown | unknown | **UNKNOWN** |
| HG8546M | documentation/source mentions | unknown | unknown | unknown | unknown | **UNKNOWN** |
| HS8145V5 | documentation/source mentions | AMP_BBSP candidate | insufficient | insufficient | insufficient | **RESEARCH_ONLY** |
| EG8141A5 | documentation/source mentions | unknown | unknown | unknown | unknown | **UNKNOWN** |
| HG8245U | documentation/source mentions | unknown | unknown | unknown | unknown | **UNKNOWN** |
| HG8245X6-8Ne | documentation/source mentions | X6 candidate, not proven | insufficient | insufficient | insufficient | **RESEARCH_ONLY** |

## HG8010H / EG8010H boundary in this PR

The registry is evidence-only. Runtime still decides from login behavior,
endpoints, parsed signatures and successful capability probes.

For HG8010H this PR integrates:

- manual recognition/routing without setting `model_verified=true`;
- RandCount challenge suffix normalization (`token[-32:]` only for the exact
  trailing 32-hex signature);
- explicit recognition/refusal of the older derived-cookie auth variant;
- WebUI optical telemetry for characterized `stOpticInfo/6`, `/8` and `/16`;
- optional operator-enabled SSH/Telnet WAP read transport;
- WAP PON status/statistics and CPU/memory/optical readers;
- dynamic read capabilities only after parser success.

EG8010H currently receives model recognition/evidence only. It is not promoted
to HG8010H's read level solely because the names and forum family are similar.

## Physical validation boundary

Only EG8041X7-10 retains local physical validation. All HG8010H/EG8010H data in
this PR is external-firmware/reference evidence plus automated characterization
tests; no physical HG8010H/EG8010H device was exercised by this PR.

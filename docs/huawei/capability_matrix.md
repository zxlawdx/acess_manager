# Huawei multi-repository capability matrix

Legend used for this integration:

- `ALREADY_EXISTS` — implemented in Access Manager before this integration.
- `IMPROVED` — existing Access Manager path strengthened in the current phase.
- `IMPLEMENTED` — integrated feature in the current phase.
- `USEFUL` — useful external knowledge scheduled for a later slice.
- `PARTIAL` — Access Manager has only part of the capability.
- `MODEL_SPECIFIC` / `FIRMWARE_SPECIFIC` — evidence cannot be generalized.
- `UNCONFIRMED` — insufficient runtime evidence.
- `PHYSICAL_VALIDATION_REQUIRED` — protocol/mapping exists but must not be advertised as physically validated.
- `NOT_USEFUL` — implementation detail intentionally not adopted.

External columns describe evidence found in those repositories; they are not claims that Access Manager currently supports every referenced model. See `research_registry.md` and `model_matrix.md` for the continuously expanded source/model inventory.

| Feature | Access Manager | External evidence / status |
|---|---|---|
| Huawei vendor fingerprint | IMPROVED | multiple WebUI generations and challenge markers |
| Model knowledge registry | IMPLEMENTED | evidence-only; does not grant runtime capability |
| Firmware detection | IMPROVED | authenticated device information where available |
| RandCount login | ALREADY_EXISTS + IMPROVED | POST/GET variance and trailing-32-hex challenge characterized |
| RandString login | IMPLEMENTED (#84) | EG8021V5 primary evidence |
| Derived-cookie RandCount auth | CHARACTERIZED / DISABLED | older HG8010H generation; recognized and refused before credentials |
| Same-TCP auth affinity | SCHEDULED | HG8245X6-specific external evidence |
| Read retry after reauth | ALREADY_EXISTS | shared Huawei transport behavior |
| Write no-blind-replay | ALREADY_EXISTS | preserved; no new cross-family writes |
| Generic JS constructor parser | ALREADY_EXISTS | reused by new optical/PON readers |
| Device info | ALREADY_EXISTS | broad generated-WebUI evidence |
| PON / ONT state | IMPLEMENTED (probed read) | WebUI from #84; normalized `PonStatus` in current PR |
| PON statistics | IMPLEMENTED (optional CLI read) | HG8010H WAP evidence + sanitized fixture/tests |
| Optical | ALREADY_EXISTS + IMPROVED | WebUI variants `/amp/` + `/status/`, signatures `/6`, `/8`, `/16`; CLI fallback |
| Device CPU/memory telemetry | IMPLEMENTED (optional CLI read) | HG8010H WAP/dump evidence |
| WAN configuration/status | ALREADY_EXISTS | next family work will extend read compatibility |
| WAN traffic statistics | SCHEDULED | OptiXstar/EG8021V5 external evidence |
| Ethernet ports | ALREADY_EXISTS / extend later | richer counters scheduled |
| LAN clients | ALREADY_EXISTS | MAC-based cross-surface dedup scheduled |
| Wi-Fi read | ALREADY_EXISTS | external family research continues |
| Wi-Fi radio enable | PARTIAL / LATER | no cross-family write inferred |
| Wi-Fi normalized CURRENT/DEFAULT/SUPPORTED | ALREADY_EXISTS | preserved |
| DHCP server | ALREADY_EXISTS | external variants not generalized |
| DHCP leases | ALREADY_EXISTS via client/status surfaces | dedup/refinement scheduled |
| DHCP static reservations | ALREADY_EXISTS for EG8041; cross-family mapping LATER | no inferred writes |
| DMZ | ALREADY_EXISTS for EG8041; cross-family mapping LATER | no inferred writes |
| TR-069 | ALREADY_EXISTS | Broadband Forum models used only for semantics |
| Persistent session | IMPROVED | WebUI central; optional CLI is session-local |
| SSH/WAP read transport | IMPLEMENTED opt-in | only pre-opened port + operator credentials + WAP prompt |
| Telnet/WAP read transport | IMPLEMENTED opt-in | only pre-opened port + operator credentials + WAP prompt |
| Cache policy | ALREADY_EXISTS session snapshot; refinement later | no external fixed TTL copied |
| Drift/reconciliation | SCHEDULED_LATER | no automatic mutation daemon |
| ASP GetConfig/SetConfig | UNCONFIRMED / FAMILY ONLY | HG8245H5 research; reader work deferred |

## PR #84 — multi-repository protocol foundation

Implemented:

- protocol-family/auth-flow objects (`amp_bbsp`, `asp_config`, `unknown`);
- RandCount vs RandString session-token authentication;
- generic model/firmware capture without false local verification;
- read-only PON/ONT state reader and dynamic capability promotion;
- protocol descriptor and source provenance.

## PR #85 — HG8010H/EG8010H telemetry + multi-transport reads

### IMPLEMENTED

- evidence-only `HuaweiModelProfile` registry with explicit support/evidence levels;
- HG8010H recognition at `READ_PARTIAL`, EG8010H recognition without inheriting HG8010H support;
- normalized vendor-neutral `PonStatus`, `PonStatistics`, `OpticalTelemetry` and `DeviceResourceTelemetry`;
- WebUI optical endpoint variants:
  - `/html/amp/opticinfo/opticinfo.asp`;
  - `/html/status/opticinfo.asp`;
- signature-gated `stOpticInfo/6`, `/8`, `/16` parsing;
- optional read-only SSH/Telnet WAP transport, disabled by default and requiring operator credentials;
- WAP readers for `display onu info`, `display optic`, `display sysinfo`, `display pon statistics`;
- explicit blocking/omission of `clear pon statistics` and other mutation commands;
- dynamic capabilities `optical_telemetry`, `pon_status`, `pon_statistics`, `resource_telemetry` only after parser success;
- RandCount POST-vs-GET evidence and exact trailing-32-hex challenge normalization;
- old HG8010H derived-cookie auth variant recognized but deliberately not implemented for authentication;
- sanitized `hg8010h_reference` fixtures and characterization tests;
- continuous `research_registry.md` and all-model `model_matrix.md`.

### ALREADY EXISTS / PRESERVED

- centralized WebUI HTTP transport/session;
- read retry after reauth and no-blind-write-replay semantics;
- robust JavaScript constructor parser;
- local EG8041X7-10 write behavior/capabilities;
- normalized Wi-Fi domain and capability-driven API/frontend;
- ZTE provider architecture.

### NEXT PRS

1. **EG8145V5 family:** strengthen recognition into functional reads using WebUI evidence first; characterize device info, WAN, optical, PON, clients, Wi-Fi telemetry and diagnostics; use optional CLI only where separately confirmed.
2. **HG8245 family expansion:** HG8245H/H5/X6 with ASP_CONFIG, page-token and same-TCP divergences preserved rather than collapsed into RandCount.
3. **EG8145X6 / HN8010:** OptiXstar generation, client/WAN reads, HN8010TS open-PR evidence.
4. **Config-tree research support:** offline-only redacted `hw_ctree.xml` parser for fixtures/capability research.
5. **Cross-family telemetry refinement:** WAN traffic stats, Ethernet counters, client deduplication and cache classes.
6. **Writes:** only after family-specific endpoint/payload/mapping/token semantics and required physical validation.

### DEFERRED PHYSICAL VALIDATION

- all new HG8010H/EG8010H WebUI/CLI behavior;
- old HG8010H derived-cookie auth implementation;
- RandString authentication on a real EG8021V5-class ONT;
- strict TCP-connection affinity for HG8245X6-style RandCount firmware;
- EG8145V5/EG8145X6 behavior beyond independently observed surfaces;
- all new cross-family writes.

### REJECTED WITH REASON

- one service/class per Huawei model: duplicates family behavior and encourages name-based inference;
- model-name-only capability grants: recognition is evidence, not runtime permission;
- copying external regex constructor parsers: Access Manager's parser is more robust;
- copying GPL/unlicensed implementation code: external sources provide factual protocol evidence only; implementation remains clean-room;
- importing internet/default device credentials: operator always supplies credentials;
- enabling SSH/Telnet, changing firewall/config tree or `X_HW_CLITelnetAccess`: invasive and outside read-only probing;
- `clear pon statistics`: mutates device counters and is unnecessary for telemetry;
- fixed external cache TTLs: freshness differs between identity/configuration/dynamic telemetry;
- automatic reconciliation daemon: unsafe before explicit drift modeling and operator-controlled remediation.

## Physical validation boundary

Only the pre-existing local EG8041X7-10 evidence may be labeled physically validated. HG8010H/EG8010H behavior in PR #85 is `OBSERVED IN EXTERNAL FIRMWARE` plus sanitized `FIXTURE_OBSERVED` and automated characterization tests. No physical HG8010H/EG8010H device was exercised by this PR.

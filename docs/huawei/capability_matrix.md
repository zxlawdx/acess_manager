# Huawei multi-repository capability matrix

Legend used for this integration:

- `ALREADY_EXISTS` — implemented in Access Manager before this integration.
- `IMPROVED` — existing Access Manager path strengthened in this PR.
- `IMPLEMENTED` — new integrated feature in this PR.
- `USEFUL` — useful external knowledge scheduled for a later slice.
- `PARTIAL` — Access Manager has only part of the capability.
- `MODEL_SPECIFIC` / `FIRMWARE_SPECIFIC` — evidence cannot be generalized.
- `UNCONFIRMED` — insufficient runtime evidence.
- `PHYSICAL_VALIDATION_REQUIRED` — protocol/mapping exists but must not be advertised as physically validated.
- `NOT_USEFUL` — implementation detail intentionally not adopted.

External columns describe evidence found in those repositories; they are not claims that Access Manager currently supports every referenced model.

| Feature | Access Manager | huawei-ont-stats | huawei-ont-mcp | huawei-hg8245h5 | go-huawei-client | EG8145X6 example |
|---|---|---|---|---|---|---|
| Huawei vendor fingerprint | IMPROVED | USEFUL | USEFUL | docs only | USEFUL | USEFUL |
| Model detection | IMPROVED | EG8021V5 | HG8245X6 ref | HG8245H5 | EG8145V5/HN8010 | EG8145X6-10 |
| Firmware detection | IMPROVED | USEFUL | UNCONFIRMED | documented | UNCONFIRMED | UNCONFIRMED |
| RandCount login | ALREADY_EXISTS + IMPROVED | DIFFERENT_IMPLEMENTATION | FIRMWARE_SPECIFIC | documented | USEFUL | USEFUL |
| RandString login | IMPLEMENTED | primary evidence | — | — | — | — |
| Same-TCP auth affinity | SCHEDULED_NEXT_PR | — | FIRMWARE_SPECIFIC | — | — | — |
| Read retry after reauth | ALREADY_EXISTS | USEFUL | USEFUL | UNCONFIRMED | session-oriented | minimal example |
| Write no-blind-replay | ALREADY_EXISTS | — | — | — | — | — |
| Generic JS constructor parser | ALREADY_EXISTS | parser weaker than AM | page-specific | docs | JS VM approach | escaped-hex example |
| Device info | ALREADY_EXISTS | USEFUL | PARTIAL | documented | PARTIAL | UNCONFIRMED |
| PON / ONT state | IMPLEMENTED (probed read) | primary evidence | UNCONFIRMED | documented | UNCONFIRMED | UNCONFIRMED |
| Optical | ALREADY_EXISTS | USEFUL | UNCONFIRMED | documented | draft HN8010 | UNCONFIRMED |
| WAN configuration/status | ALREADY_EXISTS | USEFUL | USEFUL | documented | UNCONFIRMED | UNCONFIRMED |
| WAN traffic statistics | MISSING / NEXT | USEFUL | UNCONFIRMED | UNCONFIRMED | UNCONFIRMED | UNCONFIRMED |
| Ethernet ports | ALREADY_EXISTS / extend later | USEFUL | UNCONFIRMED | documented | UNCONFIRMED | UNCONFIRMED |
| LAN clients | ALREADY_EXISTS | USEFUL | USEFUL | documented | USEFUL | USEFUL |
| Wi-Fi read | ALREADY_EXISTS | USEFUL | UNCONFIRMED | documented | UNCONFIRMED | UNCONFIRMED |
| Wi-Fi radio enable | PARTIAL / NEXT | USEFUL | UNCONFIRMED | documented | UNCONFIRMED | UNCONFIRMED |
| Wi-Fi normalized CURRENT/DEFAULT/SUPPORTED | ALREADY_EXISTS | external values only | — | — | — | — |
| DHCP server | ALREADY_EXISTS | USEFUL | UNCONFIRMED | documented | UNCONFIRMED | UNCONFIRMED |
| DHCP leases | ALREADY_EXISTS via client/status surfaces | USEFUL | client data | documented | client data | client data |
| DHCP static reservations | ALREADY_EXISTS for EG8041; cross-family mapping NEXT | USEFUL | UNCONFIRMED | documented | UNCONFIRMED | UNCONFIRMED |
| DMZ | ALREADY_EXISTS for EG8041; cross-family mapping NEXT | USEFUL | UNCONFIRMED | documented | UNCONFIRMED | UNCONFIRMED |
| TR-069 | ALREADY_EXISTS | UNCONFIRMED | UNCONFIRMED | documented | UNCONFIRMED | UNCONFIRMED |
| Persistent session | IMPROVED | USEFUL | USEFUL | documented | USEFUL | minimal |
| Cache policy | ALREADY_EXISTS session snapshot; NEXT refinement | USEFUL | auth cache only | UNCONFIRMED | UNCONFIRMED | — |
| Drift/reconciliation | SCHEDULED_LATER | USEFUL | — | — | — | — |
| ASP GetConfig/SetConfig | UNCONFIRMED / FAMILY ONLY | — | — | documented | — | — |

## PR 1: `feat/huawei-multirepo-foundation`

### IMPLEMENTED

- protocol-family/auth-flow value objects (`amp_bbsp`, `asp_config`, `unknown`; RandCount vs RandString session-token flow);
- family-aware Huawei fingerprint capable of recognizing RandString login pages;
- generic model and firmware identity capture without marking unknown models as locally verified profiles;
- RandString -> login -> post-login RandToken authentication strategy;
- single credential-bearing login attempt per login/reauth invocation (removes blind credential retry from the default Huawei runtime);
- read-only PON/ONT state reader for `/html/bbsp/common/ontstate.asp` using the existing robust constructor parser;
- runtime PON capability promotion only after endpoint + recognizable response + parser success;
- protocol descriptor in Huawei connect/capability responses;
- automated tests for family/auth detection, token privacy, no blind login retry, PON parser and conservative capability promotion.

### ALREADY_EXISTS

- centralized HTTP transport/session object;
- cookies contained in the session;
- read-only retry once after reauthentication;
- writes submitted once without blind replay after auth loss;
- quote/escape/nesting-aware JavaScript constructor parser;
- device, optical, WAN, Ethernet/LAN, clients, Wi-Fi, DHCP, DNS, DMZ, TR-069, diagnostics, profiles and history surfaces for the current local Huawei implementation;
- normalized Wi-Fi `CURRENT`, `DEFAULT`, `SUPPORTED` domain;
- capability-driven generic API routes.

### IMPROVED

- provider fingerprint now knows both RandCount and RandString markers;
- authentication selection is evidence-driven instead of one global Huawei flow;
- generic Huawei detection keeps model + firmware independently from profile verification;
- capability evidence can now be promoted dynamically from a safe probe instead of requiring a hard-coded model profile.

### SCHEDULED NEXT PR

1. **Huawei telemetry slice:** WAN traffic statistics, richer Ethernet telemetry, PON/optical normalization and LAN-client deduplication using family-specific readers where evidence exists.
2. **Session hardening slice (may move earlier if telemetry proves it necessary):** strict same-TCP RandCount strategy for the HG8245X6-style firmware, only when a fixture/device can prove the requirement; session-expiration classification and cache invalidation improvements.
3. **Wi-Fi extension slice:** radio enable and any additional channel/width/mode mappings that are confirmed for a family. Preserve normalized `WifiConfiguration`/`WifiCapabilities`; do not reuse EG8041 enums globally.
4. **DHCP/DMZ slice:** family-specific reservation/DMZ transport with dynamic WAN-domain discovery; no hard-coded universal WANPPP domain.
5. **Cache policy slice:** classify identity/capabilities/configuration/dynamic telemetry separately instead of copying fixed TTLs.
6. **Drift slice:** `DesiredConfiguration`, `CurrentSnapshot`, `ConfigurationDrift`, `DriftDetector`; no automatic ONT mutation daemon.

### DEFERRED PHYSICAL VALIDATION

- RandString authentication on a real EG8021V5-class ONT;
- PON positional semantics and online-state interpretation on EG8021V5 and any non-EG8021 firmware;
- PON endpoint availability/shape on the local EG8041X7-10;
- strict TCP-connection affinity for HG8245X6-style RandCount firmware;
- EG8145V5/EG8145X6 behavior beyond the independently observed login/read surfaces;
- all new cross-family writes.

### REJECTED WITH REASON

- copying the external regex constructor parser: Access Manager's parser is already more robust;
- executing arbitrary router JavaScript in an embedded JS VM: unnecessary for current normalized constructor data and expands the attack/runtime surface;
- using model name alone to select all Huawei behavior: contradicted by cross-repo firmware differences;
- treating `/asp/GetConfig.asp` / `/asp/SetConfig.asp` as EG8041 endpoints: evidence is from a different documented family;
- copying fixed cache TTL values: cache freshness differs by identity/configuration/telemetry;
- automatic reconciliation daemon: too risky before explicit drift modeling and operator-controlled remediation.

## Physical validation boundary

No behavior introduced by this matrix is marked physically validated merely because it appears in an external repository. External behavior is `OBSERVED IN EXTERNAL FIRMWARE`; Access Manager tests are `TESTED AUTOMATICALLY` / `TESTED WITH FIXTURE`. Real-hardware validation remains a separate state.

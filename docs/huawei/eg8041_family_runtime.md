# EG8041 AMP/BBSP/BREBG2 family runtime

This document is the implementation audit for the PR that generalizes the previously EG8041X7-owned runtime. Status describes Access Manager behavior after runtime evidence; it is not a promise based on marketing model names.

## Family selection

A session is treated as EG8041/BREBG2-compatible only after `AMP_BBSP` protocol evidence plus the expected 2.4/5 GHz `WLANConfiguration` / `WiFi.Radio` object graph is parsed. `CfgMode=BREBG2` is supporting evidence, not a universal family switch. EG8041X6-10 and EG8041X7-10 have independent authorized local evidence for this surface.

## Feature audit

| Feature | Status | Ownership / evidence | Write boundary |
|---|---|---|---|
| Device info | `GENERALIZED_IN_THIS_PR / READ_SUPPORTED` | SSMP device reader + successful parser | no new mutation |
| WAN list/status | `GENERALIZED_IN_THIS_PR / READ_SUPPORTED` | existing AMP/BBSP reader; object path retained | WAN mutation not expanded |
| WAN statistics | `READ_SUPPORTED WHEN PRESENT`, otherwise `UNKNOWN` | normalized only from actual fields | missing counter stays `None` |
| WAN object discovery | `ALREADY_SHARED + GENERALIZED` | active PPP/service object is discovered; diagnostics use selected object | no hardcoded `WANPPPConnection.1` |
| Ethernet | `READ_SUPPORTED WHEN PROBED` | existing reader promoted only after parser success | writes not promoted |
| Clients | `GENERALIZED_IN_THIS_PR / READ_SUPPORTED WHEN PROBED` | DHCP/LAN/Wi-Fi feeds merge by normalized MAC | no mutation |
| Wi-Fi Basic | `ALREADY_SHARED / READ_SUPPORTED WHEN PROBED` | existing generated-WebUI reader | write only where runtime capability exists |
| Wi-Fi Advanced | `GENERALIZED_IN_THIS_PR` | EG8041 object graph + shared mapper | POST once + readback; X6 physical write effect still pending per operation |
| Wi-Fi Radio | `GENERALIZED_IN_THIS_PR` | Radio.1/Radio.2 signatures | same safety as advanced Wi-Fi |
| Channel discovery | `GENERALIZED_IN_THIS_PR / READ_SUPPORTED` | `WlanChannel.asp`; firmware result feeds `SUPPORTED` | none |
| DHCP config | `READ_SUPPORTED WHEN PROBED` | existing family reader | X6 write not inherited from X7 |
| DHCP Static | `ALREADY_SHARED FOR X7`; X6 write `PHYSICAL_VALIDATION_PENDING` | existing object/CGI implementation | no blind promotion |
| DNS | `READ_SUPPORTED WHEN PROBED` | existing reader | X7 validated mapping preserved; X6 write requires evidence/readback |
| Static DNS hosts | `ALREADY_SHARED FOR X7`; X6 write pending | existing mapped implementation | not promoted by family name |
| DMZ | `READ_SUPPORTED WHEN PROBED` | existing reader | write not auto-promoted |
| TR-069 | `READ_SUPPORTED WHEN PROBED` | existing reader | credentials/write not auto-promoted |
| LAN IPv4 | `READ_SUPPORTED WHEN PROBED` | existing reader | destructive LAN changes not expanded |
| PON status | `ALREADY_SHARED / READ_SUPPORTED WHEN PROBED` | #84/#85 normalized PON reader | read only |
| PON statistics | `ALREADY_SHARED WHEN CLI AVAILABLE` | #85 optional read-only CLI | no counter clear |
| Optical | `ALREADY_SHARED / READ_SUPPORTED WHEN PROBED` | #85 normalized optical readers | read only |
| Resource telemetry | `READ_SUPPORTED WHEN PRESENT` | existing CLI telemetry plus WebUI normalization helper | read only |
| Firewall level/filtering | `READ_SUPPORTED WHEN PROBED` | existing reader / IPv4 filter service | X6 mutations not promoted blindly |
| Native Ping | `GENERALIZED_IN_THIS_PR / VALIDATED_PHYSICALLY` | existing native implementation + local X6/X7 evidence; normalized result added | diagnostic start is write-once command, then polling |
| Native Traceroute | `GENERALIZED_IN_THIS_PR / VALIDATED_PHYSICALLY` | existing native implementation + active-WAN discovery + normalized hops | diagnostic start once, then polling |
| Speed-test / Section Speed pages | `READ/PRESENT SURFACE OBSERVED` | mapped SSMP pages | **START = UNKNOWN**; no endpoint invented |
| Configuration profiles | `GENERALIZED_IN_THIS_PR` | generic `DeviceService` dispatch + family preflight | no silent partial apply; unsupported requirement aborts before mutation |
| History/session snapshot | `ALREADY_SHARED` | existing Huawei runtime | unchanged |
| HG8010 CLI telemetry | `ALREADY_SHARED FROM #85` | separate WebUI/CLI strategy | not forced into EG8041 family |

## Normalized Wi-Fi semantics

`CURRENT`, `DEFAULT` and `SUPPORTED` remain separate. Current state comes from the device response. Defaults are a family recommendation/known baseline. Supported channels use live `WlanChannel.asp` results when available. Unknown channel-width or mode raw values are not invented.

Known EG8041 mappings in this PR:

| Band | Normalized width | Raw value |
|---|---|---|
| 2.4 GHz | `auto_20_40` | `X_HW_HT20=0` |
| 5 GHz | `auto_20_40_80_160` | `X_HW_HT20=4` |

Advanced-field validation follows the physically observed family surface: DTIM `1..255`, beacon interval `20..1000 ms`, RTS `1..2346`, fragmentation `256..2346`.

## HTTPS/TLS and management addressing

The central Huawei transport represents scheme and port separately. An HTTP response containing the characterized Huawei `SSLPort` bootstrap may negotiate to HTTPS while keeping port 80. Embedded/untrusted certificate handling is centralized; readers do not scatter `verify=False` calls.

Vendor probing includes RFC1918 plus RFC6598 shared address space `100.64.0.0/10`. RFC6598 is never labelled RFC1918.

## Diagnostics normalization

Native ping keeps legacy response keys for compatibility and also exposes normalized `target`, `resolved_ip`, `interface`, packet counts/loss, `min_ms`, `avg_ms`, `max_ms`, `status`, and `error`.

Traceroute keeps legacy hop fields and adds normalized `index`, `address`, `hostname`, `rtt_samples_ms`, `timeout`, and `error`. The active WAN object path comes from the WAN inventory; it is not hardcoded.

## Profile application

The generic `/profiles/apply` route is device-service driven. On a non-X7 EG8041 family session, changed profile requirements are checked against the current session's write capabilities before any mutation. If one required feature is unsupported, the result returns explicit `supported` and `unsupported` feature lists and sends no partial mutation.

Each real provider writer continues to own its own write-once/readback behavior. This PR does not claim a fake global transaction or rollback.

## Physical-validation boundary

EG8041X7-10 keeps its pre-existing physical write validation. EG8041X6-10 has authorized local evidence for WebUI model/family, HTTPS-on-port-80 bootstrap, BREBG2, dual-band Wi-Fi object signatures/channel discovery, WAN and native ping/traceroute. The assistant did not re-exercise the physical device during this PR execution; that evidence was supplied by the operator and captured only in sanitized fixtures/docs. Captured X6 Wi-Fi POST structure is not labelled as a physically validated write effect.

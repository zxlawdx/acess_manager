# Huawei Phase 0 + Phase 1 evidence matrix

This document records the evidence boundary for the protocol architecture introduced by `feat/huawei-phase0-phase1-architecture`. It contains no credentials, customer addresses, cookies or live session tokens.

## Scope

The implementation keeps Huawei protocol axes orthogonal:

- transport policy;
- authentication flow;
- protocol/endpoint family;
- structural parser;
- runtime capabilities.

A marketing model string is only a hint. Runtime endpoint evidence remains authoritative.

## HG8145X6 / HG8145X6-10

### Physically validated by the project owner

- HTTP port 80 bootstrap that advertises HTTPS on port 80;
- HTTPS on port 80 with the device's self-signed certificate accepted by the local client policy;
- RandCount challenge and Base64 password login form;
- authenticated cookie/session lifecycle;
- WAN/PPPoE including IP, gateway/DNS, BRAS, VLAN, MTU and session uptime;
- SSID inventory;
- associated Wi-Fi clients;
- client RSSI and RX/TX PHY rates;
- device uptime, CPU and memory data.

These capabilities still require a successful authenticated runtime read before they are promoted for the current session.

### Runtime-probed, not yet physically classified

Optical telemetry is probed read-only, in order, from firmware-specific candidates:

1. `/html/amp/opticinfo/opticinfo.asp`
2. `/html/amp/common/getSmartDiagnoseResult.asp`
3. `/html/ssmp/common/getOpticTxRx.asp`

No candidate is assumed universal. If none returns recognizable optical/status fields, the capability remains unavailable/unknown and no value is fabricated.

### Write support

HG8145X6 write support is intentionally disabled in this phase. The EG8041 mutation payloads are not inherited merely because both devices expose AMP/BBSP pages. WPS and password-reveal behavior require their own physical browser capture/profile evidence.

## Authentication safety

`HuaweiCredentialSubmissionBudget` hard-limits one credential-bearing request per authentication attempt. Fingerprinting may perform read-only probes, but an ambiguous auth fingerprint raises `auth_family_ambiguous` before credentials are submitted. No Base64 → hash → alternate-flow brute force is permitted.

Exact TCP-connection affinity and single-write POST requirements are represented by `HuaweiTransportPolicy`, but `requests.Session` is not claimed to satisfy those guarantees. Such policies fail closed until a socket-level transport and regression fixture are implemented.

## JavaScript parsing

`HuaweiJsConstructorParser` parses generated Huawei `new Constructor(...)` structures without executing JavaScript. It handles quoted/nested arguments, `\\xNN` escapes, variable field counts, optional family schemas and preservation of unknown positional fields.

## Research-only families in this phase

The architecture recognizes but does not authenticate these as production flows yet:

- `/api/webserver/SesTokenInfo` + `/api/system/user_login` API family;
- ASP `GetConfig` / `SetConfig` family;
- Huawei LTE/5G SCRAM/PBKDF2 family.

Recognition is deliberately separate from support.

## External reference attribution

`EnochT14/ontwatch` was used as protocol/field evidence for the HG8145X6 read contract. Its current repository license was re-checked as MIT before this work. The Access Manager does **not** copy the ONTWatch Flask application, database layer or dashboard; only protocol behavior and independently normalized fields are adapted into the existing architecture.

Other Huawei repositories listed in `docs/huawei/external_references.md` remain protocol/reference evidence under their documented license constraints. GPL or unlicensed source is not copied into this implementation.

## Test classification

- **Physical evidence:** the HG8145X6 transport/auth and read fields listed above, supplied from real-device validation.
- **Fixture validated:** transport policy, HTTPS:80 bootstrap parsing, BOM/hex RandCount normalization, one-submission budget, ambiguous-auth behavior, structural JavaScript parser, HG8145X6 field mapping/fingerprint selection and optical candidate fallback.
- **Reference validated:** ONTWatch HG8145X6 endpoint/constructor semantics.
- **Research-only:** API SesToken auth, ASP_CONFIG writes, socket-affinity auth transport, LTE/5G SCRAM, HG8145X6 mutations not physically captured.

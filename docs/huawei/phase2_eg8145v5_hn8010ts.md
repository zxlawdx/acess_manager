# Huawei Phase 2 — EG8145V5 + HN8010TS

## Scope

Phase 2 reuses the Huawei transport/authentication architecture introduced in Phase 0/1 and adds read-only model profiles for **EG8145V5** and **HN8010TS**.

The implementation deliberately does **not** create another HTTP client. Both profiles use the authenticated `HuaweiFamilyAwareWebClient` session and therefore share:

- RandCount detection/authentication;
- the single credential-submission budget;
- cookies and session lifecycle;
- TLS/port negotiation;
- protected GET and read-only POST helpers;
- sanitized HTTP tracing.

Model-specific behavior lives in endpoint/schema profiles in `huawei_eg8145v5_family_runtime.py`.

## Evidence

### EG8145V5

Reference implementations:

- `chickenzord/go-huawei-client` (MIT): stateful client, `POST /asp/GetRandCount.asp`, Base64 password, `POST /login.cgi`, `POST /html/bbsp/common/GetLanUserDevInfo.asp`, and `GET /html/ssmp/deviceinfo/deviceinfo.asp` for CPU/memory information.
- `undefjs/huawei-eg8145v5-hacs` (MIT): independent confirmation of the legacy cookie, RandCount/Base64 login, device information, and the alternate `/html/bbsp/userdevinfo/getuserdevinfo.asp` client surface.

Implemented readers:

- device identity / firmware / hardware;
- CPU usage;
- memory usage;
- uptime;
- user-device inventory.

The client inventory is normalized conservatively. `Port` values containing `SSID`, `WLAN`, or `WiFi` are classified as Wi-Fi; values containing `LAN`, `ETH`, or `Ethernet` are classified as LAN; all other values remain `unknown`. RSSI/rates are not fabricated because the cited Phase-2 client surfaces do not establish those fields.

### HN8010TS

Reference implementation:

- `chickenzord/go-huawei-client` PR #2 (draft, MIT repository): adapts the EG8145V5 shared-session architecture for HN8010TS and adds optical telemetry from `/html/amp/opticinfo/opticinfo.asp` using `transOpticPower` and `revOpticPower`.

Implemented readers:

- device identity / firmware / hardware;
- CPU usage;
- memory usage;
- uptime;
- user-device inventory;
- optical TX/RX through the existing characterized `stOpticInfo` parser.

HN8010TS is not selected from the model hint alone. The runtime requires authenticated RandCount context, a matching model parsed from `deviceinfo.asp`, a recognized client schema, and recognized optical data.

## Capability policy

Both Phase-2 profiles are **read-only**.

No capability is promoted to write support from repository/reference evidence. The provider explicitly blocks Wi-Fi mutations before any inherited EG8041 writer can run. EG8145V5 does not inherit HN8010TS optical support merely because the two profiles share transport/authentication.

## Validation levels

### Reference validated

- endpoint paths and request methods described above;
- RandCount/Base64 shared-session architecture;
- HN8010TS optical endpoint and TX/RX field names.

### Fixture validated

Sanitized fixtures cover:

- `stDeviceInfo` for EG8145V5 and HN8010TS;
- `stUserDevInfo` client records;
- `stOpticInfo/16` for HN8010TS;
- CPU/memory/uptime scalar fields;
- LAN/Wi-Fi classification from explicit `Port` evidence;
- selection rejection on model mismatch or missing HN optical shape;
- write capabilities remaining disabled.

### Not physically validated

No real EG8145V5 or HN8010TS was used in this phase. Consequently:

- `physical_validation` remains `false`;
- no write is enabled;
- no Wi-Fi password/WPS/radio mutation is inferred;
- HN8010TS optics remains reference + runtime-parser evidence until confirmed on real hardware.

## Stacked delivery

This phase is developed on top of `feat/huawei-phase0-phase1-architecture` / PR #95. It should be reviewed as a stacked change and must not be merged ahead of its Phase 0/1 dependency.

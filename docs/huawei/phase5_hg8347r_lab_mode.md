# Huawei Phase 5 — HG8347R clean-room + lab mode

## HG8347R evidence boundary

Phase 5 follows the roadmap requirement to implement HG8347R by clean-room because the public `CutJiuCai/hg8347r` reference has no explicit repository license.

Only factual protocol observations are used:

- tested device in the reference: EchoLife HG8347R EPON Terminal;
- hardware: `627.A`;
- software: `V3R017C10S208`;
- customization: `BJUNICOM`;
- authentication family: legacy RandCount + Base64 password;
- user-device page: `/html/bbsp/userdevinfo/userdevinfolan.asp`;
- page token: hidden `hwonttoken` / `onttoken`;
- read-only AJAX query: `/getajax.cgi?x=InternetGatewayDevice.LANDevice.1.X_HW_UserDev.{i}&RequestFile=html/bbsp/userdevinfo/userdevinfolan.asp`;
- response: JSON list after decoding Huawei `\xNN` escapes, with terminal `{ "result": 0 }` marker;
- factual logout path: `/logout.cgi?RequestFile=html/logout.html`.

The reference does **not** establish HG8347R Wi-Fi writes, WAN writes, optical control, firmware upgrade or reboot. Those are therefore not presented as HG8347R-supported operations.

`HuaweiHG8347RRuntime` promotes only the client inventory after authenticated runtime fingerprinting. It normalizes MAC, IP, hostname, port/link type, online state, IP assignment type, uptime and traffic fields. It does not manufacture RSSI/SNR/rates that are absent from this schema.

## Explicit Huawei lab mode

The user requested a way to exercise mutations on test hardware before per-model physical validation is complete. This is provided as a session-local, opt-in lab surface.

Lab mode is **off after every connect and disconnect**.

### Enable

```http
POST /api/huawei/lab/mode
Content-Type: application/json

{"enabled": true}
```

Status:

```http
GET /api/huawei/lab
```

The status lists mapped mutation operations available in the current legacy AMP/BBSP session and the reboot modes known for that protocol.

## Experimental writes

### Named mapped operation

```http
POST /api/huawei/lab/write
Content-Type: application/json

{
  "operation": "upnp",
  "config": {
    "x.Enable": "1",
    "y.Enable": "1"
  }
}
```

The named operations come from the existing Access Manager captured/mapped Huawei surface. They still obtain a fresh page token, submit once, never blind-retry a mutation and use read-back when a mapped read-back exists.

### Exact captured request

For firmware-specific fields not represented by a named operation:

```http
POST /api/huawei/lab/write
Content-Type: application/json

{
  "path": "/html/.../set.cgi?x=...&RequestFile=...",
  "payload": {
    "x.Enable": "1"
  },
  "referer": "/html/.../page.asp",
  "token_page": "/html/.../page.asp",
  "readback_path": "/html/.../page.asp",
  "readback_expect": {
    "Enable": "1"
  }
}
```

The endpoint must remain relative to the already connected ONT. Session token/cookie fields supplied by the caller are stripped/replaced by the live session token machinery.

## Reboot lab surface

```http
POST /api/huawei/lab/reboot
Content-Type: application/json

{}
```

### HG8245H modern `/api/`

When Phase 3 is active, lab reboot supports one explicitly selected mutation per request:

- default `variant="reboot"`: `POST /api/system/reboot` with XML `<Reboot>1</Reboot>`;
- `variant="deviceinfo_restart"`: reference-observed alternate `POST /api/system/deviceinfo` with `<Restart/>`.

The two variants are **never tried sequentially**. A destructive request may have taken effect even when the response is lost, so automatic fallback would violate the no-blind-retry rule.

### HG8245H legacy

The MIT HG8245H reboot reference documents:

- token page `/html/ssmp/reset/reset.asp`;
- mutation `/html/ssmp/reset/set.cgi?x=InternetGatewayDevice.X_HW_DEBUG.SMP.DM.ResetBoard&RequestFile=html/ssmp/reset/reset.asp`;
- body containing the fresh `x.X_HW_Token`;
- a GoAhead quirk requiring the complete HTTP request to be written in a **single `sendall()`**.

`SingleWriteHttpTransport` implements that framing only for explicit lab use. It does not log or return raw response headers/body.

### Other Huawei firmware, including HG8347R

If the current firmware exposes `/html/ssmp/reboot/reboot.asp`, Access Manager may auto-submit only an unambiguous POST form whose action clearly names reboot/reset/set.cgi. Otherwise it returns `requires_exact_request=true`.

A browser-captured request can then be submitted explicitly:

```http
POST /api/huawei/lab/reboot
Content-Type: application/json

{
  "request": {
    "path": "/html/.../set.cgi?...",
    "payload": {},
    "referer": "/html/.../reboot.asp",
    "token_page": "/html/.../reboot.asp"
  }
}
```

For firmware that requires one-write framing:

```json
{
  "request": {
    "single_write": true,
    "path": "/html/.../set.cgi?...",
    "payload": {},
    "referer": "/html/.../reset.asp",
    "token_page": "/html/.../reset.asp"
  }
}
```

HG8347R has **no known reboot endpoint in the clean-room source**, so the implementation deliberately uses this live-firmware/captured-request path rather than inventing one.

## Safety contract retained in lab mode

Lab mode means “allow experimental device mutations,” not “remove protocol safety.” The following remain mandatory:

- one credential-bearing login submission budget;
- no Base64/hash brute-force login fallback;
- no blind mutation retry;
- relative endpoints only;
- fresh CSRF/token acquisition where the WebUI requires it;
- read-back when available;
- secret-safe history/trace behavior;
- experimental capabilities remain `physical_validation=false` until verified on hardware.

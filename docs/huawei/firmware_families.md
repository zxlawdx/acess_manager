# Huawei firmware / protocol families

Huawei marketing model names are not transport contracts. Access Manager resolves protocol behavior from a combination of observed endpoints, authentication flow, firmware identity, response format and parser success.

## `amp_bbsp`

This name describes the generated Huawei WebUI surface containing combinations of:

- `/html/ssmp/`
- `/html/amp/`
- `/html/bbsp/`
- older `/html/status/` read pages
- `/login.cgi`
- JavaScript constructor records such as device/WAN/Ethernet/ONT state objects

The family can contain more than one authentication strategy and more than one endpoint generation.

### `BREBG2-like` firmware strategy

`BREBG2-like` is a narrower runtime strategy inside `amp_bbsp`; it is not a
marketing-model alias.

Authorized local evidence now exists for both EG8041X6-10 and EG8041X7-10. The
shared strategy is selected only when the session proves:

1. AMP/BBSP protocol-family evidence;
2. expected WLAN object signatures including `WLANConfiguration.1`,
   `WLANConfiguration.5`, `WiFi.Radio.1` and `WiFi.Radio.2`;
3. successful parsers/probes for the feature being promoted;
4. `CfgMode=BREBG2` when it is exposed, or independent local/model evidence for
   a known EG8041 member.

The local EG8041X6-10 WebUI also demonstrated an HTTP bootstrap that advertises
`SSLPort=80` and sends browsers to HTTPS on the same explicit port. Scheme and
port are therefore negotiated independently in the central transport.

External EG8145V5-V2 material also reports `CfgMode=BREBG2`, RandCount and SSMP.
That is only **candidate family evidence**: `CfgMode` alone is insufficient to
select this strategy or enable writes.

### Auth variant: `rand_count`

Evidence:

- Access Manager local EG8041X6-10 and EG8041X7-10 evidence;
- HG8010H/EG8010H newer firmware research;
- `Erenn0989/huawei-ont-mcp` on an HG8245X6-family ISP firmware;
- `chickenzord/go-huawei-client` on EG8145V5;
- `logon84/Huawei-Optistar-EG8145X6-10-remote-login-example` on EG8145X6-10.

Common shape:

```text
/asp/GetRandCount.asp
-> /login.cgi
-> authenticated cookie/session
-> /html/{ssmp,amp,bbsp}/...
```

`x.X_HW_Token` is used in login payloads. Details differ by firmware:

- challenge may be requested with POST or GET;
- some responses are the token itself while one HG8010H exporter observes a
  larger response whose final 32 hexadecimal characters are the token;
- proof-of-login pages differ;
- HG8245X6 material reports possible challenge/login TCP affinity;
- some OptiXstar material uses HTTPS on explicit port 80.

Access Manager records POST-vs-GET challenge evidence and only applies the
trailing-32 extraction to the exact 32-hex suffix signature.

### Auth variant: `rand_cookie_hash`

Older HG8010H research shows a materially different generation where a
RandCount challenge participates in a derived authentication cookie instead of
the ordinary UserName/PassWord RandCount form. `RndSecurityFormat` and derived
cookie markers characterize this variant.

Access Manager currently **recognizes and refuses** this flow before submitting
credentials. It is not treated as ordinary RandCount and no external credential
derivation/bypass implementation was copied.

### Auth variant: `rand_string_session_token`

Evidence: `siedgustavo/huawei-ont-stats` on EG8021V5.

```text
/html/ssmp/common/getRandString.asp
-> /login.cgi
-> /html/ssmp/common/GetRandToken.asp
-> authenticated cookie/session + post-login token
```

This is not treated as a cosmetic variation of RandCount. The challenge endpoint and post-login token lifecycle are different enough to justify a separate auth strategy while keeping the same shared transport/session abstraction.

### Optical endpoint/signature variants

Cross-source HG8010H/Huawei WebUI evidence includes:

- `/html/status/opticinfo.asp` with `stOpticInfo/6`;
- `/html/amp/opticinfo/opticinfo.asp` with `stOpticInfo/8`;
- `/html/amp/opticinfo/opticinfo.asp` with extended `stOpticInfo/16`.

These are modeled as endpoint/signature variants inside the generated WebUI
family. Access Manager does not infer units/positions for any other argument
count.

## `asp_config`

External documentation for HG8245H5 describes a configuration surface around:

- `/asp/GetConfig.asp`
- `/asp/SetConfig.asp`
- `InternetGatewayDevice.*`

This family is deliberately separate from the AMP/BBSP mutation CGI model. The public reference is documentation-oriented, so Access Manager does **not** auto-enable this family merely from a model name. Runtime support stays `UNKNOWN` until an endpoint exists, returns a recognizable response and a parser succeeds.

## `unknown`

Unknown is a valid state and preferable to assigning a model to the wrong family. A successful Huawei login does not by itself prove every feature page or configuration transport.

## Detection rules

The implementation uses these conservative rules:

1. public login-page markers can select an auth strategy before credential submission;
2. read-only challenge endpoints may be probed when the login page is ambiguous;
3. observed `/html/ssmp|amp|bbsp|status/` endpoints establish generated-WebUI/`amp_bbsp` evidence;
4. actually observed `/asp/GetConfig.asp` or `/asp/SetConfig.asp` establishes `asp_config` evidence;
5. model name is recorded independently and is never sufficient to choose all behavior;
6. firmware version is retained when found in authenticated device information;
7. an unknown operational profile can be model-recognized without becoming locally verified;
8. feature support is promoted only by an endpoint/transport response plus a successful parser;
9. `BREBG2` is supporting evidence, not a blanket compatibility switch;
10. write support is never inherited from another model solely through family recognition.

## Capability promotion

Protocol-family detection and feature capabilities are separate decisions.

For a read feature:

```text
endpoint or already-enabled CLI transport exists
+ recognizable response
+ parser succeeds
= READ_SUPPORTED
```

For an EG8041-family write:

```text
shared object/endpoint signature
+ characterized payload mapping
+ POST once
+ readback
= runtime WRITE_SUPPORTED operation
```

Physical-validation metadata remains separate. A captured POST is not a
successful physical effect.

## Current validation status

- **EG8041X7-10 RandCount/BREBG2:** existing local physical evidence; existing mapped writes and readbacks remain authoritative.
- **EG8041X6-10 RandCount/BREBG2:** authorized local evidence for model/family, HTTPS:80 bootstrap, dual-band Wi-Fi signatures/channel discovery, WAN and native ping/traceroute. New mutation effects remain physical-validation-pending unless separately exercised with readback.
- **HG8010H newer RandCount + optical/WAP telemetry:** multiple external sources + sanitized characterization fixtures + automated tests; not physically validated by the HG8010 PR.
- **HG8010H older derived-cookie auth:** externally observed; recognized but deliberately unsupported for authentication.
- **EG8010H:** external family evidence; recognized only, not promoted to HG8010H read support by model similarity.
- **EG8021V5 RandString:** observed in external firmware/source; implemented and fixture-tested in Access Manager; pending physical validation on a real device.
- **EG8145V5:** multiple external RandCount/WebUI/CLI sources; recognized only until the exact reader/object signatures are characterized.
- **EG8145V5-V2:** external RandCount + SSMP + `BREBG2` evidence; research-only family candidate.
- **HG8245X6 same-TCP RandCount:** externally observed; not implemented as strict socket affinity yet.
- **EG8145X6-10 RandCount/HTTPS:80:** externally observed; family evidence only, not a promise of EG8041 semantics.
- **HG8245H5 ASP_CONFIG:** externally documented; runtime support `UNKNOWN` pending stronger evidence/fixture/device.

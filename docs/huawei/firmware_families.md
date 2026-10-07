# Huawei firmware / protocol families

Huawei marketing model names are not transport contracts. Access Manager resolves protocol behavior from a combination of observed endpoints, authentication flow, firmware identity, response format and parser success.

## `amp_bbsp`

This name describes the generated Huawei WebUI surface containing combinations of:

- `/html/ssmp/`
- `/html/amp/`
- `/html/bbsp/`
- `/login.cgi`
- JavaScript constructor records such as device/WAN/Ethernet/ONT state objects

The family can contain more than one authentication strategy.

### Auth variant: `rand_count`

Evidence:

- Access Manager local EG8041X7-10 implementation;
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

`x.X_HW_Token` is used in login payloads. Details differ: method used for the challenge, proof-of-login page and possible TCP connection affinity are firmware-specific.

### Auth variant: `rand_string_session_token`

Evidence: `siedgustavo/huawei-ont-stats` on EG8021V5.

```text
/html/ssmp/common/getRandString.asp
-> /login.cgi
-> /html/ssmp/common/GetRandToken.asp
-> authenticated cookie/session + post-login token
```

This is not treated as a cosmetic variation of RandCount. The challenge endpoint and post-login token lifecycle are different enough to justify a separate auth strategy while keeping the same shared transport/session abstraction.

## `asp_config`

External documentation for HG8245H5 describes a configuration surface around:

- `/asp/GetConfig.asp`
- `/asp/SetConfig.asp`
- `InternetGatewayDevice.*`

This family is deliberately separate from the AMP/BBSP mutation CGI model. The public reference is documentation-oriented, so Access Manager does **not** auto-enable this family merely from a model name. Runtime support stays `UNKNOWN` until an endpoint exists, returns a recognizable response and a parser succeeds.

## `unknown`

Unknown is a valid state and preferable to assigning a model to the wrong family. A successful Huawei login does not by itself prove every feature page or configuration transport.

## Detection rules

The first implementation uses these conservative rules:

1. public login-page markers can select an auth strategy before credential submission;
2. read-only challenge endpoints may be probed when the login page is ambiguous;
3. observed `/html/ssmp|amp|bbsp/` endpoints establish `amp_bbsp` evidence;
4. actually observed `/asp/GetConfig.asp` or `/asp/SetConfig.asp` establishes `asp_config` evidence;
5. model name is recorded independently and is never sufficient to choose all behavior;
6. firmware version is retained when found in authenticated device information;
7. an unknown model can be identified with medium confidence without being marked as a locally verified profile.

## Capability promotion

Protocol-family detection and feature capabilities are separate decisions.

For a read feature:

```text
endpoint exists
+ recognizable response
+ parser succeeds
= READ_SUPPORTED
```

For a write feature, endpoint presence is insufficient. Payload, mapping and semantics must be known, and physical validation is required where the current evidence policy demands it.

## Current validation status

- **EG8041X7-10 RandCount:** existing local/physical evidence predates this PR; regressions must preserve it.
- **EG8021V5 RandString:** observed in external firmware/source; implemented and fixture-tested in Access Manager; **pending physical validation on a real device**.
- **HG8245X6 same-TCP RandCount:** externally observed; **not implemented as strict socket affinity yet**.
- **EG8145V5 / EG8145X6-10 RandCount:** externally observed; family evidence only, not a promise of all EG8041 features.
- **HG8245H5 ASP_CONFIG:** externally documented; runtime support `UNKNOWN` pending stronger evidence/fixture/device.

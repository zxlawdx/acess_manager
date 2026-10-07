# EG8041X6-10 HTTPS:80 authentication hotfix

## Scope

This hotfix restores the pre-#86 authentication semantics for the Huawei EG8041X6-10 while retaining the endpoint negotiation introduced in #86. It does not promote new Wi-Fi, WAN, profile, diagnostic or telemetry write capabilities.

## Regression boundary

The last known main before #86 was `fc057eb8631c0b94afa04c2e860d63db79c402e7`.

Before #86, `DeviceService` selected `HuaweiTelemetryRuntimeService` and `HuaweiFamilyAwareWebClient`. The FamilyAware client owned the real authentication sequence:

1. fresh `requests.Session`;
2. root login page;
3. RandCount selection/probe;
4. `POST /asp/GetRandCount.asp` with safe GET fallback;
5. `POST /login.cgi` with the existing base64 password / `Language=english` / `x.X_HW_Token` contract and the legacy RandCount cookie behavior;
6. authenticated proof through `GetMenuArray` or protected `deviceinfo`.

`HuaweiNegotiatingWebClient` was introduced by commit `182559613d01f2f13f886ef758dde6aa1e4273b1`. Commit `8289b4cf163875686e761b374c39af583c38414e` changed the production dispatcher to the EG8041 family runtime and activated that client in the real connection path.

The RandCount payload/FamilyAware algorithm did not change. The regression boundary is the newly activated transport/auth wrapper. Its pre-hotfix `login()` performed an additional HTTPS root validation before delegating to `HuaweiFamilyAwareWebClient.login()`. FamilyAware then closed that session and created a new one for the actual authentication. The extra preflight was therefore outside the previously validated authentication sequence and added a new failure point. In addition, request/TLS failures wrapped by FamilyAware as `RuntimeError` were being reclassified as authentication failures, hiding the actual phase.

Because an explicit `https=true` input skips HTTP endpoint discovery, only the operator's post-merge physical retest can identify the exact network/TLS phase that affected that mode. CI does not prove the hardware-specific failure mechanism.

## Hotfix behavior

`HuaweiNegotiatingWebClient` remains a `HuaweiFamilyAwareWebClient`. Endpoint negotiation is transport-only:

- explicit `HOST:80` + `https=true` resolves directly to `https://HOST:80`;
- auto `HOST:80` + HTTP Huawei bootstrap with `SSLPort='80'` resolves to `https://HOST:80`;
- after resolution, both paths use the same FamilyAware root -> challenge -> login -> proof pipeline;
- `HuaweiFamilyAwareWebClient.login()` may recreate `requests.Session`, and the negotiating subclass factory guarantees `session.verify is False` on the newly created embedded-device session;
- session recreation never changes the resolved endpoint back to HTTP, removes port 80, or assumes port 443.

The browser's red/struck-through HTTPS / `Not secure` presentation is certificate trust status. It is not evidence that the transport is HTTP.

## Production transport audit

`DeviceService` is the production dispatcher. It selects `HuaweiEG8041FamilyProvider` and injects `HuaweiNegotiatingWebClient`. `HuaweiEG8041FamilyRuntimeService` also defaults to that client. Repository search found direct `HuaweiService()` construction only in tests; the base class remains dependency-injectable and is not a separate production provider path. Test doubles can continue to inject fake clients.

This hotfix therefore keeps one production EG8041 transport policy without rewriting the large base service during an authentication incident.

## Error classification

`HuaweiTransportError` records only sanitized metadata:

- transport code;
- connection phase;
- original exception type;
- resolved scheme;
- resolved port;
- selected auth flow.

It never records password, challenge, `X_HW_Token`, cookie or session token.

The API boundary maps at least:

- `NETWORK_ERROR` -> `Não foi possível alcançar a ONT.`
- `TLS_ERROR` -> `Não foi possível estabelecer TLS com a ONT.`
- `AUTH_REJECTED` -> `A ONT rejeitou a autenticação.`
- `AUTH_PROTOCOL_MISMATCH` -> `O fluxo de autenticação desta Huawei não foi reconhecido.`

## HUAWEI_HTTP_TRACE

When `HUAWEI_HTTP_TRACE=true`, the negotiating client's real session emits a sanitized line for root, RandCount, login and authenticated-proof requests containing method, scheme, port, path, status, redirect state, exception type and response signature.

The trace omits host by default and never emits query strings, request/response bodies, headers, passwords, cookies, challenges or tokens. Legacy `raw`/`unsafe` environment values do not disable those redactions in the negotiating client.

## Validation boundary

Sanitized fixtures characterize the known EG8041X6-10 authentication shape and test both explicit HTTPS:80 and HTTP-bootstrap-to-HTTPS:80 paths. This is fixture/CI validation only.

The hotfix becomes **physically validated** only after the operator updates `main`, runs with `HUAWEI_HTTP_TRACE=true`, and successfully authenticates the real EG8041X6-10 again.

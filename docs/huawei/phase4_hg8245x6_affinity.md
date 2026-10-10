# Huawei Phase 4 — HG8245X6 challenge/login TCP affinity

## Scope

Phase 4 implements only the transport requirement documented for a TTNET2-branded Huawei HG8245X6: the RandCount challenge and the credential-bearing `/login.cgi` request must use the exact same TCP connection.

This phase does **not** add Huawei write support, WPS, password reveal, reboot, ASP_CONFIG, or new universal HG/EG/X6 endpoint assumptions.

## Evidence

Primary public reference: `Erenn0989/huawei-ont-mcp` (MIT).

The reference reports that:

- authentication remains the legacy RandCount family;
- `POST /asp/GetRandCount.asp` returns the one-time token;
- `/login.cgi` rejects that token when the credential request is sent on a different TCP connection;
- a persistent `http.client.HTTPConnection` works because both requests stay on one connection;
- `requests.Session()` must not be treated as an exact-socket guarantee;
- repeated failed credential attempts can trigger a temporary login lockout, so blind retry is unsafe.

No source code from the MCP server is copied. Access Manager uses its own auth strategy, credential budget, response handling and provider architecture.

## Implementation

### `HuaweiEndpointProfile`

Transport requirements are represented independently from model names and runtime capabilities.

The Phase-4 reference profile is:

`hg8245x6_ttnet2_same_tcp`

It requires:

`challenge_login_connection_affinity = True`

The profile can be selected explicitly. Automatic pre-auth selection uses a strict login-page fingerprint and requires all observed markers:

- `GetRandCount.asp`
- `base64encode`
- `errloginlockNum`
- `LockLeftTime`

A marketing model string alone never activates the affinity path.

### `AffinityHttpTransport`

The adapter:

- uses `http.client.HTTPConnection` or `HTTPSConnection`;
- opens exactly one connection for the affinity exchange;
- sends challenge and login through that connection object;
- consumes each response body before the next request so HTTP/1.1 reuse remains valid;
- supports Access Manager's local TLS verification policy without changing global `requests` behavior;
- bridges only response cookies into the existing authenticated `requests.Session` after login;
- advertises `supports_connection_affinity=True`;
- deliberately advertises `supports_single_segment_post=False`.

Same-TCP authentication must never be confused with the separate single-write/raw-framing requirement researched for other Huawei firmware.

### Production composition

`HuaweiAffinityNegotiatingWebClient` subclasses the existing negotiating client.

For ordinary firmware:

- endpoint profile is `None`;
- `challenge_login_connection_affinity=False`;
- `_authenticate_rand_count()` delegates unchanged to the existing requests-based path.

For a proven affinity profile:

1. fetch RandCount on the dedicated connection;
2. normalize the challenge with the existing `RandCountAuth`;
3. claim the existing credential budget once;
4. submit `/login.cgi` on that same connection;
5. copy the returned session cookie into the normal session;
6. prove authentication through the existing read-only menu/device-info proof.

`HuaweiAffinityUnifiedProvider` only composes this client with the existing `HuaweiUnifiedProvider`. Capability behavior is unchanged.

## Safety properties

- credential submission budget remains exactly `1`;
- no sequential password transforms;
- no blind credential retry;
- no model-name-only activation;
- no global socket or `requests.Session` monkey patch;
- no new writes;
- no `verify=False` global setting;
- no raw cookie/password/token logging;
- a `single_segment_post=True` policy still fails closed in `AffinityHttpTransport`.

## Tests

`tests/test_huawei_phase4_hg8245x6_affinity.py` starts a local HTTP/1.1 fake Huawei server.

The server records the live connection object used for:

- `/asp/GetRandCount.asp`
- `/login.cgi`

The test fails unless both requests arrive over the exact same connection. It also asserts:

- exactly one credential POST;
- credential budget used exactly once;
- session cookie is adopted and read-only session proof succeeds;
- strict fingerprint selection;
- partial fingerprint does not activate affinity;
- ordinary RandCount remains on the old path;
- `requests.Session` still refuses to claim exact-socket affinity;
- same-TCP auth does not enable single-segment mutations.

## Validation state

- Transport adapter: fixture/CI validated after the Phase-4 suite passes.
- Public reference: source-code observed, MIT.
- HG8245X6 physical validation in the user's environment: pending.
- Writes: disabled.
- Model registry support level: remains conservative/research-only until physical runtime evidence exists.

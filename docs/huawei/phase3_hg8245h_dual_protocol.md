# Huawei Phase 3 — HG8245H dual protocol

## Scope

Phase 3 integrates the HG8245H as a **dual-protocol model**. The marketing model name is not a protocol selector.

Runtime selection is evidence-driven:

1. probe `GET /api/webserver/SesTokenInfo` without credentials;
2. when a valid `SesInfo` + `TokInfo` pair is returned, select the modern `api_sestoken` family;
3. otherwise keep the existing legacy Huawei fingerprint flow (`/asp/GetRandCount.asp` + `/login.cgi`);
4. never submit a second password variant after a credential-bearing request.

The implementation is stacked on Phase 0/1/2 and reuses the same session, credential budget and secret-safe tracing.

## Modern `/api/` flow

Reference: `bogomolov/huawei_HG8245H_remote` (MIT).

Characterized flow:

- `GET /api/webserver/SesTokenInfo`
  - `SesInfo` becomes session cookie context;
  - `TokInfo` becomes `__RequestVerificationToken` / `x.X_HW_Token` context.
- determine the password encoding **before credentials are submitted**;
- `POST /api/system/user_login` exactly once;
- `GET /api/system/deviceinfo` is mandatory session proof.

Two password encodings are represented by `ApiSesTokenAuth`:

- `base64(password)`;
- `base64(hex_sha256(base64(password) + token))`.

The public reference tries both automatically. Access Manager intentionally does **not** do that because the Huawei credential-safety contract is one credential submission per attempt. The mode must come from explicit frontend/auth-script evidence or an explicitly configured profile. If it remains ambiguous, authentication fails before consuming the credential budget.

## Legacy fallback

When `/api/webserver/SesTokenInfo` is absent, HTML, malformed, or does not contain a valid session/token pair, the client does not treat `/api/` as available. Existing evidence-driven auth selection remains authoritative, including the HG8245H legacy RandCount family when its runtime fingerprint is present.

This is a protocol fallback, not a password retry.

## Device identity

For the modern family, `/api/system/deviceinfo` serves two roles:

- proves that login actually produced an authenticated session;
- provides the runtime identity used by `HuaweiHG8245HApiRuntime`.

The Phase 3 runtime requires the authenticated device-info body to identify `HG8245H`. A manual model hint cannot replace this evidence.

The currently promoted read surface is intentionally small:

- `device_info`: `READ_SUPPORTED` after API session proof + model parser success.

Other AMP/BBSP readers are not inherited into the API runtime. The provider clears generic captured/mapped services when Phase 3 is selected so unsupported resources fail closed instead of crossing firmware families.

## Reboot and writes

**Reboot is not implemented in Phase 3.**

The public reference contains modern API and legacy CGI reboot logic, and the legacy firmware has framing/effect-verification quirks. The implementation prompt explicitly requires reboot to wait for physical validation.

Therefore:

- `reboot` remains `UNKNOWN` / disabled;
- Wi-Fi and other mutations remain disabled;
- no write capability is promoted;
- `physical_validation=false` for all Phase 3 capabilities.

## Test evidence

Synthetic/sanitized fixtures cover:

- SesTokenInfo XML and JSON parsing;
- both password formulas;
- algorithm ambiguity with **zero credential submissions**;
- modern API login with exactly one credential POST;
- `/api/system/deviceinfo` session proof;
- legacy RandCount fallback when the API fingerprint is invalid;
- HG8245H model fingerprint from authenticated API device info;
- provider read-only enforcement and reboot blocking.

Fixtures preserve structural response shapes only. They contain no router credentials, live cookies, real tokens, or copied vendor JavaScript.

## Validation state

- Reference/source evidence: supported.
- Automated fixture validation: required by `Huawei Phase 3 validation`.
- Physical HG8245H validation: pending.
- Reboot/write validation: pending and intentionally out of scope for this phase.

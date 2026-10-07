# Huawei external engineering references

These repositories are engineering-reverse-reference material, not runtime dependencies. Access Manager reimplements only behavior supported by independent evidence and keeps model/firmware provenance explicit. No credentials, cookies or session tokens are copied into this document.

## siedgustavo/huawei-ont-stats

- **Repository:** `siedgustavo/huawei-ont-stats`
- **Models:** EG8021V5 in the current source comments/documentation.
- **Firmware / WebUI family:** generated Huawei `/html/ssmp/`, `/html/amp/`, `/html/bbsp/` surface; treated here as `AMP_BBSP` family evidence, not as a universal model rule.
- **Authentication flow:** read-only pre-login challenge from `/html/ssmp/common/getRandString.asp`, POST `/login.cgi`, then read `/html/ssmp/common/GetRandToken.asp` on the authenticated cookie session. Source explicitly decodes the challenge/token with UTF-8 BOM handling.
- **Session lifecycle:** cookie-aware opener is returned with the post-login token. `api_server.py` adds persistent-session/cache behavior.
- **Token / CSRF:** `x.X_HW_Token` on login; post-login session token is acquired separately.
- **Read capabilities observed:** device information, ONT/PON, optical, WAN, WAN traffic statistics, Ethernet, WLAN and LAN clients.
- **Write capabilities observed:** Wi-Fi radio enable/disable, DHCP static reservation operations and DMZ configuration in `router_config.py`; these remain firmware-specific reference behavior until locally validated.
- **Known endpoints:** `/html/ssmp/deviceinfo/deviceinfo.asp`, `/html/bbsp/common/ontstate.asp`, `/html/amp/opticinfo/opticinfo.asp`, `/html/bbsp/common/getwanlist.asp`, WAN-stat pages, Ethernet/WLAN pages, LAN-client DHCP page, plus feature-specific mutation CGI used by the reference firmware.
- **InternetGatewayDevice objects:** used by configuration/mutation payloads; exact domains are model/firmware-specific and must not be copied as universal paths.
- **Parsers:** regex-based JavaScript-constructor helpers. Protocol knowledge is useful; the parser implementation is weaker than Access Manager's existing quote/escape/nesting-aware constructor parser and is not copied.
- **Caching:** API server separates persistent session and per-key static/dynamic caches with independent TTL concepts. Useful architecture idea; fixed TTL values are not copied.
- **Retry / reconciliation:** repository includes session reuse, reauthentication concepts and `reconcile.py`. Automatic reconciliation is not adopted now; desired/current/drift modeling is backlog.
- **Useful tests / fixtures:** `tests/test_api_server.py` and `tests/test_router_config.py`; external fixtures remain external-reference evidence, never local EG8041X7 captures.
- **Useful architectural ideas:** static vs dynamic cache classes, persistent session lifecycle, feature-level separation and reconciliation as a separate concern.
- **Useful protocol knowledge:** RandString auth variant, PON `OntStateInfo`, WAN traffic stats, Ethernet data and several configuration surfaces.
- **Risks:** firmware-specific positional constructor arguments; hard-coded WAN domains in mutations; some parser regexes do not safely cover nested/quoted constructor syntax.
- **License:** MIT.

## Erenn0989/huawei-ont-mcp

- **Repository:** `Erenn0989/huawei-ont-mcp`
- **Models:** repository states testing on an ISP-branded HG8245X6-family device.
- **Firmware / WebUI family:** RandCount/login WebUI with BBSP read surfaces.
- **Authentication flow:** `/asp/GetRandCount.asp` -> `/login.cgi` using a persistent HTTP connection in the repository implementation.
- **Session lifecycle:** explicit cookie/session reuse; read helpers invalidate and reauthenticate on authentication loss.
- **Token / CSRF:** pre-login RandCount token submitted as `x.X_HW_Token`.
- **Read capabilities observed:** LAN clients and WAN status, among the MCP tools.
- **Write capabilities observed:** not used as evidence for Access Manager in this first slice.
- **Known endpoints:** `/asp/GetRandCount.asp`, `/login.cgi`, `/html/bbsp/common/GetLanUserDevInfo.asp`, `/CustomApp/mainpage.asp`, `/html/bbsp/common/getwanlist.asp`.
- **Parsers:** page-specific JavaScript/HTML extraction.
- **Caching:** authentication state retained in memory.
- **Retry behavior:** read-only operations may reauthenticate and retry once. This converges with Access Manager's existing read retry policy.
- **Useful architectural ideas:** explicit session owner and separation between authenticated transport and tool consumers.
- **Useful protocol knowledge:** on the observed firmware, challenge retrieval and login reportedly require the same underlying TCP connection. A `requests.Session` pool is not a strict socket-affinity guarantee, so exact-socket support is not claimed by this PR.
- **Risks:** ISP-custom firmware; TCP-affinity requirement may not apply to other RandCount families.
- **License:** MIT.

## minzique/huawei-hg8245h5

- **Repository:** `minzique/huawei-hg8245h5`
- **Models:** HG8245H5.
- **Firmware / WebUI family:** public documentation describes an ASP configuration surface around V5R019/V500R019-era firmware.
- **Authentication flow:** documentation describes `/asp/GetRandCount.asp` + `/login.cgi`.
- **Session / CSRF:** documented session/CSRF behavior.
- **Read / write capabilities:** documentation describes `GetConfig` / `SetConfig` and an `InternetGatewayDevice.*` tree.
- **Known endpoints:** `/asp/GetConfig.asp`, `/asp/SetConfig.asp` plus login endpoints.
- **InternetGatewayDevice objects:** extensively documented.
- **Parsers/tests/fixtures:** the public main branch is documentation-oriented after sanitization; no public runtime test/fixture was found that is strong enough to make Access Manager auto-enable this family.
- **Useful architectural/protocol knowledge:** evidence that Huawei also has a materially different ASP configuration family. This is modeled as a distinct possible family rather than mixed into AMP/BBSP behavior.
- **Risks:** README/docs are not protocol proof for EG8041X7; historical sensitive material was explicitly removed from public main and is not used.
- **License:** MIT.
- **Status in Access Manager:** `OBSERVED IN EXTERNAL DOCUMENTATION`; runtime support remains `UNCONFIRMED` until a recognizable response is observed from a device/fixture with safe provenance.

## chickenzord/go-huawei-client

- **Repository:** `chickenzord/go-huawei-client`
- **Models:** EG8145V5 on main; draft PR #2 explores HN8010TS/HN8010T-like hardware.
- **Firmware / WebUI family:** RandCount + generated SSMP/AMP/BBSP surfaces.
- **Authentication flow:** RandCount -> login, cookie jar, explicit session wrapper/login/logout.
- **Session lifecycle:** client owns cookie jar, mutex, HTTP transport, credentials and session wrapper.
- **Token / CSRF:** hardware token from `/asp/GetRandCount.asp`; page/mutation token handling remains client-owned.
- **Read capabilities observed:** LAN devices, resource usage; draft PR #2 adds optical reading on `/html/amp/opticinfo/opticinfo.asp` for HN8010TS.
- **Write capabilities observed:** not used as new write evidence in this PR.
- **Parsers:** executes vendor JavaScript in an embedded JS VM and normalizes results to Go structs. Access Manager does not copy that approach because its structural constructor parser already covers the needed data without executing untrusted page JavaScript.
- **Caching:** not a primary contribution for this integration.
- **Retry/session behavior:** encapsulated in the client/session abstraction.
- **Useful tests/fixtures:** no substantial model-fixture suite was found on main.
- **Useful architectural ideas:** draft PR #2 explicitly recommends sharing Huawei WebUI login/logout/session and generalized HTTP retrieval while leaving model-specific differences separate. This independently converges with Access Manager's protocol-family direction.
- **Risks:** draft PR #2 intentionally breaks EG8145V5 compatibility while exploring HN8010TS; its code must not be treated as universal.
- **License:** MIT.

## logon84/Huawei-Optistar-EG8145X6-10-remote-login-example

- **Repository:** `logon84/Huawei-Optistar-EG8145X6-10-remote-login-example`
- **Models:** OptiXstar EG8145X6-10.
- **Firmware / WebUI family:** RandCount/login with BBSP client-reading surface.
- **Authentication flow:** `/asp/GetRandCount.asp` -> `/login.cgi`, `x.X_HW_Token`, cookies.
- **Session lifecycle:** small requests-session example.
- **Read capabilities observed:** LAN/WLAN client information example.
- **Known endpoints:** `/asp/GetRandCount.asp`, `/login.cgi`, `/html/bbsp/userdevinfo/getuserdevinfo.asp`.
- **Parsers:** Huawei escaped-hex response decoding in the example.
- **Useful protocol knowledge:** independent convergence of RandCount + login + token/cookie behavior on the X6 generation.
- **Risks:** minimal example, no test suite, no broad capability coverage.
- **License:** no license file found on the public repository; therefore used strictly as behavioral reference. No source code is copied.

## Cross-repository convergence

High-confidence cross-repo observations are still scoped to a WebUI family, never to all Huawei models:

1. **RandCount + login + `x.X_HW_Token`** converges across the existing local EG8041X7 implementation, `huawei-ont-mcp`, `go-huawei-client` and the EG8145X6-10 example.
2. **SSMP/AMP/BBSP generated pages** recur across EG8021V5, EG8145V5/HN8010 references and the local EG8041X7 implementation, but available pages and constructor shapes differ.
3. **RandString + post-login RandToken** is a real divergent auth flow observed in `huawei-ont-stats`; it must not be collapsed into RandCount.
4. **GetConfig/SetConfig** is a separate ASP configuration family documented for HG8245H5 and remains isolated until runtime evidence exists.
5. **Same-TCP challenge/login affinity** is strong firmware-specific evidence from `huawei-ont-mcp`, but is not generalized without physical/fixture validation.

## Integration rule

External repositories are sources of protocol evidence. Runtime support is promoted only when Access Manager can safely observe the endpoint, recognize the response and parse it. Write support additionally requires confirmed payload/mapping/semantics and physical validation where appropriate.

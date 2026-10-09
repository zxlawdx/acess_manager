from __future__ import annotations

import re
from urllib.parse import urljoin

import requests

from .auth import (
    ApiSesTokenAuth,
    ApiSesTokenContext,
    HuaweiCredentialSubmissionBudget,
    RandCountAuth,
    RandStringSessionTokenAuth,
)
from .client import HuaweiWebClient, LOGIN_PATH, MENU_PATH, RAND_PATH
from .errors import (
    HuaweiArchitectureError,
    HuaweiAuthFamilyAmbiguousError,
    HuaweiSessionValidationError,
    HuaweiUnsupportedFirmwareError,
)
from .protocol import (
    HuaweiAuthFlow,
    HuaweiProtocolFamily,
    HuaweiProtocolFingerprint,
    auth_flow_from_login_page,
    clean_huawei_token,
    plausible_huawei_token,
    protocol_family_from_observations,
)
from .transport import HuaweiTransportPolicy, RequestsSessionTransport


RAND_STRING_PATH = "/html/ssmp/common/getRandString.asp"
SESSION_TOKEN_PATH = "/html/ssmp/common/GetRandToken.asp"
DEVICE_INFO_PATH = "/html/ssmp/deviceinfo/deviceinfo.asp"
API_SES_TOKEN_PATH = "/api/webserver/SesTokenInfo"
API_LOGIN_PATH = "/api/system/user_login"
API_DEVICE_INFO_PATH = "/api/system/deviceinfo"


class HuaweiFamilyAwareWebClient(HuaweiWebClient):
    """Huawei transport with evidence-driven authentication selection.

    The existing Huawei transport remains authoritative for normal reads and
    writes. This subclass centralizes authentication variants that differ
    across Huawei WebUI firmware families.

    Credential-bearing login is submitted at most once per login/reauth call.
    Auto-detection may probe read-only challenge/session endpoints, but it never
    tries a second credential algorithm after a credential-bearing request.
    """

    def __init__(
        self,
        *args,
        transport_policy: HuaweiTransportPolicy | None = None,
        api_password_mode: str | None = None,
        **kwargs,
    ) -> None:
        super().__init__(*args, **kwargs)
        self.transport_policy = transport_policy or HuaweiTransportPolicy.for_endpoint(
            self.base_url,
            https=self.base_url.startswith("https://"),
            timeout=self.timeout,
        )
        self._apply_session_transport_policy(self.session)
        self.auth_flow = HuaweiAuthFlow.UNKNOWN
        self.protocol_family = HuaweiProtocolFamily.UNKNOWN
        self.protocol_evidence: tuple[str, ...] = ()
        self._session_token: str | None = None
        self._credential_budget = HuaweiCredentialSubmissionBudget(
            self.transport_policy.credential_submission_budget
        )
        self._rand_count_auth = RandCountAuth(self._credential_budget)
        self._rand_string_auth = RandStringSessionTokenAuth(self._credential_budget)
        self._api_auth = ApiSesTokenAuth(self._credential_budget)
        configured_mode = ApiSesTokenAuth.normalize_mode(api_password_mode)
        if api_password_mode not in (None, "") and configured_mode is None:
            raise ValueError("Huawei API password mode is not supported")
        self._configured_api_password_mode = configured_mode
        self._api_password_mode = configured_mode
        self._api_context: ApiSesTokenContext | None = None
        self._api_device_info_source: str | None = None
        self._login_source: str = ""

    def _apply_session_transport_policy(self, session: requests.Session) -> None:
        RequestsSessionTransport.apply_session_policy(session, self.transport_policy)

    @classmethod
    def looks_like_huawei(
        cls,
        host: str,
        *,
        https: bool = False,
        timeout: float = 2.5,
    ) -> bool:
        scheme = "https" if https else "http"
        raw = host.rstrip("/")
        base = raw if raw.startswith(("http://", "https://")) else f"{scheme}://{raw}"
        session = cls._new_session()
        try:
            response = session.get(
                base + "/",
                timeout=(2.0, timeout),
                allow_redirects=True,
            )
            body = (response.text or "").casefold()
            markers = (
                "getrandcount.asp",
                "getrandstring.asp",
                "sestokeninfo",
                "rndsecurityformat.js",
                "hwlog.jpg",
                "x_hw_token",
                "huawei",
            )
            return response.status_code < 500 and any(marker in body for marker in markers)
        except requests.RequestException:
            return False
        finally:
            session.close()

    def protocol_descriptor(self) -> dict[str, object]:
        return HuaweiProtocolFingerprint(
            family=self.protocol_family,
            auth_flow=self.auth_flow,
            evidence=self.protocol_evidence,
        ).as_dict()

    def authenticated_identity_source(self) -> tuple[str, str] | None:
        """Return the already-validated API identity body without router I/O."""

        if self.auth_flow is not HuaweiAuthFlow.API_SES_TOKEN:
            return None
        if not self._api_device_info_source:
            return None
        return API_DEVICE_INFO_PATH, self._api_device_info_source

    def _record_evidence(self, *values: str) -> None:
        self.protocol_evidence = tuple(
            dict.fromkeys((
                *self.protocol_evidence,
                *(str(value) for value in values if value),
            ))
        )

    def _record_family(self, *paths: str, sources=()) -> None:
        family, evidence = protocol_family_from_observations(paths, sources=sources)
        if family is HuaweiProtocolFamily.UNKNOWN:
            return
        self.protocol_family = family
        self._record_evidence(*evidence)

    def _fetch_rand_count(self):
        headers = {
            "Accept": "*/*",
            "X-Requested-With": "XMLHttpRequest",
            "Origin": self.base_url,
            "Referer": self.base_url + "/",
        }
        response = self.session.post(
            self.url(RAND_PATH),
            headers=headers,
            timeout=self.timeout,
            allow_redirects=False,
        )
        if plausible_huawei_token(response.text):
            self._record_evidence("auth:rand-count-post")
            return response
        response = self.session.get(
            self.url(RAND_PATH),
            headers={"Referer": self.base_url + "/"},
            timeout=self.timeout,
            allow_redirects=False,
        )
        if plausible_huawei_token(response.text):
            self._record_evidence("auth:rand-count-get")
        return response

    def _fetch_rand_string(self):
        response = self.session.get(
            self.url(RAND_STRING_PATH),
            headers={"Referer": self.base_url + "/"},
            timeout=self.timeout,
            allow_redirects=False,
        )
        if plausible_huawei_token(response.text):
            self._record_evidence("auth:rand-string-get")
        return response

    def _fetch_api_ses_token(self) -> tuple[object, ApiSesTokenContext | None]:
        response = self.session.get(
            self.url(API_SES_TOKEN_PATH),
            headers={
                "Accept": "application/json,text/xml,application/xml,*/*",
                "Referer": self.base_url + "/",
            },
            timeout=self.timeout,
            allow_redirects=False,
        )
        context = None
        if response.status_code < 400:
            try:
                context = self._api_auth.parse_session_token_info(response.text)
            except ValueError:
                context = None
        if context is not None:
            self._record_evidence("auth:api-sestoken")
            self._record_family(API_SES_TOKEN_PATH, sources=(response.text,))
        return response, context

    @staticmethod
    def _api_response_invalid(response) -> bool:
        status = getattr(response, "status_code", None)
        if status in {401, 403}:
            return True
        if status is None or status >= 400:
            return True
        text = str(getattr(response, "text", "") or "").strip()
        if not text:
            return False
        lower = text[:4000].casefold()
        return any(
            marker in lower
            for marker in (
                "<html",
                "<!doctype",
                "<error",
                "<errorcode",
                '"errorcode"',
                "/login.cgi",
            )
        )

    def _refresh_api_token_from_response(self, response) -> None:
        headers = getattr(response, "headers", {}) or {}
        header_token = clean_huawei_token(headers.get("__RequestVerificationToken"))
        if plausible_huawei_token(header_token):
            self._session_token = header_token
            self.session.headers["__RequestVerificationToken"] = header_token
            return
        try:
            context = self._api_auth.parse_session_token_info(
                getattr(response, "text", "")
            )
        except ValueError:
            return
        self._api_context = context
        self._session_token = context.token
        self.session.headers["Cookie"] = context.session_info
        self.session.headers["__RequestVerificationToken"] = context.token

    def _api_login_script_sources(self, login_html: str) -> list[str]:
        sources = [str(login_html or "")]
        seen: set[str] = set()
        for src in re.findall(
            r"<script[^>]+src\s*=\s*['\"]([^'\"]+)['\"]",
            login_html or "",
            re.I,
        ):
            lowered = src.casefold()
            if not any(
                marker in lowered
                for marker in ("login", "safe", "security", "sha", "base64", "rnd")
            ):
                continue
            url = urljoin(self.base_url + "/", src)
            if url in seen:
                continue
            seen.add(url)
            try:
                response = self.session.get(
                    url,
                    headers={"Referer": self.base_url + "/"},
                    timeout=self.timeout,
                    allow_redirects=True,
                )
            except requests.RequestException:
                continue
            if response.status_code == 200 and response.text:
                sources.append(response.text)
            if len(sources) >= 7:
                break
        return sources

    def _resolve_api_password_mode(self, login_html: str) -> str:
        if self._configured_api_password_mode:
            self._api_password_mode = self._configured_api_password_mode
            self._record_evidence(f"api-password-mode:{self._api_password_mode}:profile")
            return self._api_password_mode

        mode = ApiSesTokenAuth.infer_password_mode(
            "\n".join(self._api_login_script_sources(login_html))
        )
        if mode is None:
            raise HuaweiAuthFamilyAmbiguousError(
                "A interface Huawei /api/ foi identificada, mas a variante de "
                "senha não pôde ser determinada sem ambiguidade; nenhuma "
                "credencial foi submetida."
            )
        self._api_password_mode = mode
        self._record_evidence(f"api-password-mode:{mode}:frontend")
        return mode

    def _select_auth_flow(self, login_html: str) -> HuaweiAuthFlow:
        # Phase 3 rule: a valid SesTokenInfo fingerprint wins over marketing
        # model names and over legacy CGI markers. If it is absent/unparseable,
        # the detector falls back to the existing legacy flows.
        try:
            _api_response, context = self._fetch_api_ses_token()
        except requests.RequestException:
            context = None
        if context is not None:
            self._api_context = context
            return HuaweiAuthFlow.API_SES_TOKEN

        explicit = auth_flow_from_login_page(login_html)
        if explicit is HuaweiAuthFlow.API_SES_TOKEN:
            # Merely mentioning /api/ in HTML is not enough. The required safe
            # fingerprint above did not return a valid SesInfo/TokInfo pair.
            explicit = HuaweiAuthFlow.UNKNOWN
        if explicit is not HuaweiAuthFlow.UNKNOWN:
            return explicit

        candidates: list[HuaweiAuthFlow] = []
        try:
            response = self._fetch_rand_count()
            if response.status_code < 400 and plausible_huawei_token(response.text):
                candidates.append(HuaweiAuthFlow.RAND_COUNT)
        except requests.RequestException:
            pass

        try:
            response = self._fetch_rand_string()
            if response.status_code < 400 and plausible_huawei_token(response.text):
                candidates.append(HuaweiAuthFlow.RAND_STRING_SESSION_TOKEN)
        except requests.RequestException:
            pass

        unique = tuple(dict.fromkeys(candidates))
        if len(unique) > 1:
            raise HuaweiAuthFamilyAmbiguousError(
                "Mais de uma família de autenticação Huawei respondeu ao fingerprint; "
                "nenhuma credencial foi submetida."
            )
        return unique[0] if unique else HuaweiAuthFlow.UNKNOWN

    def _login_payload(self, challenge: str) -> dict[str, str]:
        return RandCountAuth.build_payload(
            username=self.username,
            password=self.password,
            challenge=challenge,
        )

    def _submit_login(
        self,
        challenge: str,
        *,
        legacy_cookie: bool,
        strategy: RandCountAuth,
    ):
        headers = {
            "Content-Type": "application/x-www-form-urlencoded",
            "Origin": self.base_url,
            "Referer": self.base_url + "/",
            "Upgrade-Insecure-Requests": "1",
        }
        if legacy_cookie:
            headers["Cookie"] = "Cookie=body:Language:english:id=-1"

        def submit(payload: dict[str, str]):
            return self.session.post(
                self.url(LOGIN_PATH),
                headers=headers,
                data=payload,
                timeout=self.timeout,
                allow_redirects=True,
            )

        return strategy.submit(
            submit,
            username=self.username,
            password=self.password,
            challenge=challenge,
        )

    def _authenticate_rand_count(self) -> bool:
        challenge_response = self._fetch_rand_count()
        challenge = self._rand_count_auth.normalize_challenge(challenge_response.text)

        login_response = self._submit_login(
            challenge,
            legacy_cookie=True,
            strategy=self._rand_count_auth,
        )
        if self.is_login_response(login_response):
            return False

        try:
            menu = self.session.post(
                self.url(MENU_PATH),
                headers={
                    "Accept": "*/*",
                    "X-Requested-With": "XMLHttpRequest",
                    "Referer": self.url("/index.asp"),
                },
                timeout=self.timeout,
            )
            menu_body = (menu.text or "").casefold()
            if menu.status_code == 200 and (
                "home page" in menu_body
                or "ipincoming" in menu_body
                or "bbsp" in menu_body
            ):
                if "bbsp" in menu_body or "ipincoming" in menu_body:
                    self._record_family("/html/bbsp/")
                return True
        except requests.RequestException:
            pass

        try:
            device = self.session.get(
                self.url(DEVICE_INFO_PATH),
                headers={"Referer": self.url("/index.asp")},
                timeout=self.timeout,
                allow_redirects=True,
            )
            if (
                device.status_code == 200
                and not self.is_login_response(device)
                and bool((device.text or "").strip())
            ):
                self._record_family(DEVICE_INFO_PATH, sources=(device.text,))
                return True
        except requests.RequestException:
            pass
        raise HuaweiSessionValidationError(
            "O login Huawei foi enviado, mas nenhum endpoint read-only confirmou a sessão."
        )

    def _authenticate_rand_string(self) -> bool:
        challenge_response = self._fetch_rand_string()
        challenge = self._rand_string_auth.normalize_challenge(challenge_response.text)

        login_response = self._submit_login(
            challenge,
            legacy_cookie=False,
            strategy=self._rand_string_auth,
        )
        if self.is_login_response(login_response):
            return False

        token_response = self.session.get(
            self.url(SESSION_TOKEN_PATH),
            headers={"Referer": self.url("/index.asp")},
            timeout=self.timeout,
            allow_redirects=False,
        )
        token = clean_huawei_token(token_response.text)
        if token_response.status_code != 200 or not plausible_huawei_token(token):
            raise HuaweiSessionValidationError(
                "O login RandString foi enviado, mas o token de sessão não foi confirmado."
            )

        self._session_token = token
        self._record_family(RAND_STRING_PATH, SESSION_TOKEN_PATH)
        return True

    def _authenticate_api_ses_token(self) -> bool:
        _response, context = self._fetch_api_ses_token()
        if context is None:
            raise HuaweiSessionValidationError(
                "A interface Huawei /api/ foi selecionada, mas SesTokenInfo não "
                "retornou sessão/token válidos."
            )

        mode = self._resolve_api_password_mode(self._login_source)
        self._api_context = context
        self._session_token = context.token
        self.session.headers["Cookie"] = context.session_info
        self.session.headers["__RequestVerificationToken"] = context.token

        def submit(payload: dict[str, str]):
            return self.session.post(
                self.url(API_LOGIN_PATH),
                headers={
                    "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
                    "Origin": self.base_url,
                    "Referer": self.url("/html/index.html"),
                    "__RequestVerificationToken": context.token,
                },
                data=payload,
                timeout=self.timeout,
                allow_redirects=False,
            )

        login_response = self._api_auth.submit(
            submit,
            username=self.username,
            password=self.password,
            context=context,
            mode=mode,
        )
        if self._api_response_invalid(login_response):
            return False
        self._refresh_api_token_from_response(login_response)

        device = self.session.get(
            self.url(API_DEVICE_INFO_PATH),
            headers={
                "Accept": "application/json,text/xml,application/xml,*/*",
                "Referer": self.url("/html/index.html"),
            },
            timeout=self.timeout,
            allow_redirects=False,
        )
        if self._api_response_invalid(device) or not str(device.text or "").strip():
            raise HuaweiSessionValidationError(
                "O login Huawei /api/ foi enviado, mas /api/system/deviceinfo "
                "não confirmou a sessão."
            )

        self._api_device_info_source = str(device.text or "")
        self._refresh_api_token_from_response(device)
        self._record_family(
            API_SES_TOKEN_PATH,
            API_LOGIN_PATH,
            API_DEVICE_INFO_PATH,
            sources=(device.text,),
        )
        self._record_evidence("session-proof:/api/system/deviceinfo")
        return True

    def get_api_page(self, path: str) -> str:
        """Read a characterized /api/ endpoint with one auth recovery."""

        def request():
            return self.session.get(
                self.url(path),
                headers={
                    "Accept": "application/json,text/xml,application/xml,*/*",
                    "Referer": self.url("/html/index.html"),
                },
                timeout=self.timeout,
                allow_redirects=False,
            )

        response = request()
        if self._api_response_invalid(response):
            self.reauthenticate()
            response = request()
        if self._api_response_invalid(response):
            raise RuntimeError("Endpoint Huawei /api/ indisponível ou sessão expirada.")
        self._refresh_api_token_from_response(response)
        return str(response.text or "")

    def _authenticate_flow(self, flow: HuaweiAuthFlow) -> bool:
        if flow is HuaweiAuthFlow.RAND_STRING_SESSION_TOKEN:
            return self._authenticate_rand_string()
        if flow is HuaweiAuthFlow.RAND_COUNT:
            return self._authenticate_rand_count()
        if flow is HuaweiAuthFlow.API_SES_TOKEN:
            return self._authenticate_api_ses_token()
        if flow is HuaweiAuthFlow.RAND_COOKIE_HASH:
            raise HuaweiUnsupportedFirmwareError(
                "Fluxo Huawei RandCount com cookie derivado reconhecido, "
                "mas ainda não habilitado para autenticação."
            )
        if flow is HuaweiAuthFlow.SCRAM_CPE:
            raise HuaweiUnsupportedFirmwareError(
                "Huawei LTE/5G SCRAM é uma família separada e não é tratada pelo cliente GPON."
            )
        raise HuaweiAuthFamilyAmbiguousError(
            "A família de autenticação Huawei não pôde ser determinada sem ambiguidade."
        )

    def login(self, retries: int = 1) -> bool:
        """Authenticate once; never blind-retry credential submission."""

        try:
            self.session.close()
        except Exception:
            pass
        self.session = self._new_session()
        self._apply_session_transport_policy(self.session)
        self._session_token = None
        self._api_context = None
        self._api_device_info_source = None
        self._api_password_mode = self._configured_api_password_mode
        self._credential_budget.reset()

        try:
            root = self.session.get(
                self.base_url + "/",
                timeout=self.timeout,
                allow_redirects=True,
            )
            self._login_source = str(root.text or "")
            flow = self._select_auth_flow(self._login_source)
            if flow is HuaweiAuthFlow.UNKNOWN:
                raise HuaweiAuthFamilyAmbiguousError(
                    "Nenhuma família de autenticação Huawei foi determinada; "
                    "nenhuma credencial foi submetida."
                )
            self.auth_flow = flow
            if self._authenticate_flow(flow):
                return True
        except HuaweiArchitectureError:
            raise
        except requests.RequestException as exc:
            raise RuntimeError(
                "Não foi possível autenticar na ONT Huawei."
            ) from exc

        raise RuntimeError("Não foi possível autenticar na ONT Huawei.")

    def reauthenticate(self) -> bool:
        """Refresh the selected auth flow once, without replaying a write."""

        try:
            self.session.cookies.clear()
        except Exception:
            pass
        self.session.headers.pop("Cookie", None)
        self.session.headers.pop("__RequestVerificationToken", None)
        self._session_token = None
        self._api_context = None
        self._api_device_info_source = None
        self._credential_budget.reset()

        flow = self.auth_flow
        if flow is HuaweiAuthFlow.UNKNOWN:
            try:
                root = self.session.get(
                    self.base_url + "/",
                    timeout=self.timeout,
                    allow_redirects=True,
                )
                self._login_source = str(root.text or "")
                flow = self._select_auth_flow(self._login_source)
            except HuaweiArchitectureError:
                raise
            except requests.RequestException as exc:
                raise RuntimeError(
                    "Sessão expirada; não foi possível reautenticar na ONT Huawei."
                ) from exc

        try:
            if flow is not HuaweiAuthFlow.UNKNOWN and self._authenticate_flow(flow):
                self.auth_flow = flow
                return True
        except HuaweiArchitectureError:
            raise
        except requests.RequestException as exc:
            raise RuntimeError(
                "Sessão expirada; não foi possível reautenticar na ONT Huawei."
            ) from exc

        raise RuntimeError(
            "Sessão expirada; não foi possível reautenticar na ONT Huawei."
        )

    def close(self) -> None:
        self._session_token = None
        self._api_context = None
        self._api_device_info_source = None
        super().close()

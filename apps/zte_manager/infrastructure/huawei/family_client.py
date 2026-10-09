from __future__ import annotations

import requests

from .auth import (
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


class HuaweiFamilyAwareWebClient(HuaweiWebClient):
    """Huawei transport with evidence-driven authentication selection.

    The existing Huawei transport remains authoritative for normal reads and
    writes. This subclass only centralizes the authentication variants that are
    known to differ across Huawei WebUI firmware families.

    Credential-bearing login is submitted at most once per login/reauth call.
    Auto-detection may probe challenge endpoints because those reads are
    non-destructive, but it never tries a second auth flow after credentials
    have been submitted.
    """

    def __init__(
        self,
        *args,
        transport_policy: HuaweiTransportPolicy | None = None,
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
        # Preserve the POST-first flow physically captured on the EG8041
        # family, then accept GET as a read-only firmware variation used by the
        # HG8145X6 reference. No credentials are present in either request.
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

    def _select_auth_flow(self, login_html: str) -> HuaweiAuthFlow:
        explicit = auth_flow_from_login_page(login_html)
        if explicit is not HuaweiAuthFlow.UNKNOWN:
            return explicit

        # Read-only probes may discover candidates, but ambiguity must never
        # trigger credential brute-force. Exactly one strategy must be proven.
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
        # Compatibility helper retained for tests/callers. Submission itself is
        # performed through the budgeted auth strategy below.
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
            # Preserves the physically validated EG8041X7 RandCount flow.
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

    def _authenticate_flow(self, flow: HuaweiAuthFlow) -> bool:
        if flow is HuaweiAuthFlow.RAND_STRING_SESSION_TOKEN:
            return self._authenticate_rand_string()
        if flow is HuaweiAuthFlow.RAND_COUNT:
            return self._authenticate_rand_count()
        if flow is HuaweiAuthFlow.API_SES_TOKEN:
            raise HuaweiUnsupportedFirmwareError(
                "Fluxo Huawei API SesTokenInfo reconhecido, mas ainda está em fase posterior."
            )
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
        self._credential_budget.reset()

        try:
            root = self.session.get(
                self.base_url + "/",
                timeout=self.timeout,
                allow_redirects=True,
            )
            flow = self._select_auth_flow(root.text or "")
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
        self._session_token = None
        self._credential_budget.reset()

        flow = self.auth_flow
        if flow is HuaweiAuthFlow.UNKNOWN:
            try:
                root = self.session.get(
                    self.base_url + "/",
                    timeout=self.timeout,
                    allow_redirects=True,
                )
                flow = self._select_auth_flow(root.text or "")
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
        super().close()

from __future__ import annotations

import base64

import requests

from .client import HuaweiWebClient, LOGIN_PATH, MENU_PATH, RAND_PATH
from .protocol import (
    HuaweiAuthFlow,
    HuaweiProtocolFamily,
    HuaweiProtocolFingerprint,
    auth_flow_from_login_page,
    clean_huawei_token,
    extract_huawei_challenge,
    plausible_huawei_token,
    protocol_family_from_observations,
)


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

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.auth_flow = HuaweiAuthFlow.UNKNOWN
        self.protocol_family = HuaweiProtocolFamily.UNKNOWN
        self.protocol_evidence: tuple[str, ...] = ()
        self._session_token: str | None = None

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
        response = self.session.post(
            self.url(RAND_PATH),
            headers=headers,
            timeout=self.timeout,
            allow_redirects=False,
        )
        if plausible_huawei_token(response.text):
            self._record_evidence("auth:rand-count-post")
            return response
        # Some independently observed Huawei WebUIs use GET for the same
        # challenge endpoint. Falling back here is safe because no credential
        # has been submitted yet.
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

        # Challenge probing is read-only. Do not submit credentials while
        # guessing, because several Huawei firmwares enforce login lockouts.
        try:
            response = self._fetch_rand_count()
            if response.status_code < 400 and plausible_huawei_token(response.text):
                return HuaweiAuthFlow.RAND_COUNT
        except requests.RequestException:
            pass

        try:
            response = self._fetch_rand_string()
            if response.status_code < 400 and plausible_huawei_token(response.text):
                return HuaweiAuthFlow.RAND_STRING_SESSION_TOKEN
        except requests.RequestException:
            pass

        return HuaweiAuthFlow.UNKNOWN

    def _login_payload(self, challenge: str) -> dict[str, str]:
        return {
            "UserName": self.username,
            "PassWord": base64.b64encode(
                self.password.encode("utf-8")
            ).decode("ascii"),
            "Language": "english",
            "x.X_HW_Token": challenge,
        }

    def _submit_login(self, challenge: str, *, legacy_cookie: bool):
        headers = {
            "Content-Type": "application/x-www-form-urlencoded",
            "Origin": self.base_url,
            "Referer": self.base_url + "/",
            "Upgrade-Insecure-Requests": "1",
        }
        if legacy_cookie:
            # Preserves the physically validated EG8041X7 RandCount flow.
            headers["Cookie"] = "Cookie=body:Language:english:id=-1"
        return self.session.post(
            self.url(LOGIN_PATH),
            headers=headers,
            data=self._login_payload(challenge),
            timeout=self.timeout,
            allow_redirects=True,
        )

    def _authenticate_rand_count(self) -> bool:
        challenge_response = self._fetch_rand_count()
        challenge = extract_huawei_challenge(challenge_response.text)
        if not plausible_huawei_token(challenge):
            raise RuntimeError("Huawei RandCount challenge was not returned")

        login_response = self._submit_login(challenge, legacy_cookie=True)
        if self.is_login_response(login_response):
            return False

        # Keep the existing menu proof when present because it is strong local
        # evidence for EG8041X7-class firmware.
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

        # Other RandCount firmwares do not expose getMenuArray.asp. Confirm
        # authentication with a read-only protected page instead of accepting
        # a cookie or redirect alone.
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
        return False

    def _authenticate_rand_string(self) -> bool:
        challenge_response = self._fetch_rand_string()
        challenge = clean_huawei_token(challenge_response.text)
        if not plausible_huawei_token(challenge):
            raise RuntimeError("Huawei RandString challenge was not returned")

        # The EG8021V5 reference flow does not send the EG8041X7 legacy Cookie
        # header. Keep the two auth strategies behaviorally distinct.
        login_response = self._submit_login(challenge, legacy_cookie=False)
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
            return False

        # Token stays private to the session. It is never returned/logged.
        self._session_token = token
        self._record_family(RAND_STRING_PATH, SESSION_TOKEN_PATH)
        return True

    def _authenticate_flow(self, flow: HuaweiAuthFlow) -> bool:
        if flow is HuaweiAuthFlow.RAND_STRING_SESSION_TOKEN:
            return self._authenticate_rand_string()
        if flow is HuaweiAuthFlow.RAND_COUNT:
            return self._authenticate_rand_count()
        if flow is HuaweiAuthFlow.RAND_COOKIE_HASH:
            # This variant is characterized for older HG8010H-family firmware,
            # but not implemented because its credential/cookie derivation has
            # not been physically validated in Access Manager. Crucially, do
            # not fall through to ordinary RandCount and submit credentials.
            raise RuntimeError(
                "Fluxo Huawei RandCount com cookie derivado reconhecido, "
                "mas ainda não habilitado para autenticação."
            )
        raise RuntimeError("Fluxo de autenticação Huawei não reconhecido.")

    def login(self, retries: int = 1) -> bool:
        """Authenticate once; never blind-retry credential submission."""

        try:
            self.session.close()
        except Exception:
            pass
        self.session = self._new_session()
        self._session_token = None

        try:
            root = self.session.get(
                self.base_url + "/",
                timeout=self.timeout,
                allow_redirects=True,
            )
            flow = self._select_auth_flow(root.text or "")
            if flow is HuaweiAuthFlow.UNKNOWN:
                raise RuntimeError("Fluxo de autenticação Huawei não reconhecido.")
            self.auth_flow = flow
            if self._authenticate_flow(flow):
                return True
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

        flow = self.auth_flow
        if flow is HuaweiAuthFlow.UNKNOWN:
            try:
                root = self.session.get(
                    self.base_url + "/",
                    timeout=self.timeout,
                    allow_redirects=True,
                )
                flow = self._select_auth_flow(root.text or "")
            except requests.RequestException as exc:
                raise RuntimeError(
                    "Sessão expirada; não foi possível reautenticar na ONT Huawei."
                ) from exc

        try:
            if flow is not HuaweiAuthFlow.UNKNOWN and self._authenticate_flow(flow):
                self.auth_flow = flow
                return True
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

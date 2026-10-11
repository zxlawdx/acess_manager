from __future__ import annotations

import requests

from .client import LOGIN_PATH, MENU_PATH, RAND_PATH
from .family_client import DEVICE_INFO_PATH
from .negotiating_client import HuaweiNegotiatingWebClient
from .protocol import plausible_huawei_token
from .transport import (
    AffinityHttpTransport,
    HuaweiEndpointProfile,
    endpoint_profile_from_login_source,
)


class HuaweiAffinityNegotiatingWebClient(HuaweiNegotiatingWebClient):
    """Huawei negotiating client with opt-in exact-socket RandCount auth.

    Ordinary Huawei firmware keeps the existing requests.Session path. The
    socket-affinity path is enabled only by an explicit HuaweiEndpointProfile,
    an explicit TransportPolicy, or a strict pre-auth login fingerprint. The
    authentication family itself remains RandCount and the credential budget
    remains exactly one submission.
    """

    def __init__(
        self,
        host: str,
        username: str,
        password: str,
        *,
        endpoint_profile: HuaweiEndpointProfile | None = None,
        **kwargs,
    ) -> None:
        self.endpoint_profile = endpoint_profile
        super().__init__(host, username, password, **kwargs)
        if self.endpoint_profile is not None:
            self.transport_policy = self.endpoint_profile.apply(self.transport_policy)

    def _select_auth_flow(self, login_html: str):
        if self.endpoint_profile is None:
            detected = endpoint_profile_from_login_source(login_html)
            if detected is not None:
                self.endpoint_profile = detected
                self.transport_policy = detected.apply(self.transport_policy)
                self._record_evidence(
                    f"endpoint-profile:{detected.key}",
                    *detected.evidence,
                )
        return super()._select_auth_flow(login_html)

    @staticmethod
    def _rand_count_headers(base_url: str) -> dict[str, str]:
        return {
            "Accept": "*/*",
            "X-Requested-With": "XMLHttpRequest",
            "Origin": base_url,
            "Referer": base_url + "/",
        }

    def _validate_rand_count_session(self) -> bool:
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

        from .errors import HuaweiSessionValidationError

        raise HuaweiSessionValidationError(
            "O login Huawei com afinidade TCP foi enviado, mas nenhum endpoint "
            "read-only confirmou a sessão."
        )

    def _authenticate_rand_count_affinity(self) -> bool:
        transport = AffinityHttpTransport(self.base_url, self.transport_policy)
        challenge_headers = self._rand_count_headers(self.base_url)

        with transport.connection() as connection:
            challenge_response = connection.post(
                RAND_PATH,
                headers={**challenge_headers, "Content-Length": "0"},
                data=b"",
            )
            if not plausible_huawei_token(challenge_response.text):
                challenge_response = connection.get(
                    RAND_PATH,
                    headers={"Referer": self.base_url + "/"},
                )
            challenge = self._rand_count_auth.normalize_challenge(
                challenge_response.text
            )
            self._record_evidence(
                "auth:rand-count-affinity",
                "transport:challenge-login-same-tcp",
            )

            login_headers = {
                "Content-Type": "application/x-www-form-urlencoded",
                "Origin": self.base_url,
                "Referer": self.base_url + "/",
                "Upgrade-Insecure-Requests": "1",
                "Cookie": "Cookie=body:Language:english:id=-1",
            }

            def submit(payload: dict[str, str]):
                return connection.post(
                    LOGIN_PATH,
                    headers=login_headers,
                    data=payload,
                )

            login_response = self._rand_count_auth.submit(
                submit,
                username=self.username,
                password=self.password,
                challenge=challenge,
            )
            transport.adopt_response_cookies(login_response, self.session)

        if self.is_login_response(login_response):
            return False
        return self._validate_rand_count_session()

    def _authenticate_rand_count(self) -> bool:
        if not self.transport_policy.challenge_login_connection_affinity:
            return super()._authenticate_rand_count()
        return self._authenticate_rand_count_affinity()

    def transport_descriptor(self) -> dict[str, object]:
        descriptor = super().transport_descriptor()
        descriptor.update({
            "challenge_login_connection_affinity": bool(
                self.transport_policy.challenge_login_connection_affinity
            ),
            "endpoint_profile": (
                self.endpoint_profile.key if self.endpoint_profile is not None else None
            ),
        })
        return descriptor

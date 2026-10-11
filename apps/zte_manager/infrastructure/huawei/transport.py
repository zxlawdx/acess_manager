from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Protocol
from urllib.parse import urlsplit

import requests

from .errors import (
    HuaweiSameConnectionRequiredError,
    HuaweiTransportNegotiationError,
)


@dataclass(frozen=True, slots=True)
class HuaweiTransportPolicy:
    """Orthogonal Huawei HTTP transport characteristics.

    Model names are intentionally absent. Runtime fingerprinting may replace
    endpoint properties without changing the authentication or endpoint family.
    """

    preferred_scheme: str = "http"
    port: int | None = None
    verify_tls: bool = False
    allow_self_signed: bool = True
    legacy_tls_profile: bool = False
    follow_js_redirect: bool = True
    challenge_login_connection_affinity: bool = False
    single_segment_post: bool = False
    force_content_length: bool = False
    allow_chunked: bool = True
    request_timeout: float = 10.0
    credential_submission_budget: int = 1

    def __post_init__(self) -> None:
        scheme = str(self.preferred_scheme or "").lower()
        if scheme not in {"http", "https"}:
            raise ValueError("Huawei transport scheme must be http or https")
        object.__setattr__(self, "preferred_scheme", scheme)
        if self.port is not None and not 1 <= int(self.port) <= 65535:
            raise ValueError("Huawei transport port must be in 1..65535")
        if float(self.request_timeout) <= 0:
            raise ValueError("Huawei request timeout must be positive")
        # Access Manager deliberately does not expose a knob for credential
        # brute-force/retry. One login attempt is the maximum safety contract.
        if int(self.credential_submission_budget) != 1:
            raise ValueError("Huawei credential_submission_budget must remain 1")
        if self.verify_tls and self.allow_self_signed:
            # A caller may trust a private CA, but verify=True cannot mean
            # "accept arbitrary self-signed". Keep the policy non-contradictory.
            object.__setattr__(self, "allow_self_signed", False)

    def with_endpoint(self, *, scheme: str, port: int | None) -> "HuaweiTransportPolicy":
        return replace(self, preferred_scheme=scheme, port=port)

    def as_dict(self) -> dict[str, object]:
        return {
            "preferred_scheme": self.preferred_scheme,
            "port": self.port,
            "verify_tls": self.verify_tls,
            "allow_self_signed": self.allow_self_signed,
            "legacy_tls_profile": self.legacy_tls_profile,
            "follow_js_redirect": self.follow_js_redirect,
            "challenge_login_connection_affinity": self.challenge_login_connection_affinity,
            "single_segment_post": self.single_segment_post,
            "force_content_length": self.force_content_length,
            "allow_chunked": self.allow_chunked,
            "request_timeout": self.request_timeout,
            "credential_submission_budget": self.credential_submission_budget,
        }

    @classmethod
    def for_endpoint(
        cls,
        host: str,
        *,
        https: bool = False,
        timeout: float = 10.0,
    ) -> "HuaweiTransportPolicy":
        raw = str(host or "").strip()
        supplied = raw if "://" in raw else f"{'https' if https else 'http'}://{raw}"
        parsed = urlsplit(supplied)
        try:
            port = parsed.port
        except ValueError as exc:
            raise ValueError("Invalid Huawei port") from exc
        return cls(
            preferred_scheme=(parsed.scheme or ("https" if https else "http")),
            port=port,
            verify_tls=False,
            allow_self_signed=True,
            follow_js_redirect=True,
            request_timeout=float(timeout),
            credential_submission_budget=1,
        )


class HuaweiTransport(Protocol):
    """Minimal HTTP transport contract used by Huawei auth strategies."""

    supports_connection_affinity: bool
    supports_single_segment_post: bool

    def get(self, url: str, **kwargs): ...
    def post(self, url: str, **kwargs): ...


class RequestsSessionTransport:
    """Adapter around requests.Session for ordinary Huawei WebUI firmware.

    A requests pool does not guarantee that challenge and login use the exact
    same TCP socket. Firmware requiring strict socket affinity is rejected
    explicitly until an affinity transport is selected.
    """

    supports_connection_affinity = False
    supports_single_segment_post = False

    def __init__(self, session: requests.Session, policy: HuaweiTransportPolicy) -> None:
        self.session = session
        self.policy = policy
        self.ensure_policy_supported(policy)
        self.apply_session_policy(session, policy)

    @classmethod
    def ensure_policy_supported(cls, policy: HuaweiTransportPolicy) -> None:
        if policy.challenge_login_connection_affinity and not cls.supports_connection_affinity:
            raise HuaweiSameConnectionRequiredError(
                "Este firmware exige afinidade TCP entre challenge e login; "
                "o transporte requests.Session não garante o mesmo socket."
            )
        if policy.single_segment_post and not cls.supports_single_segment_post:
            raise HuaweiTransportNegotiationError(
                "Este firmware exige POST em um único segmento/escrita; "
                "o transporte requests.Session não oferece essa garantia."
            )

    @staticmethod
    def apply_session_policy(
        session: requests.Session,
        policy: HuaweiTransportPolicy,
    ) -> requests.Session:
        session.verify = bool(policy.verify_tls)
        return session

    def get(self, url: str, **kwargs):
        kwargs.setdefault("timeout", self.policy.request_timeout)
        return self.session.get(url, **kwargs)

    def post(self, url: str, **kwargs):
        kwargs.setdefault("timeout", self.policy.request_timeout)
        return self.session.post(url, **kwargs)


class AffinityHttpTransport(RequestsSessionTransport):
    """Marker for a future exact-socket transport.

    Deliberately not advertised as supporting affinity yet. Phase 4 must supply
    a socket-level implementation and fake-server regression before enabling it.
    """

    supports_connection_affinity = False


class SingleWriteSocketTransport(RequestsSessionTransport):
    """Marker for firmware-specific single-write POST transport.

    It remains disabled until a physical/fixture contract proves the framing.
    """

    supports_single_segment_post = False

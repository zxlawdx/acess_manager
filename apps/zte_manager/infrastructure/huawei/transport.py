from __future__ import annotations

import http.client
import socket
import ssl
from contextlib import contextmanager
from dataclasses import dataclass, replace
from http.cookies import SimpleCookie
from typing import Iterator, Protocol
from urllib.parse import urlencode, urlsplit

import requests
from requests.structures import CaseInsensitiveDict

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


@dataclass(frozen=True, slots=True)
class HuaweiEndpointProfile:
    """Pre-auth transport requirements proven by profile/fingerprint evidence.

    This object deliberately contains no marketing-model matching. Callers may
    select it explicitly, or a login-page fingerprint may select it. Applying a
    profile changes only transport guarantees; it never grants a capability or
    enables a write.
    """

    key: str
    challenge_login_connection_affinity: bool = False
    single_segment_post: bool = False
    fingerprint_markers: tuple[str, ...] = ()
    evidence: tuple[str, ...] = ()

    def matches_login_source(self, source: object) -> bool:
        if not self.fingerprint_markers:
            return False
        body = str(source or "").casefold()
        return all(marker.casefold() in body for marker in self.fingerprint_markers)

    def apply(self, policy: HuaweiTransportPolicy) -> HuaweiTransportPolicy:
        return replace(
            policy,
            challenge_login_connection_affinity=(
                policy.challenge_login_connection_affinity
                or self.challenge_login_connection_affinity
            ),
            single_segment_post=(
                policy.single_segment_post or self.single_segment_post
            ),
        )


# Reference-only fingerprint for the TTNET2 HG8245X6 login page described by
# Erenn0989/huawei-ont-mcp. It is intentionally strict and does not match by
# model name. Explicit profile selection remains possible when an operator has
# stronger local evidence for the same transport requirement.
HG8245X6_TTNET2_AFFINITY_PROFILE = HuaweiEndpointProfile(
    key="hg8245x6_ttnet2_same_tcp",
    challenge_login_connection_affinity=True,
    fingerprint_markers=(
        "getrandcount.asp",
        "base64encode",
        "errloginlocknum",
        "locklefttime",
    ),
    evidence=(
        "Erenn0989/huawei-ont-mcp:TTNET2-HG8245X6",
        "challenge-token-bound-to-tcp-connection",
    ),
)

KNOWN_HUAWEI_ENDPOINT_PROFILES: tuple[HuaweiEndpointProfile, ...] = (
    HG8245X6_TTNET2_AFFINITY_PROFILE,
)


def endpoint_profile_from_login_source(source: object) -> HuaweiEndpointProfile | None:
    for profile in KNOWN_HUAWEI_ENDPOINT_PROFILES:
        if profile.matches_login_source(source):
            return profile
    return None


class HuaweiTransport(Protocol):
    """Minimal HTTP transport contract used by Huawei auth strategies."""

    supports_connection_affinity: bool
    supports_single_segment_post: bool

    def get(self, url: str, **kwargs): ...
    def post(self, url: str, **kwargs): ...


class RequestsSessionTransport:
    """Adapter around requests.Session for ordinary Huawei WebUI firmware.

    A requests pool does not guarantee that challenge and login use the exact
    same TCP socket. Firmware requiring strict socket affinity must use
    AffinityHttpTransport instead.
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


@dataclass(slots=True)
class HuaweiAffinityResponse:
    status_code: int
    text: str
    content: bytes
    headers: CaseInsensitiveDict
    raw_headers: tuple[tuple[str, str], ...]
    url: str
    history: tuple = ()


class _AffinityConnection:
    """One exact http.client connection used for an auth exchange."""

    def __init__(
        self,
        connection: http.client.HTTPConnection,
        *,
        base_url: str,
        base_path: str,
    ) -> None:
        self._connection = connection
        self.base_url = base_url.rstrip("/")
        self.base_path = base_path.rstrip("/")

    def _path(self, path: str) -> str:
        raw = str(path or "/")
        if raw.startswith(("http://", "https://")):
            parsed = urlsplit(raw)
            target = parsed.path or "/"
            if parsed.query:
                target += "?" + parsed.query
            return target
        if not raw.startswith("/"):
            raw = "/" + raw
        if self.base_path and self.base_path != "/":
            raw = self.base_path + raw
        return raw

    @staticmethod
    def _body(data: object) -> bytes | None:
        if data is None:
            return None
        if isinstance(data, bytes):
            return data
        if isinstance(data, bytearray):
            return bytes(data)
        if isinstance(data, str):
            return data.encode("utf-8")
        if isinstance(data, dict):
            return urlencode(data, doseq=True).encode("utf-8")
        raise TypeError("Unsupported affinity HTTP request body")

    def request(
        self,
        method: str,
        path: str,
        *,
        headers: dict[str, str] | None = None,
        data: object = None,
    ) -> HuaweiAffinityResponse:
        target = self._path(path)
        body = self._body(data)
        request_headers = dict(headers or {})
        request_headers.setdefault("Accept-Encoding", "identity")
        if body is not None:
            request_headers.setdefault("Content-Length", str(len(body)))

        url = self.base_url + target
        try:
            self._connection.request(
                str(method or "GET").upper(),
                target,
                body=body,
                headers=request_headers,
            )
            response = self._connection.getresponse()
            raw_headers = tuple((str(k), str(v)) for k, v in response.getheaders())
            content = response.read()
        except ssl.SSLError as exc:
            error = requests.exceptions.SSLError(str(exc))
            error.request = requests.Request(method, url).prepare()
            raise error from exc
        except (socket.timeout, TimeoutError, OSError, http.client.HTTPException) as exc:
            error = requests.exceptions.ConnectionError(str(exc))
            error.request = requests.Request(method, url).prepare()
            raise error from exc

        charset = response.headers.get_content_charset() or "utf-8-sig"
        try:
            text = content.decode(charset, errors="replace")
        except LookupError:
            text = content.decode("utf-8-sig", errors="replace")
        return HuaweiAffinityResponse(
            status_code=int(response.status),
            text=text,
            content=content,
            headers=CaseInsensitiveDict(raw_headers),
            raw_headers=raw_headers,
            url=url,
        )

    def get(self, path: str, *, headers: dict[str, str] | None = None):
        return self.request("GET", path, headers=headers)

    def post(
        self,
        path: str,
        *,
        headers: dict[str, str] | None = None,
        data: object = None,
    ):
        return self.request("POST", path, headers=headers, data=data)


class AffinityHttpTransport:
    """Exact-socket HTTP(S) transport for challenge→login affinity.

    The transport opens one http.client connection and keeps it open for the
    entire context. It does not patch requests, urllib3 pools, or global socket
    behavior. Only callers whose HuaweiEndpointProfile/TransportPolicy requires
    affinity should use it.
    """

    supports_connection_affinity = True
    supports_single_segment_post = False

    def __init__(self, base_url: str, policy: HuaweiTransportPolicy) -> None:
        self.base_url = str(base_url or "").rstrip("/")
        self.policy = policy
        parsed = urlsplit(self.base_url)
        if parsed.scheme not in {"http", "https"} or not parsed.hostname:
            raise ValueError("Invalid Huawei affinity endpoint")
        if policy.single_segment_post:
            raise HuaweiTransportNegotiationError(
                "Afinidade TCP de autenticação não implica POST de mutação em "
                "um único segmento; use o transporte específico quando houver "
                "captura física dessa exigência."
            )
        self.scheme = parsed.scheme
        self.host = parsed.hostname
        self.port = parsed.port or (443 if parsed.scheme == "https" else 80)
        self.base_path = parsed.path or ""

    def _new_connection(self) -> http.client.HTTPConnection:
        timeout = float(self.policy.request_timeout)
        if self.scheme == "https":
            context = (
                ssl.create_default_context()
                if self.policy.verify_tls
                else ssl._create_unverified_context()
            )
            return http.client.HTTPSConnection(
                self.host,
                self.port,
                timeout=timeout,
                context=context,
            )
        return http.client.HTTPConnection(
            self.host,
            self.port,
            timeout=timeout,
        )

    @contextmanager
    def connection(self) -> Iterator[_AffinityConnection]:
        connection = self._new_connection()
        try:
            yield _AffinityConnection(
                connection,
                base_url=self.base_url,
                base_path=self.base_path,
            )
        finally:
            connection.close()

    @staticmethod
    def adopt_response_cookies(
        response: HuaweiAffinityResponse,
        session: requests.Session,
    ) -> tuple[str, ...]:
        adopted: list[str] = []
        for name, value in response.raw_headers:
            if name.casefold() != "set-cookie":
                continue
            parsed = SimpleCookie()
            try:
                parsed.load(value)
            except Exception:
                continue
            for morsel in parsed.values():
                path = morsel["path"] or "/"
                session.cookies.set(morsel.key, morsel.value, path=path)
                adopted.append(morsel.key)
        return tuple(dict.fromkeys(adopted))


class SingleWriteSocketTransport(RequestsSessionTransport):
    """Marker for firmware-specific single-write POST transport.

    It remains disabled until a physical/fixture contract proves the framing.
    """

    supports_single_segment_post = False

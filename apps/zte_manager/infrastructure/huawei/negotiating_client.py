from __future__ import annotations

import re
from dataclasses import dataclass
from enum import StrEnum
from urllib.parse import urlsplit, urlunsplit

import requests
import urllib3
from urllib3.exceptions import InsecureRequestWarning

from .family_client import HuaweiFamilyAwareWebClient
from .protocol import HuaweiAuthFlow


class HuaweiTransportFailure(StrEnum):
    NETWORK_ERROR = "NETWORK_ERROR"
    TLS_ERROR = "TLS_ERROR"
    AUTH_REJECTED = "AUTH_REJECTED"
    AUTH_PROTOCOL_MISMATCH = "AUTH_PROTOCOL_MISMATCH"
    UNSUPPORTED_FIRMWARE = "UNSUPPORTED_FIRMWARE"
    SESSION_EXPIRED = "SESSION_EXPIRED"


class HuaweiTransportError(RuntimeError):
    def __init__(self, code: HuaweiTransportFailure, message: str) -> None:
        super().__init__(message)
        self.code = code


@dataclass(frozen=True)
class HuaweiEndpoint:
    scheme: str
    host: str
    port: int | None
    explicit_port: bool

    @property
    def base_url(self) -> str:
        hostname = self.host
        if ":" in hostname and not hostname.startswith("["):
            hostname = f"[{hostname}]"
        netloc = hostname
        if self.port is not None:
            netloc = f"{hostname}:{self.port}"
        return urlunsplit((self.scheme, netloc, "", "", ""))


_SSL_PORT = re.compile(
    r"\bSSLPort\s*=\s*['\"](?P<port>\d{1,5})['\"]",
    re.I,
)
_HTTPS_REDIRECT = re.compile(
    r"(?:window\.)?location(?:\.href)?\s*=.*?https://",
    re.I | re.S,
)
_HUAWEI_MARKERS = (
    "getrandcount.asp",
    "getrandstring.asp",
    "rndsecurityformat.js",
    "hwlog.jpg",
    "x_hw_token",
    "huawei",
)


def parse_huawei_https_bootstrap(source: str) -> int | None:
    """Return the advertised TLS port only for the Huawei-style bootstrap.

    A plain JavaScript redirect is not sufficient evidence. The page must
    expose the dedicated ``SSLPort`` variable and an HTTPS location expression.
    """

    text = str(source or "")
    match = _SSL_PORT.search(text)
    if match is None or _HTTPS_REDIRECT.search(text) is None:
        return None
    port = int(match.group("port"))
    return port if 1 <= port <= 65535 else None


def _endpoint_from_input(host: str, *, https: bool = False) -> HuaweiEndpoint:
    raw = str(host or "").strip().rstrip("/")
    if not raw:
        raise ValueError("Huawei host is required")
    supplied_scheme = "://" in raw
    value = raw if supplied_scheme else f"{'https' if https else 'http'}://{raw}"
    parsed = urlsplit(value)
    if not parsed.hostname:
        raise ValueError("Invalid Huawei host")
    try:
        port = parsed.port
    except ValueError as exc:
        raise ValueError("Invalid Huawei port") from exc
    explicit_port = bool(
        port is not None
        and (
            supplied_scheme
            or raw.rsplit("]", 1)[-1].startswith(":")
            or (raw.count(":") == 1 and not raw.startswith("["))
        )
    )
    return HuaweiEndpoint(
        scheme=(parsed.scheme or ("https" if https else "http")).lower(),
        host=parsed.hostname,
        port=port,
        explicit_port=explicit_port,
    )


class HuaweiNegotiatingWebClient(HuaweiFamilyAwareWebClient):
    """Huawei WebUI client with conservative HTTP -> HTTPS negotiation.

    Huawei embedded WebUIs may answer on HTTP port 80 with JavaScript that
    points the browser to HTTPS on the *same* port. ``requests`` does not run
    that JavaScript, so scheme negotiation belongs in the central transport.

    TLS verification is intentionally disabled only here for embedded Huawei
    certificates. Feature readers never set ``verify=False`` themselves.
    """

    VERIFY_TLS = False

    def __init__(self, host: str, username: str, password: str, **kwargs) -> None:
        self.endpoint = _endpoint_from_input(host, https=bool(kwargs.get("https", False)))
        self.bootstrap_detected = False
        self.negotiated = False
        super().__init__(host, username, password, **kwargs)
        self.base_url = self.endpoint.base_url
        self.session.verify = self.VERIFY_TLS
        if not self.VERIFY_TLS:
            urllib3.disable_warnings(InsecureRequestWarning)

    @staticmethod
    def _new_session() -> requests.Session:
        session = HuaweiFamilyAwareWebClient._new_session()
        session.verify = HuaweiNegotiatingWebClient.VERIFY_TLS
        return session

    @staticmethod
    def _contains_huawei_markers(source: str) -> bool:
        body = str(source or "").casefold()
        return any(marker in body for marker in _HUAWEI_MARKERS)

    @classmethod
    def _probe_root(
        cls,
        session: requests.Session,
        endpoint: HuaweiEndpoint,
        *,
        timeout: float,
    ):
        return session.get(
            endpoint.base_url + "/",
            timeout=(2.0, timeout),
            allow_redirects=True,
            verify=cls.VERIFY_TLS,
        )

    @classmethod
    def looks_like_huawei(
        cls,
        host: str,
        *,
        https: bool = False,
        timeout: float = 2.5,
    ) -> bool:
        try:
            endpoint = _endpoint_from_input(host, https=https)
        except ValueError:
            return False
        session = cls._new_session()
        try:
            response = cls._probe_root(session, endpoint, timeout=timeout)
            body = response.text or ""
            if response.status_code < 500 and cls._contains_huawei_markers(body):
                return True

            ssl_port = parse_huawei_https_bootstrap(body)
            if endpoint.scheme != "http" or ssl_port is None:
                return False
            secure = HuaweiEndpoint(
                scheme="https",
                host=endpoint.host,
                port=ssl_port,
                explicit_port=True,
            )
            secure_response = cls._probe_root(session, secure, timeout=timeout)
            return bool(
                secure_response.status_code < 500
                and cls._contains_huawei_markers(secure_response.text or "")
            )
        except requests.RequestException:
            return False
        finally:
            session.close()

    def _negotiate_endpoint(self) -> None:
        if self.endpoint.scheme != "http":
            return
        try:
            response = self._probe_root(
                self.session,
                self.endpoint,
                timeout=self.timeout,
            )
        except requests.exceptions.SSLError as exc:
            raise HuaweiTransportError(
                HuaweiTransportFailure.TLS_ERROR,
                "Falha TLS ao negociar a WebUI Huawei.",
            ) from exc
        except requests.RequestException as exc:
            raise HuaweiTransportError(
                HuaweiTransportFailure.NETWORK_ERROR,
                "Falha de rede ao negociar a WebUI Huawei.",
            ) from exc

        ssl_port = parse_huawei_https_bootstrap(response.text or "")
        if ssl_port is None:
            return

        self.bootstrap_detected = True
        self.endpoint = HuaweiEndpoint(
            scheme="https",
            host=self.endpoint.host,
            port=ssl_port,
            explicit_port=True,
        )
        self.base_url = self.endpoint.base_url
        self.negotiated = True

    def login(self, retries: int = 1) -> bool:
        self._negotiate_endpoint()
        try:
            return super().login(retries=1)
        except HuaweiTransportError:
            raise
        except RuntimeError as exc:
            code = (
                HuaweiTransportFailure.AUTH_PROTOCOL_MISMATCH
                if self.auth_flow is HuaweiAuthFlow.UNKNOWN
                else HuaweiTransportFailure.AUTH_REJECTED
            )
            raise HuaweiTransportError(code, str(exc)) from exc

    def reauthenticate(self) -> bool:
        try:
            return super().reauthenticate()
        except RuntimeError as exc:
            raise HuaweiTransportError(
                HuaweiTransportFailure.SESSION_EXPIRED,
                "Sessão Huawei expirada; a reautenticação não foi confirmada.",
            ) from exc

    def transport_descriptor(self) -> dict[str, object]:
        return {
            "scheme": self.endpoint.scheme,
            "port": self.endpoint.port,
            "explicit_port": self.endpoint.explicit_port,
            "https_bootstrap": self.bootstrap_detected,
            "negotiated": self.negotiated,
            "tls_verify": self.VERIFY_TLS,
        }

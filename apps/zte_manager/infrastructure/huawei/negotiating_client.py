from __future__ import annotations

import logging
import os
import re
from dataclasses import dataclass
from enum import StrEnum
from urllib.parse import urlsplit, urlunsplit

import requests
import urllib3
from urllib3.exceptions import InsecureRequestWarning

from .family_client import HuaweiFamilyAwareWebClient
from .protocol import HuaweiAuthFlow


logger = logging.getLogger(__name__)


class HuaweiTransportFailure(StrEnum):
    NETWORK_ERROR = "NETWORK_ERROR"
    TLS_ERROR = "TLS_ERROR"
    AUTH_REJECTED = "AUTH_REJECTED"
    AUTH_PROTOCOL_MISMATCH = "AUTH_PROTOCOL_MISMATCH"
    UNSUPPORTED_FIRMWARE = "UNSUPPORTED_FIRMWARE"
    SESSION_EXPIRED = "SESSION_EXPIRED"


class HuaweiTransportError(RuntimeError):
    """Sanitized Huawei connection failure with transport/auth context.

    The object deliberately stores only phase/code/exception *type* and the
    resolved endpoint metadata. Credentials, challenge values, cookies and
    session tokens are never attached to the exception.
    """

    def __init__(
        self,
        code: HuaweiTransportFailure,
        message: str,
        *,
        phase: str = "unknown",
        original_exception: str | None = None,
        scheme: str | None = None,
        port: int | None = None,
        auth_flow: str | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.phase = phase
        self.original_exception = original_exception
        self.scheme = scheme
        self.port = port
        self.auth_flow = auth_flow


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
_LOCATION_ASSIGN = re.compile(
    r"(?:window\.)?location(?:\.href)?\s*=\s*(?P<expr>[^;]+)",
    re.I,
)
_JS_IDENTIFIER = re.compile(r"^[A-Za-z_$][A-Za-z0-9_$]*$")
_HUAWEI_MARKERS = (
    "getrandcount.asp",
    "getrandstring.asp",
    "rndsecurityformat.js",
    "hwlog.jpg",
    "x_hw_token",
    "huawei",
)


def _trace_enabled() -> bool:
    return str(os.getenv("HUAWEI_HTTP_TRACE") or "").strip().casefold() in {
        "1",
        "true",
        "yes",
        "basic",
        "raw",
        "unsafe",
    }


def _effective_port(parsed) -> int | None:
    try:
        if parsed.port is not None:
            return parsed.port
    except ValueError:
        return None
    if parsed.scheme == "https":
        return 443
    if parsed.scheme == "http":
        return 80
    return None


def _response_signature(source: str) -> str:
    """Return a content class without exposing response bodies or tokens."""

    text = str(source or "")
    folded = text.casefold()
    if not text.strip():
        return "empty"
    if "login.cgi" in folded and (
        "username" in folded
        or "password" in folded
        or "getrandcount.asp" in folded
        or "getrandstring.asp" in folded
    ):
        return "login_page"
    if parse_huawei_https_bootstrap(text) is not None:
        return "https_bootstrap"
    if "getmenuarray" in folded or "ipincoming" in folded or "bbsp" in folded:
        return "authenticated_menu"
    if "productname" in folded or "deviceinfo" in folded:
        return "device_info"
    stripped = text.lstrip("\ufeff").strip()
    if len(stripped) >= 16 and "<" not in stripped and "{" not in stripped:
        return "token_like"
    if stripped.startswith(("{", "[")):
        return "json"
    if "<html" in folded or "<script" in folded:
        return "html"
    return "text"


def _trace_exchange(response, *args, **kwargs):
    """Requests response hook used by every negotiating-client session.

    Deliberately logs no request/response body, headers, query string, cookie,
    credential, challenge or token. This remains safe even when operators set
    HUAWEI_HTTP_TRACE=raw/unsafe from older documentation.
    """

    if not _trace_enabled():
        return response
    prepared = getattr(response, "request", None)
    method = str(getattr(prepared, "method", "") or "GET").upper()
    raw_url = str(
        getattr(prepared, "url", "")
        or getattr(response, "url", "")
        or ""
    )
    parsed = urlsplit(raw_url)
    status = getattr(response, "status_code", None)
    redirect = bool(
        status is not None
        and 300 <= int(status) < 400
    )
    message = (
        "huawei_http_trace "
        f"method={method} "
        f"scheme={parsed.scheme or 'unknown'} "
        f"port={_effective_port(parsed) or 'unknown'} "
        f"path={parsed.path or '/'} "
        f"status={status if status is not None else 'unknown'} "
        f"redirect={str(redirect).lower()} "
        "exception=- "
        f"signature={_response_signature(getattr(response, 'text', '') or '')}"
    )
    logger.info(message)
    print(message, flush=True)
    return response


def _trace_exception(*, method: str, url: str, exc: BaseException) -> None:
    if not _trace_enabled():
        return
    parsed = urlsplit(str(url or ""))
    message = (
        "huawei_http_trace "
        f"method={str(method or 'GET').upper()} "
        f"scheme={parsed.scheme or 'unknown'} "
        f"port={_effective_port(parsed) or 'unknown'} "
        f"path={parsed.path or '/'} "
        "status=- redirect=false "
        f"exception={type(exc).__name__} signature=exception"
    )
    logger.warning(message)
    print(message, flush=True)


def _has_https_location_expression(source: str) -> bool:
    """Recognize literal or one-hop-variable HTTPS location assignments.

    The physical EG8041X6 bootstrap first builds a local ``target`` variable
    containing ``https://`` and then assigns ``window.location = target``.
    Keep the recognition narrow: arbitrary redirects, nested expressions and
    variables without an explicit HTTPS initializer are rejected.
    """

    text = str(source or "")
    for location in _LOCATION_ASSIGN.finditer(text):
        expression = location.group("expr").strip()
        if "https://" in expression.casefold():
            return True
        if not _JS_IDENTIFIER.fullmatch(expression):
            continue
        initializer = re.search(
            rf"\b(?:var|let|const)\s+{re.escape(expression)}\s*=\s*(?P<expr>[^;]+)",
            text,
            re.I,
        )
        if initializer and "https://" in initializer.group("expr").casefold():
            return True
    return False


def parse_huawei_https_bootstrap(source: str) -> int | None:
    """Return the advertised TLS port only for the Huawei-style bootstrap.

    A plain JavaScript redirect is not sufficient evidence. The page must
    expose the dedicated ``SSLPort`` variable and an HTTPS location expression,
    either directly or through one explicit local variable assignment.
    """

    text = str(source or "")
    match = _SSL_PORT.search(text)
    if match is None or not _has_https_location_expression(text):
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


def _root_cause(error: BaseException) -> BaseException:
    current = error
    seen: set[int] = set()
    while id(current) not in seen:
        seen.add(id(current))
        next_error = getattr(current, "__cause__", None)
        if not isinstance(next_error, BaseException):
            break
        current = next_error
    return current


def _phase_from_exception(error: BaseException) -> str:
    request = getattr(error, "request", None)
    raw_url = str(getattr(request, "url", "") or "")
    path = urlsplit(raw_url).path.casefold()
    if not path or path == "/":
        return "root"
    if path.endswith("/asp/getrandcount.asp"):
        return "rand_count"
    if path.endswith("/html/ssmp/common/getrandstring.asp"):
        return "rand_string"
    if path.endswith("/login.cgi"):
        return "login"
    if path.endswith("/asp/getmenuarray.asp"):
        return "authenticated_proof_menu"
    if path.endswith("/html/ssmp/deviceinfo/deviceinfo.asp"):
        return "authenticated_proof_deviceinfo"
    return "request"


class HuaweiNegotiatingWebClient(HuaweiFamilyAwareWebClient):
    """FamilyAware Huawei auth plus conservative endpoint negotiation.

    Endpoint discovery is transport-only. Once a final endpoint is resolved,
    authentication remains the exact HuaweiFamilyAwareWebClient pipeline:
    one fresh requests.Session, root, challenge, login.cgi and authenticated
    proof. The negotiator never invents a second authentication strategy.
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
        # FamilyAware.login() recreates the Session before issuing root,
        # RandCount/login.cgi/proof. The embedded TLS policy therefore belongs
        # in this factory, not only on the constructor-created Session.
        session = HuaweiFamilyAwareWebClient._new_session()
        session.verify = HuaweiNegotiatingWebClient.VERIFY_TLS
        session.hooks.setdefault("response", []).append(_trace_exchange)
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
        url = endpoint.base_url + "/"
        try:
            return session.get(
                url,
                timeout=(2.0, timeout),
                allow_redirects=True,
                verify=cls.VERIFY_TLS,
            )
        except requests.RequestException as exc:
            _trace_exception(method="GET", url=url, exc=exc)
            raise

    @classmethod
    def looks_like_huawei(
        cls,
        host: str,
        *,
        https: bool = False,
        timeout: float = 2.5,
    ) -> bool:
        """Read-only fingerprint using a disposable session and no credentials."""

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

    def _transport_error(
        self,
        code: HuaweiTransportFailure,
        message: str,
        *,
        phase: str,
        original: BaseException | None = None,
    ) -> HuaweiTransportError:
        error = HuaweiTransportError(
            code,
            message,
            phase=phase,
            original_exception=(type(original).__name__ if original is not None else None),
            scheme=self.endpoint.scheme,
            port=self.endpoint.port,
            auth_flow=getattr(self.auth_flow, "value", str(self.auth_flow)),
        )
        logger.warning(
            "huawei_connect_failure phase=%s code=%s exception=%s scheme=%s port=%s auth_flow=%s",
            error.phase,
            error.code.value,
            error.original_exception or "-",
            error.scheme or "unknown",
            error.port if error.port is not None else "unknown",
            error.auth_flow or "unknown",
        )
        return error

    def _negotiate_endpoint(self, *, validate_secure: bool = False) -> None:
        if self.endpoint.scheme != "http":
            return
        try:
            response = self._probe_root(
                self.session,
                self.endpoint,
                timeout=self.timeout,
            )
        except requests.exceptions.SSLError as exc:
            raise self._transport_error(
                HuaweiTransportFailure.TLS_ERROR,
                "Falha TLS ao negociar a WebUI Huawei.",
                phase="bootstrap_http",
                original=exc,
            ) from exc
        except requests.RequestException as exc:
            raise self._transport_error(
                HuaweiTransportFailure.NETWORK_ERROR,
                "Falha de rede ao negociar a WebUI Huawei.",
                phase="bootstrap_http",
                original=exc,
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

        if not validate_secure:
            return
        try:
            self._probe_root(
                self.session,
                self.endpoint,
                timeout=self.timeout,
            )
        except requests.exceptions.SSLError as exc:
            raise self._transport_error(
                HuaweiTransportFailure.TLS_ERROR,
                "O endpoint Huawei HTTPS foi descoberto, mas a negociação TLS falhou.",
                phase="bootstrap_https",
                original=exc,
            ) from exc
        except requests.RequestException as exc:
            raise self._transport_error(
                HuaweiTransportFailure.NETWORK_ERROR,
                "O endpoint Huawei HTTPS foi descoberto, mas não pôde ser alcançado.",
                phase="bootstrap_https",
                original=exc,
            ) from exc

    def _classify_familyaware_failure(self, exc: RuntimeError) -> HuaweiTransportError:
        original = _root_cause(exc)
        if isinstance(original, requests.exceptions.SSLError):
            return self._transport_error(
                HuaweiTransportFailure.TLS_ERROR,
                "Não foi possível estabelecer TLS com a ONT Huawei.",
                phase=_phase_from_exception(original),
                original=original,
            )
        if isinstance(original, requests.RequestException):
            return self._transport_error(
                HuaweiTransportFailure.NETWORK_ERROR,
                "Não foi possível alcançar a ONT Huawei durante a autenticação.",
                phase=_phase_from_exception(original),
                original=original,
            )
        if self.auth_flow is HuaweiAuthFlow.UNKNOWN:
            return self._transport_error(
                HuaweiTransportFailure.AUTH_PROTOCOL_MISMATCH,
                "O fluxo de autenticação desta Huawei não foi reconhecido.",
                phase="auth_select",
                original=exc,
            )
        return self._transport_error(
            HuaweiTransportFailure.AUTH_REJECTED,
            "A ONT Huawei rejeitou a autenticação.",
            phase="login_or_proof",
            original=exc,
        )

    def login(self, retries: int = 1) -> bool:
        # Resolve only the endpoint here. Do not perform an additional secure
        # preflight that the pre-#86 FamilyAware authentication never required.
        # FamilyAware.login() will create its own clean Session and perform the
        # real HTTPS root/challenge/login/proof sequence on the resolved URL.
        self._negotiate_endpoint(validate_secure=False)
        self.base_url = self.endpoint.base_url
        try:
            result = super().login(retries=1)
        except HuaweiTransportError:
            raise
        except RuntimeError as exc:
            raise self._classify_familyaware_failure(exc) from exc

        # Characterization guard: login() recreates the Session. The embedded
        # certificate policy and explicit/non-standard port must survive it.
        self.session.verify = self.VERIFY_TLS
        self.base_url = self.endpoint.base_url
        return result

    def reauthenticate(self) -> bool:
        try:
            return super().reauthenticate()
        except HuaweiTransportError:
            raise
        except RuntimeError as exc:
            original = _root_cause(exc)
            if isinstance(original, requests.exceptions.SSLError):
                raise self._transport_error(
                    HuaweiTransportFailure.TLS_ERROR,
                    "Não foi possível restabelecer TLS com a ONT Huawei.",
                    phase=_phase_from_exception(original),
                    original=original,
                ) from exc
            if isinstance(original, requests.RequestException):
                raise self._transport_error(
                    HuaweiTransportFailure.NETWORK_ERROR,
                    "Não foi possível alcançar a ONT Huawei durante a reautenticação.",
                    phase=_phase_from_exception(original),
                    original=original,
                ) from exc
            raise self._transport_error(
                HuaweiTransportFailure.SESSION_EXPIRED,
                "Sessão Huawei expirada; a reautenticação não foi confirmada.",
                phase="reauthenticate",
                original=exc,
            ) from exc

    def transport_descriptor(self) -> dict[str, object]:
        return {
            "scheme": self.endpoint.scheme,
            "port": self.endpoint.port,
            "explicit_port": self.endpoint.explicit_port,
            "https_bootstrap": self.bootstrap_detected,
            "negotiated": self.negotiated,
            "tls_verify": bool(self.session.verify),
        }

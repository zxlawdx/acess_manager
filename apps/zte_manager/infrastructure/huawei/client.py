from __future__ import annotations

import base64
import logging
import os
import re
import time
from dataclasses import dataclass
from urllib.parse import urljoin

import requests
from requests.adapters import HTTPAdapter


RAND_PATH = "/asp/GetRandCount.asp"
LOGIN_PATH = "/login.cgi"
MENU_PATH = "/asp/getMenuArray.asp"

logger = logging.getLogger(__name__)

_TRACE_SECRET_KEYS = {
    "password",
    "passwd",
    "pass",
    "psk",
    "presharedkey",
    "x.x_hw_token",
    "x_hw_token",
    "token",
    "cookie",
    "authorization",
    "set-cookie",
}


def _trace_mode() -> str:
    return str(os.getenv("HUAWEI_HTTP_TRACE") or "").strip().casefold()


def _trace_enabled() -> bool:
    return _trace_mode() in {"1", "true", "yes", "basic", "raw", "unsafe"}


def _trace_raw() -> bool:
    return _trace_mode() in {"raw", "unsafe"}


def _safe_mapping(values) -> dict:
    data = dict(values or {})
    if _trace_raw():
        return data

    redacted = {}
    for key, value in data.items():
        normalized = str(key).strip().casefold()
        if (
            normalized in _TRACE_SECRET_KEYS
            or "password" in normalized
            or normalized.endswith("token")
            or "presharedkey" in normalized
        ):
            redacted[key] = "<redacted>"
        else:
            redacted[key] = value
    return redacted


def _trace_http(
    *,
    phase: str,
    method: str,
    url: str,
    payload=None,
    status=None,
    headers=None,
    body=None,
) -> None:
    if not _trace_enabled():
        return

    safe_headers = _safe_mapping(headers)
    safe_payload = _safe_mapping(payload)
    raw_body = str(body or "")
    if not _trace_raw() and len(raw_body) > 4000:
        raw_body = raw_body[:4000] + "\n...[truncated; use HUAWEI_HTTP_TRACE=raw]"

    lines = [
        f"[HUAWEI HTTP] {phase} {method} {url}",
    ]
    if payload is not None:
        lines.append(f"[HUAWEI HTTP] payload={safe_payload!r}")
    if status is not None:
        lines.append(f"[HUAWEI HTTP] status={status}")
    if headers is not None:
        lines.append(f"[HUAWEI HTTP] headers={safe_headers!r}")
    if body is not None:
        lines.append("[HUAWEI HTTP] body-begin")
        lines.append(raw_body)
        lines.append("[HUAWEI HTTP] body-end")

    message = "\n".join(lines)
    logger.info(message)
    # Vela/desktop deployments do not always configure a logging handler.
    # Print as well so a physical ONT run is visible in the launch terminal.
    print(message, flush=True)


@dataclass(frozen=True)
class HuaweiMutationTransport:
    http_status: int | None
    timed_out: bool = False
    connection_uncertain: bool = False
    body: str = ""
    content_type: str = ""
    final_url: str = ""


class HuaweiWebClient:
    """Stateful Huawei WebUI transport used by Access Manager.

    Credentials, cookies and X_HW tokens remain inside the HTTP session or
    current call stack and are never returned to the frontend.
    """

    def __init__(
        self,
        host: str,
        username: str,
        password: str,
        *,
        https: bool = False,
        timeout: float = 10.0,
    ) -> None:
        scheme = "https" if https else "http"
        raw = host.rstrip("/")
        self.base_url = (
            raw
            if raw.startswith(("http://", "https://"))
            else f"{scheme}://{raw}"
        )
        self.username = username
        self.password = password
        self.timeout = float(timeout)
        self.session = self._new_session()

    @staticmethod
    def _new_session() -> requests.Session:
        session = requests.Session()
        session.trust_env = False
        adapter = HTTPAdapter(
            pool_connections=1,
            pool_maxsize=1,
            max_retries=0,
        )
        session.mount("http://", adapter)
        session.mount("https://", adapter)
        session.headers.update({
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/154.0.0.0 Safari/537.36 Edg/154.0.0.0"
            ),
            "Accept-Language": "en-US,en;q=0.9,pt-BR;q=0.8,pt;q=0.7",
            "Connection": "keep-alive",
        })
        return session

    @staticmethod
    def _preserve_request_file(path: str) -> str:
        """Keep Huawei RequestFile slashes literal.

        The EG8041X7-10 WebUI submits RequestFile=html/bbsp/... and rejects
        the otherwise equivalent %2F-encoded form on several CGI handlers.
        Decode only slashes inside RequestFile; leave every other query value
        untouched.
        """
        value = str(path or "")
        pattern = re.compile(r"([?&]RequestFile=)([^&#]*)", re.I)

        def repl(match):
            request_file = re.sub(
                r"%2f",
                "/",
                match.group(2),
                flags=re.I,
            )
            return match.group(1) + request_file

        return pattern.sub(repl, value)

    def url(self, path: str) -> str:
        safe_path = self._preserve_request_file(path)
        return urljoin(self.base_url + "/", safe_path.lstrip("/"))

    @classmethod
    def looks_like_huawei(
        cls,
        host: str,
        *,
        https: bool = False,
        timeout: float = 2.5,
    ) -> bool:
        """Conservative read-only fingerprint before selecting the protocol."""
        scheme = "https" if https else "http"
        raw = host.rstrip("/")
        base = (
            raw
            if raw.startswith(("http://", "https://"))
            else f"{scheme}://{raw}"
        )
        session = cls._new_session()
        try:
            response = session.get(
                base + "/",
                timeout=(2.0, timeout),
                allow_redirects=True,
            )
            body = (response.text or "").lower()
            markers = (
                "getrandcount.asp",
                "rndsecurityformat.js",
                "hwlog.jpg",
                "x_hw_token",
                "huawei",
            )
            return (
                response.status_code < 500
                and any(marker in body for marker in markers)
            )
        except requests.RequestException:
            return False
        finally:
            session.close()

    def _authenticate_current_session(self) -> bool:
        self.session.get(
            self.base_url + "/",
            timeout=self.timeout,
        )

        challenge_response = self.session.post(
            self.url(RAND_PATH),
            headers={
                "Accept": "*/*",
                "X-Requested-With": "XMLHttpRequest",
                "Origin": self.base_url,
                "Referer": self.base_url + "/",
            },
            timeout=self.timeout,
            allow_redirects=False,
        )
        challenge = (
            challenge_response.text
            .lstrip("\ufeff")
            .strip()
        )
        if len(challenge) < 16:
            raise RuntimeError(
                "Huawei authentication challenge was not returned"
            )

        payload = {
            "UserName": self.username,
            "PassWord": base64.b64encode(
                self.password.encode("utf-8")
            ).decode("ascii"),
            "Language": "english",
            "x.X_HW_Token": challenge,
        }

        self.session.post(
            self.url(LOGIN_PATH),
            headers={
                "Content-Type": "application/x-www-form-urlencoded",
                "Cookie": "Cookie=body:Language:english:id=-1",
                "Origin": self.base_url,
                "Referer": self.base_url + "/",
                "Upgrade-Insecure-Requests": "1",
            },
            data=payload,
            timeout=self.timeout,
            allow_redirects=True,
        )

        menu = self.session.post(
            self.url(MENU_PATH),
            headers={
                "Accept": "*/*",
                "X-Requested-With": "XMLHttpRequest",
                "Referer": self.url("/index.asp"),
            },
            timeout=self.timeout,
        )
        body = (menu.text or "").lower()
        return bool(
            menu.status_code == 200
            and (
                "home page" in body
                or "ipincoming" in body
                or "bbsp" in body
            )
        )

    def login(self, retries: int = 4) -> bool:
        for _attempt in range(max(1, int(retries))):
            try:
                self.session.close()
            except Exception:
                pass
            self.session = self._new_session()

            try:
                if self._authenticate_current_session():
                    return True
            except (requests.RequestException, RuntimeError):
                pass

            time.sleep(0.35)

        raise RuntimeError("Não foi possível autenticar na ONT Huawei.")

    def reauthenticate(self) -> bool:
        """Refresh authentication once without replacing the active Session."""
        try:
            self.session.cookies.clear()
        except Exception:
            pass

        try:
            if self._authenticate_current_session():
                return True
        except (requests.RequestException, RuntimeError):
            pass

        raise RuntimeError(
            "Sessão expirada; não foi possível reautenticar na ONT Huawei."
        )

    @staticmethod
    def is_login_response(
        response,
        *,
        forbidden_is_login: bool = True,
    ) -> bool:
        status = getattr(response, "status_code", None)
        if status == 401 or (
            status == 403 and forbidden_is_login
        ):
            return True

        body = str(getattr(response, "text", "") or "").lower()
        final_url = str(getattr(response, "url", "") or "").lower()
        login_markup = (
            "login.cgi" in body
            and (
                "getrandcount.asp" in body
                or "username" in body
                or "password" in body
            )
        )
        redirected_login = (
            "login.cgi" in final_url
            and (
                "username" in body
                or "password" in body
            )
        )
        return bool(login_markup or redirected_login)

    @staticmethod
    def extract_token(html: str) -> str:
        patterns = (
            r'id\s*=\s*["\']hwonttoken["\'][^>]*value\s*=\s*["\']([^"\']+)',
            r'value\s*=\s*["\']([^"\']+)["\'][^>]*id\s*=\s*["\']hwonttoken["\']',
            r'name\s*=\s*["\']onttoken["\'][^>]*value\s*=\s*["\']([^"\']+)',
        )
        for pattern in patterns:
            match = re.search(
                pattern,
                html or "",
                re.I | re.S,
            )
            if match:
                return match.group(1).strip()
        raise RuntimeError(
            "Token Huawei não encontrado na página atual."
        )

    def _protected_get(self, path: str):
        url = self.url(path)
        response = self.session.get(
            url,
            headers={"Referer": self.url("/index.asp")},
            timeout=self.timeout,
            allow_redirects=True,
        )
        _trace_http(
            phase="response",
            method="GET",
            url=url,
            status=response.status_code,
            headers=getattr(response, "headers", {}),
            body=getattr(response, "text", ""),
        )
        return response

    def get_page(self, path: str) -> str:
        response = self._protected_get(path)

        if self.is_login_response(response):
            self.reauthenticate()
            response = self._protected_get(path)

        if self.is_login_response(response):
            raise RuntimeError(
                "Sessão expirada; a página Huawei continuou exigindo autenticação."
            )

        if response.status_code != 200:
            raise RuntimeError(
                "Página Huawei indisponível."
            )

        return response.text

    def post_read(
        self,
        path: str,
        payload: dict[str, str] | None = None,
        *,
        referer: str = "/index.asp",
    ) -> str:
        """Execute a read-only Huawei AJAX POST with one auth recovery.

        Several Huawei information endpoints (associated stations and LAN
        inventory) are POST-only even though they do not mutate state. Unlike
        post_form(), this method may retry once after reauthentication because
        the request is read-only and idempotent.
        """
        def request():
            url = self.url(path)
            request_headers = {
                "Accept": "*/*",
                "X-Requested-With": "XMLHttpRequest",
                "Origin": self.base_url,
                "Referer": self.url(referer),
            }
            _trace_http(
                phase="request",
                method="POST",
                url=url,
                payload=payload or {},
                headers=request_headers,
            )
            response = self.session.post(
                url,
                headers=request_headers,
                data=payload or None,
                timeout=self.timeout,
                allow_redirects=True,
            )
            _trace_http(
                phase="response",
                method="POST",
                url=str(getattr(response, "url", "") or url),
                status=response.status_code,
                headers=getattr(response, "headers", {}),
                body=getattr(response, "text", ""),
            )
            return response

        response = request()
        if self.is_login_response(response):
            self.reauthenticate()
            response = request()

        if self.is_login_response(response):
            raise RuntimeError(
                "Sessão expirada; o endpoint Huawei continuou exigindo autenticação."
            )

        if response.status_code != 200:
            raise RuntimeError(
                "Endpoint Huawei de leitura indisponível."
            )

        return response.text

    def post_form(
        self,
        path: str,
        payload: dict[str, str],
        *,
        referer: str,
    ) -> HuaweiMutationTransport:
        """Send a mutation exactly once.

        Authentication recovery after a submitted mutation never retries the
        mutation. The caller must decide success exclusively through read-back.
        """
        try:
            url = self.url(path)
            request_headers = {
                "Accept": (
                    "text/html,application/xhtml+xml,"
                    "application/xml;q=0.9,*/*;q=0.8"
                ),
                "Content-Type": "application/x-www-form-urlencoded",
                "Origin": self.base_url,
                "Referer": self.url(referer),
                "Upgrade-Insecure-Requests": "1",
            }
            _trace_http(
                phase="request",
                method="POST",
                url=url,
                payload=payload,
                headers=request_headers,
            )
            response = self.session.post(
                url,
                headers=request_headers,
                data=payload,
                timeout=(5, self.timeout),
                allow_redirects=True,
            )
            _trace_http(
                phase="response",
                method="POST",
                url=str(getattr(response, "url", "") or url),
                status=response.status_code,
                headers=getattr(response, "headers", {}),
                body=getattr(response, "text", ""),
            )

            auth_lost = self.is_login_response(
                response,
                forbidden_is_login=False,
            )
            if auth_lost:
                try:
                    self.reauthenticate()
                except RuntimeError:
                    pass

            return HuaweiMutationTransport(
                http_status=response.status_code,
                connection_uncertain=auth_lost,
                body=str(getattr(response, "text", "") or ""),
                content_type=str(
                    (getattr(response, "headers", {}) or {}).get(
                        "Content-Type"
                    )
                    or ""
                ),
                final_url=str(getattr(response, "url", "") or ""),
            )
        except requests.exceptions.ReadTimeout as exc:
            if _trace_enabled():
                message = (
                    f"[HUAWEI HTTP] timeout POST {self.url(path)}: {exc!r}"
                )
                logger.warning(message)
                print(message, flush=True)
            return HuaweiMutationTransport(
                http_status=None,
                timed_out=True,
            )
        except requests.exceptions.ConnectionError as exc:
            if _trace_enabled():
                message = (
                    f"[HUAWEI HTTP] connection-error POST {self.url(path)}: "
                    f"{exc!r}"
                )
                logger.warning(message)
                print(message, flush=True)
            return HuaweiMutationTransport(
                http_status=None,
                connection_uncertain=True,
            )

    def close(self) -> None:
        self.session.close()

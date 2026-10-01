from __future__ import annotations

import base64
import re
import time
from dataclasses import dataclass
from urllib.parse import urljoin

import requests
from requests.adapters import HTTPAdapter


RAND_PATH = "/asp/GetRandCount.asp"
LOGIN_PATH = "/login.cgi"
MENU_PATH = "/asp/getMenuArray.asp"


@dataclass(frozen=True)
class HuaweiMutationTransport:
    http_status: int | None
    timed_out: bool = False
    connection_uncertain: bool = False


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

    def url(self, path: str) -> str:
        return urljoin(self.base_url + "/", path.lstrip("/"))

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
    def is_login_response(response) -> bool:
        status = getattr(response, "status_code", None)
        if status in {401, 403}:
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
        return self.session.get(
            self.url(path),
            headers={"Referer": self.url("/index.asp")},
            timeout=self.timeout,
            allow_redirects=True,
        )

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
            response = self.session.post(
                self.url(path),
                headers={
                    "Accept": (
                        "text/html,application/xhtml+xml,"
                        "application/xml;q=0.9,*/*;q=0.8"
                    ),
                    "Content-Type": "application/x-www-form-urlencoded",
                    "Origin": self.base_url,
                    "Referer": self.url(referer),
                    "Upgrade-Insecure-Requests": "1",
                },
                data=payload,
                timeout=(5, self.timeout),
                allow_redirects=True,
            )

            auth_lost = self.is_login_response(response)
            if auth_lost:
                try:
                    self.reauthenticate()
                except RuntimeError:
                    pass

            return HuaweiMutationTransport(
                http_status=response.status_code,
                connection_uncertain=auth_lost,
            )
        except requests.exceptions.ReadTimeout:
            return HuaweiMutationTransport(
                http_status=None,
                timed_out=True,
            )
        except requests.exceptions.ConnectionError:
            return HuaweiMutationTransport(
                http_status=None,
                connection_uncertain=True,
            )

    def close(self) -> None:
        self.session.close()

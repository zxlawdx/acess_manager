from __future__ import annotations

import socket
import ssl
from dataclasses import dataclass
from urllib.parse import urlencode, urlsplit

import requests


@dataclass(frozen=True, slots=True)
class SingleWriteResult:
    sent: bool
    http_status: int | None
    response_bytes: int
    connection_closed: bool
    timed_out: bool

    def as_dict(self) -> dict[str, object]:
        return {
            "sent": self.sent,
            "http_status": self.http_status,
            "response_bytes": self.response_bytes,
            "connection_closed": self.connection_closed,
            "timed_out": self.timed_out,
        }


class SingleWriteHttpTransport:
    """Lab-only raw HTTP transport that emits one complete request via sendall.

    This transport exists for firmware whose GoAhead server binds request
    framing to a single TCP write. It is never selected automatically and must
    be invoked by an explicit lab operation/profile. It does not retry, and it
    never returns raw response headers/body because they can contain cookies or
    rotated CSRF tokens.
    """

    def __init__(
        self,
        base_url: str,
        *,
        timeout: float = 10.0,
        verify_tls: bool = False,
    ) -> None:
        parsed = urlsplit(str(base_url or ""))
        if parsed.scheme not in {"http", "https"} or not parsed.hostname:
            raise ValueError("Endpoint Huawei inválido para single-write.")
        self.scheme = parsed.scheme
        self.host = parsed.hostname
        self.port = parsed.port or (443 if parsed.scheme == "https" else 80)
        self.timeout = float(timeout)
        self.verify_tls = bool(verify_tls)

    @staticmethod
    def cookie_header(session: requests.Session) -> str:
        return "; ".join(f"{cookie.name}={cookie.value}" for cookie in session.cookies)

    def _connect(self):
        raw = socket.create_connection((self.host, self.port), timeout=self.timeout)
        if self.scheme != "https":
            return raw
        context = ssl.create_default_context() if self.verify_tls else ssl._create_unverified_context()
        return context.wrap_socket(raw, server_hostname=self.host)

    def post(
        self,
        path: str,
        payload: dict[str, object] | None = None,
        *,
        referer: str,
        cookie_header: str,
        headers: dict[str, str] | None = None,
    ) -> SingleWriteResult:
        target = str(path or "").strip()
        if not target.startswith("/") or target.startswith("//"):
            raise ValueError("Single-write aceita somente endpoint relativo.")
        body = urlencode({str(k): str(v) for k, v in dict(payload or {}).items()}).encode("utf-8")
        lines = [
            f"POST {target} HTTP/1.1",
            f"Host: {self.host}",
            "User-Agent: AccessManager-HuaweiLab/1.0",
            f"Referer: {referer}",
            "Content-Type: application/x-www-form-urlencoded",
            f"Content-Length: {len(body)}",
            "Connection: close",
        ]
        if cookie_header:
            lines.append(f"Cookie: {cookie_header}")
        for key, value in dict(headers or {}).items():
            if str(key).casefold() in {"content-length", "host", "cookie", "connection"}:
                continue
            lines.append(f"{key}: {value}")
        request = ("\r\n".join(lines) + "\r\n\r\n").encode("ascii") + body

        sock = self._connect()
        chunks: list[bytes] = []
        timed_out = False
        connection_closed = False
        try:
            # Critical contract: headers + body are submitted by exactly one
            # sendall() invocation. There is intentionally no fallback/retry.
            sock.sendall(request)
            sock.settimeout(min(self.timeout, 5.0))
            received = 0
            while received < 65536:
                try:
                    chunk = sock.recv(4096)
                except socket.timeout:
                    timed_out = True
                    break
                if not chunk:
                    connection_closed = True
                    break
                chunks.append(chunk)
                received += len(chunk)
        finally:
            try:
                sock.close()
            except OSError:
                pass

        raw_response = b"".join(chunks)
        status = None
        if raw_response.startswith(b"HTTP/"):
            first = raw_response.split(b"\r\n", 1)[0].decode("ascii", "replace")
            parts = first.split()
            if len(parts) >= 2 and parts[1].isdigit():
                status = int(parts[1])
        return SingleWriteResult(
            sent=True,
            http_status=status,
            response_bytes=len(raw_response),
            connection_closed=connection_closed,
            timed_out=timed_out,
        )

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass
from typing import Any


_HEX_ESCAPE = re.compile(r"\\x([0-9a-fA-F]{2})")
_ERR_CODE = re.compile(
    r"""\bErrCode\s*=\s*["']([^"']+)["']""",
    re.I,
)
_HTML_MARKERS = ("<!doctype html", "<html", "<body", "<head")
_DIAGNOSTIC_SPLIT = "[@#@]"
logger = logging.getLogger(__name__)

_SUCCESS_CODES = {
    "0",
    "00",
    "00000000",
    "0x0",
    "0x00000000",
    "ok",
    "success",
}
_SCRIPT_REDIRECT = re.compile(
    r"""(?:window|top|parent|self)?\s*\.?\s*location(?:\.href)?\s*=\s*["'][^"']+["']""",
    re.I,
)
_JS_RESULT_CODE = re.compile(
    r"""\b(?:result|ret(?:urn)?code|errorcode|errcode)\s*[:=]\s*["']?([0-9A-Za-z_x-]+)["']?""",
    re.I,
)


def _snippet(value: object, limit: int = 1200) -> str:
    text = str(value or "").replace("\x00", "")
    if len(text) <= limit:
        return text
    return text[:limit] + "...[truncated]"


def _warn_unaccepted(
    *,
    http_status: int | None,
    response_type: str,
    body: object,
    reason: str,
) -> None:
    logger.warning(
        "Huawei response rejected: status=%r type=%s reason=%s snippet=%r",
        http_status,
        response_type,
        reason,
        _snippet(body),
    )


def _looks_like_login_page(text: str) -> bool:
    """Recognize the authenticated WebUI falling back to its login document."""
    lower = str(text or "").casefold()
    if "login.cgi" not in lower:
        return False
    markers = (
        "getrandcount.asp",
        'name="username"',
        "name='username'",
        'id="username"',
        "id='username'",
        'name="password"',
        "name='password'",
        "password",
    )
    return any(marker in lower for marker in markers)


def decode_huawei_hex_payload(value: object) -> str:
    """Decode literal Huawei \\xNN response escapes without eval()."""
    text = str(value or "").lstrip("\ufeff")
    return _HEX_ESCAPE.sub(
        lambda match: chr(int(match.group(1), 16)),
        text,
    )


@dataclass(frozen=True)
class HuaweiResponse:
    ok: bool
    accepted: bool
    confirmed: bool
    http_status: int | None
    response_type: str
    error_code: str | None = None
    error_message: str | None = None
    data: Any = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "accepted": self.accepted,
            "confirmed": self.confirmed,
            "http_status": self.http_status,
            "response_type": self.response_type,
            "error_code": self.error_code,
            "error_message": self.error_message,
            "data": self.data,
        }


class HuaweiResponseParser:
    """Classify the direct response of one Huawei mutation.

    This parser does *not* validate feature state. A 2xx HTML page, opaque text,
    JavaScript redirect or empty body means only that the mutation transport was
    accepted. Feature-specific read-back is the source of truth for confirmation.
    """

    @staticmethod
    def parse(
        *,
        http_status: int | None,
        body: object = "",
        content_type: str = "",
    ) -> HuaweiResponse:
        text = decode_huawei_hex_payload(body).strip()
        status_ok = (
            http_status is not None
            and 200 <= int(http_status) < 300
        )
        lower = text.casefold()
        full_html = any(marker in lower for marker in _HTML_MARKERS)

        if _looks_like_login_page(text):
            _warn_unaccepted(
                http_status=http_status,
                response_type="login_page",
                body=text,
                reason="authenticated mutation returned login page",
            )
            return HuaweiResponse(
                ok=False,
                accepted=False,
                confirmed=False,
                http_status=http_status,
                response_type="login_page",
                error_code="session_expired",
                error_message=(
                    "A sessão Huawei expirou durante a operação."
                ),
            )

        err = _ERR_CODE.search(text)
        if err:
            code = err.group(1).strip()
            if code.casefold() in _SUCCESS_CODES:
                return HuaweiResponse(
                    ok=status_ok,
                    accepted=status_ok,
                    confirmed=status_ok,
                    http_status=http_status,
                    response_type="success_code",
                    error_code=None,
                    error_message=None,
                    data={"code": code},
                )

            _warn_unaccepted(
                http_status=http_status,
                response_type="error_page",
                body=text,
                reason=f"ErrCode={code}",
            )
            return HuaweiResponse(
                ok=False,
                accepted=False,
                confirmed=False,
                http_status=http_status,
                response_type="error_page",
                error_code=code,
                error_message=f"A ONT Huawei retornou ErrCode {code}.",
            )

        if http_status is not None and int(http_status) >= 400:
            _warn_unaccepted(
                http_status=http_status,
                response_type="http_error",
                body=text,
                reason=f"HTTP {http_status}",
            )
            return HuaweiResponse(
                ok=False,
                accepted=False,
                confirmed=False,
                http_status=http_status,
                response_type="http_error",
                error_message=f"HTTP {http_status} retornado pela ONT Huawei.",
            )

        if http_status is not None and 300 <= int(http_status) < 400:
            _warn_unaccepted(
                http_status=http_status,
                response_type="http_redirect",
                body=text,
                reason=f"unexpected terminal redirect {http_status}",
            )
            return HuaweiResponse(
                ok=False,
                accepted=False,
                confirmed=False,
                http_status=http_status,
                response_type="http_redirect",
                error_message=(
                    "A ONT Huawei terminou a operação em um redirecionamento "
                    "HTTP inesperado."
                ),
            )

        if not text:
            return HuaweiResponse(
                ok=status_ok,
                accepted=status_ok,
                confirmed=False,
                http_status=http_status,
                response_type="empty",
            )

        if _DIAGNOSTIC_SPLIT in text:
            output, state = text.split(_DIAGNOSTIC_SPLIT, 1)
            return HuaweiResponse(
                ok=status_ok,
                accepted=status_ok,
                confirmed=False,
                http_status=http_status,
                response_type="diagnostic",
                data={
                    "output": output.strip(),
                    "state": state.strip(),
                },
            )

        candidate = text
        if candidate[:1] in {"'", '"'} and candidate[-1:] == candidate[:1]:
            try:
                candidate = json.loads(candidate)
            except (json.JSONDecodeError, TypeError):
                pass

        if isinstance(candidate, str):
            stripped = candidate.strip()
            if stripped.startswith("{") or stripped.startswith("["):
                try:
                    parsed = json.loads(stripped)
                except json.JSONDecodeError:
                    parsed = None
                if parsed is not None:
                    if isinstance(parsed, dict) and "result" in parsed:
                        success = parsed.get("result") == 0
                        error_code = (
                            str(parsed.get("error") or "").strip()
                            or None
                        )
                        if not success:
                            _warn_unaccepted(
                                http_status=http_status,
                                response_type="ajax_json",
                                body=text,
                                reason=(
                                    f"result={parsed.get('result')!r} "
                                    f"error={error_code!r}"
                                ),
                            )
                        return HuaweiResponse(
                            ok=bool(status_ok and success),
                            accepted=bool(status_ok and success),
                            confirmed=bool(status_ok and success),
                            http_status=http_status,
                            response_type="ajax_json",
                            error_code=error_code,
                            error_message=(
                                None
                                if success
                                else (
                                    "A ONT Huawei recusou a operação"
                                    + (
                                        f" ({error_code})."
                                        if error_code
                                        else "."
                                    )
                                )
                            ),
                            data=parsed,
                        )
                    return HuaweiResponse(
                        ok=status_ok,
                        accepted=status_ok,
                        confirmed=False,
                        http_status=http_status,
                        response_type="json",
                        data=parsed,
                    )

        # Tiny script redirects are valid mutation responses. Requests follows
        # HTTP redirects already; this handles firmware-side JavaScript ones.
        if _SCRIPT_REDIRECT.search(text):
            return HuaweiResponse(
                ok=status_ok,
                accepted=status_ok,
                confirmed=False,
                http_status=http_status,
                response_type="script_redirect",
                data={"redirect": _snippet(text, 400)},
            )

        # Do not search a full configuration document for arbitrary variables
        # named "result". Huawei pages contain large JS libraries where such a
        # match is unrelated to the mutation. Explicit result codes are only
        # semantic when the response is a compact CGI/script response.
        if not full_html:
            result_code = _JS_RESULT_CODE.search(text)
            if result_code:
                code = result_code.group(1).strip()
                if code.casefold() in _SUCCESS_CODES:
                    return HuaweiResponse(
                        ok=status_ok,
                        accepted=status_ok,
                        confirmed=status_ok,
                        http_status=http_status,
                        response_type="result_code",
                        data={"code": code},
                    )
                _warn_unaccepted(
                    http_status=http_status,
                    response_type="result_code",
                    body=text,
                    reason=f"result code={code}",
                )
                return HuaweiResponse(
                    ok=False,
                    accepted=False,
                    confirmed=False,
                    http_status=http_status,
                    response_type="result_code",
                    error_code=code,
                    error_message=(
                        "A ONT Huawei retornou código de falha "
                        f"{code}."
                    ),
                )

        if (
            "text/html" in str(content_type or "").casefold()
            or full_html
        ):
            return HuaweiResponse(
                ok=status_ok,
                accepted=status_ok,
                confirmed=False,
                http_status=http_status,
                response_type="html",
            )

        # Unknown 2xx text is accepted, never confirmed. Firmware revisions may
        # return opaque CGI text while the feature-specific read-back proves the
        # state transition.
        if not status_ok:
            _warn_unaccepted(
                http_status=http_status,
                response_type="text",
                body=text,
                reason="no successful HTTP status and no known success marker",
            )
        return HuaweiResponse(
            ok=status_ok,
            accepted=status_ok,
            confirmed=False,
            http_status=http_status,
            response_type="text",
            data=text,
        )

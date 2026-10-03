from __future__ import annotations

import json
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
    """Normalize EG8041X7-10 WebUI responses.

    HTTP success and configuration success are deliberately separate:
    - set.cgi/complex.cgi commonly return a full HTML page;
    - ajax CGI may return JSON encoded as literal \\xNN bytes;
    - Huawei error pages can carry var ErrCode = "...";
    - diagnostics use the [@#@] state delimiter.
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
            and 200 <= int(http_status) < 400
        )

        err = _ERR_CODE.search(text)
        if err:
            code = err.group(1).strip()
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
            return HuaweiResponse(
                ok=False,
                accepted=False,
                confirmed=False,
                http_status=http_status,
                response_type="http_error",
                error_message=f"HTTP {http_status} retornado pela ONT Huawei.",
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

        lower = text.casefold()
        if (
            "text/html" in str(content_type or "").casefold()
            or any(marker in lower for marker in _HTML_MARKERS)
        ):
            return HuaweiResponse(
                ok=status_ok,
                accepted=status_ok,
                confirmed=False,
                http_status=http_status,
                response_type="html",
            )

        return HuaweiResponse(
            ok=status_ok,
            accepted=status_ok,
            confirmed=False,
            http_status=http_status,
            response_type="text",
            data=text,
        )

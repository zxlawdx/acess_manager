from __future__ import annotations

import base64
import hashlib
import json
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from typing import Callable, TypeVar

from .errors import HuaweiCredentialBudgetExceededError
from .protocol import clean_huawei_token, plausible_huawei_token

_ResponseT = TypeVar("_ResponseT")


@dataclass
class HuaweiCredentialSubmissionBudget:
    """Hard safety budget for credential-bearing requests."""

    maximum: int = 1
    used: int = 0

    def __post_init__(self) -> None:
        if int(self.maximum) != 1:
            raise ValueError("Huawei credential submission budget must remain exactly 1")

    @property
    def remaining(self) -> int:
        return max(0, int(self.maximum) - int(self.used))

    def reset(self) -> None:
        self.used = 0

    def claim(self) -> None:
        if self.remaining <= 0:
            raise HuaweiCredentialBudgetExceededError(
                "A única submissão de credenciais permitida para esta tentativa já foi usada."
            )
        self.used += 1


class RandCountAuth:
    """Physically validated Huawei RandCount + Base64 form strategy."""

    name = "rand_count"

    def __init__(self, budget: HuaweiCredentialSubmissionBudget) -> None:
        self.budget = budget

    @staticmethod
    def normalize_challenge(value: object) -> str:
        challenge = clean_huawei_token(value)
        if not plausible_huawei_token(challenge):
            raise ValueError("Huawei RandCount challenge is invalid")
        return challenge

    @staticmethod
    def encode_password(password: str) -> str:
        return base64.b64encode(str(password).encode("utf-8")).decode("ascii")

    @classmethod
    def build_payload(
        cls,
        *,
        username: str,
        password: str,
        challenge: str,
    ) -> dict[str, str]:
        return {
            "UserName": str(username),
            "PassWord": cls.encode_password(password),
            "Language": "english",
            "x.X_HW_Token": cls.normalize_challenge(challenge),
        }

    def submit(
        self,
        submitter: Callable[[dict[str, str]], _ResponseT],
        *,
        username: str,
        password: str,
        challenge: str,
    ) -> _ResponseT:
        self.budget.claim()
        payload = self.build_payload(
            username=username,
            password=password,
            challenge=challenge,
        )
        return submitter(payload)


class RandStringSessionTokenAuth(RandCountAuth):
    """RandString login uses the same Base64 form but a different lifecycle."""

    name = "rand_string_session_token"


@dataclass(frozen=True)
class ApiSesTokenContext:
    """Sanitized structural result from /api/webserver/SesTokenInfo."""

    session_info: str
    token: str


class ApiSesTokenAuth:
    """Huawei /api/ SesTokenInfo authentication strategy.

    Public HG8245H evidence shows two password encodings. The strategy supports
    both, but deliberately does not guess between them: callers must provide a
    fingerprinted mode before the credential budget is consumed.
    """

    name = "api_ses_token"
    MODE_BASE64 = "base64"
    MODE_TOKEN_SHA256 = "token_sha256"
    MODES = frozenset({MODE_BASE64, MODE_TOKEN_SHA256})

    def __init__(self, budget: HuaweiCredentialSubmissionBudget) -> None:
        self.budget = budget

    @classmethod
    def normalize_mode(cls, value: object) -> str | None:
        text = str(value or "").strip().casefold().replace("-", "_")
        aliases = {
            "base64": cls.MODE_BASE64,
            "b64": cls.MODE_BASE64,
            "token_sha256": cls.MODE_TOKEN_SHA256,
            "sha256": cls.MODE_TOKEN_SHA256,
            "sha256_token": cls.MODE_TOKEN_SHA256,
            "hashed": cls.MODE_TOKEN_SHA256,
        }
        return aliases.get(text)

    @staticmethod
    def _json_value(data: object, name: str) -> str:
        if not isinstance(data, dict):
            return ""
        wanted = name.casefold()
        for key, value in data.items():
            if str(key).casefold() == wanted and value not in (None, ""):
                return str(value)
            if isinstance(value, dict):
                nested = ApiSesTokenAuth._json_value(value, name)
                if nested:
                    return nested
        return ""

    @classmethod
    def parse_session_token_info(cls, source: object) -> ApiSesTokenContext:
        text = str(source or "").strip()
        if not text:
            raise ValueError("Huawei SesTokenInfo response is empty")

        session_info = ""
        token = ""
        try:
            data = json.loads(text)
        except (TypeError, ValueError, json.JSONDecodeError):
            data = None
        if data is not None:
            session_info = cls._json_value(data, "SesInfo")
            token = cls._json_value(data, "TokInfo")
        else:
            try:
                root = ET.fromstring(text)
            except ET.ParseError as exc:
                raise ValueError("Huawei SesTokenInfo is neither JSON nor XML") from exc
            for node in root.iter():
                local = str(node.tag).split("}")[-1].casefold()
                value = str(node.text or "").strip()
                if local == "sesinfo" and value:
                    session_info = value
                elif local == "tokinfo" and value:
                    token = value

        token = clean_huawei_token(token)
        session_info = str(session_info or "").strip()
        if not session_info or not plausible_huawei_token(token):
            raise ValueError("Huawei SesTokenInfo lacks a valid session/token pair")
        return ApiSesTokenContext(session_info=session_info, token=token)

    @classmethod
    def infer_password_mode(cls, source: object) -> str | None:
        """Infer a mode only from explicit frontend algorithm evidence."""

        text = str(source or "").casefold()
        if not text:
            return None
        has_base64 = any(
            marker in text
            for marker in ("base64", "btoa(", "base64encode", "base64.encode")
        )
        has_sha256 = any(marker in text for marker in ("sha256", "sha-256"))
        has_token = any(
            marker in text
            for marker in (
                "tokinfo",
                "__requestverificationtoken",
                "x.x_hw_token",
                "x_hw_token",
                "sestokeninfo",
            )
        )
        if has_base64 and has_sha256 and has_token:
            return cls.MODE_TOKEN_SHA256
        if has_base64 and not has_sha256:
            return cls.MODE_BASE64
        return None

    @staticmethod
    def _base64_password(password: str) -> str:
        return base64.b64encode(str(password).encode("utf-8")).decode("ascii")

    @classmethod
    def encode_password(cls, password: str, token: str, mode: str) -> str:
        normalized = cls.normalize_mode(mode)
        if normalized is None:
            raise ValueError("Huawei API password mode is not fingerprinted")
        password_b64 = cls._base64_password(password)
        if normalized == cls.MODE_BASE64:
            return password_b64
        digest_hex = hashlib.sha256(
            (password_b64 + clean_huawei_token(token)).encode("utf-8")
        ).hexdigest()
        return base64.b64encode(digest_hex.encode("ascii")).decode("ascii")

    @classmethod
    def build_payload(
        cls,
        *,
        username: str,
        password: str,
        context: ApiSesTokenContext,
        mode: str,
    ) -> dict[str, str]:
        normalized = cls.normalize_mode(mode)
        if normalized is None:
            raise ValueError("Huawei API password mode is not fingerprinted")
        return {
            "username": str(username),
            "password": cls.encode_password(password, context.token, normalized),
            "x.X_HW_Token": context.token,
        }

    def submit(
        self,
        submitter: Callable[[dict[str, str]], _ResponseT],
        *,
        username: str,
        password: str,
        context: ApiSesTokenContext,
        mode: str,
    ) -> _ResponseT:
        normalized = self.normalize_mode(mode)
        if normalized is None:
            raise ValueError("Huawei API password mode is not fingerprinted")
        payload = self.build_payload(
            username=username,
            password=password,
            context=context,
            mode=normalized,
        )
        self.budget.claim()
        return submitter(payload)

from __future__ import annotations

import base64
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

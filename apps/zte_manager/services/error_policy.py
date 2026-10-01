"""Stable, privacy-preserving error semantics shared by Vela API handlers.

Firmware / HTTP status alone is never evidence of an unsupported capability.
Only a positively classified MissingFirmwareCapability may say it is absent.
Services can raise the typed errors below without exposing HTTP internals.
"""
from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Any

try:
    from requests import exceptions as req
except ImportError:  # tests can exercise this module without requests
    req = None


class ApplicationFailure(RuntimeError):
    code = "OPERATION_FAILED"
    category = "state"
    retryable = False
    user_message = "Não foi possível concluir a operação."

    def __init__(self, message: str | None = None, *,
                 completed: int | None = None, total: int | None = None):
        super().__init__(message or self.user_message)
        self.completed = completed
        self.total = total


class AuthenticationFailure(ApplicationFailure):
    code, category, retryable = "AUTH_FAILED", "authentication", True
    user_message = "As credenciais não foram aceitas. Verifique os dados de acesso."


class SessionExpired(ApplicationFailure):
    code, category, retryable = "SESSION_EXPIRED", "session", True
    user_message = "A sessão expirou. Reconecte-se ao equipamento."


class MissingFirmwareCapability(ApplicationFailure):
    """Use only after firmware-specific positive negative evidence."""
    code, category = "FEATURE_ABSENT", "unsupported"
    user_message = "O equipamento confirmou que este recurso não está disponível."


class ProviderFeatureUnavailable(ApplicationFailure):
    code, category = "PROVIDER_FEATURE_UNAVAILABLE", "unsupported"
    user_message = "Este recurso ainda não está disponível para o fabricante conectado."


class CapabilityUnconfirmed(ApplicationFailure):
    code, category, retryable = "CAPABILITY_UNCONFIRMED", "unconfirmed", True
    user_message = (
        "Não foi possível confirmar este recurso no equipamento atual. "
        "Verifique a sessão e tente detectar novamente. Nenhuma alteração foi realizada."
    )


class NotAuthorized(ApplicationFailure):
    code, category = "OPERATION_FORBIDDEN", "permission"
    user_message = "A sessão atual não possui autorização para realizar esta operação."


class UnexpectedDeviceResponse(ApplicationFailure):
    code, category, retryable = "INVALID_DEVICE_RESPONSE", "invalid_response", True
    user_message = "O equipamento enviou uma resposta inesperada. Nenhuma alteração foi confirmada."


class PartialOperation(ApplicationFailure):
    code, category, retryable = "OPERATION_PARTIAL", "partial", True
    user_message = (
        "Parte das alterações pode ter sido aplicada. Consulte o estado atual "
        "do equipamento antes de repetir."
    )


SAFE_WORDS = re.compile(
    r"^[\wÀ-ÿ .,;:()!?áàâãéêíóôõúçñ\-]{1,150}$",
    re.UNICODE,
)
SENSITIVE = re.compile(
    r"(?:https?://|/api/|\\|<|>|\{|\}|=|\b(?:password|passwd|token|"
    r"credential|senha|secret|traceback|post|put|get|delete|cookie)\b)",
    re.IGNORECASE,
)


def _safe_domain_text(error: BaseException, fallback: str) -> str:
    """Only simple operator-facing text. Reject free-form driver/HTTP dumps."""
    value = str(error).strip()
    if not value or not SAFE_WORDS.fullmatch(value) or SENSITIVE.search(value):
        return fallback
    return value


@dataclass(frozen=True)
class PublicFailure:
    code: str
    type: str
    message: str
    retryable: bool = False
    completed: int | None = None
    total: int | None = None

    def envelope(self) -> dict[str, Any]:
        result: dict[str, Any] = {
            "error": self.message, "type": self.type,
            "code": self.code, "retryable": self.retryable,
        }
        if self.type == "partial" and self.completed is not None:
            result["completed"] = max(0, self.completed)
        if self.type == "partial" and self.total is not None:
            result["total"] = max(0, self.total)
        return result


def classify(error: BaseException) -> PublicFailure | None:
    """Return None only for unexpected errors that require an incident ID."""
    if isinstance(error, ApplicationFailure):
        return PublicFailure(
            error.code, error.category, error.user_message, error.retryable,
            error.completed, error.total,
        )
    # The exception class is evidence of transport failure; do not log or
    # return its text (may embed hosts, URLs or credentials).
    if isinstance(error, TimeoutError) or (req and isinstance(error, req.Timeout)):
        return PublicFailure(
            "TIMEOUT", "timeout",
            "O equipamento não respondeu dentro do tempo esperado. Tente novamente.",
            True,
        )
    if isinstance(error, (ConnectionError, BrokenPipeError)) or (
        req and isinstance(error, req.ConnectionError)
    ):
        return PublicFailure(
            "NETWORK_UNREACHABLE", "connection",
            "A comunicação falhou. Verifique se o equipamento está acessível.",
            True,
        )
    if isinstance(error, PermissionError):
        return classify(NotAuthorized())
    if req and isinstance(error, req.HTTPError):
        status = getattr(getattr(error, "response", None), "status_code", None)
        if status == 401:
            return classify(AuthenticationFailure())
        if status == 403:
            return classify(NotAuthorized())
        # A 404 may be a missing route, a proxy or a firmware reply.
        # It is never automatically treated as an absent capability.
        if status == 404:
            return PublicFailure(
                "ROUTE_UNCONFIRMED", "unconfirmed",
                "A operação não foi localizada. Confira a versão do aplicativo e a sessão.",
                True,
            )
        return PublicFailure(
            "REMOTE_HTTP_ERROR", "connection",
            "O equipamento ou serviço recusou a comunicação. Tente novamente.",
            True,
        )
    if isinstance(error, ValueError):
        return PublicFailure(
            "INVALID_INPUT", "validation",
            _safe_domain_text(error, "Verifique os dados informados e tente novamente."),
        )
    if isinstance(error, RuntimeError):
        text = str(error).strip().casefold()
        if text.startswith(("sessão expirada", "sessiontimeout", "session expired")):
            return classify(SessionExpired())
        if text.startswith(("autenticação inválida", "falha na autenticação")):
            return classify(AuthenticationFailure())
        return PublicFailure(
            "OPERATION_STATE", "state",
            _safe_domain_text(error, "Não foi possível concluir esta operação com a sessão atual."),
        )
    return None

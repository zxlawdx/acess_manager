from __future__ import annotations


class HuaweiArchitectureError(Exception):
    """Base error for evidence-driven Huawei architecture decisions.

    These errors are deliberately *not* RuntimeError: the negotiating transport
    has legacy RuntimeError compatibility handling that would otherwise collapse
    precise architecture outcomes such as ``auth_family_ambiguous`` into a
    generic auth rejection. Presentation code can safely expose only the stable
    code/public metadata below; no credential, cookie, challenge or session
    token is ever attached.
    """

    code = "huawei_error"
    category = "state"
    retryable = False
    public_message = "Não foi possível determinar com segurança o fluxo desta Huawei."

    def __init__(self, message: str | None = None) -> None:
        super().__init__(message or self.public_message)


class HuaweiTransportNegotiationError(HuaweiArchitectureError):
    code = "transport_negotiation_failed"
    category = "connection"
    retryable = True
    public_message = "Não foi possível negociar com segurança o transporte da ONT Huawei."


class HuaweiAuthFamilyAmbiguousError(HuaweiArchitectureError):
    code = "auth_family_ambiguous"
    category = "unconfirmed"
    public_message = (
        "A família de autenticação Huawei não pôde ser determinada sem ambiguidade. "
        "Nenhuma credencial foi submetida."
    )


class HuaweiCredentialBudgetExceededError(HuaweiArchitectureError):
    code = "credential_submission_budget_exceeded"
    category = "authentication"
    public_message = (
        "O limite seguro de uma submissão de credenciais para esta tentativa foi atingido."
    )


class HuaweiSessionValidationError(HuaweiArchitectureError):
    code = "session_validation_failed"
    category = "session"
    retryable = True
    public_message = "O login foi enviado, mas a sessão Huawei não pôde ser confirmada."


class HuaweiUnsupportedFirmwareError(HuaweiArchitectureError):
    code = "unsupported_firmware"
    category = "unsupported"
    public_message = "O firmware Huawei foi reconhecido, mas este fluxo ainda não está habilitado."


class HuaweiCapabilityUnavailableError(HuaweiArchitectureError):
    code = "capability_unavailable"
    category = "unsupported"
    public_message = "A capability Huawei não foi confirmada neste firmware."


class HuaweiSameConnectionRequiredError(HuaweiArchitectureError):
    code = "same_connection_required"
    category = "unconfirmed"
    public_message = (
        "Este firmware exige afinidade de conexão TCP ainda não validada pelo transporte atual."
    )

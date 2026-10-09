from __future__ import annotations


class HuaweiArchitectureError(RuntimeError):
    """Base error for Huawei protocol/transport decisions.

    Errors intentionally carry only a stable code and a sanitized message.
    Credentials, cookies, challenges and session tokens must never be attached.
    """

    code = "huawei_error"

    def __init__(self, message: str | None = None) -> None:
        super().__init__(message or self.code)


class HuaweiTransportNegotiationError(HuaweiArchitectureError):
    code = "transport_negotiation_failed"


class HuaweiAuthFamilyAmbiguousError(HuaweiArchitectureError):
    code = "auth_family_ambiguous"


class HuaweiCredentialBudgetExceededError(HuaweiArchitectureError):
    code = "credential_submission_budget_exceeded"


class HuaweiSessionValidationError(HuaweiArchitectureError):
    code = "session_validation_failed"


class HuaweiUnsupportedFirmwareError(HuaweiArchitectureError):
    code = "unsupported_firmware"


class HuaweiCapabilityUnavailableError(HuaweiArchitectureError):
    code = "capability_unavailable"


class HuaweiSameConnectionRequiredError(HuaweiArchitectureError):
    code = "same_connection_required"

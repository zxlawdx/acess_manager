from __future__ import annotations

import re
from dataclasses import dataclass
from enum import StrEnum
from typing import Iterable


class HuaweiProtocolFamily(StrEnum):
    """Observed Huawei WebUI/config transport family.

    Family is evidence-driven and deliberately independent from the marketing
    model name. A model can move between families across firmware/ISP builds.
    """

    AMP_BBSP = "amp_bbsp"
    ASP_CONFIG = "asp_config"
    UNKNOWN = "unknown"


class HuaweiAuthFlow(StrEnum):
    """Authentication challenge lifecycle observed in Huawei WebUIs."""

    RAND_COUNT = "rand_count"
    RAND_STRING_SESSION_TOKEN = "rand_string_session_token"
    RAND_COOKIE_HASH = "rand_cookie_hash"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class HuaweiProtocolFingerprint:
    family: HuaweiProtocolFamily = HuaweiProtocolFamily.UNKNOWN
    auth_flow: HuaweiAuthFlow = HuaweiAuthFlow.UNKNOWN
    evidence: tuple[str, ...] = ()

    def as_dict(self) -> dict[str, object]:
        return {
            "family": self.family.value,
            "auth_flow": self.auth_flow.value,
            "evidence": list(self.evidence),
        }


def clean_huawei_token(value: object) -> str:
    """Normalize Huawei challenge/session tokens without exposing them."""

    return str(value or "").lstrip("\ufeff").strip()


def extract_huawei_challenge(value: object) -> str:
    """Extract a challenge while preserving observed Huawei token variance.

    Some RandCount responses are the token itself. Others include a prefix and
    consumers independently observe the final 32 hexadecimal characters as the
    challenge. Only that exact trailing-hex signature is sliced; arbitrary long
    tokens remain untouched.
    """

    token = clean_huawei_token(value)
    match = re.search(r"([0-9A-Fa-f]{32})$", token)
    if match and len(token) > 32:
        return match.group(1)
    return token


def plausible_huawei_token(value: object) -> bool:
    token = clean_huawei_token(value)
    lower = token.casefold()
    return bool(
        len(token) >= 16
        and "<html" not in lower
        and "<form" not in lower
        and "login.cgi" not in lower
    )


def auth_flow_from_login_page(source: object) -> HuaweiAuthFlow:
    """Resolve only explicit login-page evidence; never guess by model."""

    text = str(source or "").casefold()
    if "getrandstring.asp" in text:
        return HuaweiAuthFlow.RAND_STRING_SESSION_TOKEN

    # Older HG8010H-family pages compute an authentication cookie from the
    # random challenge instead of submitting UserName/PassWord in the ordinary
    # RandCount form. Keep this distinct so Access Manager never sends the
    # wrong credential-bearing request merely because GetRandCount is present.
    legacy_cookie_markers = (
        "rndsecurityformat",
        "cookie=username:",
        "cookie=rid=",
    )
    if "getrandcount.asp" in text and any(
        marker in text for marker in legacy_cookie_markers
    ):
        return HuaweiAuthFlow.RAND_COOKIE_HASH

    if "getrandcount.asp" in text:
        return HuaweiAuthFlow.RAND_COUNT
    return HuaweiAuthFlow.UNKNOWN


def protocol_family_from_observations(
    paths: Iterable[str],
    *,
    sources: Iterable[object] = (),
) -> tuple[HuaweiProtocolFamily, tuple[str, ...]]:
    """Classify a WebUI family from endpoints actually observed at runtime.

    GetConfig/SetConfig wins only when that ASP configuration surface was
    actually observed. AMP/BBSP/SSMP pages otherwise establish the common
    Huawei generated-WebUI family. Documentation alone must not call this.
    """

    normalized_paths = tuple(str(path or "") for path in paths if path)
    lowered = tuple(path.casefold() for path in normalized_paths)
    evidence: list[str] = []

    if any(
        path.startswith("/asp/getconfig.asp")
        or path.startswith("/asp/setconfig.asp")
        for path in lowered
    ):
        evidence.extend(
            path
            for path in normalized_paths
            if path.casefold().startswith(("/asp/getconfig.asp", "/asp/setconfig.asp"))
        )
        return HuaweiProtocolFamily.ASP_CONFIG, tuple(dict.fromkeys(evidence))

    amp_paths = tuple(
        path
        for path in normalized_paths
        if path.casefold().startswith(("/html/amp/", "/html/bbsp/", "/html/ssmp/", "/html/status/"))
    )
    if amp_paths:
        return HuaweiProtocolFamily.AMP_BBSP, tuple(dict.fromkeys(amp_paths))

    # Source markers are lower-confidence runtime evidence. They are useful for
    # public login pages but never promote ASP_CONFIG without an observed ASP
    # configuration endpoint.
    joined = "\n".join(str(source or "") for source in sources).casefold()
    if any(
        marker in joined
        for marker in ("/html/amp/", "/html/bbsp/", "/html/ssmp/", "/html/status/")
    ):
        return HuaweiProtocolFamily.AMP_BBSP, ("html-family-marker",)

    return HuaweiProtocolFamily.UNKNOWN, ()

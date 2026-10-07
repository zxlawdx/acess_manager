from __future__ import annotations

import re
from dataclasses import dataclass
from enum import StrEnum


class HuaweiEvidenceLevel(StrEnum):
    SOURCE_MENTIONED = "SOURCE_MENTIONED"
    SOURCE_CODE_OBSERVED = "SOURCE_CODE_OBSERVED"
    FIXTURE_OBSERVED = "FIXTURE_OBSERVED"
    MULTIPLE_SOURCES_AGREE = "MULTIPLE_SOURCES_AGREE"
    LOCAL_FIRMWARE_OBSERVED = "LOCAL_FIRMWARE_OBSERVED"
    TESTED_AUTOMATICALLY = "TESTED_AUTOMATICALLY"
    PHYSICALLY_VALIDATED = "PHYSICALLY_VALIDATED"


class HuaweiSupportLevel(StrEnum):
    RESEARCH_ONLY = "RESEARCH_ONLY"
    RECOGNIZED = "RECOGNIZED"
    READ_PARTIAL = "READ_PARTIAL"
    READ_SUPPORTED = "READ_SUPPORTED"
    WRITE_PARTIAL = "WRITE_PARTIAL"
    WRITE_SUPPORTED = "WRITE_SUPPORTED"


@dataclass(frozen=True)
class HuaweiModelProfile:
    """Knowledge/evidence about a Huawei model, never a runtime permission.

    Runtime family detection and capability probes remain authoritative. This
    registry exists so model aliases and researched evidence do not get mixed
    with the physically validated operational HuaweiProfile capabilities.
    """

    canonical_model: str
    aliases: tuple[str, ...] = ()
    known_hardware_revisions: tuple[str, ...] = ()
    known_firmware_versions: tuple[str, ...] = ()
    probable_protocol_families: tuple[str, ...] = ()
    observed_auth_strategies: tuple[str, ...] = ()
    known_endpoint_signatures: tuple[str, ...] = ()
    known_cli_surfaces: tuple[str, ...] = ()
    reference_sources: tuple[str, ...] = ()
    confidence: HuaweiEvidenceLevel = HuaweiEvidenceLevel.SOURCE_MENTIONED
    support_level: HuaweiSupportLevel = HuaweiSupportLevel.RESEARCH_ONLY
    physical_validation: bool = False

    def public(self) -> dict[str, object]:
        return {
            "canonical_model": self.canonical_model,
            "aliases": list(self.aliases),
            "known_hardware_revisions": list(self.known_hardware_revisions),
            "known_firmware_versions": list(self.known_firmware_versions),
            "probable_protocol_families": list(self.probable_protocol_families),
            "observed_auth_strategies": list(self.observed_auth_strategies),
            "known_endpoint_signatures": list(self.known_endpoint_signatures),
            "known_cli_surfaces": list(self.known_cli_surfaces),
            "reference_sources": list(self.reference_sources),
            "confidence": self.confidence.value,
            "support_level": self.support_level.value,
            "physical_validation": self.physical_validation,
        }


def _compact(model: str | None) -> str:
    value = str(model or "").strip().upper()
    value = re.sub(r"\bHUAWEI\b", " ", value)
    return re.sub(r"[^A-Z0-9]+", "", value)


HUAWEI_MODEL_REGISTRY: tuple[HuaweiModelProfile, ...] = (
    HuaweiModelProfile(
        canonical_model="EG8041X7-10",
        aliases=("EG8041X710", "EG8041X7 10", "EG8041X7_10"),
        probable_protocol_families=("amp_bbsp",),
        observed_auth_strategies=("rand_count",),
        known_endpoint_signatures=(
            "/html/ssmp/deviceinfo/deviceinfo.asp",
            "/html/amp/opticinfo/opticinfo.asp",
            "/html/bbsp/",
        ),
        reference_sources=("access-manager:eg8041x7_10_local",),
        confidence=HuaweiEvidenceLevel.PHYSICALLY_VALIDATED,
        support_level=HuaweiSupportLevel.WRITE_SUPPORTED,
        physical_validation=True,
    ),
    HuaweiModelProfile(
        canonical_model="HG8010H",
        aliases=("EchoLife HG8010H", "Huawei HG8010H"),
        known_hardware_revisions=("v1", "v2", "v3", "v4", "v5", "v6"),
        probable_protocol_families=("amp_bbsp",),
        observed_auth_strategies=("rand_count", "rand_cookie_hash"),
        known_endpoint_signatures=(
            "/html/status/opticinfo.asp:stOpticInfo/6",
            "/html/amp/opticinfo/opticinfo.asp:stOpticInfo/15",
            "/asp/GetRandCount.asp",
        ),
        known_cli_surfaces=(
            "WAP>:display onu info",
            "WAP>:display optic",
            "WAP>:display sysinfo",
            "WAP>:display pon statistics",
        ),
        reference_sources=(
            "sirjeannot/huawei-ont-2-mqtt",
            "loiklo/huawei-onu-to-graphite",
            "DictumMortuum/servus-extapi",
            "PayungsakCNR/ais-fibre-huawei-hg8010h-hacking",
            "Marco d'Itri:Exploring the Huawei HG8010H GPON ONT",
            "CAPS:Acces ONT HG8010H et EG8010H",
            "hack-gpon.org:ont-huawei-hg8010h",
        ),
        confidence=HuaweiEvidenceLevel.MULTIPLE_SOURCES_AGREE,
        support_level=HuaweiSupportLevel.READ_PARTIAL,
        physical_validation=False,
    ),
    HuaweiModelProfile(
        canonical_model="EG8010H",
        aliases=("EchoLife EG8010H", "Huawei EG8010H"),
        probable_protocol_families=("amp_bbsp",),
        observed_auth_strategies=("rand_count",),
        known_endpoint_signatures=(
            "/asp/GetRandCount.asp",
            "/html/amp/opticinfo/opticinfo.asp",
        ),
        known_cli_surfaces=("WAP>",),
        reference_sources=("CAPS:Acces ONT HG8010H et EG8010H",),
        confidence=HuaweiEvidenceLevel.SOURCE_CODE_OBSERVED,
        support_level=HuaweiSupportLevel.RECOGNIZED,
        physical_validation=False,
    ),
    HuaweiModelProfile(
        canonical_model="EG8021V5",
        aliases=("Huawei EG8021V5",),
        probable_protocol_families=("amp_bbsp",),
        observed_auth_strategies=("rand_string_session_token",),
        known_endpoint_signatures=(
            "/html/ssmp/common/getRandString.asp",
            "/html/ssmp/common/GetRandToken.asp",
            "/html/bbsp/common/ontstate.asp",
            "/html/amp/opticinfo/opticinfo.asp",
        ),
        reference_sources=("siedgustavo/huawei-ont-stats",),
        confidence=HuaweiEvidenceLevel.TESTED_AUTOMATICALLY,
        support_level=HuaweiSupportLevel.READ_PARTIAL,
        physical_validation=False,
    ),
    HuaweiModelProfile(
        canonical_model="EG8145V5",
        aliases=("Huawei EG8145V5",),
        probable_protocol_families=("amp_bbsp",),
        observed_auth_strategies=("rand_count",),
        known_endpoint_signatures=(
            "/html/ssmp/deviceinfo/deviceinfo.asp",
            "/html/amp/opticinfo/opticinfo.asp",
        ),
        reference_sources=(
            "chickenzord/go-huawei-client",
            "jasperf/huawei-echolife-eg8145V5",
        ),
        confidence=HuaweiEvidenceLevel.MULTIPLE_SOURCES_AGREE,
        support_level=HuaweiSupportLevel.RECOGNIZED,
        physical_validation=False,
    ),
)


def resolve_huawei_model_knowledge(model: str | None) -> HuaweiModelProfile | None:
    compact = _compact(model)
    if not compact:
        return None
    for profile in HUAWEI_MODEL_REGISTRY:
        candidates = {
            _compact(profile.canonical_model),
            *(_compact(alias) for alias in profile.aliases),
        }
        if compact in candidates:
            return profile
    return None


def canonical_registered_huawei_model(model: str | None) -> str | None:
    profile = resolve_huawei_model_knowledge(model)
    return profile.canonical_model if profile is not None else None


def is_recognized_huawei_model(model: str | None) -> bool:
    return resolve_huawei_model_knowledge(model) is not None

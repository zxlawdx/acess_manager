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
    with operational HuaweiProfile capabilities.
    """

    canonical_model: str
    aliases: tuple[str, ...] = ()
    known_hardware_revisions: tuple[str, ...] = ()
    known_firmware_versions: tuple[str, ...] = ()
    probable_protocol_families: tuple[str, ...] = ()
    probable_firmware_families: tuple[str, ...] = ()
    known_cfg_modes: tuple[str, ...] = ()
    observed_auth_strategies: tuple[str, ...] = ()
    known_endpoint_signatures: tuple[str, ...] = ()
    known_cli_surfaces: tuple[str, ...] = ()
    observed_transports: tuple[str, ...] = ()
    observed_features: tuple[str, ...] = ()
    physically_validated_features: tuple[str, ...] = ()
    write_validation_status: str = "not_validated"
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
            "probable_firmware_families": list(self.probable_firmware_families),
            "known_cfg_modes": list(self.known_cfg_modes),
            "observed_auth_strategies": list(self.observed_auth_strategies),
            "known_endpoint_signatures": list(self.known_endpoint_signatures),
            "known_cli_surfaces": list(self.known_cli_surfaces),
            "observed_transports": list(self.observed_transports),
            "observed_features": list(self.observed_features),
            "physically_validated_features": list(self.physically_validated_features),
            "write_validation_status": self.write_validation_status,
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
        canonical_model="EG8041X6-10",
        aliases=("EG8041X610", "EG8041X6 10", "EG8041X6_10"),
        probable_protocol_families=("amp_bbsp",),
        probable_firmware_families=("brebg2",),
        known_cfg_modes=("BREBG2",),
        observed_auth_strategies=("rand_count",),
        known_endpoint_signatures=(
            "/asp/GetRandCount.asp",
            "/html/ssmp/deviceinfo/deviceinfo.asp",
            "/html/amp/wlanadv/WlanAdvance.asp?2G",
            "/html/amp/wlanadv/WlanAdvance.asp?5G",
            "/html/amp/common/WlanChannel.asp?1=1",
            "/html/bbsp/maintenance/diagnosecommon.asp",
            "InternetGatewayDevice.LANDevice.1.WLANConfiguration.1",
            "InternetGatewayDevice.LANDevice.1.WLANConfiguration.5",
            "InternetGatewayDevice.LANDevice.1.WiFi.Radio.1",
            "InternetGatewayDevice.LANDevice.1.WiFi.Radio.2",
        ),
        observed_transports=("webui:http-bootstrap", "webui:https:80"),
        observed_features=(
            "device_info", "wifi_basic", "wifi_radio", "wifi_advanced",
            "wifi_channel_discovery", "wan", "optical_telemetry",
            "diagnostics.ping", "diagnostics.traceroute",
        ),
        physically_validated_features=(
            "device_info", "wifi_radio", "wifi_channel_discovery", "wan",
            "diagnostics.ping", "diagnostics.traceroute",
        ),
        write_validation_status=(
            "wifi mutation surface captured; physical write effect/readback "
            "must still be confirmed per operation"
        ),
        reference_sources=("access-manager:eg8041x6_10_local",),
        confidence=HuaweiEvidenceLevel.PHYSICALLY_VALIDATED,
        support_level=HuaweiSupportLevel.READ_SUPPORTED,
        physical_validation=True,
    ),
    HuaweiModelProfile(
        canonical_model="EG8041X7-10",
        aliases=("EG8041X710", "EG8041X7 10", "EG8041X7_10"),
        probable_protocol_families=("amp_bbsp",),
        probable_firmware_families=("brebg2",),
        known_cfg_modes=("BREBG2",),
        observed_auth_strategies=("rand_count",),
        known_endpoint_signatures=(
            "/html/ssmp/deviceinfo/deviceinfo.asp",
            "/html/amp/opticinfo/opticinfo.asp",
            "/html/bbsp/",
        ),
        observed_transports=("webui",),
        observed_features=("broad_amp_bbsp_surface",),
        physically_validated_features=("broad_amp_bbsp_surface",),
        write_validation_status="physically validated with readback for mapped operations",
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
            "/html/amp/opticinfo/opticinfo.asp:stOpticInfo/8",
            "/html/amp/opticinfo/opticinfo.asp:stOpticInfo/16",
            "/asp/GetRandCount.asp",
        ),
        known_cli_surfaces=(
            "WAP>:display onu info",
            "WAP>:display optic",
            "WAP>:display sysinfo",
            "WAP>:display pon statistics",
        ),
        observed_transports=("webui", "telnet-wap", "ssh-wap"),
        reference_sources=(
            "sirjeannot/huawei-ont-2-mqtt",
            "loiklo/huawei-onu-to-graphite",
            "DictumMortuum/servus-extapi",
            "PayungsakCNR/ais-fibre-huawei-hg8010h-hacking",
            "lilmayofuksu/huawei-gpon-thing",
            "TheIcelandicguy/huawei_ont",
            "Marco d'Itri:Exploring the Huawei HG8010H GPON ONT",
            "CAPS:Acces ONT HG8010H et EG8010H",
            "hack-gpon.org:ont-huawei-hg8010h",
        ),
        confidence=HuaweiEvidenceLevel.MULTIPLE_SOURCES_AGREE,
        support_level=HuaweiSupportLevel.READ_PARTIAL,
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
        observed_transports=("webui", "wap"),
        reference_sources=("CAPS:Acces ONT HG8010H et EG8010H",),
        confidence=HuaweiEvidenceLevel.SOURCE_CODE_OBSERVED,
        support_level=HuaweiSupportLevel.RECOGNIZED,
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
        observed_transports=("webui",),
        reference_sources=("siedgustavo/huawei-ont-stats",),
        confidence=HuaweiEvidenceLevel.TESTED_AUTOMATICALLY,
        support_level=HuaweiSupportLevel.READ_PARTIAL,
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
        observed_transports=("webui", "ssh-wap"),
        reference_sources=(
            "chickenzord/go-huawei-client",
            "jasperf/huawei-echolife-eg8145V5",
            "kevinantoniowiyonolauw/netcut",
        ),
        confidence=HuaweiEvidenceLevel.MULTIPLE_SOURCES_AGREE,
        support_level=HuaweiSupportLevel.RECOGNIZED,
    ),
    HuaweiModelProfile(
        canonical_model="EG8145V5-V2",
        aliases=("Huawei EG8145V5-V2", "EG8145V5 V2"),
        probable_protocol_families=("amp_bbsp",),
        probable_firmware_families=("brebg2_candidate",),
        known_cfg_modes=("BREBG2",),
        observed_auth_strategies=("rand_count",),
        known_endpoint_signatures=(
            "/asp/GetRandCount.asp", "/login.cgi", "/html/ssmp/",
        ),
        observed_transports=("webui",),
        reference_sources=(
            "EletronicaBR:EG8145V5-V2 firmware R020/R021 research",
        ),
        confidence=HuaweiEvidenceLevel.SOURCE_MENTIONED,
        support_level=HuaweiSupportLevel.RESEARCH_ONLY,
    ),
    HuaweiModelProfile(
        canonical_model="EG8145X6-10",
        probable_protocol_families=("amp_bbsp",),
        observed_auth_strategies=("rand_count",),
        known_endpoint_signatures=(
            "/asp/GetRandCount.asp", "/login.cgi",
            "/html/bbsp/userdevinfo/getuserdevinfo.asp",
        ),
        observed_transports=("webui:https:80",),
        reference_sources=("logon84/Huawei-Optistar-EG8145X6-10-remote-login-example",),
        confidence=HuaweiEvidenceLevel.SOURCE_CODE_OBSERVED,
        support_level=HuaweiSupportLevel.RESEARCH_ONLY,
    ),
    HuaweiModelProfile(
        canonical_model="HG8245X6",
        probable_protocol_families=("amp_bbsp",),
        observed_auth_strategies=("rand_count_same_tcp_candidate",),
        reference_sources=("Erenn0989/huawei-ont-mcp",),
        confidence=HuaweiEvidenceLevel.SOURCE_CODE_OBSERVED,
        support_level=HuaweiSupportLevel.RESEARCH_ONLY,
    ),
    HuaweiModelProfile(
        canonical_model="HG8245H5",
        probable_protocol_families=("asp_config",),
        known_endpoint_signatures=("/asp/GetConfig.asp", "/asp/SetConfig.asp"),
        reference_sources=("minzique/huawei-hg8245h5",),
        confidence=HuaweiEvidenceLevel.SOURCE_CODE_OBSERVED,
        support_level=HuaweiSupportLevel.RESEARCH_ONLY,
    ),
    HuaweiModelProfile(canonical_model="HG8245H", support_level=HuaweiSupportLevel.RESEARCH_ONLY),
    HuaweiModelProfile(canonical_model="HG8012H", support_level=HuaweiSupportLevel.RESEARCH_ONLY),
    HuaweiModelProfile(canonical_model="HG8240H5", support_level=HuaweiSupportLevel.RESEARCH_ONLY),
    HuaweiModelProfile(
        canonical_model="HN8010TS",
        probable_protocol_families=("amp_bbsp",),
        reference_sources=("chickenzord/go-huawei-client:draft",),
        support_level=HuaweiSupportLevel.RESEARCH_ONLY,
    ),
    HuaweiModelProfile(canonical_model="HN8010T", aliases=("HN8010T-like",)),
    HuaweiModelProfile(canonical_model="HG8245Q2"),
    HuaweiModelProfile(canonical_model="HG8546M"),
    HuaweiModelProfile(canonical_model="HS8145V5", probable_protocol_families=("amp_bbsp",)),
    HuaweiModelProfile(canonical_model="EG8141A5"),
    HuaweiModelProfile(canonical_model="HG8245U"),
    HuaweiModelProfile(canonical_model="HG8245X6-8NE", aliases=("HG8245X6-8Ne",)),
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

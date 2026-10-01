from __future__ import annotations

import re
from dataclasses import dataclass

from .base import DeviceAdapter, FeatureSpec


@dataclass(frozen=True)
class HuaweiIPv4FilterCapability:
    read: bool = False
    create: bool = False
    update: bool = False
    delete: bool = False
    verified: bool = False

    def as_dict(self) -> dict[str, bool]:
        return {
            "read": self.read,
            "create": self.create,
            "update": self.update,
            "delete": self.delete,
            "verified": self.verified,
        }


@dataclass(frozen=True)
class HuaweiProfile:
    key: str
    model: str
    aliases: tuple[str, ...]
    ipv4_filter: HuaweiIPv4FilterCapability

    @property
    def vendor(self) -> str:
        return "huawei"

    @property
    def verified(self) -> bool:
        return self.ipv4_filter.verified


class HuaweiEG8041X7Profile(HuaweiProfile):
    def __init__(self) -> None:
        super().__init__(
            key="huawei_eg8041x7_10",
            model="EG8041X7-10",
            aliases=(
                "EG8041X7-10",
                "Huawei EG8041X7-10",
                "EG8041X7 10",
                "EG8041X7_10",
                "EG8041X710",
            ),
            ipv4_filter=HuaweiIPv4FilterCapability(
                read=True,
                create=True,
                update=True,
                delete=True,
                verified=True,
            ),
        )


class HuaweiUnknownProfile(HuaweiProfile):
    def __init__(self, model: str | None = None) -> None:
        display = canonical_huawei_model(model) or "Huawei"
        super().__init__(
            key="huawei_unknown",
            model=display,
            aliases=(),
            ipv4_filter=HuaweiIPv4FilterCapability(),
        )


KNOWN_HUAWEI_PROFILES: tuple[HuaweiProfile, ...] = (
    HuaweiEG8041X7Profile(),
)


def _compact_huawei_model(model: str | None) -> str:
    value = str(model or "").strip().upper()
    value = re.sub(r"\bHUAWEI\b", " ", value)
    return re.sub(r"[^A-Z0-9]+", "", value)


def canonical_huawei_model(model: str | None) -> str:
    compact = _compact_huawei_model(model)
    if not compact:
        return ""

    for profile in KNOWN_HUAWEI_PROFILES:
        if compact in {
            _compact_huawei_model(profile.model),
            *(_compact_huawei_model(alias) for alias in profile.aliases),
        }:
            return profile.model

    value = str(model or "").strip()
    value = re.sub(r"(?i)^\s*huawei\s+", "", value)
    value = re.sub(r"[\s_]+", "-", value)
    return value.upper().strip("-")


def resolve_huawei_profile(
    model: str | None,
    *,
    unknown: bool = True,
) -> HuaweiProfile | None:
    compact = _compact_huawei_model(model)
    if compact:
        for profile in KNOWN_HUAWEI_PROFILES:
            aliases = {
                _compact_huawei_model(profile.model),
                *(_compact_huawei_model(alias) for alias in profile.aliases),
            }
            if compact in aliases:
                return profile

    return HuaweiUnknownProfile(model) if unknown else None


def huawei_profile_key(model: str | None) -> str:
    profile = resolve_huawei_profile(model)
    return profile.key if profile is not None else "huawei_unknown"


def huawei_ipv4_filter_capability(
    model: str | None,
) -> HuaweiIPv4FilterCapability:
    profile = resolve_huawei_profile(model)
    if profile is None:
        return HuaweiIPv4FilterCapability()
    return profile.ipv4_filter


def is_known_huawei_model(model: str | None) -> bool:
    profile = resolve_huawei_profile(model, unknown=False)
    return profile is not None


class HuaweiWebAdapter(DeviceAdapter):
    family = "Huawei WebUI"
    name = "huawei-webui"

    def __init__(
        self,
        model: str | None = None,
        firmware: str | None = None,
        *,
        profile: HuaweiProfile | None = None,
    ) -> None:
        self.profile = profile or resolve_huawei_profile(model)
        super().__init__(
            model=(self.profile.model if self.profile else model),
            firmware=firmware,
        )

    @property
    def features(self) -> dict[str, FeatureSpec]:
        capability = (
            self.profile.ipv4_filter
            if self.profile is not None
            else HuaweiIPv4FilterCapability()
        )
        return {
            "ipv4_filter": FeatureSpec(
                key="ipv4_filter",
                label="IPv4 Filtering",
                writable=(
                    capability.create
                    or capability.update
                    or capability.delete
                ),
                dangerous=False,
                notes=(
                    "CRUD validado fisicamente para EG8041X7-10. "
                    "Outros modelos Huawei permanecem sem escrita "
                    "até existir validação física própria."
                ),
            )
        }

    def describe(self) -> dict:
        data = super().describe()
        capability = (
            self.profile.ipv4_filter
            if self.profile is not None
            else HuaweiIPv4FilterCapability()
        )
        feature = data["features"]["ipv4_filter"]
        feature["operations"] = capability.as_dict()
        feature["verified"] = capability.verified
        data["profile"] = (
            self.profile.key if self.profile is not None else "huawei_unknown"
        )
        return data

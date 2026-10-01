from __future__ import annotations

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


_HUAWEI_PROFILES: dict[str, HuaweiIPv4FilterCapability] = {
    "EG8041X7-10": HuaweiIPv4FilterCapability(
        read=True,
        create=True,
        update=True,
        delete=True,
        verified=True,
    ),
}


def canonical_huawei_model(model: str | None) -> str:
    return (
        str(model or "")
        .strip()
        .upper()
        .replace(" ", "")
    )


def huawei_ipv4_filter_capability(
    model: str | None,
) -> HuaweiIPv4FilterCapability:
    return _HUAWEI_PROFILES.get(
        canonical_huawei_model(model),
        HuaweiIPv4FilterCapability(),
    )


def is_known_huawei_model(model: str | None) -> bool:
    return canonical_huawei_model(model) in _HUAWEI_PROFILES


class HuaweiWebAdapter(DeviceAdapter):
    family = "Huawei WebUI"
    name = "huawei-webui"

    @property
    def features(self) -> dict[str, FeatureSpec]:
        capability = huawei_ipv4_filter_capability(
            self.model
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
                    "Outros modelos Huawei exigem validação própria "
                    "antes de liberar escrita."
                ),
            )
        }

    def describe(self) -> dict:
        data = super().describe()
        capability = huawei_ipv4_filter_capability(
            self.model
        )
        data["features"]["ipv4_filter"]["operations"] = (
            capability.as_dict()
        )
        data["features"]["ipv4_filter"]["verified"] = (
            capability.verified
        )
        return data

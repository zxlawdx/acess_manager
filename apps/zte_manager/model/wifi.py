from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Generic, TypeVar

T = TypeVar("T")


@dataclass(frozen=True)
class WifiRadioConfiguration:
    """Vendor-neutral Wi-Fi radio state/intention.

    Values are normalized for Access Manager. Missing observations remain None;
    they must never be replaced by recommended defaults while representing the
    current device state.
    """

    enabled: bool | None = None
    channel: str | None = None
    channel_width: str | None = None
    mode: str | None = None
    tx_power: int | None = None
    regulatory_domain: str | None = None
    airtime_fairness: bool | None = None
    band_steering: bool | None = None
    dtim_period: int | None = None
    beacon_period: int | None = None
    rts_threshold: int | None = None

    def as_dict(self) -> dict:
        return asdict(self)


@dataclass(frozen=True)
class WifiConfiguration:
    radio_2g: WifiRadioConfiguration | None = None
    radio_5g: WifiRadioConfiguration | None = None

    def as_dict(self) -> dict:
        return {
            "2.4ghz": self.radio_2g.as_dict() if self.radio_2g else None,
            "5ghz": self.radio_5g.as_dict() if self.radio_5g else None,
        }


@dataclass(frozen=True)
class SupportedValueSet(Generic[T]):
    supported: tuple[T, ...]
    default: T | None = None

    def as_dict(self) -> dict:
        return {
            "default": self.default,
            "supported": list(self.supported),
        }


@dataclass(frozen=True)
class WifiRadioCapabilities:
    supported: bool
    read: bool
    write: bool
    channel: SupportedValueSet[str]
    channel_width: SupportedValueSet[str]
    mode: SupportedValueSet[str]
    tx_power: bool = False
    regulatory_domain: bool = False
    airtime_fairness: bool = False
    band_steering: bool = False
    dtim_period: bool = False
    beacon_period: bool = False
    rts_threshold: bool = False

    def as_dict(self) -> dict:
        return {
            "supported": self.supported,
            "read": self.read,
            "write": self.write,
            "channel": self.channel.as_dict(),
            "channel_width": self.channel_width.as_dict(),
            "mode": self.mode.as_dict(),
            "fields": {
                "tx_power": self.tx_power,
                "regulatory_domain": self.regulatory_domain,
                "airtime_fairness": self.airtime_fairness,
                "band_steering": self.band_steering,
                "dtim_period": self.dtim_period,
                "beacon_period": self.beacon_period,
                "rts_threshold": self.rts_threshold,
            },
        }


@dataclass(frozen=True)
class WifiCapabilities:
    radio_2g: WifiRadioCapabilities | None = None
    radio_5g: WifiRadioCapabilities | None = None

    def as_dict(self) -> dict:
        return {
            "2.4ghz": self.radio_2g.as_dict() if self.radio_2g else None,
            "5ghz": self.radio_5g.as_dict() if self.radio_5g else None,
        }


@dataclass(frozen=True)
class WifiConfigurationDescriptor:
    """Keeps observed state, defaults and supported values semantically apart."""

    current: WifiConfiguration
    defaults: WifiConfiguration
    capabilities: WifiCapabilities

    def as_dict(self) -> dict:
        return {
            "current": self.current.as_dict(),
            "defaults": self.defaults.as_dict(),
            "capabilities": self.capabilities.as_dict(),
        }

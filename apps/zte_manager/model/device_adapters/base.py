from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Mapping


@dataclass(frozen=True)
class EndpointSpec:
    """Descreve uma página ThinkLua sem acoplar o Service aos nomes do firmware."""

    view: str
    tag: str
    query: Mapping[str, Any] = field(default_factory=dict)
    object_keys: tuple[str, ...] = ()


@dataclass(frozen=True)
class FeatureSpec:
    """
    Capability de alto nível.

    O adapter declara *onde* o recurso vive. A leitura/escrita fica em gateways
    e services próprios; assim F6600P/F670L compartilham o fluxo sem ifs por modelo.
    """

    key: str
    label: str
    endpoints: tuple[EndpointSpec, ...] = ()
    writable: bool = False
    dangerous: bool = False
    notes: str = ""


class DeviceAdapter(ABC):
    """Strategy/Adapter para diferenças entre modelos e firmwares."""

    family = "ZTE ThinkLua"

    def __init__(
        self,
        model: str | None = None,
        firmware: str | None = None,
    ):
        self.model = (model or "ZTE").strip()
        self.firmware = (firmware or "").strip()

    @property
    @abstractmethod
    def name(self) -> str:
        raise NotImplementedError

    @property
    @abstractmethod
    def features(self) -> dict[str, FeatureSpec]:
        raise NotImplementedError

    def feature(self, key: str) -> FeatureSpec:
        try:
            return self.features[key]
        except KeyError as error:
            raise ValueError(
                f"Capability {key!r} não foi declarada para {self.name}."
            ) from error

    def describe(self) -> dict[str, Any]:
        return {
            "adapter": self.name,
            "family": self.family,
            "model": self.model,
            "firmware": self.firmware,
            "features": {
                key: {
                    "label": spec.label,
                    "writable": spec.writable,
                    "dangerous": spec.dangerous,
                    "notes": spec.notes,
                }
                for key, spec in self.features.items()
            },
        }

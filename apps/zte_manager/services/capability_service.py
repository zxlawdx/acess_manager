from __future__ import annotations

import xml.etree.ElementTree as ET
from typing import Any, Iterable

from apps.zte_manager.model.device_adapters import DeviceAdapter


_SECRET_MARKERS = (
    "password",
    "passwd",
    "passphrase",
    "secret",
)


def _mask_secrets(value: Any) -> Any:
    """Remove segredos antes de qualquer retorno genérico de capability."""
    if isinstance(value, dict):
        sanitized = {}

        for key, item in value.items():
            lower = str(key).lower()

            if any(marker in lower for marker in _SECRET_MARKERS):
                sanitized[key] = "••••••••" if item not in (None, "") else ""
            else:
                sanitized[key] = _mask_secrets(item)

        return sanitized

    if isinstance(value, list):
        return [_mask_secrets(item) for item in value]

    return value


class ThinkLuaCapabilityGateway:
    """
    Gateway genérico de leitura/probe.

    Ele conhece o protocolo menuView -> menuData, mas não conhece regras de
    negócio. A lista de páginas vem do DeviceAdapter.
    """

    def __init__(
        self,
        zte,
        adapter: DeviceAdapter,
    ):
        self.zte = zte
        self.adapter = adapter

    def read(self, feature_key: str) -> dict[str, Any]:
        spec = self.adapter.feature(feature_key)

        if not spec.endpoints:
            return {
                "feature": feature_key,
                "label": spec.label,
                "available": False,
                "probeable": False,
                "writable": spec.writable,
                "dangerous": spec.dangerous,
                "notes": spec.notes,
                "objects": {},
            }

        errors: list[str] = []

        for endpoint in spec.endpoints:
            try:
                self.zte.get_view(
                    endpoint.view,
                    Menu3Location=0,
                )

                xml = self.zte.get_menu(
                    endpoint.tag,
                    **dict(endpoint.query),
                )

                self.zte._validar_resposta(xml)
                objects = self.zte._parse_instances(xml)

                if endpoint.object_keys:
                    objects = {
                        key: objects.get(key, [])
                        for key in endpoint.object_keys
                    }

                meta = self._scalar_meta(
                    xml
                )

                if meta:
                    objects["__meta__"] = meta

                return {
                    "feature": feature_key,
                    "label": spec.label,
                    "available": True,
                    "probeable": True,
                    "writable": spec.writable,
                    "dangerous": spec.dangerous,
                    "notes": spec.notes,
                    "endpoint": {
                        "view": endpoint.view,
                        "tag": endpoint.tag,
                    },
                    "objects": _mask_secrets(objects),
                }

            except Exception as error:
                errors.append(
                    f"{endpoint.view}/{endpoint.tag}: {error}"
                )

        raise RuntimeError(
            f"{spec.label} não está disponível para este login/firmware. "
            + " | ".join(errors)
        )

    @staticmethod
    def _scalar_meta(
        xml_text: str,
    ) -> dict[str, Any]:
        """
        Preserva campos simples fora de OBJ_*/ID_*.

        Alguns menus, como syslog, retornam o conteúdo principal em tags como
        <logStr>. O parser de instâncias propositalmente ignora esses campos.
        """
        try:
            root = ET.fromstring(
                xml_text
            )
        except ET.ParseError:
            return {}

        result = {}

        for child in root:
            if list(child):
                continue

            if child.tag.startswith(
                "IF_"
            ):
                continue

            if child.tag in {
                "encode",
                "_sessionTOKEN",
            }:
                continue

            value = (
                child.text or ""
            ).strip()

            if value:
                result[
                    child.tag
                ] = value

        return _mask_secrets(
            result
        )

    def probe(self, feature_key: str) -> dict[str, Any]:
        try:
            data = self.read(feature_key)

            return {
                "feature": feature_key,
                "available": bool(data.get("available")),
                "writable": data.get("writable", False),
                "dangerous": data.get("dangerous", False),
                "notes": data.get("notes", ""),
                "endpoint": data.get("endpoint"),
            }

        except Exception as error:
            spec = self.adapter.feature(feature_key)

            return {
                "feature": feature_key,
                "available": False,
                "writable": spec.writable,
                "dangerous": spec.dangerous,
                "notes": spec.notes,
                "error": str(error),
            }

    def probe_many(
        self,
        feature_keys: Iterable[str] | None = None,
    ) -> list[dict[str, Any]]:
        keys = list(feature_keys or self.adapter.features.keys())

        return [
            self.probe(key)
            for key in keys
        ]


class CapabilityService:
    """Application Service para catálogo, probe e leitura de recursos."""

    def __init__(
        self,
        zte,
        adapter: DeviceAdapter,
    ):
        self.adapter = adapter
        self.gateway = ThinkLuaCapabilityGateway(
            zte,
            adapter,
        )

    def catalog(self) -> dict[str, Any]:
        return self.adapter.describe()

    def probe(
        self,
        features: Iterable[str] | None = None,
    ) -> dict[str, Any]:
        requested = list(features or self.adapter.features.keys())

        invalid = [
            key
            for key in requested
            if key not in self.adapter.features
        ]

        if invalid:
            raise ValueError(
                "Capabilities desconhecidas: "
                + ", ".join(invalid)
            )

        return {
            "adapter": self.adapter.name,
            "features": self.gateway.probe_many(requested),
        }

    def shape(self, feature_key: str) -> dict[str, Any]:
        """Retorna somente chaves e contagens do firmware, nunca valores.

        Inspirado no conceito de support bundle estrutural do zte_tracker,
        implementado independentemente e sem copiar seu código GPL.
        """
        result = self.gateway.read(feature_key)
        if not result.get("available"):
            return {
                "feature": feature_key,
                "available": False,
                "objects": {},
            }

        shape = {}
        for name, entries in result.get("objects", {}).items():
            if name == "__meta__":
                shape[name] = {
                    "fields": sorted(entries.keys())
                    if isinstance(entries, dict) else [],
                }
                continue

            if isinstance(entries, list):
                fields = set()
                for entry in entries:
                    if isinstance(entry, dict):
                        fields.update(str(key) for key in entry)
                shape[name] = {
                    "count": len(entries),
                    "fields": sorted(fields),
                }

        return {
            "feature": feature_key,
            "available": True,
            "endpoint": result.get("endpoint"),
            "objects": shape,
        }

    def read(self, feature_key: str) -> dict[str, Any]:
        return self.gateway.read(feature_key)

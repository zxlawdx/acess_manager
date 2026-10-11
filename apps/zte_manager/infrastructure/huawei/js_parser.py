from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from typing import Any

from .codec import decode_huawei_js_string

SchemaKey = tuple[str, str]


class HuaweiJsConstructorParser:
    """Structural parser for Huawei generated ``new Constructor(...)`` data.

    The parser never executes page JavaScript. It understands quotes, escapes,
    nested delimiters, constructor definitions and optional evidence-scoped
    positional schemas. Unknown positional values remain available in ``_args``
    and ``_extra_args`` instead of being discarded.
    """

    def __init__(
        self,
        schemas: Mapping[SchemaKey, Sequence[str]] | None = None,
    ) -> None:
        self.schemas = {
            (str(family), str(constructor)): tuple(fields)
            for (family, constructor), fields in dict(schemas or {}).items()
        }

    @staticmethod
    def _matching_delimiter(source: str, start: int, opening: str, closing: str) -> int:
        depth = 0
        quote: str | None = None
        escaped = False
        for index in range(start, len(source)):
            char = source[index]
            if quote:
                if escaped:
                    escaped = False
                elif char == "\\":
                    escaped = True
                elif char == quote:
                    quote = None
                continue
            if char in {"'", '"'}:
                quote = char
                continue
            if char == opening:
                depth += 1
            elif char == closing:
                depth -= 1
                if depth == 0:
                    return index
        return -1

    @staticmethod
    def _split_arguments(raw: str) -> list[str]:
        items: list[str] = []
        current: list[str] = []
        quote: str | None = None
        escaped = False
        depth = 0
        for char in raw:
            if quote:
                current.append(char)
                if escaped:
                    escaped = False
                elif char == "\\":
                    escaped = True
                elif char == quote:
                    quote = None
                continue
            if char in {"'", '"'}:
                quote = char
                current.append(char)
                continue
            if char in "([{":
                depth += 1
                current.append(char)
                continue
            if char in ")]}":
                depth = max(0, depth - 1)
                current.append(char)
                continue
            if char == "," and depth == 0:
                items.append("".join(current).strip())
                current = []
                continue
            current.append(char)
        if current or raw.strip():
            items.append("".join(current).strip())
        return items

    @staticmethod
    def _literal(raw: str) -> Any:
        value = raw.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
            return decode_huawei_js_string(value[1:-1])
        low = value.casefold()
        if low in {"null", "undefined"}:
            return ""
        if low == "true":
            return True
        if low == "false":
            return False
        if re.fullmatch(r"-?[0-9]+", value):
            try:
                return int(value)
            except ValueError:
                pass
        if re.fullmatch(r"-?(?:[0-9]+\.[0-9]*|[0-9]*\.[0-9]+)", value):
            try:
                return float(value)
            except ValueError:
                pass
        return decode_huawei_js_string(value)

    @classmethod
    def _definitions(cls, source: str) -> dict[str, tuple[list[str], dict[str, str]]]:
        definitions: dict[str, tuple[list[str], dict[str, str]]] = {}
        pattern = re.compile(r"function\s+([A-Za-z_$][\w$]*)\s*\(")
        for match in pattern.finditer(source or ""):
            open_paren = match.end() - 1
            close_paren = cls._matching_delimiter(source, open_paren, "(", ")")
            if close_paren < 0:
                continue
            body_start = source.find("{", close_paren)
            if body_start < 0:
                continue
            body_end = cls._matching_delimiter(source, body_start, "{", "}")
            if body_end < 0:
                continue
            params = [
                item.strip()
                for item in source[open_paren + 1:close_paren].split(",")
                if item.strip()
            ]
            body = source[body_start + 1:body_end]
            assignments: dict[str, str] = {}
            for prop, param in re.findall(
                r"this\s*\.\s*([A-Za-z_$][\w$]*)\s*=\s*([A-Za-z_$][\w$]*)",
                body,
            ):
                assignments[prop] = param
            for prop, param in re.findall(
                r"this\s*\[\s*['\"]([^'\"]+)['\"]\s*\]\s*=\s*([A-Za-z_$][\w$]*)",
                body,
            ):
                assignments[prop] = param
            definitions[match.group(1)] = (params, assignments)
        return definitions

    def parse(
        self,
        source: str,
        *,
        protocol_family: str = "unknown",
    ) -> list[dict[str, Any]]:
        text = str(source or "")
        definitions = self._definitions(text)
        records: list[dict[str, Any]] = []
        pattern = re.compile(r"new\s+([A-Za-z_$][\w$]*)\s*\(")
        for match in pattern.finditer(text):
            name = match.group(1)
            open_paren = match.end() - 1
            close_paren = self._matching_delimiter(text, open_paren, "(", ")")
            if close_paren < 0:
                continue
            raw_items = self._split_arguments(text[open_paren + 1:close_paren])
            values = [self._literal(item) for item in raw_items]
            params, assignments = definitions.get(name, ([], {}))
            record: dict[str, Any] = {
                "_constructor": name,
                "_args": values,
                "_raw_args": raw_items,
            }
            for index, param in enumerate(params):
                if index < len(values):
                    record[param] = values[index]
            param_index = {param: index for index, param in enumerate(params)}
            for prop, param in assignments.items():
                index = param_index.get(param)
                if index is not None and index < len(values):
                    record[prop] = values[index]

            schema = self.schemas.get((str(protocol_family), name))
            if schema is not None:
                for index, field in enumerate(schema):
                    if index < len(values) and field:
                        record.setdefault(str(field), values[index])
                if len(values) > len(schema):
                    record["_extra_args"] = values[len(schema):]
            elif len(values) > len(params):
                record["_extra_args"] = values[len(params):]
            records.append(record)
        return records


def parse_huawei_js_constructors(
    source: str,
    *,
    protocol_family: str = "unknown",
    schemas: Mapping[SchemaKey, Sequence[str]] | None = None,
) -> list[dict[str, Any]]:
    return HuaweiJsConstructorParser(schemas=schemas).parse(
        source,
        protocol_family=protocol_family,
    )

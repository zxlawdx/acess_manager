from __future__ import annotations

import json
import re

_HEX_ESCAPE = re.compile(r"\\x([0-9a-fA-F]{2})")


def decode_huawei_js_string(value: str) -> str:
    """Decode Huawei JavaScript string escapes without firmware-specific hacks.

    Huawei pages commonly serialize dots and underscores with hexadecimal
    JavaScript escapes. Decode every valid hexadecimal byte first, then let the
    JSON string decoder handle ordinary JavaScript/JSON escapes.
    """
    text = str(value or "")
    text = _HEX_ESCAPE.sub(lambda match: chr(int(match.group(1), 16)), text)
    try:
        return json.loads(f'"{text}"')
    except (json.JSONDecodeError, TypeError):
        return text.replace(r'\\"', '"').replace(r"\\\\", "\\")

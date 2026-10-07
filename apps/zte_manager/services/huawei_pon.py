from __future__ import annotations

import re
from typing import Any

from apps.zte_manager.infrastructure.huawei import decode_huawei_js_string
from apps.zte_manager.services.huawei_captured_features import parse_huawei_js_records


PON_STATE_PAGE = "/html/bbsp/common/ontstate.asp"


def _js_scalar(source: str, name: str) -> str:
    escaped = re.escape(name)
    match = re.search(
        rf"(?:var\s+)?{escaped}\s*=\s*['\"]([^'\"]*)['\"]",
        source or "",
        re.I,
    )
    return decode_huawei_js_string(match.group(1)).strip() if match else ""


def _record_text(record: dict[str, Any], *keys: str) -> str:
    wanted = {key.casefold() for key in keys}
    for key, value in record.items():
        if str(key).casefold() in wanted and value not in (None, ""):
            return str(value).strip()
    return ""


class HuaweiPonStateReader:
    """Read the non-destructive Huawei ONT/PON state surface.

    The constructor fallback positions are reference knowledge observed on an
    external EG8021V5 firmware. They are used only when the response explicitly
    contains ``OntStateInfo``; successful parsing at runtime is what promotes
    the capability to READ_SUPPORTED for the connected device.
    """

    def __init__(self, client) -> None:
        self.client = client

    def read(self) -> dict[str, Any]:
        source = self.client.get_page(PON_STATE_PAGE)
        records = [
            record
            for record in parse_huawei_js_records(source)
            if str(record.get("_constructor") or "").casefold()
            == "ontstateinfo"
        ]
        pon_mode = _js_scalar(source, "PonMode")
        config_mode = _js_scalar(source, "CfgModeWord")

        if not records and not pon_mode and not config_mode:
            raise RuntimeError(
                "A resposta Huawei não contém estado PON reconhecível."
            )

        record = records[0] if records else {}
        args = list(record.get("_args") or [])

        ont_id = _record_text(
            record,
            "OntId",
            "ONTID",
            "OnuId",
            "ONUId",
            "id",
        )
        registration = _record_text(
            record,
            "Status",
            "ONTState",
            "OntState",
            "RegisterStatus",
            "RegStatus",
        )

        # Reference semantics from EG8021V5: OntStateInfo(..., ont_id, status,
        # ...). Do not apply this fallback to arbitrary constructors.
        if not ont_id and len(args) > 1:
            ont_id = str(args[1] or "").strip()
        if not registration and len(args) > 2:
            registration = str(args[2] or "").strip()

        normalized_mode = pon_mode.strip().upper()
        normalized_status = registration.strip().upper()
        online: bool | None = None
        if normalized_status:
            if "GPON" in normalized_mode:
                online = normalized_status in {"O5", "O5AUTH"}
            elif "EPON" in normalized_mode:
                online = normalized_status == "ONLINE"
            elif normalized_status in {"O5", "O5AUTH", "ONLINE", "UP"}:
                online = True
            elif normalized_status in {
                "OFFLINE",
                "DOWN",
                "LOS",
                "O1",
                "O2",
                "O3",
                "O4",
                "O6",
                "O7",
            }:
                online = False

        return {
            "pon_mode": pon_mode or None,
            "registration_status": registration or None,
            "onu_id": ont_id or None,
            "configuration_mode": config_mode or None,
            "online": online,
            "source_endpoint": PON_STATE_PAGE,
            "constructor": (
                str(record.get("_constructor") or "") or None
            ),
        }

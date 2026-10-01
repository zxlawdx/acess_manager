from __future__ import annotations

import logging
import re
from dataclasses import dataclass

from apps.zte_manager.infrastructure.huawei.codec import decode_huawei_js_string
from apps.zte_manager.model.device_adapters.huawei import (
    canonical_huawei_model,
    is_known_huawei_model,
)

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class HuaweiDetection:
    vendor: str = "huawei"
    model_raw: str | None = None
    model: str | None = None
    confidence: str = "unknown"
    source: str | None = None

    @property
    def verified(self) -> bool:
        return bool(
            self.confidence == "high"
            and self.model
            and is_known_huawei_model(self.model)
        )


class HuaweiDetector:
    AUTHENTICATED_PAGES = (
        "/html/ssmp/deviceinfo/deviceinfo.asp",
        "/html/amp/opticinfo/opticinfo.asp",
        "/html/bbsp/ipincoming/ipincoming.asp",
        "/index.asp",
    )

    _KNOWN_MODEL_PATTERNS = (
        re.compile(r"(?i)\b(?:HUAWEI\s+)?EG8041X7[\s_\-]*10\b"),
        re.compile(r"(?i)\bEG8041X710\b"),
    )

    @classmethod
    def looks_like_huawei(
        cls,
        client_type,
        host: str,
        *,
        https: bool = False,
    ) -> bool:
        return bool(
            client_type.looks_like_huawei(
                host,
                https=https,
            )
        )

    @classmethod
    def detect_authenticated(
        cls,
        client,
    ) -> HuaweiDetection:
        observations: list[tuple[str, str]] = []

        for page in cls.AUTHENTICATED_PAGES:
            try:
                body = client.get_page(page)
            except Exception as exc:
                logger.debug(
                    "huawei_model_probe_failed page=%s error_type=%s",
                    page,
                    type(exc).__name__,
                )
                continue

            decoded = decode_huawei_js_string(body or "")
            raw = cls._extract_known_model(decoded)
            if raw:
                observations.append((page, raw))

        if observations:
            source, raw = observations[0]
            model = canonical_huawei_model(raw)
            return HuaweiDetection(
                model_raw=raw,
                model=model,
                confidence="high",
                source=source,
            )

        return HuaweiDetection()

    @classmethod
    def _extract_known_model(
        cls,
        source: str,
    ) -> str | None:
        text = str(source or "")
        for pattern in cls._KNOWN_MODEL_PATTERNS:
            match = pattern.search(text)
            if match:
                return match.group(0).strip()

        compact = re.sub(
            r"[^A-Z0-9]+",
            "",
            text.upper(),
        )
        if "EG8041X710" in compact:
            return "EG8041X7-10"

        return None

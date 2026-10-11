from __future__ import annotations

import logging
import re
from dataclasses import dataclass

from apps.zte_manager.infrastructure.huawei.codec import decode_huawei_js_string
from apps.zte_manager.infrastructure.huawei.protocol import (
    HuaweiAuthFlow,
    HuaweiProtocolFamily,
    protocol_family_from_observations,
)
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
    firmware_raw: str | None = None
    firmware: str | None = None
    confidence: str = "unknown"
    source: str | None = None
    protocol_family: HuaweiProtocolFamily = HuaweiProtocolFamily.UNKNOWN
    auth_flow: HuaweiAuthFlow = HuaweiAuthFlow.UNKNOWN
    protocol_evidence: tuple[str, ...] = ()

    @property
    def verified(self) -> bool:
        return bool(
            self.confidence == "high"
            and self.model
            and is_known_huawei_model(self.model)
        )

    def protocol_dict(self) -> dict[str, object]:
        return {
            "family": self.protocol_family.value,
            "auth_flow": self.auth_flow.value,
            "evidence": list(self.protocol_evidence),
        }


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
    _GENERIC_MODEL = re.compile(
        r"(?i)\b((?:EG|HG|HS|HN)\d{4}[A-Z0-9]*(?:[-_][A-Z0-9]+)*)\b"
    )
    _FIRMWARE = re.compile(
        r"(?i)\b(V\d{3,4}R\d{3}[A-Z0-9._-]*)\b"
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
        model_observations: list[tuple[str, str]] = []
        firmware_observations: list[tuple[str, str]] = []
        observed_paths: list[str] = []
        observed_sources: list[str] = []

        # API SesToken firmware proves its session with /api/system/deviceinfo
        # during login. Consume that already-validated body first instead of
        # forcing an AMP/BBSP page request or a second authentication cycle.
        identity_source = getattr(client, "authenticated_identity_source", None)
        if callable(identity_source):
            try:
                snapshot = identity_source()
            except Exception:
                snapshot = None
            if snapshot:
                page, body = snapshot
                decoded = decode_huawei_js_string(body or "")
                observed_paths.append(str(page))
                observed_sources.append(decoded)
                raw_model = cls._extract_model(decoded)
                if raw_model:
                    model_observations.append((str(page), raw_model))
                raw_firmware = cls._extract_firmware(decoded)
                if raw_firmware:
                    firmware_observations.append((str(page), raw_firmware))

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

            observed_paths.append(page)
            decoded = decode_huawei_js_string(body or "")
            observed_sources.append(decoded)
            raw_model = cls._extract_model(decoded)
            if raw_model:
                model_observations.append((page, raw_model))
            raw_firmware = cls._extract_firmware(decoded)
            if raw_firmware:
                firmware_observations.append((page, raw_firmware))

        family, family_evidence = protocol_family_from_observations(
            observed_paths,
            sources=observed_sources,
        )
        auth_flow = HuaweiAuthFlow.UNKNOWN
        descriptor = getattr(client, "protocol_descriptor", None)
        if callable(descriptor):
            protocol = descriptor() or {}
            try:
                client_family = HuaweiProtocolFamily(
                    str(protocol.get("family") or "unknown")
                )
            except ValueError:
                client_family = HuaweiProtocolFamily.UNKNOWN
            try:
                auth_flow = HuaweiAuthFlow(
                    str(protocol.get("auth_flow") or "unknown")
                )
            except ValueError:
                auth_flow = HuaweiAuthFlow.UNKNOWN
            if client_family is not HuaweiProtocolFamily.UNKNOWN:
                family = client_family
            client_evidence = tuple(
                str(value)
                for value in protocol.get("evidence") or ()
                if value
            )
            family_evidence = tuple(
                dict.fromkeys((*client_evidence, *family_evidence))
            )

        raw_model = model_observations[0][1] if model_observations else None
        model = canonical_huawei_model(raw_model) if raw_model else None
        raw_firmware = (
            firmware_observations[0][1]
            if firmware_observations
            else None
        )
        confidence = (
            "high"
            if model and is_known_huawei_model(model)
            else "medium"
            if model
            else "unknown"
        )
        return HuaweiDetection(
            model_raw=raw_model,
            model=model,
            firmware_raw=raw_firmware,
            firmware=raw_firmware,
            confidence=confidence,
            source=(model_observations[0][0] if model_observations else None),
            protocol_family=family,
            auth_flow=auth_flow,
            protocol_evidence=family_evidence,
        )

    @classmethod
    def _extract_model(
        cls,
        source: str,
    ) -> str | None:
        text = str(source or "")
        for pattern in cls._KNOWN_MODEL_PATTERNS:
            match = pattern.search(text)
            if match:
                return match.group(0).strip()

        assignments = re.finditer(
            r"(?i)(?:ProductName|ProductClass|ModelName|DeviceType|Model|DeviceName)"
            r"\s*(?:=|:)\s*['\"]([^'\"]+)['\"]",
            text,
        )
        for match in assignments:
            value = match.group(1).strip()
            generic = cls._GENERIC_MODEL.search(value)
            if generic:
                return generic.group(1)

        generic = cls._GENERIC_MODEL.search(text)
        if generic:
            return generic.group(1)

        compact = re.sub(
            r"[^A-Z0-9]+",
            "",
            text.upper(),
        )
        if "EG8041X710" in compact:
            return "EG8041X7-10"

        return None

    @classmethod
    def _extract_firmware(cls, source: str) -> str | None:
        text = str(source or "")
        assignments = re.finditer(
            r"(?i)(?:SoftwareVersion|SoftwareVer|FirmwareVersion|MainSoftwareVersion)"
            r"\s*(?:=|:)\s*['\"]([^'\"]+)['\"]",
            text,
        )
        for match in assignments:
            value = match.group(1).strip()
            if value:
                return value
        match = cls._FIRMWARE.search(text)
        return match.group(1) if match else None

    @classmethod
    def _extract_known_model(
        cls,
        source: str,
    ) -> str | None:
        """Compatibility alias retained for older detector tests/callers."""
        value = cls._extract_model(source)
        return value if value and is_known_huawei_model(value) else None

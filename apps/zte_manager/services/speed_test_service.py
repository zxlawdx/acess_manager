from __future__ import annotations

import os
import statistics
import time
from abc import ABC, abstractmethod
from typing import Any
from urllib.parse import urlparse

import requests


class SpeedTestStrategy(ABC):
    """Strategy para separar medição feita pela ONT da medição pelo PC."""

    name = "unknown"

    @abstractmethod
    def run(self) -> dict[str, Any]:
        raise NotImplementedError


class NativeOntSpeedTestStrategy(SpeedTestStrategy):
    name = "ont_native"

    def __init__(
        self,
        zte,
        server_url: str | None = None,
    ):
        self.zte = zte
        self.server_url = server_url

    def run(self) -> dict[str, Any]:
        return self.zte.native_speedtest(
            server_url=self.server_url
        )


class HttpWorkstationSpeedTestStrategy(SpeedTestStrategy):
    """
    Fallback HTTP executado pelo computador do atendente.

    Ele mede PC -> LAN/Wi-Fi -> ONT -> Internet, portanto o resultado é
    intencionalmente identificado como workstation e nunca confundido com a
    medição nativa da ONT.
    """

    name = "workstation_http"

    def __init__(
        self,
        base_url: str | None = None,
    ):
        self.base_url = (
            base_url
            or os.getenv(
                "ZTE_SPEEDTEST_BASE_URL"
            )
            or "https://speed.cloudflare.com"
        ).rstrip("/")

        self.download_bytes = int(
            os.getenv(
                "ZTE_SPEEDTEST_DOWN_BYTES",
                "25000000",
            )
        )

        self.upload_bytes = int(
            os.getenv(
                "ZTE_SPEEDTEST_UP_BYTES",
                "10000000",
            )
        )

    def run(self) -> dict[str, Any]:
        session = requests.Session()

        latency_samples = []

        for _ in range(5):
            started = time.perf_counter()

            response = session.get(
                self.base_url + "/__down",
                params={
                    "bytes": 0,
                },
                timeout=10,
            )

            response.raise_for_status()

            latency_samples.append(
                (
                    time.perf_counter()
                    - started
                ) * 1000
            )

        down_started = time.perf_counter()

        response = session.get(
            self.base_url + "/__down",
            params={
                "bytes": self.download_bytes,
            },
            timeout=45,
        )

        response.raise_for_status()

        downloaded = len(
            response.content
        )

        down_seconds = max(
            time.perf_counter()
            - down_started,
            0.001,
        )

        upload_payload = b"0" * self.upload_bytes
        up_started = time.perf_counter()

        response = session.post(
            self.base_url + "/__up",
            data=upload_payload,
            timeout=45,
        )

        response.raise_for_status()

        up_seconds = max(
            time.perf_counter()
            - up_started,
            0.001,
        )

        host = (
            urlparse(
                self.base_url
            ).hostname
            or self.base_url
        )

        return {
            "success": True,
            "source": self.name,
            "server": {
                "name": host,
                "url": self.base_url,
            },
            "download_mbps": round(
                downloaded
                * 8
                / down_seconds
                / 1_000_000,
                2,
            ),
            "upload_mbps": round(
                self.upload_bytes
                * 8
                / up_seconds
                / 1_000_000,
                2,
            ),
            "latency_ms": round(
                statistics.mean(
                    latency_samples
                ),
                2,
            ),
            "jitter_ms": round(
                statistics.pstdev(
                    latency_samples
                ),
                2,
            ),
            "download_bytes": downloaded,
            "upload_bytes": self.upload_bytes,
            "note": (
                "Medição executada pelo computador do atendente; "
                "inclui LAN/Wi-Fi local no caminho."
            ),
        }


class SpeedTestService:
    """Chain of Responsibility: nativo primeiro, fallback HTTP depois."""

    def __init__(
        self,
        zte,
    ):
        self.zte = zte

    def run(
        self,
        *,
        allow_fallback: bool = True,
        server_url: str | None = None,
    ) -> dict[str, Any]:
        strategies: list[SpeedTestStrategy] = [
            NativeOntSpeedTestStrategy(
                self.zte,
                server_url=server_url,
            )
        ]

        if allow_fallback:
            strategies.append(
                HttpWorkstationSpeedTestStrategy()
            )

        attempts = []

        for strategy in strategies:
            try:
                result = strategy.run()

                result["attempts"] = attempts

                return result

            except Exception as error:
                attempts.append({
                    "strategy": strategy.name,
                    "error": str(error),
                })

        raise RuntimeError(
            "Nenhuma estratégia de Speed Test ficou disponível. "
            + " | ".join(
                (
                    f"{item['strategy']}: {item['error']}"
                )
                for item in attempts
            )
        )

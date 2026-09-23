from __future__ import annotations

import os
import re
import statistics
import time
from abc import ABC, abstractmethod
from concurrent.futures import ThreadPoolExecutor
from typing import Any
from urllib.parse import urljoin, urlparse

import requests


_BROWSER_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/131.0 Safari/537.36"
    ),
    "Cache-Control": "no-cache",
}


def _normalize_base_url(value: str | None) -> str | None:
    if not value:
        return None

    url = str(value).strip()

    if not url:
        return None

    if "://" not in url:
        url = "https://" + url

    return url.rstrip("/")


def _hostname(value: str | None) -> str:
    url = _normalize_base_url(
        value
    )

    if not url:
        return ""

    return (
        urlparse(url).hostname
        or ""
    ).lower()


def _latency_stats(samples: list[float]) -> tuple[float | None, float | None]:
    if not samples:
        return None, None

    latency = round(
        statistics.mean(samples),
        2,
    )

    jitter = round(
        statistics.pstdev(samples),
        2,
    ) if len(samples) > 1 else 0.0

    return latency, jitter


class SpeedTestStrategy(ABC):
    """Strategy base para os diferentes provedores de medição."""

    name = "unknown"
    provider = "unknown"

    @abstractmethod
    def run(self) -> dict[str, Any]:
        raise NotImplementedError


class NativeOntSpeedTestStrategy(SpeedTestStrategy):
    name = "ont_native"
    provider = "zte_native"

    def __init__(
        self,
        zte,
        server_url: str | None = None,
    ):
        self.zte = zte
        self.server_url = server_url

    def run(self) -> dict[str, Any]:
        result = self.zte.native_speedtest(
            server_url=self.server_url
        )

        result.setdefault(
            "provider",
            self.provider,
        )

        return result


class CloudflareSpeedTestStrategy(SpeedTestStrategy):
    """Medição HTTP usando os endpoints públicos do Cloudflare Speed Test."""

    name = "workstation_cloudflare"
    provider = "cloudflare"

    def __init__(
        self,
        base_url: str | None = None,
    ):
        self.base_url = (
            _normalize_base_url(base_url)
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
        session.headers.update(
            _BROWSER_HEADERS
        )

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

        latency_ms, jitter_ms = _latency_stats(
            latency_samples
        )

        return {
            "success": True,
            "source": self.name,
            "provider": self.provider,
            "server": {
                "name": (
                    urlparse(
                        self.base_url
                    ).hostname
                    or "Cloudflare"
                ),
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
            "latency_ms": latency_ms,
            "jitter_ms": jitter_ms,
            "download_bytes": downloaded,
            "upload_bytes": self.upload_bytes,
            "note": (
                "Medição executada pelo computador do atendente usando "
                "os endpoints do Cloudflare Speed Test."
            ),
        }


class FastComSpeedTestStrategy(SpeedTestStrategy):
    """
    Adapter do FAST.com.

    O FAST.com não usa /__down e /__up. O adapter obtém o token da página
    oficial, pede os alvos CDN à API da Netflix e mede GET/POST diretamente
    contra os servidores retornados.
    """

    name = "workstation_fast"
    provider = "fast.com"

    def __init__(self):
        self.base_url = "https://fast.com"
        self.api_url = (
            "https://api.fast.com/netflix/speedtest/v2"
        )
        self.url_count = int(
            os.getenv(
                "ZTE_FAST_URL_COUNT",
                "4",
            )
        )
        self.download_bytes = int(
            os.getenv(
                "ZTE_FAST_DOWNLOAD_BYTES",
                "25000000",
            )
        )
        self.upload_bytes = int(
            os.getenv(
                "ZTE_FAST_UPLOAD_BYTES",
                "5000000",
            )
        )

    def _session(self) -> requests.Session:
        session = requests.Session()
        session.headers.update(
            _BROWSER_HEADERS
        )

        return session

    def _token(self, session: requests.Session) -> str:
        response = session.get(
            self.base_url + "/",
            timeout=15,
        )

        response.raise_for_status()

        script_match = re.search(
            r'(/app-[^"\']+\.js)',
            response.text,
        )

        if not script_match:
            raise RuntimeError(
                "FAST.com: não foi possível localizar o bundle JavaScript."
            )

        script_url = urljoin(
            self.base_url,
            script_match.group(1),
        )

        script = session.get(
            script_url,
            timeout=15,
        )

        script.raise_for_status()

        token_match = re.search(
            r'token\s*:\s*["\']([A-Za-z0-9]+)["\']',
            script.text,
        )

        if not token_match:
            raise RuntimeError(
                "FAST.com: token da API não foi encontrado no bundle atual."
            )

        return token_match.group(1)

    def _targets(
        self,
        session: requests.Session,
        token: str,
        *,
        upload: bool = False,
    ) -> list[str]:
        params = {
            "https": "true",
            "token": token,
            "urlCount": self.url_count,
        }

        if upload:
            params["type"] = "upload"

        response = session.get(
            self.api_url,
            params=params,
            timeout=15,
        )

        response.raise_for_status()

        payload = response.json()

        if isinstance(
            payload,
            dict,
        ):
            raw_targets = (
                payload.get("targets")
                or payload.get("urls")
                or []
            )
        elif isinstance(
            payload,
            list,
        ):
            raw_targets = payload
        else:
            raw_targets = []

        targets = []

        for item in raw_targets:
            if isinstance(
                item,
                dict,
            ):
                url = item.get("url")
            else:
                url = item

            if url:
                targets.append(
                    str(url)
                )

        if not targets:
            raise RuntimeError(
                "FAST.com: a API não retornou servidores de medição."
            )

        return targets

    @staticmethod
    def _range_url(
        url: str,
        start: int,
        end: int,
    ) -> str:
        if "/speedtest/range/" in url:
            return re.sub(
                r"/speedtest/range/\d+-\d+",
                f"/speedtest/range/{start}-{end}",
                url,
                count=1,
            )

        return url.replace(
            "/speedtest",
            f"/speedtest/range/{start}-{end}",
            1,
        )

    @staticmethod
    def _download_one(
        url: str,
    ) -> int:
        with requests.get(
            url,
            headers=_BROWSER_HEADERS,
            stream=True,
            timeout=45,
        ) as response:
            response.raise_for_status()

            total = 0

            for chunk in response.iter_content(
                chunk_size=256 * 1024
            ):
                if chunk:
                    total += len(
                        chunk
                    )

            return total

    @staticmethod
    def _upload_one(
        url: str,
        payload: bytes,
    ) -> int:
        response = requests.post(
            url,
            headers=_BROWSER_HEADERS,
            data=payload,
            timeout=45,
        )

        response.raise_for_status()

        return len(
            payload
        )

    def _latency(
        self,
        target: str,
    ) -> tuple[float | None, float | None]:
        samples = []
        ping_url = self._range_url(
            target,
            0,
            0,
        )

        for _ in range(5):
            started = time.perf_counter()

            response = requests.get(
                ping_url,
                headers=_BROWSER_HEADERS,
                timeout=10,
            )

            response.raise_for_status()

            samples.append(
                (
                    time.perf_counter()
                    - started
                ) * 1000
            )

        return _latency_stats(
            samples
        )

    def run(self) -> dict[str, Any]:
        session = self._session()
        token = self._token(
            session
        )

        download_targets = self._targets(
            session,
            token,
        )

        upload_targets = self._targets(
            session,
            token,
            upload=True,
        )

        latency_ms, jitter_ms = self._latency(
            download_targets[0]
        )

        download_urls = [
            self._range_url(
                target,
                0,
                self.download_bytes - 1,
            )
            for target in download_targets
        ]

        down_started = time.perf_counter()

        with ThreadPoolExecutor(
            max_workers=len(
                download_urls
            )
        ) as pool:
            downloaded = sum(
                pool.map(
                    self._download_one,
                    download_urls,
                )
            )

        down_seconds = max(
            time.perf_counter()
            - down_started,
            0.001,
        )

        upload_urls = [
            self._range_url(
                target,
                0,
                0,
            )
            for target in upload_targets
        ]

        payload = os.urandom(
            self.upload_bytes
        )

        up_started = time.perf_counter()

        with ThreadPoolExecutor(
            max_workers=len(
                upload_urls
            )
        ) as pool:
            uploaded = sum(
                pool.map(
                    lambda url: self._upload_one(
                        url,
                        payload,
                    ),
                    upload_urls,
                )
            )

        up_seconds = max(
            time.perf_counter()
            - up_started,
            0.001,
        )

        server_names = []

        for target in download_targets:
            host = (
                urlparse(target).hostname
                or ""
            )

            if host and host not in server_names:
                server_names.append(
                    host
                )

        return {
            "success": True,
            "source": self.name,
            "provider": self.provider,
            "server": {
                "name": (
                    ", ".join(
                        server_names[:3]
                    )
                    or "Netflix CDN"
                ),
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
                uploaded
                * 8
                / up_seconds
                / 1_000_000,
                2,
            ),
            "latency_ms": latency_ms,
            "jitter_ms": jitter_ms,
            "download_bytes": downloaded,
            "upload_bytes": uploaded,
            "note": (
                "Medição executada pelo computador do atendente contra "
                "servidores Netflix selecionados pela API do FAST.com."
            ),
        }


class LibreSpeedSpeedTestStrategy(SpeedTestStrategy):
    """Adapter para LibreSpeed/servidor próprio compatível."""

    name = "workstation_librespeed"
    provider = "librespeed"

    def __init__(
        self,
        base_url: str,
    ):
        normalized = _normalize_base_url(
            base_url
        )

        if not normalized:
            raise ValueError(
                "Informe a URL do servidor LibreSpeed."
            )

        self.base_url = normalized
        self.download_megabytes = int(
            os.getenv(
                "ZTE_LIBRESPEED_DOWNLOAD_MB",
                "25",
            )
        )
        self.upload_bytes = int(
            os.getenv(
                "ZTE_LIBRESPEED_UPLOAD_BYTES",
                "5000000",
            )
        )

    def _discover(
        self,
    ) -> tuple[str, str]:
        candidates = (
            (
                "backend/garbage.php",
                "backend/empty.php",
            ),
            (
                "garbage.php",
                "empty.php",
            ),
        )

        session = requests.Session()
        session.headers.update(
            _BROWSER_HEADERS
        )

        failures = []

        for download_path, empty_path in candidates:
            ping_url = (
                self.base_url
                + "/"
                + empty_path
            )

            download_url = (
                self.base_url
                + "/"
                + download_path
            )

            try:
                ping = session.get(
                    ping_url,
                    params={
                        "r": time.time_ns(),
                    },
                    timeout=6,
                )
                ping.raise_for_status()

                probe = session.get(
                    download_url,
                    params={
                        "ckSize": 1,
                        "r": time.time_ns(),
                    },
                    stream=True,
                    timeout=8,
                )
                probe.raise_for_status()
                probe.close()

                return (
                    download_url,
                    ping_url,
                )

            except Exception as error:
                failures.append(
                    f"{download_path}: {error}"
                )

        raise RuntimeError(
            "LibreSpeed: endpoints garbage.php/empty.php não foram encontrados. "
            + " | ".join(
                failures
            )
        )

    @staticmethod
    def _download_one(
        url: str,
        megabytes: int,
    ) -> int:
        with requests.get(
            url,
            headers=_BROWSER_HEADERS,
            params={
                "ckSize": megabytes,
                "r": time.time_ns(),
            },
            stream=True,
            timeout=45,
        ) as response:
            response.raise_for_status()

            total = 0

            for chunk in response.iter_content(
                chunk_size=256 * 1024
            ):
                if chunk:
                    total += len(
                        chunk
                    )

            return total

    @staticmethod
    def _upload_one(
        url: str,
        payload: bytes,
    ) -> int:
        response = requests.post(
            url,
            headers=_BROWSER_HEADERS,
            params={
                "r": time.time_ns(),
            },
            data=payload,
            timeout=45,
        )

        response.raise_for_status()

        return len(
            payload
        )

    def run(self) -> dict[str, Any]:
        download_url, empty_url = self._discover()

        latency_samples = []

        for _ in range(5):
            started = time.perf_counter()

            response = requests.get(
                empty_url,
                headers=_BROWSER_HEADERS,
                params={
                    "r": time.time_ns(),
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

        with ThreadPoolExecutor(
            max_workers=4
        ) as pool:
            downloaded = sum(
                pool.map(
                    lambda _: self._download_one(
                        download_url,
                        self.download_megabytes,
                    ),
                    range(4),
                )
            )

        down_seconds = max(
            time.perf_counter()
            - down_started,
            0.001,
        )

        payload = os.urandom(
            self.upload_bytes
        )

        up_started = time.perf_counter()

        with ThreadPoolExecutor(
            max_workers=4
        ) as pool:
            uploaded = sum(
                pool.map(
                    lambda _: self._upload_one(
                        empty_url,
                        payload,
                    ),
                    range(4),
                )
            )

        up_seconds = max(
            time.perf_counter()
            - up_started,
            0.001,
        )

        latency_ms, jitter_ms = _latency_stats(
            latency_samples
        )

        return {
            "success": True,
            "source": self.name,
            "provider": self.provider,
            "server": {
                "name": (
                    urlparse(
                        self.base_url
                    ).hostname
                    or self.base_url
                ),
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
                uploaded
                * 8
                / up_seconds
                / 1_000_000,
                2,
            ),
            "latency_ms": latency_ms,
            "jitter_ms": jitter_ms,
            "download_bytes": downloaded,
            "upload_bytes": uploaded,
            "note": (
                "Medição executada pelo computador do atendente usando "
                "backend LibreSpeed compatível."
            ),
        }


class SpeedtestNetSpeedTestStrategy(SpeedTestStrategy):
    """Adapter do speedtest.net usando a biblioteca speedtest-cli."""

    name = "workstation_speedtest_net"
    provider = "speedtest.net"

    def run(self) -> dict[str, Any]:
        try:
            import speedtest
        except ImportError as error:
            raise RuntimeError(
                "Speedtest.net: dependência speedtest-cli não está instalada."
            ) from error

        tester = speedtest.Speedtest(
            secure=True
        )

        best = tester.get_best_server()

        download = tester.download()
        upload = tester.upload(
            pre_allocate=False
        )

        result = tester.results.dict()

        return {
            "success": True,
            "source": self.name,
            "provider": self.provider,
            "server": {
                "name": (
                    best.get("sponsor")
                    or best.get("name")
                    or best.get("host")
                    or "Speedtest.net"
                ),
                "url": best.get("url"),
                "host": best.get("host"),
                "id": best.get("id"),
                "country": best.get("country"),
            },
            "download_mbps": round(
                download / 1_000_000,
                2,
            ),
            "upload_mbps": round(
                upload / 1_000_000,
                2,
            ),
            "latency_ms": result.get(
                "ping"
            ),
            "jitter_ms": None,
            "download_bytes": None,
            "upload_bytes": None,
            "note": (
                "Medição executada pelo computador do atendente usando "
                "a rede de servidores do Speedtest.net."
            ),
        }


class SpeedTestProviderFactory:
    """Factory que impede aplicar protocolo Cloudflare em qualquer URL."""

    @staticmethod
    def detect(
        provider: str | None,
        base_url: str | None,
    ) -> str:
        normalized = str(
            provider
            or "auto"
        ).strip().lower()

        aliases = {
            "fast.com": "fast",
            "fastcom": "fast",
            "speedtest.net": "speedtest_net",
            "ookla": "speedtest_net",
            "cloudflare": "cloudflare",
            "librespeed": "librespeed",
            "custom": "auto",
            "auto_url": "auto",
        }

        normalized = aliases.get(
            normalized,
            normalized,
        )

        if normalized in {
            "native_auto",
            "cloudflare",
            "fast",
            "speedtest_net",
            "librespeed",
        }:
            return normalized

        host = _hostname(
            base_url
        )

        if not host:
            return "cloudflare"

        if (
            host == "fast.com"
            or host.endswith(
                ".fast.com"
            )
        ):
            return "fast"

        if (
            host == "speedtest.net"
            or host.endswith(
                ".speedtest.net"
            )
        ):
            return "speedtest_net"

        if (
            host == "speed.cloudflare.com"
            or host.endswith(
                ".cloudflare.com"
            )
        ):
            return "cloudflare"

        if (
            host == "minhaconexao.com.br"
            or host.endswith(
                ".minhaconexao.com.br"
            )
        ):
            raise RuntimeError(
                "Minha Conexão não expõe um backend público estável para "
                "automação direta. Escolha Cloudflare, FAST.com, Speedtest.net "
                "ou informe um servidor LibreSpeed próprio."
            )

        # Uma URL desconhecida pode ser um LibreSpeed self-hosted.
        return "librespeed"

    @classmethod
    def build(
        cls,
        provider: str | None,
        base_url: str | None,
    ) -> SpeedTestStrategy:
        resolved = cls.detect(
            provider,
            base_url,
        )

        if resolved == "cloudflare":
            return CloudflareSpeedTestStrategy(
                base_url=(
                    base_url
                    if _hostname(base_url).endswith(
                        "cloudflare.com"
                    )
                    else None
                )
            )

        if resolved == "fast":
            return FastComSpeedTestStrategy()

        if resolved == "speedtest_net":
            return SpeedtestNetSpeedTestStrategy()

        if resolved == "librespeed":
            return LibreSpeedSpeedTestStrategy(
                base_url=(
                    base_url
                    or ""
                )
            )

        raise ValueError(
            f"Provedor de Speed Test não suportado: {resolved}"
        )


# Compatibilidade com código/testes da versão 0.6.1.
HttpWorkstationSpeedTestStrategy = CloudflareSpeedTestStrategy


class SpeedTestService:
    """
    Chain of Responsibility.

    native_auto:
        ONT nativa -> Cloudflare (se permitido)

    provedor explícito:
        executa exatamente o provedor escolhido pelo atendente.
    """

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
        fallback_base_url: str | None = None,
        provider: str | None = None,
    ) -> dict[str, Any]:
        resolved = SpeedTestProviderFactory.detect(
            provider,
            fallback_base_url,
        )

        strategies: list[SpeedTestStrategy] = []

        if resolved == "native_auto":
            strategies.append(
                NativeOntSpeedTestStrategy(
                    self.zte,
                    server_url=server_url,
                )
            )

            if allow_fallback:
                strategies.append(
                    CloudflareSpeedTestStrategy()
                )

        else:
            strategies.append(
                SpeedTestProviderFactory.build(
                    resolved,
                    fallback_base_url,
                )
            )

        attempts = []

        for strategy in strategies:
            try:
                result = strategy.run()

                result["attempts"] = attempts
                result.setdefault(
                    "provider",
                    strategy.provider,
                )

                return result

            except Exception as error:
                attempts.append({
                    "strategy": strategy.name,
                    "provider": strategy.provider,
                    "error": str(error),
                })

        raise RuntimeError(
            "Nenhuma estratégia de Speed Test ficou disponível. "
            + " | ".join(
                (
                    f"{item['provider']}: {item['error']}"
                )
                for item in attempts
            )
        )

from __future__ import annotations

import math
import re
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Callable

from apps.zte_manager.services.automatic_diagnostic_service import (
    AutomaticDiagnosticService,
    DiagnosticThresholds,
)
from apps.zte_manager.services.speed_test_service import SpeedTestService


def _number(value: Any) -> float | None:
    if value in (None, "", "NULL"):
        return None

    match = re.search(
        r"-?\d+(?:[.,]\d+)?",
        str(value),
    )

    if not match:
        return None

    return float(
        match.group(0).replace(",", ".")
    )


def _rate_mbps(value: Any) -> float | None:
    """Normaliza Mbps/Kbps/bps e os valores numéricos usados pelos firmwares."""
    number = _number(
        value
    )

    if number is None:
        return None

    text = str(
        value
    ).lower()

    if "gb" in text:
        return number * 1000

    if "mb" in text:
        return number

    if "kb" in text:
        return number / 1000

    if "bps" in text:
        return number / 1_000_000

    # Em vários builds ZTE o RxRate/TxRate vem em Kbps sem unidade.
    if number >= 1000:
        return number / 1000

    return number


def _valid_ipish(value: Any) -> bool:
    text = str(
        value or ""
    ).strip()

    return text not in {
        "",
        "0.0.0.0",
        "::",
        "NULL",
        "None",
    }


@dataclass(frozen=True)
class SupportDiagnosticOptions:
    mode: str = "general"
    affected_mac: str | None = None
    affected_ip: str | None = None
    ping_host: str = "1.1.1.1"
    dns_host: str = "cloudflare.com"
    include_traceroute: bool = False
    include_speedtest: bool = True
    allow_speedtest_fallback: bool = True
    speedtest_provider: str = "native_auto"
    speedtest_base_url: str | None = None
    expected_download_mbps: float | None = None
    expected_upload_mbps: float | None = None


class DiagnosticCollector(ABC):
    """Collector Pattern: uma falha não cancela a bateria inteira."""

    name = "collector"

    @abstractmethod
    def collect(
        self,
        context: dict[str, Any],
    ) -> Any:
        raise NotImplementedError


class CallableCollector(DiagnosticCollector):
    def __init__(
        self,
        name: str,
        callback: Callable[
            [dict[str, Any]],
            Any
        ],
    ):
        self.name = name
        self.callback = callback

    def collect(
        self,
        context: dict[str, Any],
    ) -> Any:
        return self.callback(
            context
        )


class WifiEnvironmentCollector(DiagnosticCollector):
    name = "wifi_environment"

    def __init__(
        self,
        zte,
    ):
        self.zte = zte

    def collect(
        self,
        context: dict[str, Any],
    ) -> dict[str, Any]:
        radios = self.zte.channel_status()
        bands = {}

        for band in (
            "2.4GHz",
            "5GHz",
        ):
            scan_error = None

            try:
                scan = self.zte.wifi_neighbor_scan(
                    band
                )
            except Exception as error:
                scan_error = str(error)
                scan = {
                    "band": band,
                    "available": False,
                    "networks": [],
                }

            radio = next((
                item
                for item in radios
                if str(
                    item.get("banda")
                    or item.get("band")
                ).lower() == band.lower()
            ), {})

            try:
                channels = self.zte.available_channels(
                    band=band,
                    bandwidth=radio.get(
                        "largura"
                    ) or radio.get(
                        "bandwidth"
                    ),
                    country=(
                        radio.get("pais")
                        or radio.get("country")
                        or "BRI"
                    ),
                )
            except Exception:
                channels = []

            analysis = ChannelAnalyzer().analyze(
                band=band,
                radio=radio,
                neighbors=scan.get(
                    "networks",
                    [],
                ),
                available_channels=channels,
            )

            bands[band] = {
                **scan,
                "radio": radio,
                "analysis": analysis,
                "error": scan_error,
            }

        return {
            "bands": bands,
        }


class DnsHealthCollector(DiagnosticCollector):
    name = "dns_health"

    def __init__(
        self,
        zte,
        hostname: str,
    ):
        self.zte = zte
        self.hostname = hostname

    def collect(
        self,
        context: dict[str, Any],
    ) -> dict[str, Any]:
        static = self.zte.dns_status()
        wan = (
            context.get("sections", {})
            .get("wan")
            or []
        )

        effective = []

        def walk(value):
            if isinstance(
                value,
                dict,
            ):
                for key, item in value.items():
                    if (
                        "dns" in str(
                            key
                        ).lower()
                        and not isinstance(
                            item,
                            (dict, list),
                        )
                        and _valid_ipish(item)
                    ):
                        effective.append(
                            str(item).strip()
                        )

                    walk(item)

            elif isinstance(
                value,
                list,
            ):
                for item in value:
                    walk(item)

        walk(
            wan
        )

        static_values = [
            static.get("ipv4_1"),
            static.get("ipv4_2"),
            static.get("ipv6_1"),
            static.get("ipv6_2"),
        ]

        static_effective = [
            str(value).strip()
            for value in static_values
            if _valid_ipish(value)
        ]

        lookup = None
        lookup_error = None

        try:
            lookup = self.zte.nslookup(
                self.hostname
            )
        except Exception as error:
            lookup_error = str(error)

        return {
            "static": static,
            "static_effective": list(
                dict.fromkeys(
                    static_effective
                )
            ),
            "wan_effective": list(
                dict.fromkeys(
                    effective
                )
            ),
            "lookup": lookup,
            "lookup_error": lookup_error,
        }


class FirmwareHealthCollector(DiagnosticCollector):
    name = "firmware_health"

    def __init__(
        self,
        capability_service,
    ):
        self.capability_service = (
            capability_service
        )

    def collect(
        self,
        context: dict[str, Any],
    ) -> dict[str, Any]:
        result = {}

        for feature in (
            "sntp",
            "tr069",
        ):
            try:
                result[
                    feature
                ] = self.capability_service.read(
                    feature
                )
            except Exception as error:
                result[
                    feature
                ] = {
                    "available": False,
                    "error": str(error),
                }

        return result


class SpeedTestCollector(DiagnosticCollector):
    name = "speedtest"

    def __init__(
        self,
        zte,
        *,
        allow_fallback: bool,
        provider: str = "native_auto",
        fallback_base_url: str | None = None,
    ):
        self.zte = zte
        self.allow_fallback = (
            allow_fallback
        )
        self.provider = provider
        self.fallback_base_url = (
            fallback_base_url
        )

    def collect(
        self,
        context: dict[str, Any],
    ) -> dict[str, Any]:
        return SpeedTestService(
            self.zte
        ).run(
            allow_fallback=(
                self.allow_fallback
            ),
            fallback_base_url=(
                self.fallback_base_url
            ),
            provider=self.provider,
        )


class DiagnosticRule(ABC):
    """Specification/Rule Pattern para transformar telemetria em conclusão."""

    code = "rule"

    @abstractmethod
    def evaluate(
        self,
        context: dict[str, Any],
    ) -> list[dict[str, Any]]:
        raise NotImplementedError

    @staticmethod
    def finding(
        code: str,
        severity: str,
        message: str,
        *,
        recommendation: dict[str, Any] | None = None,
        **data,
    ) -> dict[str, Any]:
        item = {
            "code": code,
            "severity": severity,
            "message": message,
            "data": data,
        }

        if recommendation:
            item[
                "recommendation"
            ] = recommendation

        return item


class DnsHealthRule(DiagnosticRule):
    code = "dns_health"

    def evaluate(
        self,
        context: dict[str, Any],
    ) -> list[dict[str, Any]]:
        data = (
            context.get(
                "sections",
                {}
            ).get(
                "dns_health"
            )
            or {}
        )

        if not data:
            return []

        lookup = (
            data.get("lookup")
            or {}
        )

        resolved = bool(
            lookup.get("success")
            and _valid_ipish(
                lookup.get("addresses")
            )
        )

        static_dns = data.get(
            "static_effective",
            [],
        )

        wan_dns = data.get(
            "wan_effective",
            [],
        )

        if resolved:
            if not static_dns:
                origin = (
                    "DNS recebido pela WAN/PPPoE"
                    if wan_dns
                    else "DNS resolvido pelo caminho efetivo da ONT"
                )

                return [
                    self.finding(
                        self.code,
                        "ok",
                        (
                            "DNS estático vazio/0.0.0.0, mas a resolução está "
                            f"funcionando ({origin})."
                        ),
                        addresses=lookup.get(
                            "addresses"
                        ),
                        wan_dns=wan_dns,
                    )
                ]

            return [
                self.finding(
                    self.code,
                    "ok",
                    "DNS configurado e resolução de nomes concluída com sucesso.",
                    addresses=lookup.get(
                        "addresses"
                    ),
                    static_dns=static_dns,
                    wan_dns=wan_dns,
                )
            ]

        if (
            static_dns
            or wan_dns
        ):
            return [
                self.finding(
                    self.code,
                    "warning",
                    "Há servidor DNS configurado/recebido, mas o DNS Lookup da ONT falhou.",
                    static_dns=static_dns,
                    wan_dns=wan_dns,
                    error=data.get(
                        "lookup_error"
                    ),
                )
            ]

        if data.get(
            "lookup"
        ) is None:
            return [
                self.finding(
                    self.code,
                    "info",
                    (
                        "O firmware não permitiu confirmar DNS via NsLookup e "
                        "não expôs servidores efetivos na WAN; resultado inconclusivo."
                    ),
                    error=data.get(
                        "lookup_error"
                    ),
                )
            ]

        return [
            self.finding(
                self.code,
                "critical",
                "Nenhum DNS efetivo foi identificado e a resolução de nomes falhou.",
                error=data.get(
                    "lookup_error"
                ),
            )
        ]


class ClientPathRule(DiagnosticRule):
    code = "client_path"

    def __init__(
        self,
        options: SupportDiagnosticOptions,
    ):
        self.options = options

    def evaluate(
        self,
        context: dict[str, Any],
    ) -> list[dict[str, Any]]:
        sections = context.get(
            "sections",
            {}
        )

        wifi = sections.get(
            "wifi_clients"
        ) or []

        lan = sections.get(
            "lan_clients"
        ) or []

        selected = self._select(
            wifi,
            lan,
        )

        if not selected:
            if self.options.mode == "low_speed":
                return [
                    self.finding(
                        self.code,
                        "info",
                        "Selecione o dispositivo afetado para localizar o gargalo de banda com mais precisão.",
                    )
                ]

            return []

        kind, client = selected

        context[
            "affected_client"
        ] = {
            "kind": kind,
            **client,
        }

        if kind == "lan":
            interface = str(
                client.get("interface")
                or ""
            )

            port_number = None
            match = re.search(
                r"(\d+)$",
                interface,
            )

            if match:
                port_number = int(
                    match.group(1)
                )

                if interface.lower().startswith(
                    "eth"
                ):
                    port_number += 1

            port = next((
                item
                for item in (
                    sections.get(
                        "lan_ports"
                    )
                    or []
                )
                if (
                    port_number is not None
                    and int(
                        item.get("port")
                        or -1
                    ) == port_number
                )
            ), None)

            speed = _rate_mbps(
                (
                    port
                    or {}
                ).get(
                    "speed"
                )
            )

            if (
                speed is not None
                and speed <= 100
            ):
                return [
                    self.finding(
                        "affected_lan_negotiation",
                        "warning",
                        (
                            f"Dispositivo afetado está na LAN {port_number} "
                            f"negociando {speed:.0f} Mbps."
                        ),
                        client=client,
                        port=port,
                    )
                ]

            return [
                self.finding(
                    self.code,
                    "ok",
                    (
                        f"Dispositivo afetado identificado como cliente Ethernet"
                        + (
                            f" na LAN {port_number}"
                            if port_number is not None
                            else ""
                        )
                        + "."
                    ),
                    client=client,
                    port=port,
                )
            ]

        band = self._band(
            client
        )

        rssi = _number(
            client.get("rssi")
        )

        rates = [
            _rate_mbps(
                client.get("rx_rate")
            ),
            _rate_mbps(
                client.get("tx_rate")
            ),
        ]

        rates = [
            value
            for value in rates
            if value is not None
        ]

        findings = []

        if (
            self.options.mode == "low_speed"
            and band == "2.4GHz"
        ):
            findings.append(
                self.finding(
                    "client_on_24ghz",
                    "warning",
                    "O dispositivo afetado está conectado em 2.4 GHz; a banda pode limitar testes de alta velocidade.",
                    recommendation={
                        "title": "Verificar 5 GHz / Band Steering",
                        "action": {
                            "type": "inspect_band_steering",
                        },
                        "safe": True,
                    },
                    client=client,
                    band=band,
                )
            )

        if (
            self.options.mode == "low_speed"
            and rates
            and max(rates) <= 120
        ):
            findings.append(
                self.finding(
                    "wifi_phy_rate",
                    "warning",
                    f"Taxa de enlace Wi-Fi do dispositivo está em torno de {max(rates):.0f} Mbps.",
                    client=client,
                    band=band,
                    phy_rate_mbps=max(
                        rates
                    ),
                )
            )

        if (
            rssi is not None
            and rssi <= -70
        ):
            findings.append(
                self.finding(
                    "affected_client_rssi",
                    (
                        "critical"
                        if rssi <= -80
                        else "warning"
                    ),
                    f"Dispositivo afetado com RSSI {rssi:.0f} dBm.",
                    client=client,
                    band=band,
                )
            )

        if not findings:
            findings.append(
                self.finding(
                    self.code,
                    "ok",
                    (
                        f"Dispositivo afetado identificado no Wi-Fi {band or 'sem banda identificada'} "
                        "sem limitação óbvia nos critérios atuais."
                    ),
                    client=client,
                    band=band,
                )
            )

        return findings

    def _select(
        self,
        wifi,
        lan,
    ):
        wanted_mac = (
            self.options.affected_mac
            or ""
        ).lower()

        wanted_ip = (
            self.options.affected_ip
            or ""
        ).strip()

        for kind, clients in (
            ("wifi", wifi),
            ("lan", lan),
        ):
            for client in clients:
                if (
                    wanted_mac
                    and str(
                        client.get("mac")
                        or ""
                    ).lower() == wanted_mac
                ):
                    return kind, client

                if (
                    wanted_ip
                    and str(
                        client.get("ip")
                        or ""
                    ).strip() == wanted_ip
                ):
                    return kind, client

        if (
            self.options.mode == "low_speed"
            and len(wifi) + len(lan) == 1
        ):
            if wifi:
                return "wifi", wifi[0]

            return "lan", lan[0]

        return None

    @staticmethod
    def _band(
        client,
    ) -> str | None:
        ap = str(
            client.get("ap")
            or client.get("interface")
            or ""
        ).upper()

        if (
            "AP1" in ap
            or "RD1" in ap
            or "2.4" in ap
        ):
            return "2.4GHz"

        if (
            "AP5" in ap
            or "RD2" in ap
            or "5G" in ap
        ):
            return "5GHz"

        mode = str(
            client.get("modo")
            or ""
        ).lower()

        if (
            "ac" in mode
            or "5g" in mode
        ):
            return "5GHz"

        return None


class BandSteeringHealthRule(DiagnosticRule):
    code = "band_steering_health"

    def __init__(
        self,
        options: SupportDiagnosticOptions,
    ):
        self.options = options

    def evaluate(
        self,
        context: dict[str, Any],
    ) -> list[dict[str, Any]]:
        if self.options.mode != "low_speed":
            return []

        client = context.get(
            "affected_client"
        ) or {}

        if client.get(
            "kind"
        ) != "wifi":
            return []

        band = ClientPathRule._band(
            client
        )

        if band != "2.4GHz":
            return []

        steering = (
            context.get(
                "sections",
                {}
            ).get(
                "band_steering"
            )
            or {}
        )

        if not steering.get(
            "available"
        ):
            return [
                self.finding(
                    self.code,
                    "info",
                    "Band Steering não ficou disponível para validar este cliente.",
                )
            ]

        if steering.get(
            "enabled"
        ):
            return [
                self.finding(
                    self.code,
                    "warning",
                    (
                        "Band Steering está ativo, mas o dispositivo afetado permaneceu "
                        "em 2.4 GHz; alcance, compatibilidade ou thresholds podem estar impedindo a migração."
                    ),
                    parameters=steering.get(
                        "parameters"
                    ),
                )
            ]

        return [
            self.finding(
                self.code,
                "info",
                "Band Steering está desativado e o dispositivo afetado está em 2.4 GHz.",
                recommendation={
                    "title": "Revisar Band Steering",
                    "action": {
                        "type": "inspect_band_steering",
                    },
                    "safe": True,
                },
            )
        ]


class LanErrorsRule(DiagnosticRule):
    code = "lan_errors"

    def evaluate(
        self,
        context: dict[str, Any],
    ) -> list[dict[str, Any]]:
        findings = []

        for port in (
            context.get(
                "sections",
                {}
            ).get(
                "lan_ports"
            )
            or []
        ):
            counters = {
                "rx_errors": _number(
                    port.get("rx_errors")
                ) or 0,
                "tx_errors": _number(
                    port.get("tx_errors")
                ) or 0,
                "rx_discard": _number(
                    port.get("rx_discard")
                ) or 0,
                "tx_discard": _number(
                    port.get("tx_discard")
                ) or 0,
            }

            total = sum(
                counters.values()
            )

            if total <= 0:
                continue

            findings.append(
                self.finding(
                    self.code,
                    "warning",
                    (
                        f"LAN {port.get('port', '?')} possui {int(total)} "
                        "erro(s)/descarte(s) nos contadores da interface."
                    ),
                    port=port,
                    counters=counters,
                )
            )

        return findings


class DeviceResourcesRule(DiagnosticRule):
    code = "device_resources"

    def evaluate(
        self,
        context: dict[str, Any],
    ) -> list[dict[str, Any]]:
        device = (
            context.get(
                "sections",
                {}
            ).get(
                "device"
            )
            or {}
        )

        findings = []

        memory = _number(
            device.get(
                "memoria_percent"
            )
        )

        if (
            memory is not None
            and memory >= 90
        ):
            findings.append(
                self.finding(
                    "device_memory",
                    "warning",
                    f"Memória da ONT em {memory:.0f}%.",
                    memory_percent=memory,
                )
            )

        cpu_values = []

        for value in (
            device.get("cpu")
            or {}
        ).values():
            parsed = _number(
                value
            )

            if parsed is not None:
                cpu_values.append(
                    parsed
                )

        if cpu_values:
            average = sum(
                cpu_values
            ) / len(
                cpu_values
            )

            if average >= 90:
                findings.append(
                    self.finding(
                        "device_cpu",
                        "warning",
                        f"CPU média da ONT em {average:.0f}%.",
                        cpu_percent=average,
                    )
                )

        return findings


class ChannelRule(DiagnosticRule):
    code = "wifi_channel"

    def evaluate(
        self,
        context: dict[str, Any],
    ) -> list[dict[str, Any]]:
        environment = (
            context.get(
                "sections",
                {}
            ).get(
                "wifi_environment"
            )
            or {}
        )

        findings = []

        for band, data in (
            environment.get(
                "bands",
                {}
            ).items()
        ):
            analysis = data.get(
                "analysis"
            ) or {}

            recommendation = (
                analysis.get(
                    "recommendation"
                )
                or {}
            )

            action = recommendation.get(
                "action"
            )

            if (
                analysis.get("auto_channel")
                and (
                    action
                    or {}
                ).get("type") == "wifi_auto_channel"
            ):
                # Não gravamos uma mutação sem efeito só porque o rádio já
                # está em Auto. O histórico deve representar mudanças reais.
                recommendation = {}
                action = None

            if (
                not data.get("available")
                or not data.get("networks")
            ):
                findings.append(
                    self.finding(
                        f"wifi_environment_{band}",
                        "info",
                        (
                            f"Scan de vizinhança {band} indisponível/sem resultados; "
                            + (
                                "o rádio já está em Auto."
                                if analysis.get("auto_channel")
                                else "canal automático é a opção mais segura."
                            )
                        ),
                        recommendation=(
                            None
                            if analysis.get("auto_channel")
                            else {
                                "title": f"Usar Auto em {band}",
                                "action": {
                                    "type": "wifi_auto_channel",
                                    "band": band,
                                },
                                "safe": True,
                            }
                        ),
                    )
                )
                continue

            current = analysis.get(
                "current_channel"
            )

            best = analysis.get(
                "best_channel"
            )

            score = analysis.get(
                "current_score"
            )

            if action:
                findings.append(
                    self.finding(
                        f"wifi_channel_{band}",
                        "warning",
                        recommendation.get(
                            "message"
                        )
                        or (
                            f"Canal {current} em {band} pode ser otimizado para {best}."
                        ),
                        recommendation={
                            "title": recommendation.get(
                                "title"
                            ),
                            "action": action,
                            "safe": True,
                        },
                        analysis=analysis,
                    )
                )
            else:
                findings.append(
                    self.finding(
                        f"wifi_channel_{band}",
                        "ok",
                        (
                            f"Canal {current or 'Auto'} em {band} sem ganho claro de troca "
                            f"(score {score:.1f})."
                            if isinstance(
                                score,
                                (int, float),
                            )
                            else f"Canal de {band} sem indicação clara de mudança."
                        ),
                        analysis=analysis,
                    )
                )

        return findings


class SpeedRule(DiagnosticRule):
    code = "speedtest"

    def __init__(
        self,
        options: SupportDiagnosticOptions,
    ):
        self.options = options

    def evaluate(
        self,
        context: dict[str, Any],
    ) -> list[dict[str, Any]]:
        data = (
            context.get(
                "sections",
                {}
            ).get(
                "speedtest"
            )
            or {}
        )

        if not data:
            return []

        down = _number(
            data.get("download_mbps")
        )

        up = _number(
            data.get("upload_mbps")
        )

        expected = (
            self.options.expected_download_mbps
        )

        if (
            expected
            and down is not None
            and down < expected * 0.7
        ):
            return [
                self.finding(
                    self.code,
                    "warning",
                    f"Download medido em {down:.1f} Mbps para referência esperada de {expected:.0f} Mbps.",
                    speedtest=data,
                )
            ]

        return [
            self.finding(
                self.code,
                "ok",
                (
                    f"Speed Test: {down:.1f} Mbps download / {up:.1f} Mbps upload."
                    if (
                        down is not None
                        and up is not None
                    )
                    else "Speed Test concluído."
                ),
                speedtest=data,
            )
        ]


class ChannelAnalyzer:
    """
    Strategy de seleção de canal.

    RSSI forte pesa mais que quantidade bruta de SSIDs. Em 2.4 GHz também
    aplicamos peso aos canais sobrepostos; em 5 GHz o peso principal fica no
    mesmo canal. Se o cenário estiver ruim/insuficiente, a recomendação é Auto.
    """

    def analyze(
        self,
        *,
        band: str,
        radio: dict[str, Any],
        neighbors: list[dict[str, Any]],
        available_channels: Any,
    ) -> dict[str, Any]:
        candidates = self._candidates(
            band,
            available_channels,
        )

        current = _number(
            radio.get("canal")
            if "canal" in radio
            else radio.get("channel")
        )

        auto = bool(
            radio.get("canal_automatico")
            if "canal_automatico" in radio
            else radio.get("auto_channel")
        )

        scores = {
            channel: round(
                self._score(
                    band,
                    channel,
                    neighbors,
                ),
                2,
            )
            for channel in candidates
        }

        best = min(
            scores,
            key=scores.get,
        ) if scores else None

        current_score = (
            scores.get(
                int(current)
            )
            if current is not None
            else None
        )

        best_score = (
            scores.get(best)
            if best is not None
            else None
        )

        recommendation = {}

        if not neighbors:
            recommendation = {
                "title": f"Canal automático em {band}",
                "message": (
                    f"Sem amostra suficiente de redes vizinhas em {band}; "
                    "prefira Auto em vez de escolher um canal no escuro."
                ),
                "action": {
                    "type": "wifi_auto_channel",
                    "band": band,
                },
                "confidence": "low",
            }

        elif (
            best_score is not None
            and best_score >= 80
        ):
            recommendation = {
                "title": f"Usar Auto em {band}",
                "message": (
                    f"Todos os canais candidatos em {band} estão congestionados; "
                    "o firmware pode reagir melhor em Auto."
                ),
                "action": {
                    "type": "wifi_auto_channel",
                    "band": band,
                },
                "confidence": "medium",
            }

        elif (
            not auto
            and current_score is not None
            and best is not None
            and int(current or -1) != best
            and (
                current_score
                - float(
                    best_score or 0
                )
            ) >= 15
        ):
            recommendation = {
                "title": f"Mudar {band} para canal {best}",
                "message": (
                    f"Canal {int(current)} em {band} tem score {current_score:.1f}; "
                    f"canal {best} caiu para {best_score:.1f}."
                ),
                "action": {
                    "type": "wifi_channel",
                    "band": band,
                    "channel": best,
                },
                "confidence": "high",
            }

        return {
            "band": band,
            "current_channel": (
                int(current)
                if current is not None
                else None
            ),
            "auto_channel": auto,
            "current_score": current_score,
            "best_channel": best,
            "best_score": best_score,
            "scores": scores,
            "neighbor_count": len(
                neighbors
            ),
            "recommendation": recommendation,
        }

    @staticmethod
    def _candidates(
        band: str,
        available_channels: Any,
    ) -> list[int]:
        raw = []

        if isinstance(
            available_channels,
            dict,
        ):
            for key in (
                "channels",
                "available_channels",
                "values",
                "canais",
            ):
                value = available_channels.get(
                    key
                )

                if isinstance(
                    value,
                    list,
                ):
                    raw.extend(
                        value
                    )

        elif isinstance(
            available_channels,
            list,
        ):
            raw = available_channels

        parsed = []

        for item in raw:
            if isinstance(
                item,
                dict,
            ):
                item = (
                    item.get("channel")
                    or item.get("value")
                    or item.get("id")
                )

            number = _number(
                item
            )

            if number is not None:
                parsed.append(
                    int(number)
                )

        is_24 = "2.4" in str(
            band
        )

        defaults = (
            [1, 6, 11]
            if is_24
            else [
                36,
                40,
                44,
                48,
                149,
                153,
                157,
                161,
            ]
        )

        if is_24:
            safe = [
                channel
                for channel in parsed
                if channel in {
                    1,
                    6,
                    11,
                }
            ]

            return (
                sorted(
                    set(safe)
                )
                or defaults
            )

        return (
            sorted(
                set(parsed)
            )
            or defaults
        )

    @staticmethod
    def _signal_weight(
        value: Any,
    ) -> float:
        signal = _number(
            value
        )

        if signal is None:
            return 12.0

        if signal <= 0:
            return max(
                1.0,
                min(
                    100.0,
                    100.0 + signal,
                ),
            )

        return max(
            1.0,
            min(
                100.0,
                signal,
            ),
        )

    def _score(
        self,
        band: str,
        candidate: int,
        neighbors: list[dict[str, Any]],
    ) -> float:
        is_24 = "2.4" in str(
            band
        )

        score = 0.0

        for network in neighbors:
            channel = _number(
                network.get("channel")
            )

            if channel is None:
                continue

            distance = abs(
                candidate
                - int(channel)
            )

            if is_24:
                overlap = max(
                    0.0,
                    1.0 - distance / 5.0,
                )
            else:
                overlap = (
                    1.0
                    if distance == 0
                    else 0.18
                    if distance <= 4
                    else 0.0
                )

            strength = self._signal_weight(
                network.get("signal")
            )

            score += (
                strength
                * overlap
            )

            noise = _number(
                network.get("noise")
            )

            if (
                noise is not None
                and noise > -75
            ):
                score += (
                    min(
                        20.0,
                        noise + 95.0,
                    )
                    * overlap
                )

        return score


class SupportDiagnosticService:
    """
    Orquestrador do diagnóstico de atendimento.

    Composite:
      AutomaticDiagnosticService -> base
      Collectors -> extensões opcionais
      Rules -> conclusões/recomendações

    A classe não grava configuração. Remediação fica no ZTEService para
    continuar passando pelo audit trail central.
    """

    def __init__(
        self,
        zte,
        capability_service,
    ):
        self.zte = zte
        self.capability_service = (
            capability_service
        )

    def run(
        self,
        options: SupportDiagnosticOptions,
        thresholds: DiagnosticThresholds,
    ) -> dict[str, Any]:
        base = AutomaticDiagnosticService(
            self.zte
        ).run(
            ping_host=options.ping_host,
            include_traceroute=(
                options.include_traceroute
            ),
            thresholds=thresholds,
        )

        context = {
            "mode": options.mode,
            "status": base.get(
                "status"
            ),
            "summary": base.get(
                "summary"
            ),
            "findings": list(
                base.get(
                    "findings",
                    []
                )
            ),
            "sections": dict(
                base.get(
                    "sections",
                    {}
                )
            ),
            "errors": dict(
                base.get(
                    "errors",
                    {}
                )
            ),
            "thresholds": base.get(
                "thresholds",
                {},
            ),
        }

        collectors: list[DiagnosticCollector] = [
            CallableCollector(
                "wifi_radios",
                lambda _: self.zte.channel_status(),
            ),
            CallableCollector(
                "band_steering",
                lambda _: self.zte.band_steering_status(),
            ),
            WifiEnvironmentCollector(
                self.zte
            ),
            DnsHealthCollector(
                self.zte,
                options.dns_host,
            ),
            CallableCollector(
                "dhcp",
                lambda _: self.zte.dhcp_status(),
            ),
            FirmwareHealthCollector(
                self.capability_service
            ),
        ]

        if options.include_speedtest:
            collectors.append(
                SpeedTestCollector(
                    self.zte,
                    allow_fallback=(
                        options.allow_speedtest_fallback
                    ),
                    provider=(
                        options.speedtest_provider
                    ),
                    fallback_base_url=(
                        options.speedtest_base_url
                    ),
                )
            )

        for collector in collectors:
            try:
                context[
                    "sections"
                ][collector.name] = (
                    collector.collect(
                        context
                    )
                )
            except Exception as error:
                context[
                    "errors"
                ][collector.name] = str(
                    error
                )

        rules: list[DiagnosticRule] = [
            DnsHealthRule(),
            ClientPathRule(
                options
            ),
            BandSteeringHealthRule(
                options
            ),
            LanErrorsRule(),
            DeviceResourcesRule(),
            ChannelRule(),
            SpeedRule(
                options
            ),
        ]

        for rule in rules:
            try:
                context[
                    "findings"
                ].extend(
                    rule.evaluate(
                        context
                    )
                )
            except Exception as error:
                context[
                    "errors"
                ][f"rule:{rule.code}"] = str(
                    error
                )

        context[
            "recommendations"
        ] = self._recommendations(
            context[
                "findings"
            ]
        )

        context[
            "status"
        ] = self._overall_status(
            context[
                "findings"
            ]
        )

        context[
            "summary"
        ] = self._summary(
            context
        )

        return context

    @staticmethod
    def _recommendations(
        findings,
    ):
        result = []

        for finding in findings:
            recommendation = finding.get(
                "recommendation"
            )

            if not recommendation:
                continue

            result.append({
                "source": finding.get(
                    "code"
                ),
                **recommendation,
            })

        return result

    @staticmethod
    def _overall_status(
        findings,
    ) -> str:
        levels = {
            item.get("severity")
            for item in findings
        }

        if "critical" in levels:
            return "critical"

        if "warning" in levels:
            return "warning"

        return "ok"

    @staticmethod
    def _summary(
        context,
    ) -> str:
        problems = [
            item.get("message")
            for item in context.get(
                "findings",
                []
            )
            if item.get("severity") in {
                "warning",
                "critical",
            }
        ]

        if problems:
            return " ".join(
                problems[:5]
            )

        return (
            "Diagnóstico concluído sem alertas nos critérios disponíveis."
        )

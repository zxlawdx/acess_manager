from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Callable


@dataclass(frozen=True)
class DiagnosticThresholds:
    optical_rx_min: float = -27.0
    optical_rx_max: float = -8.0
    wifi_rssi_warning: int = -70
    wifi_rssi_bad: int = -80
    expected_lan_mbps: int = 1000
    ping_warning_ms: float = 80.0


class AutomaticDiagnosticService:
    """
    Composite de diagnóstico.

    Cada coleta é isolada: um menu bloqueado no F670L não invalida WAN/PON ou
    outras leituras. As conclusões usam thresholds enviados pela empresa/UI.
    """

    def __init__(self, zte):
        self.zte = zte

    def run(
        self,
        *,
        ping_host: str = "8.8.8.8",
        include_traceroute: bool = False,
        thresholds: DiagnosticThresholds | None = None,
    ) -> dict[str, Any]:
        limits = thresholds or DiagnosticThresholds()
        sections: dict[str, Any] = {}
        errors: dict[str, str] = {}

        collectors: list[tuple[str, Callable[[], Any]]] = [
            ("device", self.zte.device_status),
            ("optical", self.zte.optical_status),
            ("wan", self.zte.wan_status),
            (
                "pppoe",
                lambda: self.zte.pppoe_status(
                    reveal_password=False
                ),
            ),
            ("lan_ports", self.zte.lan_ports),
            ("wifi_clients", self.zte.wifi_clients),
            ("lan_clients", self.zte.lan_clients),
            (
                "ping",
                lambda: self.zte.ping({
                    "host": ping_host,
                    "interface": "",
                    "ip_version": "IPv4",
                }),
            ),
        ]

        if include_traceroute:
            collectors.append((
                "traceroute",
                lambda: self.zte.traceroute({
                    "host": ping_host,
                    "interface": "",
                    "max_hops": 30,
                    "timeout": 5000,
                    "protocol": "ICMP",
                    "ip_version": "IPv4",
                }),
            ))

        for name, collector in collectors:
            try:
                sections[name] = collector()
            except Exception as error:
                errors[name] = str(error)

        findings = self._analyze(
            sections,
            limits,
        )

        severity = self._overall_status(
            findings
        )

        return {
            "status": severity,
            "summary": self._summary(
                findings,
                errors,
            ),
            "findings": findings,
            "sections": sections,
            "errors": errors,
            "thresholds": {
                "optical_rx_min": limits.optical_rx_min,
                "optical_rx_max": limits.optical_rx_max,
                "wifi_rssi_warning": limits.wifi_rssi_warning,
                "wifi_rssi_bad": limits.wifi_rssi_bad,
                "expected_lan_mbps": limits.expected_lan_mbps,
                "ping_warning_ms": limits.ping_warning_ms,
            },
        }

    def _analyze(
        self,
        sections: dict[str, Any],
        limits: DiagnosticThresholds,
    ) -> list[dict[str, Any]]:
        findings: list[dict[str, Any]] = []

        optical = sections.get("optical") or {}
        registration = str(
            optical.get("registration_status") or ""
        ).strip()

        if registration:
            registered = registration.lower() in {
                "1",
                "registered",
                "registration success",
                "o5",
                "up",
                "online",
            }

            findings.append(
                self._finding(
                    "pon_registration",
                    "ok" if registered else "critical",
                    (
                        f"GPON registrado ({registration})."
                        if registered
                        else f"GPON não registrado ({registration})."
                    ),
                    registration_status=registration,
                )
            )

        rx = self._float(
            optical.get("rx_power_dbm")
        )

        if rx is not None:
            in_range = (
                limits.optical_rx_min
                <= rx
                <= limits.optical_rx_max
            )

            findings.append(
                self._finding(
                    "optical_rx",
                    "ok" if in_range else "warning",
                    (
                        f"Potência óptica RX {rx:.2f} dBm dentro do intervalo configurado."
                        if in_range
                        else (
                            f"Potência óptica RX {rx:.2f} dBm fora do intervalo "
                            f"{limits.optical_rx_min:.1f} a {limits.optical_rx_max:.1f} dBm."
                        )
                    ),
                    rx_dbm=rx,
                )
            )

        wan = sections.get("wan") or []
        if isinstance(wan, dict):
            wan = [wan]

        connected = [
            item
            for item in wan
            if self._is_up(item.get("status"))
        ]

        findings.append(
            self._finding(
                "wan_status",
                "ok" if connected else "critical",
                (
                    f"{len(connected)} interface(s) WAN conectada(s)."
                    if connected
                    else "Nenhuma interface WAN foi encontrada como conectada."
                ),
            )
        )

        for port in sections.get("lan_ports") or []:
            if not self._is_up(
                port.get("status")
                or port.get("link")
                or port.get("LinkStatus")
            ):
                continue

            speed = self._speed_mbps(
                port.get("speed")
                or port.get("velocidade")
                or port.get("Speed")
                or port.get("Rate")
            )

            if speed is None:
                continue

            if (
                limits.expected_lan_mbps >= 1000
                and speed <= 100
            ):
                findings.append(
                    self._finding(
                        "lan_negotiation",
                        "warning",
                        (
                            f"Porta {port.get('port') or port.get('nome') or port.get('id') or '?'} "
                            f"negociando {speed} Mbps."
                        ),
                        port=port,
                    )
                )

        weak_clients = []

        for client in sections.get("wifi_clients") or []:
            rssi = self._float(
                client.get("rssi")
            )

            if rssi is None:
                continue

            if rssi <= limits.wifi_rssi_bad:
                level = "critical"
            elif rssi <= limits.wifi_rssi_warning:
                level = "warning"
            else:
                continue

            weak_clients.append({
                "hostname": client.get("hostname"),
                "mac": client.get("mac"),
                "ssid": client.get("ssid"),
                "rssi": rssi,
                "severity": level,
            })

        if weak_clients:
            worst = (
                "critical"
                if any(
                    item["severity"] == "critical"
                    for item in weak_clients
                )
                else "warning"
            )

            findings.append(
                self._finding(
                    "wifi_signal",
                    worst,
                    f"{len(weak_clients)} cliente(s) Wi-Fi com sinal abaixo do limite.",
                    clients=weak_clients,
                )
            )
        elif "wifi_clients" in sections:
            findings.append(
                self._finding(
                    "wifi_signal",
                    "ok",
                    "Clientes Wi-Fi lidos sem RSSI abaixo do limite configurado.",
                )
            )

        ping = sections.get("ping") or {}
        average = self._float(
            ping.get("medio_ms")
        )
        failures = self._float(
            ping.get("falha")
        )

        if ping:
            if failures and failures > 0:
                level = "warning"
                message = f"Ping apresentou {int(failures)} falha(s)."
            elif (
                average is not None
                and average > limits.ping_warning_ms
            ):
                level = "warning"
                message = f"Latência média elevada: {average:.1f} ms."
            else:
                level = "ok"
                message = (
                    f"Ping normal: {average:.1f} ms de média."
                    if average is not None
                    else "Ping concluído."
                )

            findings.append(
                self._finding(
                    "internet_ping",
                    level,
                    message,
                    ping=ping,
                )
            )

        return findings

    @staticmethod
    def _finding(
        code: str,
        severity: str,
        message: str,
        **data,
    ) -> dict[str, Any]:
        return {
            "code": code,
            "severity": severity,
            "message": message,
            "data": data,
        }

    @staticmethod
    def _overall_status(
        findings: list[dict[str, Any]],
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
        findings: list[dict[str, Any]],
        errors: dict[str, str],
    ) -> str:
        messages = [
            item["message"]
            for item in findings
            if item.get("severity") != "ok"
        ]

        if not messages:
            messages = [
                "Não foram encontrados alertas com os limites configurados."
            ]

        if errors:
            messages.append(
                f"{len(errors)} coleta(s) não ficaram disponíveis neste firmware/login."
            )

        return " ".join(messages)

    @staticmethod
    def _is_up(value: Any) -> bool:
        return str(value or "").strip().lower() in {
            "1",
            "up",
            "online",
            "connected",
            "linkup",
        }

    @staticmethod
    def _float(value: Any) -> float | None:
        if value in (None, ""):
            return None

        try:
            return float(
                str(value)
                .replace("dBm", "")
                .replace("ms", "")
                .strip()
            )
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _speed_mbps(
        value: Any,
    ) -> int | None:
        if value in (None, ""):
            return None

        text = str(
            value
        ).strip().lower()

        match = re.search(
            r"-?\d+(?:[.,]\d+)?",
            text,
        )

        if not match:
            return None

        number = float(
            match.group(0).replace(",", ".")
        )

        if "gb" in text:
            number *= 1000

        return int(number)

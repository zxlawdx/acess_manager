from __future__ import annotations

import re
import time
from datetime import datetime, timezone
from threading import Event, Lock, Thread
from typing import Any

from apps.zte_manager.repositories.management_repository import (
    ManagementRepository,
    management_repository,
)


def _number(value):
    if value in (
        None,
        "",
    ):
        return None

    match = re.search(
        r"-?\d+(?:[.,]\d+)?",
        str(value),
    )

    if not match:
        return None

    return float(
        match.group(0).replace(
            ",",
            ".",
        )
    )


def _wan_online(wan) -> bool:
    if not isinstance(
        wan,
        list,
    ):
        return False

    for item in wan:
        text = " ".join(
            str(value)
            for value in item.values()
            if not isinstance(
                value,
                (dict, list),
            )
        ).lower()

        if any(
            marker in text
            for marker in (
                "connected",
                "up",
                "online",
            )
        ) and not any(
            marker in text
            for marker in (
                "disconnected",
                "down",
            )
        ):
            return True

    return False


class MonitoringService:
    """Monitor temporal da sessão ThinkLua atual."""

    def __init__(
        self,
        repository: ManagementRepository = management_repository,
    ):
        self.repository = repository
        self._workers: dict[
            int,
            tuple[Thread, Event]
        ] = {}
        self._lock = Lock()

    def start_current(
        self,
        zte_service,
        *,
        device_id: int | None = None,
        duration_seconds: int = 300,
        interval_seconds: int = 10,
        ping_host: str = "1.1.1.1",
    ) -> dict[str, Any]:
        if not zte_service.connected:
            raise RuntimeError(
                "Conecte a uma ONT antes de iniciar o monitor."
            )

        duration_seconds = max(
            30,
            min(
                int(duration_seconds),
                900,
            ),
        )

        interval_seconds = max(
            5,
            min(
                int(interval_seconds),
                60,
            ),
        )

        monitor = self.repository.start_monitor(
            device_id,
            interval_seconds=interval_seconds,
            duration_seconds=duration_seconds,
        )

        stop_event = Event()

        worker = Thread(
            target=self._run,
            args=(
                monitor["id"],
                zte_service,
                duration_seconds,
                interval_seconds,
                ping_host,
                stop_event,
            ),
            daemon=True,
            name=f"cpe-monitor-{monitor['id']}",
        )

        with self._lock:
            self._workers[
                monitor["id"]
            ] = (
                worker,
                stop_event,
            )

        worker.start()

        return monitor

    def stop(
        self,
        run_id: int,
    ) -> dict[str, Any]:
        with self._lock:
            worker = self._workers.get(
                run_id
            )

        if worker:
            worker[
                1
            ].set()

        self.repository.finish_monitor(
            run_id,
            "stopped",
        )

        result = self.repository.get_monitor(
            run_id
        )

        if result is None:
            raise ValueError(
                "Monitor não encontrado."
            )

        return self._decorate(
            result
        )

    def status(
        self,
        run_id: int,
    ) -> dict[str, Any]:
        result = self.repository.get_monitor(
            run_id
        )

        if result is None:
            raise ValueError(
                "Monitor não encontrado."
            )

        return self._decorate(
            result
        )

    def _run(
        self,
        run_id,
        zte_service,
        duration,
        interval,
        ping_host,
        stop_event,
    ):
        deadline = (
            time.monotonic()
            + duration
        )

        final_status = "completed"

        try:
            while (
                time.monotonic()
                < deadline
                and not stop_event.is_set()
            ):
                sample = self._sample(
                    zte_service,
                    ping_host,
                )

                self.repository.add_monitor_sample(
                    run_id,
                    sample,
                )

                remaining = max(
                    0,
                    deadline
                    - time.monotonic()
                )

                stop_event.wait(
                    min(
                        interval,
                        remaining,
                    )
                )

            if stop_event.is_set():
                final_status = "stopped"

        except Exception as error:
            self.repository.add_monitor_sample(
                run_id,
                {
                    "captured_at": datetime.now(
                        timezone.utc
                    ).isoformat(),
                    "error": str(error),
                },
            )

            final_status = "failed"

        finally:
            self.repository.finish_monitor(
                run_id,
                final_status,
            )

            with self._lock:
                self._workers.pop(
                    run_id,
                    None,
                )

    @staticmethod
    def _safe(
        func,
    ):
        try:
            return func()
        except Exception as error:
            return {
                "_error": str(error),
            }

    def _sample(
        self,
        zte_service,
        ping_host,
    ):
        captured_at = datetime.now(
            timezone.utc
        ).isoformat()

        optical = self._safe(
            zte_service.optical_status
        )

        wan = self._safe(
            zte_service.wan_status
        )

        lan = self._safe(
            zte_service.lan_ports
        )

        wifi = self._safe(
            zte_service.wifi_clients
        )

        device = self._safe(
            zte_service.device_status
        )

        ping = self._safe(
            lambda: zte_service.ping({
                "host": ping_host,
                "interface": "",
                "count": 3,
                "timeout": 3000,
                "protocol": "ICMP",
                "ip_version": "IPv4",
            })
        )

        return {
            "captured_at": captured_at,
            "optical": optical,
            "wan": wan,
            "wan_online": _wan_online(
                wan
            ),
            "lan_ports": lan,
            "wifi_clients": wifi,
            "device": device,
            "ping": ping,
        }

    def _decorate(
        self,
        monitor,
    ):
        result = dict(
            monitor
        )

        result[
            "events"
        ] = self._events(
            monitor.get(
                "samples"
            )
            or []
        )

        result[
            "summary"
        ] = self._summary(
            monitor.get(
                "samples"
            )
            or [],
            result[
                "events"
            ],
        )

        return result

    @staticmethod
    def _events(
        samples,
    ):
        events = []
        previous = None

        for sample in samples:
            payload = (
                sample.get(
                    "payload"
                )
                or {}
            )

            if not payload:
                continue

            timestamp = sample.get(
                "captured_at"
            )

            if payload.get(
                "error"
            ):
                events.append({
                    "at": timestamp,
                    "severity": "critical",
                    "code": "sample_error",
                    "message": payload[
                        "error"
                    ],
                })
                previous = payload
                continue

            rx = _number(
                (
                    payload.get(
                        "optical"
                    )
                    or {}
                ).get(
                    "rx_power_dbm"
                )
            )

            if (
                rx is not None
                and (
                    rx < -27
                    or rx > -8
                )
            ):
                events.append({
                    "at": timestamp,
                    "severity": "critical",
                    "code": "optical_out_of_range",
                    "message": (
                        f"RX óptico em {rx:.1f} dBm."
                    ),
                })

            if previous:
                previous_online = bool(
                    previous.get(
                        "wan_online"
                    )
                )
                current_online = bool(
                    payload.get(
                        "wan_online"
                    )
                )

                if (
                    previous_online
                    != current_online
                ):
                    events.append({
                        "at": timestamp,
                        "severity": (
                            "ok"
                            if current_online
                            else "critical"
                        ),
                        "code": (
                            "wan_restored"
                            if current_online
                            else "wan_down"
                        ),
                        "message": (
                            "WAN voltou a responder."
                            if current_online
                            else "WAN deixou de responder."
                        ),
                    })

                previous_rx = _number(
                    (
                        previous.get(
                            "optical"
                        )
                        or {}
                    ).get(
                        "rx_power_dbm"
                    )
                )

                if (
                    previous_rx is not None
                    and rx is not None
                    and abs(
                        previous_rx - rx
                    ) >= 3
                ):
                    events.append({
                        "at": timestamp,
                        "severity": "warning",
                        "code": "optical_variation",
                        "message": (
                            f"RX variou {previous_rx:.1f} → {rx:.1f} dBm."
                        ),
                    })

            previous = payload

        return events

    @staticmethod
    def _summary(
        samples,
        events,
    ):
        rx_values = []

        for sample in samples:
            rx = _number(
                (
                    (
                        sample.get(
                            "payload"
                        )
                        or {}
                    ).get(
                        "optical"
                    )
                    or {}
                ).get(
                    "rx_power_dbm"
                )
            )

            if rx is not None:
                rx_values.append(
                    rx
                )

        return {
            "samples": len(
                samples
            ),
            "events": len(
                events
            ),
            "critical_events": sum(
                1
                for item in events
                if item.get(
                    "severity"
                ) == "critical"
            ),
            "rx_min": (
                min(rx_values)
                if rx_values
                else None
            ),
            "rx_max": (
                max(rx_values)
                if rx_values
                else None
            ),
        }


class TopologyService:
    """Monta uma topologia lógica usando inventário + sessão atual."""

    def __init__(
        self,
        repository: ManagementRepository = management_repository,
    ):
        self.repository = repository

    def build(
        self,
        device_id: int,
        *,
        current_clients: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        device = self.repository.get_device(
            device_id
        )

        if device is None:
            raise ValueError(
                "Equipamento não encontrado."
            )

        nodes = []
        edges = []

        def add_node(
            node_id,
            label,
            kind,
            status="unknown",
            **meta,
        ):
            nodes.append({
                "id": node_id,
                "label": label,
                "kind": kind,
                "status": status,
                "meta": meta,
            })

        device_status = (
            "ok"
            if device.get(
                "status"
            ) == "online"
            else "critical"
            if device.get(
                "status"
            ) == "offline"
            else "unknown"
        )

        add_node(
            "ont",
            (
                device.get("model")
                or "ONT"
            ),
            "ont",
            device_status,
            host=device.get("host"),
            rx_power=device.get(
                "rx_power"
            ),
            firmware=device.get(
                "firmware"
            ),
        )

        previous = "ont"

        if device.get(
            "cto"
        ):
            add_node(
                "cto",
                device["cto"],
                "cto",
                "ok",
            )
            edges.append({
                "from": "ont",
                "to": "cto",
                "label": "drop/fibra",
                "status": device_status,
            })
            previous = "cto"

        if device.get(
            "olt"
        ):
            add_node(
                "olt",
                device["olt"],
                "olt",
                "ok",
            )
            edges.append({
                "from": previous,
                "to": "olt",
                "label": "PON",
                "status": device_status,
            })
            previous = "olt"

        if device.get(
            "pop"
        ):
            add_node(
                "pop",
                device["pop"],
                "pop",
                "ok",
            )
            edges.append({
                "from": previous,
                "to": "pop",
                "label": "uplink",
                "status": "ok",
            })
            previous = "pop"

        add_node(
            "internet",
            "Internet",
            "internet",
            "unknown",
        )
        edges.append({
            "from": previous,
            "to": "internet",
            "label": "WAN",
            "status": "unknown",
        })

        if current_clients:
            for index, client in enumerate(
                current_clients.get(
                    "wifi"
                )
                or []
            ):
                node_id = f"wifi-client-{index}"

                rssi = _number(
                    client.get(
                        "rssi"
                    )
                )

                status = (
                    "critical"
                    if (
                        rssi is not None
                        and rssi <= -80
                    )
                    else "warning"
                    if (
                        rssi is not None
                        and rssi <= -70
                    )
                    else "ok"
                )

                add_node(
                    node_id,
                    (
                        client.get(
                            "hostname"
                        )
                        or client.get(
                            "mac"
                        )
                        or "Wi-Fi"
                    ),
                    "client_wifi",
                    status,
                    rssi=rssi,
                    ip=client.get("ip"),
                )
                edges.append({
                    "from": node_id,
                    "to": "ont",
                    "label": "Wi-Fi",
                    "status": status,
                })

            for index, client in enumerate(
                current_clients.get(
                    "lan"
                )
                or []
            ):
                node_id = f"lan-client-{index}"

                add_node(
                    node_id,
                    (
                        client.get(
                            "hostname"
                        )
                        or client.get(
                            "mac"
                        )
                        or "Ethernet"
                    ),
                    "client_lan",
                    "ok",
                    ip=client.get("ip"),
                )
                edges.append({
                    "from": node_id,
                    "to": "ont",
                    "label": "Ethernet",
                    "status": "ok",
                })

        return {
            "device": device,
            "nodes": nodes,
            "edges": edges,
        }


class IncidentCorrelationService:
    """
    Correlação simples por escopo físico.

    Sem telemetria central do OLT ainda não afirmamos rompimento; geramos
    'possível incidente' quando vários CPEs do mesmo POP/OLT/CTO aparecem
    offline ou com potência crítica na janela atual do inventário.
    """

    def __init__(
        self,
        repository: ManagementRepository = management_repository,
    ):
        self.repository = repository

    def correlate(
        self,
        *,
        minimum_devices: int = 5,
    ) -> dict[str, Any]:
        minimum_devices = max(
            2,
            int(
                minimum_devices
            ),
        )

        devices = self.repository.list_devices(
            limit=5000
        )

        incidents = []

        for field in (
            "cto",
            "olt",
            "pop",
        ):
            groups: dict[
                str,
                list[dict[str, Any]]
            ] = {}

            for device in devices:
                value = str(
                    device.get(field)
                    or ""
                ).strip()

                if not value:
                    continue

                unhealthy = (
                    device.get(
                        "status"
                    ) == "offline"
                )

                rx = _number(
                    device.get(
                        "rx_power"
                    )
                )

                if (
                    rx is not None
                    and rx < -27
                ):
                    unhealthy = True

                if not unhealthy:
                    continue

                groups.setdefault(
                    value,
                    [],
                ).append(
                    device
                )

            for value, members in groups.items():
                if len(
                    members
                ) < minimum_devices:
                    continue

                device_ids = [
                    item["id"]
                    for item in members
                ]

                severity = (
                    "critical"
                    if len(
                        members
                    ) >= max(
                        15,
                        minimum_devices,
                    )
                    else "warning"
                )

                incident = self.repository.upsert_incident(
                    incident_key=(
                        f"{field}:{value}"
                    ),
                    severity=severity,
                    title=(
                        "Possível incidente regional: "
                        f"{len(members)} CPEs afetados em {field.upper()} {value}"
                    ),
                    scope={
                        "type": field,
                        "value": value,
                    },
                    device_ids=device_ids,
                )

                incidents.append(
                    incident
                )

        return {
            "incidents": incidents,
            "minimum_devices": minimum_devices,
        }

    def list(
        self,
        status=None,
    ):
        return self.repository.list_incidents(
            status=status
        )


monitoring_service = MonitoringService()
topology_service = TopologyService()
incident_correlation_service = IncidentCorrelationService()

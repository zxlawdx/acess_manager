"""Bounded read-only comparison from the technician's computer, NOT the ONT.

No configurable destinations, subprocesses, router mutations or packet-loss
claims. A failed public probe can mean a firewall: it is not a diagnosis
of the customer's last-mile connection. Injectable I/O makes it testable.
"""
from __future__ import annotations

import socket
import statistics
from time import perf_counter
from typing import Callable


class WorkstationPathDiagnostic:
    def __init__(
        self, *,
        resolver: Callable = socket.getaddrinfo,
        connector: Callable = socket.create_connection,
        clock: Callable[[], float] = perf_counter,
    ) -> None:
        self._resolver = resolver
        self._connector = connector
        self._clock = clock

    def run(self) -> dict:
        # Fixed destinations prevent the desktop endpoint being used as a
        # scanner against user-entered/internal hosts or router services.
        dns_ok = False
        dns_ms = None
        start = self._clock()
        try:
            self._resolver("cloudflare.com", 443, type=socket.SOCK_STREAM)
            dns_ok = True
            dns_ms = round((self._clock() - start) * 1000, 1)
        except (OSError, ValueError):
            pass

        samples = []
        attempts = 3
        # A TCP handshake is NOT ICMP ping. Timeouts/refusals also depend on
        # the local firewall, remote port policy and proxy setup.
        for _ in range(attempts):
            begin = self._clock()
            try:
                connection = self._connector(("1.1.1.1", 443), timeout=1.5)
                try:
                    samples.append(round(
                        (self._clock() - begin) * 1000, 1,
                    ))
                finally:
                    connection.close()
            except (OSError, TimeoutError):
                continue
        mean = round(statistics.fmean(samples), 1) if samples else None
        variation = (
            round(max(samples) - min(samples), 1)
            if len(samples) >= 2 else None
        )
        return {
            "source": "technician_workstation",
            "dns": {
                "ok": dns_ok, "duration_ms": dns_ms,
                "name": "Resolução DNS do PC",
            },
            "tcp": {
                "ok": bool(samples), "target": "Cloudflare (porta 443)",
                "attempts": attempts, "successful": len(samples),
                "mean_connect_ms": mean, "variation_ms": variation,
            },
            "limitations": (
                "Mede apenas o computador do técnico. Os tempos TCP não "
                "equivalem a ping, jitter UDP nem perda de pacotes. "
                "Uma falha pode ser causada por proxy, firewall ou DNS local."
            ),
        }

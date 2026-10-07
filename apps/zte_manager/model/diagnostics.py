from __future__ import annotations

from dataclasses import asdict, dataclass, field


@dataclass(frozen=True)
class NativePingResult:
    target: str
    resolved_ip: str | None = None
    interface: str | None = None
    packets_sent: int | None = None
    packets_received: int | None = None
    packet_loss_percent: float | int | None = None
    min_ms: float | None = None
    avg_ms: float | None = None
    max_ms: float | None = None
    status: str = "unknown"
    error: str | None = None

    def as_dict(self) -> dict:
        return asdict(self)


@dataclass(frozen=True)
class TracerouteHop:
    index: int
    address: str | None = None
    hostname: str | None = None
    rtt_samples_ms: tuple[float, ...] = ()
    timeout: bool = False
    error: str | None = None

    def as_dict(self) -> dict:
        data = asdict(self)
        data["rtt_samples_ms"] = list(self.rtt_samples_ms)
        return data


@dataclass(frozen=True)
class NativeTracerouteResult:
    target: str
    interface: str | None = None
    status: str = "unknown"
    hops: tuple[TracerouteHop, ...] = field(default_factory=tuple)
    error: str | None = None

    def as_dict(self) -> dict:
        return {
            "target": self.target,
            "interface": self.interface,
            "status": self.status,
            "hops": [item.as_dict() for item in self.hops],
            "error": self.error,
        }

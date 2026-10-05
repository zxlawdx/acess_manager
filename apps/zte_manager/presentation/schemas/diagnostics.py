from pydantic import BaseModel, Field


class PingRequest(BaseModel):
    host: str = "8.8.8.8"
    interface: str = ""
    ip_version: str = "IPv4"
    count: int = Field(default=4, ge=1, le=30)
    data_size: int = Field(default=64, ge=1, le=1400)
    timeout: int = Field(default=5000, ge=1000, le=10000)


class TracerouteRequest(BaseModel):
    host: str = "8.8.8.8"
    interface: str = ""
    max_hops: int = Field(default=30, ge=1, le=64)
    timeout: int = Field(default=5000, ge=2000, le=10000)
    protocol: str = "ICMP"
    ip_version: str = "IPv4"


class AutomaticDiagnosticRequest(BaseModel):
    ping_host: str = "8.8.8.8"
    include_traceroute: bool = False
    optical_rx_min: float = -27.0
    optical_rx_max: float = -8.0
    wifi_rssi_warning: int = -70
    wifi_rssi_bad: int = -80
    expected_lan_mbps: int = Field(default=1000, ge=10)
    ping_warning_ms: float = Field(default=80.0, ge=1)


class SupportDiagnosticRequest(BaseModel):
    mode: str = "general"
    run_ping: bool = True
    affected_mac: str | None = None
    affected_ip: str | None = None
    ping_host: str = "1.1.1.1"
    dns_host: str = "cloudflare.com"
    include_traceroute: bool = False
    include_speedtest: bool = True
    allow_speedtest_fallback: bool = True
    speedtest_provider: str = "native_auto"
    speedtest_base_url: str | None = None
    auto_optimize_wifi: bool = False
    expected_download_mbps: float | None = Field(default=None, ge=0)
    expected_upload_mbps: float | None = Field(default=None, ge=0)
    optical_rx_min: float = -27.0
    optical_rx_max: float = -8.0
    wifi_rssi_warning: int = -70
    wifi_rssi_bad: int = -80
    expected_lan_mbps: int = Field(default=1000, ge=10)
    ping_warning_ms: float = Field(default=80.0, ge=1)


class DiagnosticRemediationRequest(BaseModel):
    action: str
    band: str | None = None
    channel: int | None = Field(default=None, ge=1, le=196)


class SpeedTestRequest(BaseModel):
    allow_fallback: bool = True
    server_url: str | None = None
    provider: str = "native_auto"
    fallback_base_url: str | None = None


class AttendanceReportRequest(BaseModel):
    diagnostic_id: int | None = Field(default=None, ge=1)

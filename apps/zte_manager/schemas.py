from typing import Any

from pydantic import BaseModel, Field


class ConnectRequest(BaseModel):
    ip: str
    username: str
    password: str
    https: bool = False
    attendant: str | None = None


class WifiRadioRequest(BaseModel):
    band: str | None = None
    auto_channel: bool | None = None
    channel: int | None = None
    standard: str | None = None
    country: str | None = None
    bandwidth: str | None = None
    sgi: bool | None = None
    beacon_interval: int | None = Field(
        default=None,
        ge=100,
        le=1000
    )
    tx_power: str | None = None
    sideband: str | None = None
    mu_mimo: bool | None = None
    uplink_mu_mimo: bool | None = None
    downlink_mu_mimo: bool | None = None
    uplink_ofdma: bool | None = None
    downlink_ofdma: bool | None = None
    twt: bool | None = None
    spatial_reuse: bool | None = None
    ssid_isolation: bool | None = None
    qos_type: str | None = None
    work_mode: str | None = None
    rts_cts: int | None = Field(
        default=None,
        ge=0,
        le=2347
    )
    dtim: int | None = Field(
        default=None,
        ge=1,
        le=5
    )
    preamble_type: str | None = None


class WifiSSIDRequest(BaseModel):
    ssid_id: str | None = None
    enabled: bool | None = None
    ssid: str | None = None
    password: str | None = None
    broadcast: bool | None = None
    hidden: bool | None = None
    isolation: bool | None = None
    max_clients: int | None = Field(
        default=None,
        ge=1,
        le=64
    )
    encryption: str | None = None


class AdminPasswordRequest(BaseModel):
    new_password: str = Field(
        min_length=1,
        max_length=256
    )


class RadioPowerRequest(BaseModel):
    band: str
    enabled: bool


class BandSteeringRequest(BaseModel):
    enabled: bool


class BandSteeringConfigRequest(BaseModel):
    rssi_limit_24g: int | None = Field(default=None, ge=-120, le=0)
    rssi_limit_5g: int | None = Field(default=None, ge=-120, le=0)
    vht_check_24g: int | None = Field(default=None, ge=0, le=1)
    vht_check_5g: int | None = Field(default=None, ge=0, le=1)
    active_sta_check_24g: int | None = Field(default=None, ge=0)
    active_sta_check_5g: int | None = Field(default=None, ge=0)
    idle_rate_limit_24g: int | None = Field(default=None, ge=0)
    idle_rate_limit_5g: int | None = Field(default=None, ge=0)
    bandwidth_util_24g: int | None = Field(default=None, ge=0, le=100)
    bandwidth_util_5g: int | None = Field(default=None, ge=0, le=100)
    accept_bandwidth_util_24g: int | None = Field(default=None, ge=0, le=100)
    accept_bandwidth_util_5g: int | None = Field(default=None, ge=0, le=100)
    accept_rssi_24g: int | None = Field(default=None, ge=-120, le=0)
    accept_rssi_5g: int | None = Field(default=None, ge=-120, le=0)
    accept_vht_check_24g: int | None = Field(default=None, ge=0, le=1)
    accept_vht_check_5g: int | None = Field(default=None, ge=0, le=1)
    bounce_detect_time: int | None = Field(default=None, ge=0)
    bounce_count: int | None = Field(default=None, ge=0)
    bounce_dwell_time: int | None = Field(default=None, ge=0)


class WifiScheduleRequest(BaseModel):
    enabled: bool
    start_hour: int = Field(default=2, ge=0, le=23)
    start_minute: int = Field(default=0, ge=0, le=59)
    end_hour: int = Field(default=6, ge=0, le=23)
    end_minute: int = Field(default=0, ge=0, le=59)


class WpsRequest(BaseModel):
    band: str
    mode: str


class UpnpRequest(BaseModel):
    enabled: bool | None = None
    wan: str | None = None
    wan_ipv6: str | None = None
    advertisement_period: int | None = Field(
        default=None,
        ge=4,
        le=1440
    )
    ttl: int | None = Field(
        default=None,
        ge=1,
        le=255
    )


class DnsRequest(BaseModel):
    domain_name: str | None = None
    ipv4_1: str | None = None
    ipv4_2: str | None = None
    ipv6_1: str | None = None
    ipv6_2: str | None = None
    hosts: list[dict[str, Any]] = Field(
        default_factory=list
    )


class PingRequest(BaseModel):
    host: str = "8.8.8.8"
    interface: str = ""
    ip_version: str = "IPv4"


class TracerouteRequest(BaseModel):
    host: str = "8.8.8.8"
    interface: str = ""
    max_hops: int = Field(
        default=30,
        ge=1,
        le=64
    )
    timeout: int = Field(
        default=5000,
        ge=2000,
        le=10000
    )
    protocol: str = "ICMP"
    ip_version: str = "IPv4"


class ProfileRequest(BaseModel):
    attendant: str
    wifi: dict[str, dict[str, Any]] = Field(
        default_factory=dict
    )
    dns: dict[str, Any] = Field(
        default_factory=dict
    )


class AttendantRequest(BaseModel):
    attendant: str


class CapabilityProbeRequest(BaseModel):
    features: list[str] = Field(
        default_factory=list
    )


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
    expected_download_mbps: float | None = Field(
        default=None,
        ge=0
    )
    expected_upload_mbps: float | None = Field(
        default=None,
        ge=0
    )
    optical_rx_min: float = -27.0
    optical_rx_max: float = -8.0
    wifi_rssi_warning: int = -70
    wifi_rssi_bad: int = -80
    expected_lan_mbps: int = Field(
        default=1000,
        ge=10
    )
    ping_warning_ms: float = Field(
        default=80.0,
        ge=1
    )


class DiagnosticRemediationRequest(BaseModel):
    action: str
    band: str | None = None
    channel: int | None = Field(
        default=None,
        ge=1,
        le=196
    )


class SpeedTestRequest(BaseModel):
    allow_fallback: bool = True
    server_url: str | None = None
    provider: str = "native_auto"
    fallback_base_url: str | None = None


class AttendanceReportRequest(BaseModel):
    diagnostic_id: int | None = Field(
        default=None,
        ge=1
    )


class DhcpBasicRequest(BaseModel):
    enabled: bool | None = None
    min_address: str | None = None
    max_address: str | None = None
    dns_source: str | None = None
    dns1: str | None = None
    dns2: str | None = None
    lease_time: int | None = Field(default=None, ge=60)
    ipv4_dns_origin: str | None = None


class DhcpReservationRequest(BaseModel):
    id: str | None = None
    name: str = Field(min_length=1, max_length=64)
    ip: str = Field(min_length=7, max_length=45)
    mac: str = Field(min_length=11, max_length=32)


class ResourceIdRequest(BaseModel):
    id: str = Field(min_length=1)
    confirm: bool = False


class PortForwardRequest(BaseModel):
    id: str | None = None
    name: str = Field(default="", max_length=64)
    enabled: bool = True
    protocol: str = "TCP"
    interface: str | None = None
    all_interfaces: bool = True
    external_port: int = Field(ge=1, le=65535)
    external_port_end: int | None = Field(default=None, ge=1, le=65535)
    internal_client: str
    internal_port: int = Field(ge=1, le=65535)
    internal_port_end: int | None = Field(default=None, ge=1, le=65535)
    remote_host: str | None = None
    remote_host_end: str | None = None
    description: str | None = Field(default=None, max_length=128)
    confirm: bool = False


class DmzRequest(BaseModel):
    id: str | None = None
    enabled: bool = False
    internal_client: str = ""
    wan: str | None = None
    confirm: bool = False



# =========================================================
# CPE MANAGEMENT PLATFORM
# =========================================================


class InventorySyncRequest(BaseModel):
    customer_name: str | None = None
    olt: str | None = None
    cto: str | None = None
    pop: str | None = None
    agent_id: int | None = Field(
        default=None,
        ge=1
    )
    tags: list[str] = Field(
        default_factory=list
    )


class InventoryUpdateRequest(BaseModel):
    device_id: int = Field(ge=1)
    customer_name: str | None = None
    olt: str | None = None
    cto: str | None = None
    pop: str | None = None
    agent_id: int | None = Field(
        default=None,
        ge=1
    )
    status: str | None = None
    tags: list[str] | None = None
    metadata: dict[str, Any] | None = None


class ManagementProfileRequest(BaseModel):
    name: str = Field(
        min_length=1,
        max_length=120
    )
    description: str | None = None
    config: dict[str, Any] = Field(
        default_factory=dict
    )
    is_default: bool = False


class DriftRequest(BaseModel):
    profile_id: int | None = Field(
        default=None,
        ge=1
    )
    profile_name: str | None = None
    confirm: bool = False


class BatchManagementRequest(BaseModel):
    operation: str
    device_ids: list[int] = Field(
        min_length=1
    )
    payload: dict[str, Any] = Field(
        default_factory=dict
    )


class AgentRequest(BaseModel):
    name: str = Field(
        min_length=1,
        max_length=120
    )
    host: str = Field(
        min_length=1,
        max_length=255
    )
    ssh_port: int = Field(
        default=22,
        ge=1,
        le=65535
    )
    ssh_user: str = Field(
        min_length=1,
        max_length=120
    )
    ssh_key_path: str | None = None
    vpn_driver: str = "none"
    vpn_config: dict[str, Any] = Field(
        default_factory=dict
    )
    enabled: bool = True


class RemoteAccessRequest(BaseModel):
    device_id: int = Field(ge=1)
    attendant: str | None = None
    ttl_minutes: int = Field(
        default=30,
        ge=5,
        le=240
    )
    remote_port: int = Field(
        default=80,
        ge=1,
        le=65535
    )


class NumericIdRequest(BaseModel):
    id: int = Field(ge=1)


class GatewayCommandRequest(BaseModel):
    agent_id: int = Field(ge=1)
    command: str
    params: dict[str, Any] = Field(
        default_factory=dict
    )


class MonitorStartRequest(BaseModel):
    device_id: int | None = Field(
        default=None,
        ge=1
    )
    duration_seconds: int = Field(
        default=300,
        ge=30,
        le=900
    )
    interval_seconds: int = Field(
        default=10,
        ge=5,
        le=60
    )
    ping_host: str = "1.1.1.1"


class QoSManagementRequest(BaseModel):
    kind: str
    id: str | None = None
    config: dict[str, Any] = Field(
        default_factory=dict
    )
    confirm: bool = False


class FirewallManagementRequest(BaseModel):
    config: dict[str, Any] = Field(
        default_factory=dict
    )
    confirm: bool = False


class SNTPManagementRequest(BaseModel):
    config: dict[str, Any] = Field(
        default_factory=dict
    )


class TR069ManagementRequest(BaseModel):
    config: dict[str, Any] = Field(
        default_factory=dict
    )
    confirm: bool = False


class WANManagementRequest(BaseModel):
    id: str
    config: dict[str, Any] = Field(
        default_factory=dict
    )
    confirm: bool = False


class WANActionRequest(BaseModel):
    id: str
    action: str


class BridgeModeRequest(BaseModel):
    id: str
    config: dict[str, Any] = Field(
        default_factory=dict
    )
    confirm: bool = False


class ManagementBackupRequest(BaseModel):
    device_id: int | None = Field(
        default=None,
        ge=1
    )
    reason: str = Field(
        default="manual",
        max_length=120
    )


class RestoreBackupRequest(BaseModel):
    backup_id: int = Field(ge=1)
    confirm: bool = False


class FirmwareRegisterRequest(BaseModel):
    model: str = Field(
        min_length=1,
        max_length=120
    )
    version: str = Field(
        min_length=1,
        max_length=120
    )
    file_path: str = Field(
        min_length=1
    )
    approved: bool = False
    notes: str | None = None


class FirmwareUpgradeRequest(BaseModel):
    device_id: int = Field(ge=1)
    firmware_id: int = Field(ge=1)
    confirm: bool = False


class ACSConfigRequest(BaseModel):
    provider: str = "genieacs"
    base_url: str
    timeout: int = Field(
        default=20,
        ge=1,
        le=120
    )


class ACSParameterRequest(BaseModel):
    device_id: int = Field(ge=1)
    parameters: dict[str, Any] = Field(
        default_factory=dict
    )


class ZeroTouchRequest(BaseModel):
    profile_id: int = Field(ge=1)
    customer_name: str | None = None
    olt: str | None = None
    cto: str | None = None
    pop: str | None = None
    agent_id: int | None = Field(
        default=None,
        ge=1
    )
    tags: list[str] = Field(
        default_factory=list
    )
    confirm: bool = False



class FirewallRuleManagementRequest(BaseModel):
    kind: str
    id: str | None = None
    config: dict[str, Any] = Field(
        default_factory=dict
    )
    confirm: bool = False


class FilterGlobalManagementRequest(BaseModel):
    config: dict[str, Any] = Field(
        default_factory=dict
    )
    confirm: bool = False


class WANCreateRequest(BaseModel):
    config: dict[str, Any] = Field(
        default_factory=dict
    )
    confirm: bool = False


class BackupCompareRequest(BaseModel):
    left_id: int = Field(ge=1)
    right_id: int = Field(ge=1)



class WANDeleteRequest(BaseModel):
    id: str
    confirm: bool = False



class BufferbloatRequest(BaseModel):
    agent_id: int = Field(ge=1)
    ping_host: str = "1.1.1.1"
    iperf_host: str
    direction: str = "download"
    duration: int = Field(
        default=10,
        ge=5,
        le=30
    )
    streams: int = Field(
        default=4,
        ge=1,
        le=8
    )

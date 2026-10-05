from typing import Any

from pydantic import BaseModel, Field


class InventorySyncRequest(BaseModel):
    customer_name: str | None = None
    olt: str | None = None
    cto: str | None = None
    pop: str | None = None
    agent_id: int | None = Field(default=None, ge=1)
    tags: list[str] = Field(default_factory=list)


class InventoryUpdateRequest(BaseModel):
    device_id: int = Field(ge=1)
    customer_name: str | None = None
    olt: str | None = None
    cto: str | None = None
    pop: str | None = None
    agent_id: int | None = Field(default=None, ge=1)
    status: str | None = None
    tags: list[str] | None = None
    metadata: dict[str, Any] | None = None


class ManagementProfileRequest(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    description: str | None = None
    config: dict[str, Any] = Field(default_factory=dict)
    is_default: bool = False


class DriftRequest(BaseModel):
    profile_id: int | None = Field(default=None, ge=1)
    profile_name: str | None = None
    confirm: bool = False


class BatchManagementRequest(BaseModel):
    operation: str
    device_ids: list[int] = Field(min_length=1)
    payload: dict[str, Any] = Field(default_factory=dict)


class AgentRequest(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    host: str = Field(min_length=1, max_length=255)
    ssh_port: int = Field(default=22, ge=1, le=65535)
    ssh_user: str = Field(min_length=1, max_length=120)
    ssh_key_path: str | None = None
    vpn_driver: str = "none"
    vpn_config: dict[str, Any] = Field(default_factory=dict)
    enabled: bool = True


class RemoteAccessRequest(BaseModel):
    device_id: int = Field(ge=1)
    attendant: str | None = None
    ttl_minutes: int = Field(default=30, ge=5, le=240)
    remote_port: int = Field(default=80, ge=1, le=65535)


class NumericIdRequest(BaseModel):
    id: int = Field(ge=1)


class GatewayCommandRequest(BaseModel):
    agent_id: int = Field(ge=1)
    command: str
    params: dict[str, Any] = Field(default_factory=dict)


class MonitorStartRequest(BaseModel):
    device_id: int | None = Field(default=None, ge=1)
    duration_seconds: int = Field(default=300, ge=30, le=900)
    interval_seconds: int = Field(default=10, ge=5, le=60)
    ping_host: str = "1.1.1.1"


class MeshConfigRequest(BaseModel):
    enabled: bool
    band_steering: bool | None = None
    rssi_limit_24g: int | None = Field(default=None, ge=-110, le=-40)
    rssi_limit_5g: int | None = Field(default=None, ge=-110, le=-40)
    legacy_station_roaming: bool | None = None
    confirm: bool = False


class MeshPairRequest(BaseModel):
    confirm: bool = False


class QoSManagementRequest(BaseModel):
    kind: str
    id: str | None = None
    config: dict[str, Any] = Field(default_factory=dict)
    confirm: bool = False


class FirewallManagementRequest(BaseModel):
    config: dict[str, Any] = Field(default_factory=dict)
    confirm: bool = False


class SNTPManagementRequest(BaseModel):
    config: dict[str, Any] = Field(default_factory=dict)


class TR069ManagementRequest(BaseModel):
    config: dict[str, Any] = Field(default_factory=dict)
    confirm: bool = False


class WANManagementRequest(BaseModel):
    id: str
    config: dict[str, Any] = Field(default_factory=dict)
    confirm: bool = False


class WANActionRequest(BaseModel):
    id: str
    action: str


class BridgeModeRequest(BaseModel):
    id: str
    config: dict[str, Any] = Field(default_factory=dict)
    confirm: bool = False


class ManagementBackupRequest(BaseModel):
    device_id: int | None = Field(default=None, ge=1)
    reason: str = Field(default="manual", max_length=120)


class RestoreBackupRequest(BaseModel):
    backup_id: int = Field(ge=1)
    confirm: bool = False


class FirmwareRegisterRequest(BaseModel):
    model: str = Field(min_length=1, max_length=120)
    version: str = Field(min_length=1, max_length=120)
    file_path: str = Field(min_length=1)
    approved: bool = False
    notes: str | None = None


class FirmwareUpgradeRequest(BaseModel):
    device_id: int = Field(ge=1)
    firmware_id: int = Field(ge=1)
    confirm: bool = False


class ACSConfigRequest(BaseModel):
    provider: str = "genieacs"
    base_url: str
    timeout: int = Field(default=20, ge=1, le=120)


class ACSParameterRequest(BaseModel):
    device_id: int = Field(ge=1)
    parameters: dict[str, Any] = Field(default_factory=dict)


class ZeroTouchRequest(BaseModel):
    profile_id: int = Field(ge=1)
    customer_name: str | None = None
    olt: str | None = None
    cto: str | None = None
    pop: str | None = None
    agent_id: int | None = Field(default=None, ge=1)
    tags: list[str] = Field(default_factory=list)
    confirm: bool = False


class FirewallRuleManagementRequest(BaseModel):
    kind: str
    id: str | None = None
    config: dict[str, Any] = Field(default_factory=dict)
    confirm: bool = False


class FilterGlobalManagementRequest(BaseModel):
    config: dict[str, Any] = Field(default_factory=dict)
    confirm: bool = False


class WANCreateRequest(BaseModel):
    config: dict[str, Any] = Field(default_factory=dict)
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
    duration: int = Field(default=10, ge=5, le=30)
    streams: int = Field(default=4, ge=1, le=8)

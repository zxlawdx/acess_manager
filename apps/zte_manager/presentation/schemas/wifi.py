from pydantic import BaseModel, Field


class WifiRadioRequest(BaseModel):
    band: str | None = None
    auto_channel: bool | None = None
    channel: int | None = None
    standard: str | None = None
    country: str | None = None
    bandwidth: str | None = None
    sgi: bool | None = None
    beacon_interval: int | None = Field(default=None, ge=100, le=1000)
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
    rts_cts: int | None = Field(default=None, ge=0, le=2347)
    dtim: int | None = Field(default=None, ge=1, le=5)
    preamble_type: str | None = None
    frag_threshold: int | None = Field(default=None, ge=256, le=2346)
    band_steering: bool | None = None
    band_steering_policy: int | str | None = None
    airtime_fairness: bool | None = None
    auto_channel_scope: int | str | None = None
    bandwidth_code: int | str | None = None


class WifiSSIDRequest(BaseModel):
    ssid_id: str | None = None
    enabled: bool | None = None
    ssid: str | None = None
    password: str | None = None
    broadcast: bool | None = None
    hidden: bool | None = None
    isolation: bool | None = None
    max_clients: int | None = Field(default=None, ge=1, le=64)
    encryption: str | None = None
    authentication_mode: str | None = None
    encryption_mode: str | None = None
    group_rekey: int | None = Field(default=None, ge=0)
    wps_enabled: bool | None = None
    wps_method: str | None = None


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

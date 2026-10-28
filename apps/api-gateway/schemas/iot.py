"""
IoT API schemas.
"""

from datetime import datetime
from typing import Any, Dict, List, Optional
from enum import Enum

from pydantic import BaseModel, Field


class IoTDeviceType(str, Enum):
    CAMERA = "camera"
    PLUG = "plug"
    ROUTER = "router"
    SPEAKER = "speaker"


class IoTDeviceStatus(str, Enum):
    ONLINE = "online"
    OFFLINE = "offline"


class IoTEventType(str, Enum):
    CONNECTION = "connection"
    MOTION = "motion"
    TRAFFIC = "traffic"


class IoTAlertSeverity(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class DeviceRegisterRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=120)
    type: IoTDeviceType
    location: str = Field(..., min_length=1, max_length=120)
    mac_address: Optional[str] = Field(None, max_length=17)


class DeviceResponse(BaseModel):
    id: str
    name: str
    type: str
    location: str
    status: str
    mac_address: Optional[str] = None
    risk_score: int
    risk_label: str
    last_seen: Optional[datetime] = None
    open_alerts: int = 0
    created_at: datetime

    model_config = {"from_attributes": True}


class DeviceListResponse(BaseModel):
    total: int
    items: List[DeviceResponse]


class TelemetryResponse(BaseModel):
    id: str
    device_id: Optional[str] = None
    event_type: str
    data: Dict[str, Any]
    created_at: datetime

    model_config = {"from_attributes": True}


class AlertResponse(BaseModel):
    id: str
    device_id: Optional[str] = None
    device_name: Optional[str] = None
    rule_triggered: str
    severity: str
    description: str
    is_resolved: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class AlertListResponse(BaseModel):
    total: int
    page: int
    limit: int
    items: List[AlertResponse]


class SeedDemoResponse(BaseModel):
    message: str
    devices: List[DeviceResponse]


# ── Simulation event types exposed to the frontend ──────────────────────────
class SimEventType(str, Enum):
    """
    Simulation-only event categories.
    These map onto the three low-level IoT event types (connection/motion/traffic)
    and pre-fill the data payload so the existing rule engine can evaluate them.
    They are NOT real hardware events.
    """
    NORMAL_ACTIVITY   = "normal_activity"
    BRUTE_FORCE       = "brute_force"
    SUSPICIOUS_DNS    = "suspicious_dns"
    UNKNOWN_DEVICE    = "unknown_device"
    NETWORK_ANOMALY   = "network_anomaly"
    DEVICE_OFFLINE    = "device_offline"


class TelemetryIngestRequest(BaseModel):
    """
    Validated request body for POST /iot/telemetry.
    Replaces the previous untyped dict.
    """
    device_id: str = Field(..., description="UUID of the registered virtual device")
    # Low-level IoT event type understood by the rule engine
    event_type: IoTEventType = Field(..., description="connection | motion | traffic")
    # Free-form data payload evaluated by the rule engine
    data: Dict[str, Any] = Field(default_factory=dict, description="Event payload")
    # Optional simulated MAC for unknown-device scenarios
    mac_address: Optional[str] = Field(None, max_length=17)

    model_config = {"json_schema_extra": {
        "example": {
            "device_id": "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx",
            "event_type": "traffic",
            "data": {"dns_query": "malware-c2.xyz"},
        }
    }}


class TelemetryIngestResponse(BaseModel):
    """What the telemetry endpoint returns after processing."""
    telemetry_id: str
    device_id: Optional[str] = None
    event_type: str
    alerts_created: int
    risk_score: int
    risk_label: str


class TelemetryRecord(BaseModel):
    """A single telemetry entry for the history panel."""
    id: str
    device_id: Optional[str] = None
    event_type: str
    data: Dict[str, Any]
    alert_triggered: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class TelemetryHistoryResponse(BaseModel):
    total: int
    page: int
    limit: int
    items: List[TelemetryRecord]

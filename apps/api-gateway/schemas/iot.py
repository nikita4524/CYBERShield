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

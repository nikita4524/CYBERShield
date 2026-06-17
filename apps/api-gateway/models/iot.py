"""
IoT models — devices, telemetry, and security alerts.
"""

import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    Column,
    String,
    SmallInteger,
    Boolean,
    Text,
    DateTime,
    Enum as SAEnum,
    ForeignKey,
    CheckConstraint,
    Index,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from database import Base
from models.db_types import json_type


class IoTDevice(Base):
    __tablename__ = "iot_devices"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name = Column(String(120), nullable=False)
    type = Column(
        SAEnum("camera", "plug", "router", "speaker", name="iot_device_type", create_type=True),
        nullable=False,
    )
    location = Column(String(120), nullable=False, default="Unknown")
    status = Column(
        SAEnum("online", "offline", name="iot_device_status", create_type=True),
        nullable=False,
        default="offline",
    )
    mac_address = Column(String(17), nullable=True, index=True)
    risk_score = Column(SmallInteger, nullable=False, default=0)
    risk_label = Column(
        SAEnum("safe", "suspicious", "dangerous", name="iot_risk_label", create_type=True),
        nullable=False,
        default="safe",
    )
    last_seen = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )

    user = relationship("User", backref="iot_devices")
    telemetry = relationship(
        "IoTTelemetry",
        back_populates="device",
        cascade="all, delete-orphan",
    )
    alerts = relationship(
        "IoTAlert",
        back_populates="device",
        cascade="all, delete-orphan",
    )

    __table_args__ = (
        CheckConstraint("risk_score >= 0 AND risk_score <= 100", name="ck_iot_risk_score_range"),
    )

    def __repr__(self):
        return f"<IoTDevice {self.name} status={self.status} score={self.risk_score}>"


class IoTTelemetry(Base):
    __tablename__ = "iot_telemetry"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    device_id = Column(
        UUID(as_uuid=True),
        ForeignKey("iot_devices.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    event_type = Column(
        SAEnum("connection", "motion", "traffic", name="iot_event_type", create_type=True),
        nullable=False,
    )
    data = Column(json_type(), nullable=False, default=dict)
    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        index=True,
    )

    device = relationship("IoTDevice", back_populates="telemetry")

    __table_args__ = (Index("ix_iot_telemetry_device_created", "device_id", "created_at"),)


class IoTAlert(Base):
    __tablename__ = "iot_alerts"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    device_id = Column(
        UUID(as_uuid=True),
        ForeignKey("iot_devices.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    rule_triggered = Column(String(64), nullable=False, index=True)
    severity = Column(
        SAEnum("low", "medium", "high", name="iot_alert_severity", create_type=True),
        nullable=False,
    )
    description = Column(Text, nullable=False)
    is_resolved = Column(Boolean, nullable=False, default=False, index=True)
    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        index=True,
    )

    device = relationship("IoTDevice", back_populates="alerts")

    def __repr__(self):
        return f"<IoTAlert rule={self.rule_triggered} severity={self.severity}>"

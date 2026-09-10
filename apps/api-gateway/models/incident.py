"""
SecurityIncident model — records BLOCK, QUARANTINE, RESTRICT events.
"""

import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    Column, String, SmallInteger, Text, Integer,
    DateTime, ForeignKey, Index
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from database import Base
from models.db_types import json_type


class SecurityIncident(Base):
    __tablename__ = "security_incidents"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    incident_number = Column(String(20), unique=True, nullable=False, index=True)
    # e.g. INC-2026-0001

    threat_type = Column(String(50), nullable=False)
    # e.g. "phishing_url", "deepfake_audio", "phishing_email", "malicious_qr"

    source = Column(String(20), nullable=False)
    # "url" | "email" | "qr" | "audio" | "video" | "image"

    input_reference = Column(Text, nullable=True)
    # Truncated URL / email subject / filename — never full content

    risk_score = Column(SmallInteger, nullable=False)

    severity = Column(String(20), nullable=False)
    # "SAFE" | "MEDIUM" | "HIGH" | "CRITICAL"

    action = Column(String(20), nullable=False)
    # "ALLOW" | "WARN" | "RESTRICT" | "BLOCK" | "QUARANTINE" | "FLAG"

    reasons = Column(json_type(), nullable=True, default=list)
    # List of human-readable reason strings

    status = Column(String(20), nullable=False, default="OPEN")
    # "OPEN" | "REVIEWING" | "RESOLVED" | "FALSE_POSITIVE"

    resolution_note = Column(Text, nullable=True)

    analysis_id = Column(
        UUID(as_uuid=True),
        ForeignKey("analyses.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    user_id = Column(UUID(as_uuid=True), nullable=True, index=True)
    # Who triggered the analysis (NULL for anonymous)

    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        index=True,
    )

    resolved_at = Column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        Index("ix_incidents_status_created", "status", "created_at"),
        Index("ix_incidents_source_severity", "source", "severity"),
    )

    def __repr__(self):
        return (
            f"<SecurityIncident {self.incident_number} "
            f"action={self.action} status={self.status}>"
        )

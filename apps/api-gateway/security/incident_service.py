"""
CyberShield AI — Incident Service
====================================

Creates and manages SecurityIncident records in the database.
Called by the Prevention Engine whenever a BLOCK / QUARANTINE / FLAG
or serious RESTRICT event occurs.

Incident numbers are auto-generated in the format INC-YYYY-NNNN.
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)


class IncidentService:
    """Manages creation and status updates for SecurityIncidents."""

    def create_incident(
        self,
        db: Session,
        *,
        source: str,
        threat_type: str,
        risk_score: int,
        severity: str,
        action: str,
        reasons: list,
        input_reference: Optional[str] = None,
        analysis_id: Optional[str] = None,
        user_id=None,
    ) -> Optional[str]:
        """
        Persist a new SecurityIncident.

        Returns the incident_number string (e.g. "INC-2026-0001"),
        or None if persistence fails (never raises — app must continue working).
        """
        try:
            from models.incident import SecurityIncident

            incident_number = self._generate_number(db)
            incident_id = uuid.uuid4()

            # Sanitize input_reference — never store full bodies
            ref = self._sanitize_reference(input_reference or "", source)

            # Convert user_id to UUID if it's a string
            uid = None
            if user_id is not None:
                try:
                    uid = uuid.UUID(str(user_id)) if not isinstance(user_id, uuid.UUID) else user_id
                except (ValueError, AttributeError):
                    uid = None

            # Convert analysis_id to UUID if it's a string
            aid = None
            if analysis_id is not None:
                try:
                    aid = uuid.UUID(str(analysis_id)) if not isinstance(analysis_id, uuid.UUID) else analysis_id
                except (ValueError, AttributeError):
                    aid = None

            incident = SecurityIncident(
                id=incident_id,
                incident_number=incident_number,
                threat_type=threat_type,
                source=source,
                input_reference=ref,
                risk_score=risk_score,
                severity=severity,
                action=action,
                reasons=reasons[:6],  # cap
                status="OPEN",
                analysis_id=aid,
                user_id=uid,
                created_at=datetime.now(timezone.utc),
            )

            db.add(incident)
            db.commit()
            db.refresh(incident)

            logger.info(
                "Incident created: %s source=%s action=%s score=%d",
                incident_number, source, action, risk_score,
            )
            return incident_number

        except Exception as exc:
            logger.error("Failed to create incident: %s", exc)
            try:
                db.rollback()
            except Exception:
                pass
            return None

    def update_status(
        self,
        db: Session,
        incident_id: str,
        status: str,
        resolution_note: Optional[str] = None,
    ) -> bool:
        """Update the status of an existing incident. Returns True on success."""
        try:
            from models.incident import SecurityIncident

            incident = (
                db.query(SecurityIncident)
                .filter(SecurityIncident.id == uuid.UUID(incident_id))
                .first()
            )
            if not incident:
                return False

            incident.status = status
            if resolution_note:
                incident.resolution_note = resolution_note
            if status in ("RESOLVED", "FALSE_POSITIVE"):
                incident.resolved_at = datetime.now(timezone.utc)

            db.commit()
            return True

        except Exception as exc:
            logger.error("Failed to update incident %s: %s", incident_id, exc)
            db.rollback()
            return False

    # ------------------------------------------------------------------
    def _generate_number(self, db: Session) -> str:
        """
        Generate the next sequential incident number: INC-YYYY-NNNN.
        Uses a DB count to determine the sequence, with fallback to UUID suffix.
        """
        try:
            from models.incident import SecurityIncident

            year = datetime.now(timezone.utc).year
            count = (
                db.query(SecurityIncident)
                .filter(SecurityIncident.incident_number.like(f"INC-{year}-%"))
                .count()
            )
            return f"INC-{year}-{count + 1:04d}"

        except Exception:
            # Fallback to random suffix
            suffix = str(uuid.uuid4())[:4].upper()
            return f"INC-{datetime.now(timezone.utc).year}-{suffix}"

    def _sanitize_reference(self, value: str, source: str) -> str:
        """
        Truncate and sanitize the input reference to avoid storing
        sensitive content (full email bodies, long URLs, etc.).
        """
        if not value:
            return ""

        value = str(value).strip()

        # For URLs: truncate at 150 chars
        if source in ("url", "qr"):
            return value[:150]

        # For email: only store subject (first 200 chars)
        if source == "email":
            lines = value.split("\n")
            subject_line = next(
                (l for l in lines if l.lower().startswith("subj")), lines[0]
            )
            return subject_line[:200]

        # For media: store just the filename
        return value[:80]

    def _map_threat_type(self, source: str, risk_label: str) -> str:
        """Derive threat_type from source + risk_label."""
        mapping = {
            "url":   "phishing_url",
            "email": "phishing_email",
            "qr":    "malicious_qr",
            "audio": "deepfake_audio",
            "video": "deepfake_video",
            "image": "deepfake_image",
        }
        return mapping.get(source, f"threat_{source}")


def get_threat_type(source: str) -> str:
    """Public helper for routes to derive threat type."""
    mapping = {
        "url":   "phishing_url",
        "email": "phishing_email",
        "qr":    "malicious_qr",
        "audio": "deepfake_audio",
        "video": "deepfake_video",
        "image": "deepfake_image",
    }
    return mapping.get(source, f"threat_{source}")


# ── Singleton ──────────────────────────────────────────────────────────
incident_service = IncidentService()

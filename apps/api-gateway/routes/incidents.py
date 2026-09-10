"""
CyberShield AI — Security Incidents API Routes
Endpoints for querying, viewing, and updating security incidents.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import desc, func
from sqlalchemy.orm import Session

from database import get_db
from dependencies import get_current_user_optional, get_current_user_required
from models.incident import SecurityIncident

router = APIRouter()


# ── Schemas ──────────────────────────────────────────────────────────

class IncidentSummary(BaseModel):
    id: str
    incident_number: str
    threat_type: str
    source: str
    input_reference: Optional[str] = None
    risk_score: int
    severity: str
    action: str
    reasons: List[str] = Field(default_factory=list)
    status: str
    analysis_id: Optional[str] = None
    created_at: datetime
    resolved_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class IncidentDetailResponse(IncidentSummary):
    resolution_note: Optional[str] = None
    user_id: Optional[str] = None


class IncidentListResponse(BaseModel):
    total: number if False else int
    page: int
    limit: int
    items: List[IncidentSummary]


class IncidentUpdateStatusRequest(BaseModel):
    status: str = Field(..., description="OPEN | REVIEWING | RESOLVED | FALSE_POSITIVE")
    resolution_note: Optional[str] = None


class IncidentStatsResponse(BaseModel):
    total: int
    critical: int
    high: int
    medium: int
    blocked: int
    quarantined: int
    resolved: int
    open: int


# ── Endpoints ────────────────────────────────────────────────────────

@router.get(
    "/stats",
    response_model=IncidentStatsResponse,
    summary="Get incident summary metrics",
)
async def get_incident_stats(
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user_optional),
):
    """Returns total counts by severity, action, and resolution status."""
    query = db.query(SecurityIncident)
    if current_user and current_user.role not in ("admin", "org_admin"):
        query = query.filter(
            (SecurityIncident.user_id == current_user.id) | (SecurityIncident.user_id.is_(None))
        )

    all_incidents = query.all()

    total = len(all_incidents)
    critical = sum(1 for i in all_incidents if i.severity == "CRITICAL")
    high = sum(1 for i in all_incidents if i.severity == "HIGH")
    medium = sum(1 for i in all_incidents if i.severity == "MEDIUM")
    blocked = sum(1 for i in all_incidents if i.action == "BLOCK")
    quarantined = sum(1 for i in all_incidents if i.action == "QUARANTINE")
    resolved = sum(1 for i in all_incidents if i.status == "RESOLVED")
    open_count = sum(1 for i in all_incidents if i.status in ("OPEN", "REVIEWING"))

    return IncidentStatsResponse(
        total=total,
        critical=critical,
        high=high,
        medium=medium,
        blocked=blocked,
        quarantined=quarantined,
        resolved=resolved,
        open=open_count,
    )


@router.get(
    "",
    response_model=IncidentListResponse,
    summary="List security incidents with filtering and pagination",
)
async def list_incidents(
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    threat_type: Optional[str] = None,
    severity: Optional[str] = None,
    action: Optional[str] = None,
    status: Optional[str] = None,
    source: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user_optional),
):
    """Retrieve security incidents with optional filters."""
    query = db.query(SecurityIncident)

    if current_user and current_user.role not in ("admin", "org_admin"):
        query = query.filter(
            (SecurityIncident.user_id == current_user.id) | (SecurityIncident.user_id.is_(None))
        )

    if threat_type:
        query = query.filter(SecurityIncident.threat_type == threat_type)
    if severity:
        query = query.filter(SecurityIncident.severity == severity.upper())
    if action:
        query = query.filter(SecurityIncident.action == action.upper())
    if status:
        query = query.filter(SecurityIncident.status == status.upper())
    if source:
        query = query.filter(SecurityIncident.source == source.lower())

    total = query.count()
    offset = (page - 1) * limit
    incidents = query.order_by(desc(SecurityIncident.created_at)).offset(offset).limit(limit).all()

    items = []
    for inc in incidents:
        items.append(
            IncidentSummary(
                id=str(inc.id),
                incident_number=inc.incident_number,
                threat_type=inc.threat_type,
                source=inc.source,
                input_reference=inc.input_reference,
                risk_score=inc.risk_score,
                severity=inc.severity,
                action=inc.action,
                reasons=inc.reasons or [],
                status=inc.status,
                analysis_id=str(inc.analysis_id) if inc.analysis_id else None,
                created_at=inc.created_at,
                resolved_at=inc.resolved_at,
            )
        )

    return IncidentListResponse(
        total=total,
        page=page,
        limit=limit,
        items=items,
    )


@router.get(
    "/{incident_id}",
    response_model=IncidentDetailResponse,
    summary="Get single incident by ID or incident number",
)
async def get_incident(
    incident_id: str,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user_optional),
):
    """Fetch details of a single incident by UUID or INC-YYYY-NNNN."""
    query = db.query(SecurityIncident)

    try:
        uid = uuid.UUID(incident_id)
        query = query.filter(SecurityIncident.id == uid)
    except ValueError:
        query = query.filter(SecurityIncident.incident_number == incident_id)

    incident = query.first()
    if not incident:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Incident not found",
        )

    return IncidentDetailResponse(
        id=str(incident.id),
        incident_number=incident.incident_number,
        threat_type=incident.threat_type,
        source=incident.source,
        input_reference=incident.input_reference,
        risk_score=incident.risk_score,
        severity=incident.severity,
        action=incident.action,
        reasons=incident.reasons or [],
        status=incident.status,
        resolution_note=incident.resolution_note,
        analysis_id=str(incident.analysis_id) if incident.analysis_id else None,
        user_id=str(incident.user_id) if incident.user_id else None,
        created_at=incident.created_at,
        resolved_at=incident.resolved_at,
    )


@router.patch(
    "/{incident_id}",
    response_model=IncidentDetailResponse,
    summary="Update incident status and resolution notes",
)
async def update_incident_status(
    incident_id: str,
    update_req: IncidentUpdateStatusRequest,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user_optional),
):
    """Change incident status to OPEN, REVIEWING, RESOLVED, or FALSE_POSITIVE."""
    query = db.query(SecurityIncident)

    try:
        uid = uuid.UUID(incident_id)
        query = query.filter(SecurityIncident.id == uid)
    except ValueError:
        query = query.filter(SecurityIncident.incident_number == incident_id)

    incident = query.first()
    if not incident:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Incident not found",
        )

    valid_statuses = ("OPEN", "REVIEWING", "RESOLVED", "FALSE_POSITIVE")
    new_status = update_req.status.upper()
    if new_status not in valid_statuses:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid status '{update_req.status}'. Must be one of: {valid_statuses}",
        )

    incident.status = new_status
    if update_req.resolution_note is not None:
        incident.resolution_note = update_req.resolution_note

    if new_status in ("RESOLVED", "FALSE_POSITIVE"):
        incident.resolved_at = datetime.now(timezone.utc)
    else:
        incident.resolved_at = None

    db.commit()
    db.refresh(incident)

    return IncidentDetailResponse(
        id=str(incident.id),
        incident_number=incident.incident_number,
        threat_type=incident.threat_type,
        source=incident.source,
        input_reference=incident.input_reference,
        risk_score=incident.risk_score,
        severity=incident.severity,
        action=incident.action,
        reasons=incident.reasons or [],
        status=incident.status,
        resolution_note=incident.resolution_note,
        analysis_id=str(incident.analysis_id) if incident.analysis_id else None,
        user_id=str(incident.user_id) if incident.user_id else None,
        created_at=incident.created_at,
        resolved_at=incident.resolved_at,
    )

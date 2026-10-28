"""
Reports routes — analysis history, quiz history for authenticated users.
"""

import uuid
from typing import Optional, Dict, Any, List
from fastapi import APIRouter, Depends, HTTPException, status, Query, Response
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from sqlalchemy import desc

from database import get_db
from dependencies import get_current_user_required, get_current_user_optional
from services.pdf_generator import generate_forensic_pdf

from models.analysis import Analysis, AnalysisDetail
from models.quiz import QuizSession

from schemas.analysis import (
    AnalysisSummary,
    AnalysisListResponse,
    AnalysisDetailResponse,
)
from schemas.quiz import (
    QuizResultResponse,
    QuizAnswerResult,
)

router = APIRouter()


# ═══════════════════════════════════════════
# ANALYSIS HISTORY
# ═══════════════════════════════════════════

@router.get(
    "/analyses",
    response_model=AnalysisListResponse,
    status_code=status.HTTP_200_OK,
    summary="Get analysis history",
    description="Returns paginated list of past analyses for the authenticated user.",
)
async def get_analysis_history(
    page: int = Query(1, ge=1, description="Page number"),
    limit: int = Query(20, ge=1, le=100, description="Items per page"),
    type: str = Query(None, description="Filter by type: email, url, qr, audio, video"),
    current_user=Depends(get_current_user_required),
    db: Session = Depends(get_db),
):
    query = (
        db.query(Analysis)
        .filter(Analysis.user_id == current_user.id)
    )

    if type:
        if type not in ("email", "url", "qr", "audio", "video"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid type filter '{type}'. Must be: email, url, qr, audio, video",
            )
        query = query.filter(Analysis.type == type)

    total = query.count()
    offset = (page - 1) * limit

    analyses = (
        query
        .order_by(desc(Analysis.created_at))
        .offset(offset)
        .limit(limit)
        .all()
    )

    return AnalysisListResponse(
        total=total,
        page=page,
        limit=limit,
        analyses=[
            AnalysisSummary(
                id=str(a.id),
                type=a.type,
                risk_score=a.risk_score,
                risk_label=a.risk_label,
                explanation_summary=a.explanation_summary or "",
                processing_time_ms=a.processing_time_ms,
                is_demo=a.is_demo,
                created_at=a.created_at,
            )
            for a in analyses
        ],
    )


@router.get(
    "/analyses/{analysis_id}",
    response_model=AnalysisDetailResponse,
    status_code=status.HTTP_200_OK,
    summary="Get analysis detail",
    description="Returns full detail of a specific past analysis.",
)
async def get_analysis_detail(
    analysis_id: str,
    current_user=Depends(get_current_user_required),
    db: Session = Depends(get_db),
):
    try:
        aid = uuid.UUID(analysis_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid analysis ID format",
        )

    analysis = (
        db.query(Analysis)
        .filter(
            Analysis.id == aid,
            Analysis.user_id == current_user.id,
        )
        .first()
    )

    if not analysis:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Analysis not found",
        )

    detail = (
        db.query(AnalysisDetail)
        .filter(AnalysisDetail.analysis_id == aid)
        .first()
    )

    return AnalysisDetailResponse(
        id=str(analysis.id),
        type=analysis.type,
        risk_score=analysis.risk_score,
        risk_label=analysis.risk_label,
        explanation_summary=analysis.explanation_summary or "",
        model_scores=analysis.model_scores,
        processing_time_ms=analysis.processing_time_ms,
        raw_metadata=detail.raw_metadata if detail else None,
        highlighted_elements=detail.highlighted_elements if detail else None,
        contributing_factors=detail.contributing_factors if detail else None,
        is_demo=analysis.is_demo,
        created_at=analysis.created_at,
    )


class ExportPdfRequest(BaseModel):
    analysis_id: Optional[str] = None
    type: Optional[str] = "Analysis"
    risk_score: int = 0
    risk_label: str = "safe"
    explanation_summary: Optional[str] = None
    explanation: Optional[Dict[str, Any]] = None
    model_scores: Optional[Dict[str, Any]] = None
    contributing_factors: Optional[List[Dict[str, Any]]] = None
    raw_metadata: Optional[Dict[str, Any]] = None
    input_hash: Optional[str] = None


@router.post(
    "/analyses/export-pdf",
    status_code=status.HTTP_200_OK,
    summary="Generate forensic PDF report from payload",
    description="Generates an official CERT-In aligned forensic incident PDF report from active analysis result.",
)
async def export_analysis_pdf(
    payload: ExportPdfRequest,
    current_user=Depends(get_current_user_optional),
):
    analysis_data = {
        "id": payload.analysis_id or str(uuid.uuid4()),
        "type": payload.type,
        "risk_score": payload.risk_score,
        "risk_label": payload.risk_label,
        "explanation_summary": payload.explanation_summary or (payload.explanation.get("summary") if payload.explanation else ""),
        "model_scores": payload.model_scores,
        "contributing_factors": payload.contributing_factors or (payload.explanation.get("contributing_factors") if payload.explanation else []),
        "input_hash": payload.input_hash,
    }
    detail_data = {
        "raw_metadata": payload.raw_metadata,
        "contributing_factors": payload.contributing_factors,
    }

    user_email = current_user.email if current_user else None
    pdf_bytes = generate_forensic_pdf(analysis_data, detail_data, user_email)

    safe_id = (payload.analysis_id or "evidence")[:8]
    filename = f"CyberShield_Forensic_Report_{safe_id}.pdf"

    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "Access-Control-Expose-Headers": "Content-Disposition",
        },
    )


@router.get(
    "/analyses/{analysis_id}/pdf",
    status_code=status.HTTP_200_OK,
    summary="Download forensic PDF report by analysis ID",
    description="Retrieves a past analysis from the database and returns a cryptographically signed forensic PDF report.",
)
async def get_analysis_pdf(
    analysis_id: str,
    current_user=Depends(get_current_user_optional),
    db: Session = Depends(get_db),
):
    try:
        aid = uuid.UUID(analysis_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid analysis ID format",
        )

    query = db.query(Analysis).filter(Analysis.id == aid)
    if current_user and getattr(current_user, "role", None) != "admin":
        # Allow if owned by current user or if anonymous/demo scan
        query = query.filter((Analysis.user_id == current_user.id) | (Analysis.user_id.is_(None)) | (Analysis.is_demo.is_(True)))
    
    analysis = query.first()
    if not analysis:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Analysis not found or access denied",
        )

    detail = (
        db.query(AnalysisDetail)
        .filter(AnalysisDetail.analysis_id == aid)
        .first()
    )

    analysis_data = {
        "id": str(analysis.id),
        "type": analysis.type,
        "risk_score": analysis.risk_score,
        "risk_label": analysis.risk_label,
        "explanation_summary": analysis.explanation_summary,
        "model_scores": analysis.model_scores,
        "created_at": analysis.created_at,
        "input_hash": getattr(analysis, "input_hash", None),
    }

    detail_data = {
        "raw_metadata": detail.raw_metadata if detail else None,
        "contributing_factors": detail.contributing_factors if detail else None,
    }

    user_email = current_user.email if current_user else None
    pdf_bytes = generate_forensic_pdf(analysis_data, detail_data, user_email)

    safe_id = str(analysis.id)[:8]
    filename = f"CyberShield_Forensic_Report_{safe_id}.pdf"

    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "Access-Control-Expose-Headers": "Content-Disposition",
        },
    )


# ═══════════════════════════════════════════
# QUIZ HISTORY
# ═══════════════════════════════════════════

@router.get(
    "/quizzes",
    status_code=status.HTTP_200_OK,
    summary="Get quiz history",
    description="Returns list of past quiz sessions for the authenticated user.",
)
async def get_quiz_history(
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    category: str = Query(None, description="Filter by category"),
    current_user=Depends(get_current_user_optional),
    db: Session = Depends(get_db),
):
    query = db.query(QuizSession).filter(QuizSession.completed_at.isnot(None))
    if current_user:
        query = query.filter(QuizSession.user_id == current_user.id)
    else:
        query = query.filter(QuizSession.user_id.is_(None))

    if category:
        query = query.filter(QuizSession.category == category)

    total = query.count()
    offset = (page - 1) * limit

    sessions = (
        query
        .order_by(desc(QuizSession.completed_at))
        .offset(offset)
        .limit(limit)
        .all()
    )

    return {
        "total": total,
        "page": page,
        "limit": limit,
        "sessions": [
            {
                "id": str(s.id),
                "category": s.category,
                "total_questions": s.total_questions,
                "correct_count": s.correct_count,
                "score_pct": s.score_pct,
                "badge_earned": s.badge_earned,
                "started_at": s.started_at.isoformat() if s.started_at else None,
                "completed_at": s.completed_at.isoformat() if s.completed_at else None,
            }
            for s in sessions
        ],
    }
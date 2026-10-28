"""
/analyze/*  routes  —  Email · URL · QR · Audio · Video · Image

Each endpoint:
  1. validates input
  2. calls the appropriate analyser  →  ai_score + rule_score
  3. passes result into ScoringEngine  →  75% AI / 25% rules
  4. persists to DB (if authenticated)
  5. returns JSON response
"""
from __future__ import annotations

import hashlib
import logging
import os
import time
import uuid
from typing import Optional

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy.orm import Session

from config import settings
from database import get_db
from dependencies import get_current_user_optional
from schemas.analysis import (
    AnalysisResponse,
    EmailAnalysisRequest,
    URLAnalysisRequest,
)
from services.scoring_engine import (
    ModalityResult,
    ScoringEngine,
    ScoringInput,
)
from services.explainability import ExplainabilityService
from security.prevention import prevention_engine
from security.incident_service import incident_service, get_threat_type

logger = logging.getLogger(__name__)
router = APIRouter()

# Instantiate services once
scoring_engine = ScoringEngine()
explainer = ExplainabilityService()


# ── Module-level Helpers (available to all endpoints) ──────────────────
def _save_temp(upload: UploadFile, suffix: str = "") -> str:
    """Write UploadFile to disk, return temp path."""
    os.makedirs(settings.UPLOAD_DIR, exist_ok=True)
    ext = suffix or os.path.splitext(upload.filename or "")[1]
    path = os.path.join(settings.UPLOAD_DIR, f"{uuid.uuid4()}{ext}")
    content = upload.file.read()
    with open(path, "wb") as f:
        f.write(content)
    return path


def _persist(db: Session, user, analysis_type: str, input_hash: str,
             score_out, explanation: dict, processing_ms: int,
             model_scores: dict, raw_metadata: dict, is_demo: bool = False):
    """Save analysis + detail rows to DB."""
    try:
        from models.analysis import Analysis, AnalysisDetail
        analysis = Analysis(
            id=uuid.uuid4(),
            user_id=user.id if user else None,
            type=analysis_type,
            input_hash=input_hash,
            risk_score=score_out.risk_score,
            risk_label=score_out.risk_label,
            explanation_summary=score_out.explanation_summary,
            model_scores=model_scores,
            processing_time_ms=processing_ms,
            is_demo=is_demo,
        )
        db.add(analysis)
        detail = AnalysisDetail(
            analysis_id=analysis.id,
            raw_metadata=raw_metadata,
            highlighted_elements=explanation.get("highlights", {}),
            contributing_factors=score_out.contributing_factors,
        )
        db.add(detail)
        db.commit()
        return str(analysis.id)
    except Exception as e:
        logger.warning("DB persist failed: %s", e)
        db.rollback()
        return str(uuid.uuid4())


# ═══════════════════════════════════════════════════════════════════
# POST /analyze/email
# ═══════════════════════════════════════════════════════════════════
@router.post("/email", response_model=None)
async def analyze_email(
    request: EmailAnalysisRequest,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user_optional),
):
    start = time.time()
    from services.email_analyzer import EmailAnalyzer

    analyzer = EmailAnalyzer()
    input_text = f"{request.subject}|{request.body}|{request.sender}|{'|'.join(request.urls or [])}"
    input_hash = hashlib.sha256(input_text.encode()).hexdigest()

    phish_result = analyzer.analyze(
        subject=request.subject,
        body=request.body,
        sender=request.sender,
        urls=request.urls or [],
    )

    modality = ModalityResult(
        ai_probability=phish_result.ai_probability,
        rule_score=phish_result.probability,
        confidence=phish_result.confidence,
        features=phish_result.features,
        flags=phish_result.flags,
        model_available=phish_result.model_available,
    )

    score_out = scoring_engine.compute(ScoringInput(
        phish_result=modality,
        analysis_type="email",
        contextual_flags=phish_result.flags,
    ))

    # Merge highlighted phrases, flagged URLs, and sender flags into features
    # so ExplainabilityService._email_highlights() can surface them in the response.
    email_features = {
        **phish_result.features,
        "flagged_phrases": phish_result.highlighted_phrases,
        "flagged_urls": phish_result.flagged_urls,
        "sender_flags": phish_result.sender_analysis,
    }
    explanation = explainer.generate("email", score_out, email_features)
    processing_ms = int((time.time() - start) * 1000)

    analysis_id = _persist(
        db, current_user, "email", input_hash, score_out,
        explanation, processing_ms,
        score_out.model_scores, phish_result.features,
    )

    prevention = prevention_engine.evaluate(
        risk_score=score_out.risk_score,
        analysis_type="email",
        contributing_factors=score_out.contributing_factors,
        risk_label=score_out.risk_label,
    )

    if prevention.should_create_incident:
        incident_id = incident_service.create_incident(
            db=db,
            source="email",
            threat_type=get_threat_type("email"),
            risk_score=score_out.risk_score,
            severity=prevention.severity,
            action=prevention.action,
            reasons=prevention.reasons,
            input_reference=f"Subject: {request.subject}",
            analysis_id=analysis_id,
            user_id=current_user.id if current_user else None,
        )
        prevention.incident_id = incident_id

    return {
        "analysis_id": analysis_id,
        "risk_score": score_out.risk_score,
        "risk_label": score_out.risk_label,
        "confidence_level": score_out.confidence_level,
        "calibration_note": score_out.calibration_note,
        "processing_time_ms": processing_ms,
        "action": prevention.action,
        "severity": prevention.severity,
        "reasons": prevention.reasons,
        "prevention": prevention.to_dict(),
        "explanation": {
            "summary": score_out.explanation_summary,
            **explanation,
            "contributing_factors": score_out.contributing_factors,
            "scoring_breakdown": score_out.breakdown,
        },
        "tip": explainer.get_tip("email", score_out.risk_label),
    }


# ═══════════════════════════════════════════════════════════════════
# POST /analyze/email/parse-eml
# ═══════════════════════════════════════════════════════════════════
@router.post("/email/parse-eml", response_model=None)
async def parse_eml_file(
    file: UploadFile = File(...),
):
    """
    Parse an uploaded .eml file and return extracted fields so the
    frontend can pre-populate the Manual Email Entry form.
    The actual threat analysis is NOT performed here — the user
    reviews the extracted data and submits via POST /analyze/email.
    """
    import email as _email
    import email.policy
    import re
    import html
    from email.header import decode_header as _decode_header

    # ── Validation ──
    MAX_EML_SIZE = 5 * 1024 * 1024  # 5 MB
    filename = (file.filename or "").lower()
    if not filename.endswith(".eml"):
        raise HTTPException(status_code=400, detail="Only .eml files are supported.")

    content = await file.read()
    if len(content) > MAX_EML_SIZE:
        raise HTTPException(status_code=413, detail="File too large. Maximum size is 5 MB.")
    if not content:
        raise HTTPException(status_code=400, detail="Uploaded file is empty.")

    # ── Parse ──
    try:
        msg = _email.message_from_bytes(content, policy=email.policy.compat32)
    except Exception:
        raise HTTPException(status_code=422, detail="Failed to parse .eml file. The file may be corrupted or in an unsupported format.")

    # ── Header decoder helper ──
    def _decode(raw: str | None) -> str:
        if not raw:
            return ""
        try:
            parts = _decode_header(raw)
            decoded = []
            for chunk, charset in parts:
                if isinstance(chunk, bytes):
                    decoded.append(chunk.decode(charset or "utf-8", errors="replace"))
                else:
                    decoded.append(str(chunk))
            return " ".join(decoded).strip()
        except Exception:
            return str(raw).strip()

    # ── Extract headers ──
    subject = _decode(msg.get("Subject", ""))
    sender  = _decode(msg.get("From", ""))
    to      = _decode(msg.get("To", ""))
    cc      = _decode(msg.get("Cc", ""))
    reply_to = _decode(msg.get("Reply-To", ""))
    date    = _decode(msg.get("Date", ""))

    # Normalise sender: strip display name, keep bare address
    addr_match = re.search(r"[\w.+\-]+@[\w.\-]+", sender)
    sender_email = addr_match.group(0) if addr_match else sender

    # ── Extract body parts ──
    plain_body = ""
    html_body  = ""
    if msg.is_multipart():
        for part in msg.walk():
            ct = part.get_content_type()
            cd = str(part.get("Content-Disposition", ""))
            if "attachment" in cd:
                continue
            charset = part.get_content_charset() or "utf-8"
            try:
                payload = part.get_payload(decode=True)
                if payload is None:
                    continue
                text = payload.decode(charset, errors="replace")
            except Exception:
                continue
            if ct == "text/plain" and not plain_body:
                plain_body = text
            elif ct == "text/html" and not html_body:
                html_body = text
    else:
        charset = msg.get_content_charset() or "utf-8"
        try:
            raw_payload = msg.get_payload(decode=True)
            if raw_payload:
                text = raw_payload.decode(charset, errors="replace")
                if msg.get_content_type() == "text/html":
                    html_body = text
                else:
                    plain_body = text
        except Exception:
            pass

    # Sanitise HTML: strip tags to derive a plain-text fallback,
    # and escape any remaining markup — never rendered as raw HTML.
    def _strip_tags(h: str) -> str:
        clean = re.sub(r"<[^>]+>", " ", h)
        clean = re.sub(r"\s+", " ", clean).strip()
        return html.unescape(clean)

    body = plain_body.strip() or _strip_tags(html_body)

    # ── Extract URLs from body ──
    url_pattern = re.compile(
        r"https?://[^\s\"'<>()\[\]{}\\]+"
    )
    urls_in_body = list(dict.fromkeys(url_pattern.findall(plain_body or _strip_tags(html_body))))

    # ── Extract IP addresses ──
    ip_pattern = re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b")
    ips = list(dict.fromkeys(ip_pattern.findall(plain_body + html_body)))

    # ── Extract domains from URLs ──
    domain_pattern = re.compile(r"https?://([^/\s\"'<>]+)")
    domains = list(dict.fromkeys(domain_pattern.findall(plain_body + html_body)))

    # ── List attachments (metadata only — never executed or returned as data) ──
    attachments = []
    if msg.is_multipart():
        for part in msg.walk():
            cd = str(part.get("Content-Disposition", ""))
            if "attachment" in cd:
                att_name = part.get_filename() or "unnamed"
                att_type = part.get_content_type() or "unknown"
                attachments.append({"name": att_name, "content_type": att_type})

    # ── Authentication results (SPF / DKIM / DMARC) ──
    auth_results_raw = msg.get("Authentication-Results", "")
    spf = dkim = dmarc = ""
    if auth_results_raw:
        for token, key in [("spf", "spf"), ("dkim", "dkim"), ("dmarc", "dmarc")]:
            m = re.search(rf"{token}=(\S+)", auth_results_raw, re.IGNORECASE)
            if m:
                if key == "spf":    spf   = m.group(1)
                elif key == "dkim": dkim  = m.group(1)
                elif key == "dmarc": dmarc = m.group(1)

    # ── Raw headers (safe string representation) ──
    raw_headers = {k: _decode(v) for k, v in msg.items()}

    return {
        "subject":      subject,
        "sender":       sender_email,
        "to":           to,
        "cc":           cc,
        "reply_to":     reply_to,
        "date":         date,
        "body":         body,
        "html_body":    _strip_tags(html_body),   # sanitised, no raw HTML
        "urls":         urls_in_body,
        "domains":      domains,
        "ips":          ips,
        "attachments":  attachments,
        "headers":      raw_headers,
        "auth": {
            "spf":   spf,
            "dkim":  dkim,
            "dmarc": dmarc,
        },
    }


# ═══════════════════════════════════════════════════════════════════
# POST /analyze/audio
# ═══════════════════════════════════════════════════════════════════
@router.post("/audio", response_model=None)
async def analyze_audio(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user_optional),
):
    from utils.file_validation import validate_audio_file
    from services.audio_analyzer import AudioAnalyzer

    start = time.time()
    await validate_audio_file(file)

    content = await file.read()
    await file.seek(0)
    temp_path = _save_temp(file)
    try:
        input_hash = hashlib.sha256(content).hexdigest()

        analyzer = AudioAnalyzer()
        audio_result = analyzer.analyze(temp_path)

        modality = ModalityResult(
            ai_probability=audio_result.ai_probability,
            rule_score=audio_result.rule_score,
            confidence=audio_result.confidence,
            features=audio_result.features,
            flags=audio_result.flags,
            model_available=audio_result.model_available,
        )

        score_out = scoring_engine.compute(ScoringInput(
            audio_result=modality,
            analysis_type="audio",
        ))

        explanation = explainer.generate("audio", score_out, audio_result.features)
        processing_ms = int((time.time() - start) * 1000)

        analysis_id = _persist(
            db, current_user, "audio", input_hash, score_out,
            explanation, processing_ms,
            score_out.model_scores, audio_result.metadata,
        )

        prevention = prevention_engine.evaluate(
            risk_score=score_out.risk_score,
            analysis_type="audio",
            contributing_factors=score_out.contributing_factors,
            risk_label=score_out.risk_label,
        )

        if prevention.should_create_incident:
            incident_id = incident_service.create_incident(
                db=db,
                source="audio",
                threat_type=get_threat_type("audio"),
                risk_score=score_out.risk_score,
                severity=prevention.severity,
                action=prevention.action,
                reasons=prevention.reasons,
                input_reference=file.filename or "audio_upload",
                analysis_id=analysis_id,
                user_id=current_user.id if current_user else None,
            )
            prevention.incident_id = incident_id

        return {
            "analysis_id": analysis_id,
            "risk_score": score_out.risk_score,
            "risk_label": score_out.risk_label,
            "confidence_level": score_out.confidence_level,
            "calibration_note": score_out.calibration_note,
            "processing_time_ms": processing_ms,
            "action": prevention.action,
            "severity": prevention.severity,
            "reasons": prevention.reasons,
            "prevention": prevention.to_dict(),
            "audio_metadata": audio_result.metadata,
            "explanation": {
                "summary": score_out.explanation_summary,
                **explanation,
                "contributing_factors": score_out.contributing_factors,
                "scoring_breakdown": score_out.breakdown,
            },
            "tip": explainer.get_tip("audio", score_out.risk_label),
        }
    finally:
        if os.path.exists(temp_path):
            os.unlink(temp_path)


# ═══════════════════════════════════════════════════════════════════
# POST /analyze/video
# ═══════════════════════════════════════════════════════════════════
@router.post("/video", response_model=None)
async def analyze_video(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user_optional),
):
    from utils.file_validation import validate_video_file
    from services.video_analyzer import VideoAnalyzer

    start = time.time()
    await validate_video_file(file)

    content = await file.read()
    await file.seek(0)
    temp_path = _save_temp(file)
    try:
        input_hash = hashlib.sha256(content).hexdigest()

        analyzer = VideoAnalyzer()
        video_result = analyzer.analyze(temp_path)

        modality = ModalityResult(
            ai_probability=video_result.ai_probability,
            rule_score=video_result.rule_score,
            confidence=video_result.confidence,
            features=video_result.features,
            flags=video_result.flags,
            model_available=video_result.model_available,
        )

        score_out = scoring_engine.compute(ScoringInput(
            video_result=modality,
            analysis_type="video",
        ))

        explanation = explainer.generate("video", score_out, video_result.features)
        processing_ms = int((time.time() - start) * 1000)

        analysis_id = _persist(
            db, current_user, "video", input_hash, score_out,
            explanation, processing_ms,
            score_out.model_scores, video_result.metadata,
        )

        prevention = prevention_engine.evaluate(
            risk_score=score_out.risk_score,
            analysis_type="video",
            contributing_factors=score_out.contributing_factors,
            risk_label=score_out.risk_label,
        )

        if prevention.should_create_incident:
            incident_id = incident_service.create_incident(
                db=db,
                source="video",
                threat_type=get_threat_type("video"),
                risk_score=score_out.risk_score,
                severity=prevention.severity,
                action=prevention.action,
                reasons=prevention.reasons,
                input_reference=file.filename or "video_upload",
                analysis_id=analysis_id,
                user_id=current_user.id if current_user else None,
            )
            prevention.incident_id = incident_id

        return {
            "analysis_id": analysis_id,
            "risk_score": score_out.risk_score,
            "risk_label": score_out.risk_label,
            "confidence_level": score_out.confidence_level,
            "calibration_note": score_out.calibration_note,
            "processing_time_ms": processing_ms,
            "action": prevention.action,
            "severity": prevention.severity,
            "reasons": prevention.reasons,
            "prevention": prevention.to_dict(),
            "video_metadata": video_result.metadata,
            "explanation": {
                "summary": score_out.explanation_summary,
                **explanation,
                "contributing_factors": score_out.contributing_factors,
                "scoring_breakdown": score_out.breakdown,
            },
            "tip": explainer.get_tip("video", score_out.risk_label),
        }
    finally:
        if os.path.exists(temp_path):
            os.unlink(temp_path)


# ═══════════════════════════════════════════════════════════════════
# POST /analyze/image
# ═══════════════════════════════════════════════════════════════════
@router.post("/image", response_model=None)
async def analyze_image(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user_optional),
):
    from utils.file_validation import validate_image_file
    from services.image_analyzer import ImageAnalyzer

    start = time.time()
    await validate_image_file(file)

    content = await file.read()
    await file.seek(0)
    temp_path = _save_temp(file)
    try:
        input_hash = hashlib.sha256(content).hexdigest()

        analyzer = ImageAnalyzer()
        image_result = analyzer.analyze(temp_path)

        modality = ModalityResult(
            ai_probability=image_result.ai_probability,
            rule_score=image_result.rule_score,
            confidence=image_result.confidence,
            features=image_result.features,
            flags=image_result.flags,
            model_available=image_result.model_available,
        )

        score_out = scoring_engine.compute(ScoringInput(
            video_result=modality,
            analysis_type="image",
        ))

        explanation = explainer.generate("image", score_out, image_result.features)
        processing_ms = int((time.time() - start) * 1000)

        analysis_id = _persist(
            db, current_user, "image", input_hash, score_out,
            explanation, processing_ms,
            score_out.model_scores, image_result.metadata,
        )

        prevention = prevention_engine.evaluate(
            risk_score=score_out.risk_score,
            analysis_type="image",
            contributing_factors=score_out.contributing_factors,
            risk_label=score_out.risk_label,
        )

        if prevention.should_create_incident:
            incident_id = incident_service.create_incident(
                db=db,
                source="image",
                threat_type=get_threat_type("image"),
                risk_score=score_out.risk_score,
                severity=prevention.severity,
                action=prevention.action,
                reasons=prevention.reasons,
                input_reference=file.filename or "image_upload",
                analysis_id=analysis_id,
                user_id=current_user.id if current_user else None,
            )
            prevention.incident_id = incident_id

        return {
            "analysis_id": analysis_id,
            "risk_score": score_out.risk_score,
            "risk_label": score_out.risk_label,
            "confidence_level": score_out.confidence_level,
            "calibration_note": score_out.calibration_note,
            "processing_time_ms": processing_ms,
            "action": prevention.action,
            "severity": prevention.severity,
            "reasons": prevention.reasons,
            "prevention": prevention.to_dict(),
            "image_metadata": image_result.metadata,
            "per_face_scores": image_result.per_face_scores,
            "ela_score": round(image_result.ela_score, 4),
            "forensic_signals": image_result.forensic_signals,
            "explanation": {
                "summary": score_out.explanation_summary,
                **explanation,
                "contributing_factors": score_out.contributing_factors,
                "scoring_breakdown": score_out.breakdown,
            },
            "tip": explainer.get_tip("image", score_out.risk_label),
        }
    finally:
        if os.path.exists(temp_path):
            os.unlink(temp_path)


# ═══════════════════════════════════════════════════════════════════
# POST /analyze/url
# ═══════════════════════════════════════════════════════════════════
@router.post("/url", response_model=None)
async def analyze_url(
    request: URLAnalysisRequest,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user_optional),
):
    start = time.time()
    # ── FIX: import the singleton instance directly, don't re-call it ──
    from services.url_analyzer import url_analyzer

    url_result = url_analyzer.analyze(request.url)

    modality = ModalityResult(
        ai_probability=url_result.probability,
        rule_score=getattr(url_result, "rule_score", url_result.probability),
        confidence=url_result.confidence,
        features=url_result.features,
        flags=url_result.flags,
        # Heuristic-only engine, no trained model backing this score — the
        # scoring engine uses this flag to skip AI-probability calibration,
        # which would otherwise distort/dampen a raw heuristic score.
        model_available=False,
    )

    score_out = scoring_engine.compute(ScoringInput(
        phish_result=modality,
        analysis_type="url",
        contextual_flags=url_result.flags,
    ))

    explanation = explainer.generate("url", score_out, url_result.features)
    processing_ms = int((time.time() - start) * 1000)
    input_hash = hashlib.sha256(request.url.encode()).hexdigest()

    analysis_id = _persist(
        db, current_user, "url", input_hash, score_out,
        explanation, processing_ms,
        score_out.model_scores, url_result.features,
    )

    prevention = prevention_engine.evaluate(
        risk_score=score_out.risk_score,
        analysis_type="url",
        contributing_factors=score_out.contributing_factors,
        risk_label=score_out.risk_label,
    )

    if prevention.should_create_incident:
        incident_id = incident_service.create_incident(
            db=db,
            source="url",
            threat_type=get_threat_type("url"),
            risk_score=score_out.risk_score,
            severity=prevention.severity,
            action=prevention.action,
            reasons=prevention.reasons,
            input_reference=request.url,
            analysis_id=analysis_id,
            user_id=current_user.id if current_user else None,
        )
        prevention.incident_id = incident_id

    return {
        "analysis_id": analysis_id,
        "url": request.url,
        "prediction": "malicious" if score_out.risk_label == "dangerous" else "suspicious" if score_out.risk_label == "suspicious" else "benign",
        "risk_score": score_out.risk_score,
        "risk_label": score_out.risk_label,
        "confidence_level": score_out.confidence_level,
        "calibration_note": score_out.calibration_note,
        "processing_time_ms": processing_ms,
        "action": prevention.action,
        "severity": prevention.severity,
        "reasons": prevention.reasons,
        "prevention": prevention.to_dict(),
        "explanation": {
            "summary": score_out.explanation_summary,
            **explanation,
            "contributing_factors": score_out.contributing_factors,
            "scoring_breakdown": score_out.breakdown,
        },
        "tip": explainer.get_tip("url", score_out.risk_label),
    }


# ═══════════════════════════════════════════════════════════════════
# POST /analyze/qr
# ═══════════════════════════════════════════════════════════════════
@router.post("/qr", response_model=None)
async def analyze_qr(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user_optional),
):
    from utils.file_validation import validate_image_file
    from services.qr_analyzer import qr_analyzer

    start = time.time()
    await validate_image_file(file)

    content = await file.read()
    await file.seek(0)
    temp_path = _save_temp(file)
    try:
        qr_result = qr_analyzer.analyze(temp_path)

        modality = ModalityResult(
            ai_probability=qr_result.probability,
            rule_score=getattr(qr_result, "rule_score", qr_result.probability),
            confidence=qr_result.confidence,
            features=qr_result.features,
            flags=qr_result.flags,
            # Heuristic-only engine (decoded payload run through the same
            # rule-based checks as URL analysis) — no trained model.
            model_available=False,
        )

        score_out = scoring_engine.compute(ScoringInput(
            phish_result=modality,
            analysis_type="qr",
            contextual_flags=qr_result.flags,
        ))

        explanation = explainer.generate("qr", score_out, qr_result.features)
        processing_ms = int((time.time() - start) * 1000)
        input_hash = hashlib.sha256(content).hexdigest()

        analysis_id = _persist(
            db, current_user, "qr", input_hash, score_out,
            explanation, processing_ms,
            score_out.model_scores, qr_result.features,
        )

        prevention = prevention_engine.evaluate(
            risk_score=score_out.risk_score,
            analysis_type="qr",
            contributing_factors=score_out.contributing_factors,
            risk_label=score_out.risk_label,
        )

        # Reference: decoded URL or raw data
        ref_data = (qr_result.decoded.get("raw") or file.filename or "qr_upload") if qr_result.decoded else file.filename or "qr_upload"

        if prevention.should_create_incident:
            incident_id = incident_service.create_incident(
                db=db,
                source="qr",
                threat_type=get_threat_type("qr"),
                risk_score=score_out.risk_score,
                severity=prevention.severity,
                action=prevention.action,
                reasons=prevention.reasons,
                input_reference=ref_data,
                analysis_id=analysis_id,
                user_id=current_user.id if current_user else None,
            )
            prevention.incident_id = incident_id

        return {
            "analysis_id": analysis_id,
            "decoded": qr_result.decoded,
            "risk_score": score_out.risk_score,
            "risk_label": score_out.risk_label,
            "confidence_level": score_out.confidence_level,
            "calibration_note": score_out.calibration_note,
            "processing_time_ms": processing_ms,
            "action": prevention.action,
            "severity": prevention.severity,
            "reasons": prevention.reasons,
            "prevention": prevention.to_dict(),
            "explanation": {
                "summary": score_out.explanation_summary,
                **explanation,
                "contributing_factors": score_out.contributing_factors,
                "scoring_breakdown": score_out.breakdown,
            },
            "tip": explainer.get_tip("qr", score_out.risk_label),
        }
    finally:
        if os.path.exists(temp_path):
            os.unlink(temp_path)
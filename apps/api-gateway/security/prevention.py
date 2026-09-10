"""
CyberShield AI — Prevention Engine
====================================

Converts a 0–100 risk score into a deterministic security action.

Policy:
  0–30   → ALLOW      / SAFE
  31–60  → WARN       / MEDIUM
  61–80  → RESTRICT   / HIGH
  81–100 → BLOCK      / CRITICAL

For media (audio/video/image): BLOCK becomes FLAG (no destructive action).
For email ≥81:                  BLOCK becomes QUARANTINE.

The Prevention Engine is a pure function — it NEVER modifies the ML
model's prediction and NEVER executes the threat (no URL visits, etc.).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import List, Optional

logger = logging.getLogger(__name__)


# ── Configurable Thresholds ────────────────────────────────────────
# Change these here and they propagate everywhere in the app.

ALLOW_MAX    = 30   # 0–30   → ALLOW
WARN_MAX     = 60   # 31–60  → WARN
RESTRICT_MAX = 80   # 61–80  → RESTRICT
BLOCK_MIN    = 81   # 81–100 → BLOCK


# ── Media sources that must never be auto-blocked ─────────────────
MEDIA_SOURCES = {"audio", "video", "image"}


# ── Severity labels ───────────────────────────────────────────────
def _severity(score: int) -> str:
    if score <= ALLOW_MAX:
        return "SAFE"
    elif score <= WARN_MAX:
        return "MEDIUM"
    elif score <= RESTRICT_MAX:
        return "HIGH"
    else:
        return "CRITICAL"


# ── Result dataclass ──────────────────────────────────────────────

@dataclass
class PreventionResult:
    """Output of the Prevention Engine for one analysis."""

    action: str           # ALLOW | WARN | RESTRICT | BLOCK | QUARANTINE | FLAG
    severity: str         # SAFE | MEDIUM | HIGH | CRITICAL
    risk_score: int
    message: str
    reasons: List[str] = field(default_factory=list)
    should_create_incident: bool = False
    incident_id: Optional[str] = None   # filled in by incident_service

    def to_dict(self) -> dict:
        return {
            "action": self.action,
            "severity": self.severity,
            "risk_score": self.risk_score,
            "message": self.message,
            "reasons": self.reasons,
            "should_create_incident": self.should_create_incident,
            "incident_id": self.incident_id,
        }


# ── Messages ──────────────────────────────────────────────────────

_MESSAGES = {
    "ALLOW":      "Content appears safe. No threats detected.",
    "WARN":       "This content has suspicious characteristics. Proceed with caution.",
    "RESTRICT":   "Access to this content should be restricted due to high risk indicators.",
    "BLOCK":      "This content has been identified as highly dangerous and access has been blocked.",
    "QUARANTINE": "This content has been quarantined due to strong phishing indicators.",
    "FLAG":       "This media has been flagged for human review due to potential manipulation.",
}


# ── Engine ────────────────────────────────────────────────────────

class PreventionEngine:
    """
    Stateless prevention decision engine.
    Call evaluate() after every analysis.
    """

    def evaluate(
        self,
        risk_score: int,
        analysis_type: str,
        contributing_factors: List[dict] | None = None,
        risk_label: str = "",
    ) -> PreventionResult:
        """
        Determine the prevention action for a given risk score.

        Args:
            risk_score:          0–100 from ScoringEngine.
            analysis_type:       "url" | "email" | "qr" | "audio" | "video" | "image"
            contributing_factors: Raw factor list from ScoringEngine (used for reasons).
            risk_label:          "safe" | "suspicious" | "dangerous" (for logging).

        Returns:
            PreventionResult with action, severity, message, reasons.
        """
        score      = max(0, min(100, risk_score))
        severity   = _severity(score)
        is_media   = analysis_type in MEDIA_SOURCES
        is_email   = analysis_type == "email"

        # ── Core action decision ──────────────────────────────────
        if score <= ALLOW_MAX:
            action = "ALLOW"
        elif score <= WARN_MAX:
            action = "WARN"
        elif score <= RESTRICT_MAX:
            action = "RESTRICT"
        else:
            # score >= 81 — would be BLOCK, but adapt for context:
            if is_media:
                action = "FLAG"        # Never auto-block media
            elif is_email:
                action = "QUARANTINE"  # Simulate email quarantine
            else:
                action = "BLOCK"

        message = _MESSAGES[action]

        # ── Reason extraction ─────────────────────────────────────
        reasons = self._extract_reasons(
            contributing_factors or [], score, analysis_type
        )

        # ── Incident threshold ────────────────────────────────────
        # Create incidents for BLOCK, QUARANTINE, FLAG, and RESTRICT≥70
        should_create = action in ("BLOCK", "QUARANTINE", "FLAG") or (
            action == "RESTRICT" and score >= 70
        )

        result = PreventionResult(
            action=action,
            severity=severity,
            risk_score=score,
            message=message,
            reasons=reasons,
            should_create_incident=should_create,
        )

        logger.info(
            "Prevention decision: score=%d type=%s → action=%s severity=%s incident=%s",
            score, analysis_type, action, severity, should_create,
        )

        return result

    # ------------------------------------------------------------------
    def _extract_reasons(
        self,
        factors: List[dict],
        score: int,
        analysis_type: str,
    ) -> List[str]:
        """Build a human-readable list of reasons from contributing factors."""
        reasons: List[str] = []

        for f in factors:
            description = f.get("description", "")
            raw_score   = f.get("raw_score") or f.get("calibrated_score", 0)
            factor_name = f.get("factor", "")

            # Only include factors with meaningful contribution
            if not description:
                continue
            if raw_score and float(raw_score) < 0.15:
                continue

            # Skip very technical model-weight descriptions
            if "weight" in description.lower() and "calibrated" in description.lower():
                continue

            # Convert factor descriptions to user-friendly strings
            readable = self._factor_to_reason(factor_name, description)
            if readable and readable not in reasons:
                reasons.append(readable)

        # Fallback reasons when factors are sparse
        if not reasons:
            reasons = self._fallback_reasons(score, analysis_type)

        return reasons[:6]  # Cap at 6 reasons

    def _factor_to_reason(self, factor: str, description: str) -> str:
        """Convert a raw factor name + description to a user-friendly string."""
        # Rule-based adjustments produce the clearest descriptions
        if "rule_adjustment" in factor:
            # Strip leading score adjustments like "(+20)"
            import re
            clean = re.sub(r"\s*\([+\-]?\d+\)\s*$", "", description).strip()
            return clean if clean else description

        # Heuristic and AI factor descriptions
        if "Suspicious domain" in description:
            return "Suspicious domain detected"
        if "Credential" in description or "credential" in description:
            return "Credential harvesting indicators found"
        if "phishing" in description.lower():
            return "Phishing pattern detected"
        if "Bank" in description or "bank" in description:
            return "Bank name abuse in non-official domain"
        if "UPI" in description or "upi" in description:
            return "UPI/payment fraud indicators"
        if "Urgency" in description or "urgency" in description:
            return "Urgency language used to pressure action"
        if "Non-HTTPS" in description or "non_https" in description:
            return "Insecure (non-HTTPS) link"
        if "URL shortener" in description.lower():
            return "URL shortener masking destination"
        if "spectral" in description.lower() or "Mel" in description:
            return "Abnormal audio spectral patterns"
        if "pitch" in description.lower():
            return "Unnatural voice pitch detected"
        if "face" in description.lower():
            return "Facial inconsistency across frames"
        if "temporal" in description.lower():
            return "Temporal manipulation artifacts"

        # Generic fallback — use description as-is if it's short
        return description if len(description) < 80 else ""

    def _fallback_reasons(self, score: int, analysis_type: str) -> List[str]:
        """Generic fallback reasons when no factor detail is available."""
        type_map = {
            "url":   ["Suspicious URL structure", "High-risk domain indicators"],
            "email": ["Phishing language patterns", "Suspicious sender domain"],
            "qr":    ["Malicious QR payload", "Suspicious embedded URL"],
            "audio": ["Synthetic voice characteristics", "Abnormal audio patterns"],
            "video": ["Facial manipulation artifacts", "Video deepfake indicators"],
            "image": ["AI-generated image characteristics", "Facial inconsistency"],
        }
        return type_map.get(analysis_type, [f"Risk score: {score}/100"])


# ── Singleton ────────────────────────────────────────────────────────
prevention_engine = PreventionEngine()

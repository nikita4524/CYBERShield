"""
IoT risk scoring — rules-only, mirrors scoring_engine output shape.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List

from config import settings
from services.iot_rules import RULE_SCORES


@dataclass
class IoTScoringOutput:
    risk_score: int = 0
    risk_label: str = "safe"
    contributing_factors: List[Dict] = field(default_factory=list)
    explanation_summary: str = ""


class IoTScoringService:
    """Compute device risk from triggered rule contributions."""

    def __init__(
        self,
        safe_threshold: int | None = None,
        dangerous_threshold: int | None = None,
    ):
        self.safe_threshold = safe_threshold or settings.SAFE_THRESHOLD
        self.dangerous_threshold = dangerous_threshold or settings.DANGEROUS_THRESHOLD

    def compute(self, triggered_rules: List[str]) -> IoTScoringOutput:
        if not triggered_rules:
            return IoTScoringOutput(
                risk_score=0,
                risk_label="safe",
                explanation_summary="No active IoT security alerts. Device appears normal.",
            )

        unique_rules = list(dict.fromkeys(triggered_rules))
        total = 0
        factors: List[Dict] = []

        for rule_id in unique_rules:
            contribution = RULE_SCORES.get(rule_id, 10)
            total += contribution
            factors.append(
                {
                    "factor": rule_id,
                    "contribution": contribution,
                    "description": f"Rule '{rule_id}' triggered",
                }
            )

        risk_score = min(100, total)
        risk_label = self._label_for_score(risk_score)
        summary = self._build_summary(risk_label, unique_rules, risk_score)

        return IoTScoringOutput(
            risk_score=risk_score,
            risk_label=risk_label,
            contributing_factors=factors,
            explanation_summary=summary,
        )

    def _label_for_score(self, score: int) -> str:
        if score <= self.safe_threshold:
            return "safe"
        if score >= self.dangerous_threshold:
            return "dangerous"
        return "suspicious"

    @staticmethod
    def _build_summary(label: str, rules: List[str], score: int) -> str:
        rule_names = ", ".join(rules)
        if label == "safe":
            return "Device telemetry looks normal with no significant IoT threats detected."
        if label == "suspicious":
            return (
                f"Moderate IoT risk (score {score}/100). "
                f"Triggered rules: {rule_names}. Review device settings."
            )
        return (
            f"High IoT risk (score {score}/100). "
            f"Triggered rules: {rule_names}. Isolate the device and change network credentials."
        )


iot_scoring_service = IoTScoringService()

from __future__ import annotations

from dataclasses import dataclass
import math


@dataclass(slots=True)
class ImpactResult:
    score: int
    level: str
    rationale: list[str]


def score_to_level(score: int) -> str:
    if score <= 25:
        return "LOW"
    if score <= 50:
        return "MEDIUM"
    if score <= 75:
        return "HIGH"
    return "CRITICAL"


def calculate_customer_impact(
    delay_minutes: float,
    violation_count: int,
    service_duration_minutes: float,
    csat_score: float | None,
    urgency_level: str,
    severity: str,
    repeat_visit_risk: bool = False,
) -> ImpactResult:
    score = min(40, int(delay_minutes * 0.45))
    score += min(18, violation_count * 8)
    score += min(12, int(max(service_duration_minutes - 240, 0) / 30) * 2)
    if repeat_visit_risk:
        score += 10
    if csat_score is not None and not math.isnan(csat_score):
        score += max(0, int((5 - csat_score) * 5))
    urgency_bonus = {"LOW": 0, "MEDIUM": 6, "HIGH": 12}.get(urgency_level.upper(), 4)
    score += urgency_bonus
    severity_bonus = {"LOW": 0, "MEDIUM": 6, "HIGH": 12, "CRITICAL": 18}.get(severity.upper(), 0)
    score += severity_bonus
    score = max(0, min(100, score))
    rationale = [
        f"Delay contribution: {delay_minutes:.0f} minutes",
        f"Violation count contribution: {violation_count}",
        f"Service duration contribution: {service_duration_minutes:.0f} minutes",
        f"Urgency level: {urgency_level}",
        f"Severity: {severity}",
    ]
    if csat_score is not None and not math.isnan(csat_score):
        rationale.append(f"Historical CSAT: {csat_score:.1f}")
    if repeat_visit_risk:
        rationale.append("Repeat visit risk observed")
    return ImpactResult(score=score, level=score_to_level(score), rationale=rationale)

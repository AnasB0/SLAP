from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

import pandas as pd

from src.analysis.root_cause import analyze_root_cause
from src.database.connection import DEFAULT_DB_PATH, get_connection
from src.database.repository import WarehouseRepository
from src.sla.impact import ImpactResult, calculate_customer_impact


@dataclass(slots=True)
class SlaEvaluation:
    policy_id: str
    violation_type: str
    threshold_minutes: float
    actual_minutes: float
    difference_minutes: float
    status: str
    severity: str


class SLAEngine:
    def __init__(self, db_path: str | Path = DEFAULT_DB_PATH) -> None:
        self.db_path = Path(db_path)
        self.repository = WarehouseRepository(db_path)

    @staticmethod
    def _status(actual: float, threshold: float, at_risk_ratio: float) -> str:
        if actual > threshold:
            return "VIOLATED"
        if actual >= threshold * at_risk_ratio:
            return "AT_RISK"
        return "ON_TRACK"

    @staticmethod
    def _severity(difference: float, threshold: float) -> str:
        if difference <= 0:
            return "LOW"
        ratio = difference / max(threshold, 1)
        if ratio < 0.15:
            return "LOW"
        if ratio < 0.35:
            return "MEDIUM"
        if ratio < 0.75:
            return "HIGH"
        return "CRITICAL"

    @staticmethod
    def _build_event_map(events_df: pd.DataFrame) -> dict[str, pd.Timestamp]:
        return {
            row.event_type: pd.Timestamp(row.event_timestamp)
            for row in events_df.sort_values("event_timestamp").itertuples()
        }

    def evaluate_ro(self, ro_id: str) -> list[dict[str, Any]]:
        ro = self.repository.get_repair_order(ro_id)
        if not ro:
            return []
        events_df = self.repository.get_service_events(ro_id)
        part_df = self.repository.get_part_requests(ro_id)
        policies_df = self.repository.query_df("SELECT * FROM dim_sla_policy ORDER BY policy_id")
        csat_df = self.repository.query_df("SELECT AVG(score) AS avg_score FROM fact_customer_satisfaction WHERE ro_id = ?", [ro_id])
        avg_csat = None if csat_df.empty else csat_df.iloc[0]["avg_score"]
        event_map = self._build_event_map(events_df)
        root_cause = analyze_root_cause(events_df, part_df)

        def minutes_between(start: str, end: str) -> float | None:
            if start not in event_map or end not in event_map:
                return None
            return round((event_map[end] - event_map[start]).total_seconds() / 60.0, 2)

        actuals: dict[str, float | None] = {
            "appointment_wait": minutes_between("APPOINTMENT", "CUSTOMER_CHECK_IN"),
            "inspection_start": minutes_between("CUSTOMER_CHECK_IN", "INSPECTION_STARTED"),
            "technician_assignment": minutes_between("INSPECTION_COMPLETED", "TECHNICIAN_ASSIGNED"),
            "parts_wait": None,
            "repair_duration": minutes_between("REPAIR_STARTED", "REPAIR_COMPLETED"),
            "qc_start": minutes_between("REPAIR_COMPLETED", "QC_STARTED"),
            "customer_notification": minutes_between("VEHICLE_READY", "CUSTOMER_NOTIFIED"),
            "delivery_wait": minutes_between("CUSTOMER_ARRIVED_FOR_PICKUP", "VEHICLE_DELIVERED"),
            "overall_service_duration": minutes_between("CUSTOMER_CHECK_IN", "VEHICLE_READY"),
        }
        if not part_df.empty:
            first_part = part_df.sort_values("requested_at").iloc[0]
            if pd.notna(first_part["received_at"]):
                actuals["parts_wait"] = round((pd.Timestamp(first_part["received_at"]) - pd.Timestamp(first_part["requested_at"])).total_seconds() / 60.0, 2)
            else:
                actuals["parts_wait"] = 90.0

        repeat_visit_risk = ro["concern"] in {"Battery warning", "Hybrid system alert", "Check engine light"}
        evaluations: list[dict[str, Any]] = []
        for policy in policies_df.itertuples():
            actual = actuals.get(policy.policy_id)
            if actual is None:
                continue
            status = self._status(actual, policy.threshold_minutes, policy.at_risk_ratio)
            difference = round(actual - policy.threshold_minutes, 2)
            severity = self._severity(difference, policy.threshold_minutes)
            impact: ImpactResult = calculate_customer_impact(
                delay_minutes=max(difference, 0),
                violation_count=1 if status != "ON_TRACK" else 0,
                service_duration_minutes=actuals.get("overall_service_duration") or 0.0,
                csat_score=avg_csat,
                urgency_level=ro["urgency_level"],
                severity=severity,
                repeat_visit_risk=repeat_visit_risk,
            )
            evaluations.append(
                {
                    "violation_id": f"VI-{ro_id}-{policy.policy_id}",
                    "ro_id": ro_id,
                    "policy_id": policy.policy_id,
                    "violation_type": policy.policy_name,
                    "severity": severity,
                    "threshold_minutes": float(policy.threshold_minutes),
                    "actual_minutes": float(actual),
                    "difference_minutes": difference,
                    "detected_at": datetime.now(UTC),
                    "status": status,
                    "customer_impact": impact.level,
                    "customer_impact_score": impact.score,
                    "root_cause": root_cause.primary_root_cause,
                }
            )
        return evaluations

    def refresh_sla_states(self) -> None:
        ro_ids = self.repository.query_df("SELECT ro_id FROM fact_repair_order ORDER BY ro_id")["ro_id"].tolist()
        conn = get_connection(self.db_path)
        try:
            conn.execute("DELETE FROM fact_sla_violation")
            rows: list[tuple[Any, ...]] = []
            for ro_id in ro_ids:
                for result in self.evaluate_ro(ro_id):
                    if result["status"] == "ON_TRACK":
                        continue
                    rows.append(
                        (
                            result["violation_id"],
                            result["ro_id"],
                            result["policy_id"],
                            result["violation_type"],
                            result["severity"],
                            result["threshold_minutes"],
                            result["actual_minutes"],
                            result["difference_minutes"],
                            result["detected_at"],
                            result["status"],
                            result["customer_impact"],
                            result["customer_impact_score"],
                            result["root_cause"],
                        )
                    )
            if rows:
                conn.executemany(
                    """
                    INSERT INTO fact_sla_violation VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    rows,
                )
        finally:
            conn.close()

    def get_top_violations(self, limit: int = 10) -> pd.DataFrame:
        return self.repository.query_df(
            """
            SELECT * FROM fact_sla_violation
            WHERE status IN ('AT_RISK', 'VIOLATED')
            ORDER BY customer_impact_score DESC, difference_minutes DESC
            LIMIT ?
            """,
            [limit],
        )

    def mark_mitigated(self, violation_id: str) -> None:
        self.repository.execute(
            "UPDATE fact_sla_violation SET status = 'MITIGATED' WHERE violation_id = ? AND status <> 'MITIGATED'",
            [violation_id],
        )

    def create_violation_if_missing(self, ro_id: str, policy_id: str) -> str:
        violation_id = f"VI-{ro_id}-{policy_id}"
        existing = self.repository.query_df("SELECT violation_id FROM fact_sla_violation WHERE violation_id = ?", [violation_id])
        if not existing.empty:
            return violation_id
        evaluated = [item for item in self.evaluate_ro(ro_id) if item["policy_id"] == policy_id and item["status"] != "ON_TRACK"]
        if not evaluated:
            return violation_id
        result = evaluated[0]
        self.repository.execute(
            """
            INSERT INTO fact_sla_violation VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                result["violation_id"], result["ro_id"], result["policy_id"], result["violation_type"],
                result["severity"], result["threshold_minutes"], result["actual_minutes"], result["difference_minutes"],
                result["detected_at"], result["status"], result["customer_impact"], result["customer_impact_score"],
                result["root_cause"],
            ],
        )
        return violation_id

    @staticmethod
    def make_mitigation_id() -> str:
        return f"MIT-{uuid4().hex[:10].upper()}"

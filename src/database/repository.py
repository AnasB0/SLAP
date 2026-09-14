from __future__ import annotations

from collections.abc import Iterable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

import pandas as pd
import duckdb

from src.database.connection import DEFAULT_DB_PATH, get_connection
from src.database.queries import KPI_QUERY


class WarehouseRepository:
    """Typed access layer for DuckDB-backed warehouse queries."""

    def __init__(self, db_path: str | Path = DEFAULT_DB_PATH) -> None:
        self.db_path = Path(db_path)

    def query_df(self, sql: str, params: Iterable[Any] | None = None) -> pd.DataFrame:
        conn = get_connection(self.db_path)
        try:
            result = conn.execute(sql, params or []).fetchdf()
        finally:
            conn.close()
        return result

    def execute(self, sql: str, params: Iterable[Any] | None = None) -> None:
        conn = get_connection(self.db_path)
        try:
            conn.execute(sql, params or [])
        finally:
            conn.close()

    def execute_many(self, sql: str, values: list[tuple[Any, ...]]) -> None:
        conn = get_connection(self.db_path)
        try:
            conn.executemany(sql, values)
        finally:
            conn.close()

    def table_count(self, table_name: str) -> int:
        return int(self.query_df(f"SELECT COUNT(*) AS count FROM {table_name}").iloc[0]["count"])

    def get_repair_order(self, ro_id: str) -> dict[str, Any] | None:
        df = self.query_df(
            """
            SELECT ro.*, c.customer_name, v.make, v.model, v.model_year, v.urgency_level, adv.advisor_name, tech.technician_name
            FROM fact_repair_order ro
            JOIN dim_customer c ON c.customer_id = ro.customer_id
            JOIN dim_vehicle v ON v.vehicle_id = ro.vehicle_id
            JOIN dim_service_advisor adv ON adv.advisor_id = ro.advisor_id
            LEFT JOIN dim_technician tech ON tech.technician_id = ro.technician_id
            WHERE ro.ro_id = ?
            """,
            [ro_id],
        )
        if df.empty:
            return None
        return df.iloc[0].to_dict()

    def get_repair_orders(self) -> pd.DataFrame:
        return self.query_df(
            """
            SELECT ro.ro_id,
                   c.customer_name,
                   CONCAT(v.make, ' ', v.model, ' ', v.model_year) AS vehicle,
                   adv.advisor_name,
                   ro.ro_status,
                   ro.service_type,
                   ro.priority,
                   ro.opened_at,
                   ro.promised_ready_at
            FROM fact_repair_order ro
            JOIN dim_customer c ON c.customer_id = ro.customer_id
            JOIN dim_vehicle v ON v.vehicle_id = ro.vehicle_id
            JOIN dim_service_advisor adv ON adv.advisor_id = ro.advisor_id
            ORDER BY ro.opened_at DESC
            """
        )

    def get_customer(self, customer_id: int) -> dict[str, Any] | None:
        df = self.query_df("SELECT * FROM dim_customer WHERE customer_id = ?", [customer_id])
        return None if df.empty else df.iloc[0].to_dict()

    def get_vehicle(self, vehicle_id: int) -> dict[str, Any] | None:
        df = self.query_df("SELECT * FROM dim_vehicle WHERE vehicle_id = ?", [vehicle_id])
        return None if df.empty else df.iloc[0].to_dict()

    def get_advisor(self, advisor_id: int) -> dict[str, Any] | None:
        df = self.query_df("SELECT * FROM dim_service_advisor WHERE advisor_id = ?", [advisor_id])
        return None if df.empty else df.iloc[0].to_dict()

    def get_technician(self, technician_id: int) -> dict[str, Any] | None:
        df = self.query_df("SELECT * FROM dim_technician WHERE technician_id = ?", [technician_id])
        return None if df.empty else df.iloc[0].to_dict()

    def get_service_events(self, ro_id: str) -> pd.DataFrame:
        return self.query_df(
            "SELECT * FROM fact_service_event WHERE ro_id = ? ORDER BY event_timestamp ASC",
            [ro_id],
        )

    def get_part_requests(self, ro_id: str) -> pd.DataFrame:
        return self.query_df(
            """
            SELECT pr.*, p.part_name, p.category
            FROM fact_part_request pr
            JOIN dim_part p ON p.part_id = pr.part_id
            WHERE pr.ro_id = ?
            ORDER BY requested_at ASC
            """,
            [ro_id],
        )

    def get_sla_violations(self, ro_id: str | None = None) -> pd.DataFrame:
        base = """
            SELECT vi.*, c.customer_name,
                   CONCAT(v.make, ' ', v.model, ' ', v.model_year) AS vehicle,
                   adv.advisor_name,
                   ro.concern
            FROM fact_sla_violation vi
            JOIN fact_repair_order ro ON ro.ro_id = vi.ro_id
            JOIN dim_customer c ON c.customer_id = ro.customer_id
            JOIN dim_vehicle v ON v.vehicle_id = ro.vehicle_id
            JOIN dim_service_advisor adv ON adv.advisor_id = ro.advisor_id
        """
        if ro_id:
            return self.query_df(base + " WHERE vi.ro_id = ? ORDER BY vi.customer_impact_score DESC", [ro_id])
        return self.query_df(base + " ORDER BY vi.customer_impact_score DESC, vi.detected_at DESC")

    def get_violation(self, violation_id: str) -> dict[str, Any] | None:
        df = self.query_df(
            """
            SELECT vi.*, ro.customer_id, ro.advisor_id, ro.vehicle_id, ro.ro_status, ro.promised_ready_at,
                   c.customer_name,
                   CONCAT(v.make, ' ', v.model, ' ', v.model_year) AS vehicle,
                   adv.advisor_name
            FROM fact_sla_violation vi
            JOIN fact_repair_order ro ON ro.ro_id = vi.ro_id
            JOIN dim_customer c ON c.customer_id = ro.customer_id
            JOIN dim_vehicle v ON v.vehicle_id = ro.vehicle_id
            JOIN dim_service_advisor adv ON adv.advisor_id = ro.advisor_id
            WHERE vi.violation_id = ?
            """,
            [violation_id],
        )
        return None if df.empty else df.iloc[0].to_dict()

    def get_primary_violation_for_ro(self, ro_id: str) -> dict[str, Any] | None:
        df = self.query_df(
            """
            SELECT *
            FROM fact_sla_violation
            WHERE ro_id = ?
            ORDER BY customer_impact_score DESC, difference_minutes DESC
            LIMIT 1
            """,
            [ro_id],
        )
        return None if df.empty else df.iloc[0].to_dict()

    def get_kpis(self) -> dict[str, Any]:
        df = self.query_df(KPI_QUERY)
        return df.iloc[0].fillna(0).to_dict()

    def get_advisor_performance(self) -> pd.DataFrame:
        return self.query_df(
            """
            SELECT adv.advisor_name,
                   COUNT(DISTINCT ro.ro_id) AS total_ros,
                   COUNT(DISTINCT CASE WHEN vi.status IN ('AT_RISK', 'VIOLATED', 'MITIGATED') THEN ro.ro_id END) AS sla_breaches,
                   ROUND(100.0 * (
                       COUNT(DISTINCT ro.ro_id) - COUNT(DISTINCT CASE WHEN vi.status IN ('AT_RISK', 'VIOLATED', 'MITIGATED') THEN ro.ro_id END)
                   ) / NULLIF(COUNT(DISTINCT ro.ro_id), 0), 2) AS compliance_pct,
                   ROUND(AVG(csat.score), 2) AS avg_customer_satisfaction
            FROM dim_service_advisor adv
            LEFT JOIN fact_repair_order ro ON ro.advisor_id = adv.advisor_id
            LEFT JOIN fact_sla_violation vi ON vi.ro_id = ro.ro_id
            LEFT JOIN fact_customer_satisfaction csat ON csat.ro_id = ro.ro_id
            GROUP BY adv.advisor_name
            ORDER BY sla_breaches DESC, compliance_pct ASC
            """
        )

    def get_root_cause_summary(self) -> pd.DataFrame:
        return self.query_df(
            """
            SELECT root_cause, COUNT(*) AS violation_count
            FROM fact_sla_violation
            GROUP BY root_cause
            ORDER BY violation_count DESC
            """
        )

    def get_customer_satisfaction(self) -> pd.DataFrame:
        return self.query_df(
            """
            SELECT score, COUNT(*) AS count
            FROM fact_customer_satisfaction
            GROUP BY score
            ORDER BY score
            """
        )

    def get_mitigation_history(self) -> pd.DataFrame:
        return self.query_df(
            """
            SELECT m.executed_at AS timestamp,
                   m.ro_id,
                   v.violation_type,
                   m.action,
                   v.root_cause,
                   v.customer_impact,
                   m.status AS result
            FROM fact_mitigation m
            JOIN fact_sla_violation v ON v.violation_id = m.violation_id
            ORDER BY m.executed_at DESC
            """
        )

    def get_notifications(self, ro_id: str) -> pd.DataFrame:
        return self.query_df(
            "SELECT * FROM fact_customer_notification WHERE ro_id = ? ORDER BY timestamp DESC",
            [ro_id],
        )

    def get_ro_timeline_view(self, ro_id: str) -> pd.DataFrame:
        return self.query_df(
            """
            SELECT event_type, event_timestamp, notes
            FROM fact_service_event
            WHERE ro_id = ?
            ORDER BY event_timestamp ASC
            """,
            [ro_id],
        )

    def query_warehouse(self, sql: str) -> pd.DataFrame:
        return self.query_df(sql)

    def add_service_event(
        self,
        ro_id: str,
        event_type: str,
        event_timestamp: datetime,
        actor_type: str,
        actor_id: str,
        notes: str,
        meta_json: str = "{}",
    ) -> int:
        event_id = int(datetime.now(UTC).timestamp() * 1000)
        self.execute(
            "INSERT INTO fact_service_event VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            [event_id, ro_id, event_type, event_timestamp, actor_type, actor_id, notes, meta_json],
        )
        return event_id

    def update_repair_order_state(
        self,
        ro_id: str,
        ro_status: str,
        actual_ready_at: datetime | None = None,
        delivered_at: datetime | None = None,
        customer_arrival_at: datetime | None = None,
        technician_id: int | None = None,
    ) -> bool:
        try:
            self.execute(
                """
                UPDATE fact_repair_order
                SET ro_status = ?,
                    actual_ready_at = COALESCE(?, actual_ready_at),
                    delivered_at = COALESCE(?, delivered_at),
                    customer_arrival_at = COALESCE(?, customer_arrival_at),
                    technician_id = COALESCE(?, technician_id)
                WHERE ro_id = ?
                """,
                [ro_status, actual_ready_at, delivered_at, customer_arrival_at, technician_id, ro_id],
            )
            return True
        except duckdb.ConstraintException:
            return False

    def insert_mitigation(
        self,
        ro_id: str,
        violation_id: str,
        action: str,
        reason: str,
        executed_by: str,
        customer_notification: bool,
        idempotency_key: str,
    ) -> dict[str, Any]:
        existing = self.query_df("SELECT * FROM fact_mitigation WHERE idempotency_key = ?", [idempotency_key])
        if not existing.empty:
            return existing.iloc[0].to_dict()
        mitigation_id = f"MIT-{uuid4().hex[:10].upper()}"
        executed_at = datetime.now(UTC)
        self.execute(
            "INSERT INTO fact_mitigation VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            [mitigation_id, ro_id, violation_id, action, reason, executed_at, executed_by, "EXECUTED", customer_notification, idempotency_key],
        )
        return {
            "mitigation_id": mitigation_id,
            "ro_id": ro_id,
            "violation_id": violation_id,
            "action": action,
            "reason": reason,
            "executed_at": executed_at,
            "executed_by": executed_by,
            "status": "EXECUTED",
            "customer_notification": customer_notification,
            "idempotency_key": idempotency_key,
        }

    def insert_notification(
        self,
        ro_id: str,
        customer_id: int,
        message: str,
        channel: str = "SIMULATED_SMS",
        status: str = "SENT",
    ) -> dict[str, Any]:
        notification_id = f"NOTIF-{uuid4().hex[:10].upper()}"
        now = datetime.now(UTC)
        self.execute(
            "INSERT INTO fact_customer_notification VALUES (?, ?, ?, ?, ?, ?, ?)",
            [notification_id, ro_id, customer_id, message, now, channel, status],
        )
        self.add_service_event(
            ro_id=ro_id,
            event_type="CUSTOMER_NOTIFICATION_SENT",
            event_timestamp=now,
            actor_type="SYSTEM",
            actor_id="0",
            notes=message,
        )
        return {
            "notification_id": notification_id,
            "ro_id": ro_id,
            "customer_id": customer_id,
            "message": message,
            "timestamp": now,
            "channel": channel,
            "status": status,
        }

    def violation_status_counts(self) -> pd.DataFrame:
        return self.query_df(
            "SELECT status, COUNT(*) AS count FROM fact_sla_violation GROUP BY status ORDER BY count DESC"
        )

    def compliance_breakdown(self) -> pd.DataFrame:
        return self.query_df(
            """
            WITH per_ro AS (
                SELECT ro.ro_id,
                       CASE
                           WHEN MAX(CASE WHEN vi.status = 'VIOLATED' THEN 1 ELSE 0 END) = 1 THEN 'Violated'
                           WHEN MAX(CASE WHEN vi.status = 'AT_RISK' THEN 1 ELSE 0 END) = 1 THEN 'At Risk'
                           WHEN MAX(CASE WHEN vi.status = 'MITIGATED' THEN 1 ELSE 0 END) = 1 THEN 'Mitigated'
                           ELSE 'Compliant'
                       END AS compliance_state
                FROM fact_repair_order ro
                LEFT JOIN fact_sla_violation vi ON vi.ro_id = ro.ro_id
                GROUP BY ro.ro_id
            )
            SELECT compliance_state, COUNT(*) AS count
            FROM per_ro
            GROUP BY compliance_state
            ORDER BY count DESC
            """
        )


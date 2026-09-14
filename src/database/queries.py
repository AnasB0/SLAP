from __future__ import annotations

KPI_QUERY = """
WITH violation_rollup AS (
    SELECT
        ro_id,
        MAX(CASE WHEN status = 'VIOLATED' THEN 1 ELSE 0 END) AS has_violated,
        MAX(CASE WHEN status = 'AT_RISK' THEN 1 ELSE 0 END) AS has_at_risk,
        MAX(CASE WHEN status = 'MITIGATED' THEN 1 ELSE 0 END) AS has_mitigated,
        MAX(CASE WHEN severity = 'CRITICAL' THEN 1 ELSE 0 END) AS has_critical,
        MAX(customer_impact_score) AS impact_score
    FROM fact_sla_violation
    GROUP BY ro_id
)
SELECT
    (SELECT COUNT(*) FROM fact_repair_order) AS total_repair_orders,
    (SELECT COUNT(*) FROM fact_sla_violation WHERE status IN ('AT_RISK', 'VIOLATED')) AS active_sla_violations,
    (SELECT COUNT(*) FROM fact_sla_violation WHERE severity = 'CRITICAL' AND status IN ('AT_RISK', 'VIOLATED')) AS critical_violations,
    (SELECT COUNT(*) FROM violation_rollup WHERE has_at_risk = 1) AS at_risk_ros,
    (SELECT COUNT(*) FROM fact_sla_violation WHERE status = 'MITIGATED') AS mitigated_violations,
    (SELECT ROUND(100.0 * SUM(CASE WHEN ro_id NOT IN (SELECT DISTINCT ro_id FROM fact_sla_violation WHERE status IN ('AT_RISK', 'VIOLATED')) THEN 1 ELSE 0 END) / COUNT(*), 2) FROM fact_repair_order) AS average_sla_compliance,
    (SELECT ROUND(AVG(score), 2) FROM fact_customer_satisfaction) AS average_customer_satisfaction,
    (SELECT COUNT(*) FROM violation_rollup WHERE impact_score >= 51) AS high_customer_impact_cases
"""

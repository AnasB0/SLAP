SELECT ro.ro_id,
       c.customer_name,
       v.make,
       v.model,
       ro.ro_status,
       COUNT(vi.violation_id) AS violation_count,
       AVG(csat.score) AS avg_csat
FROM fact_repair_order ro
JOIN dim_customer c ON c.customer_id = ro.customer_id
JOIN dim_vehicle v ON v.vehicle_id = ro.vehicle_id
LEFT JOIN fact_sla_violation vi ON vi.ro_id = ro.ro_id
LEFT JOIN fact_customer_satisfaction csat ON csat.ro_id = ro.ro_id
GROUP BY 1,2,3,4,5
ORDER BY violation_count DESC, avg_csat ASC;

SELECT adv.advisor_name,
       COUNT(DISTINCT ro.ro_id) AS total_ros,
       COUNT(DISTINCT vi.ro_id) AS breached_ros,
       ROUND(100.0 * (COUNT(DISTINCT ro.ro_id) - COUNT(DISTINCT vi.ro_id)) / NULLIF(COUNT(DISTINCT ro.ro_id), 0), 2) AS compliance_pct,
       ROUND(AVG(csat.score), 2) AS avg_csat
FROM dim_service_advisor adv
LEFT JOIN fact_repair_order ro ON ro.advisor_id = adv.advisor_id
LEFT JOIN fact_sla_violation vi ON vi.ro_id = ro.ro_id AND vi.status IN ('AT_RISK', 'VIOLATED', 'MITIGATED')
LEFT JOIN fact_customer_satisfaction csat ON csat.ro_id = ro.ro_id
GROUP BY 1
ORDER BY breached_ros DESC, compliance_pct ASC;

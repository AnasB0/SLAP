from __future__ import annotations

from typing import Any

import pandas as pd
import plotly.express as px


def make_kpi_markdown(kpis: dict[str, Any]) -> str:
    cards = [
        ("Total Repair Orders", kpis.get("total_repair_orders", 0)),
        ("Active SLA Violations", kpis.get("active_sla_violations", 0)),
        ("Critical Violations", kpis.get("critical_violations", 0)),
        ("At-Risk ROs", kpis.get("at_risk_ros", 0)),
        ("Mitigated Violations", kpis.get("mitigated_violations", 0)),
        ("Average SLA Compliance", f"{kpis.get('average_sla_compliance', 0)}%"),
        ("Average Customer Satisfaction", kpis.get("average_customer_satisfaction", 0)),
        ("High Customer Impact Cases", kpis.get("high_customer_impact_cases", 0)),
    ]
    lines = ["### KPI Snapshot", ""]
    for label, value in cards:
        lines.append(f"- **{label}:** {value}")
    return "\n".join(lines)


def compliance_chart(df: pd.DataFrame):
    if df.empty:
        return px.bar(title="No compliance data")
    return px.pie(df, names="compliance_state", values="count", title="SLA Compliance")


def status_chart(df: pd.DataFrame):
    if df.empty:
        return px.bar(title="No SLA status data")
    return px.bar(df, x="status", y="count", color="status", title="Violation Status")


def root_cause_chart(df: pd.DataFrame):
    if df.empty:
        return px.bar(title="No root-cause data")
    return px.bar(df, x="root_cause", y="violation_count", color="root_cause", title="Root Causes")


def advisor_chart(df: pd.DataFrame):
    if df.empty:
        return px.bar(title="No advisor performance data")
    return px.bar(df, x="advisor_name", y="sla_breaches", color="compliance_pct", title="Advisor SLA Breaches")


def csat_chart(df: pd.DataFrame):
    if df.empty:
        return px.bar(title="No customer satisfaction data")
    return px.bar(df, x="score", y="count", title="Customer Satisfaction Distribution")

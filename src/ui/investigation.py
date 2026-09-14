from __future__ import annotations

from src.analysis.root_cause import ROOT_CAUSE_LABELS, RootCauseResult


def timeline_markdown(events_df) -> str:
    if events_df.empty:
        return "No service events found."
    lines = []
    alert_types = {
        "PARTS_REQUESTED": "🔴",
        "PARTS_RECEIVED": "🔴",
        "TECHNICIAN_ASSIGNED": "🟡",
        "CUSTOMER_NOTIFIED": "🟡",
    }
    for row in events_df.itertuples():
        marker = alert_types.get(row.event_type, "🟢")
        lines.append(f"{row.event_timestamp:%H:%M}  {marker} {row.event_type.replace('_', ' ').title()}")
    return "\n".join(lines)


def root_cause_markdown(result: RootCauseResult, customer_impact: str | None = None) -> str:
    label = ROOT_CAUSE_LABELS.get(result.primary_root_cause, result.primary_root_cause)
    lines = [f"Primary Root Cause: {label}", "", "Evidence:"]
    for evidence in result.evidence:
        lines.append(f"- {evidence['label']}: {evidence['start']} -> {evidence['end']} ({evidence['delay_minutes']} minutes)")
    lines.append("")
    lines.append(f"Contribution: {result.contribution_pct}% of total delay")
    if customer_impact:
        lines.append(f"Customer Impact: {customer_impact}")
    return "\n".join(lines)


def external_context_markdown(recalls: dict, weather: dict) -> str:
    recall_lines = ["### NHTSA Recall Context", recalls.get("message", "")]
    if recalls.get("results"):
        for item in recalls["results"]:
            recall_lines.append(f"- Campaign: {item['campaign']} | Component: {item['component']}")
            recall_lines.append(f"  Summary: {item['summary']}")
    else:
        recall_lines.append("No relevant recall found.")
    weather_lines = ["", "### Weather Context", weather.get("message", "")]
    current = weather.get("current", {})
    weather_lines.append(
        f"Temperature: {current.get('temperature', 'N/A')} | Wind: {current.get('windspeed', 'N/A')} | Note: {current.get('note', 'N/A')}"
    )
    return "\n".join(recall_lines + weather_lines)

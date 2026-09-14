from __future__ import annotations

from src.agents.mitigation_agent import MitigationPlan


def plan_markdown(plan: MitigationPlan | None) -> str:
    if not plan:
        return "No mitigation plan available."
    lines = [f"Selected RO: {plan.ro_id}", "", "Recommended mitigation:"]
    for index, action in enumerate(plan.actions, start=1):
        lines.append(f"{index}. {action}")
    lines.append("")
    lines.append(f"Reason: {plan.reason}")
    lines.append("")
    lines.append("Waiting for explicit user approval before execution.")
    return "\n".join(lines)

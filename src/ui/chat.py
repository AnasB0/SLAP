from __future__ import annotations


def activity_markdown(activity_log: list[str]) -> str:
    if not activity_log:
        return "No agent activity recorded yet."
    return "\n".join(f"- {item}" for item in activity_log)

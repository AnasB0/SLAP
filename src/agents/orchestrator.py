from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from src.agents.context_agent import ContextAgent
from src.agents.data_agent import DataAgent
from src.agents.investigation_agent import InvestigationAgent
from src.agents.mitigation_agent import MitigationAgent
from src.agents.sla_agent import SLAAgent
from src.database.connection import DEFAULT_DB_PATH
from src.llm.openrouter_client import OpenRouterClient


class OrchestratorAgent:
    objective = "Understand the user's objective, decompose the task, delegate work to specialized agents/tools, and produce a final evidence-based answer."

    def __init__(self, db_path: str | Path = DEFAULT_DB_PATH) -> None:
        self.data_agent = DataAgent(db_path)
        self.sla_agent = SLAAgent(db_path)
        self.investigation_agent = InvestigationAgent(db_path)
        self.context_agent = ContextAgent(db_path)
        self.mitigation_agent = MitigationAgent(db_path)
        self.llm_client = OpenRouterClient()

    @staticmethod
    def _extract_ro_id(text: str) -> str | None:
        match = re.search(r"RO-\d{4}", text.upper())
        return match.group(0) if match else None

    @staticmethod
    def _determine_intent(text: str) -> str:
        lowered = text.lower()
        if "mitigate" in lowered or "execute" in lowered:
            return "mitigation"
        if "why" in lowered or "investigate" in lowered or "caused" in lowered:
            return "investigation"
        if "highest customer-impact" in lowered or "worst customer-impact" in lowered:
            return "impact_ranking"
        if "advisor" in lowered and ("breaches" in lowered or "violations" in lowered):
            return "advisor_ranking"
        if "recall" in lowered:
            return "recall_query"
        if "compliance" in lowered or "dashboard" in lowered:
            return "dashboard_query"
        if "violation" in lowered or "at risk" in lowered:
            return "violations_query"
        return "general_question"

    def handle_request(self, user_message: str, selected_ro: str | None = None) -> dict[str, Any]:
        ro_id = self._extract_ro_id(user_message) or selected_ro
        intent = self._determine_intent(user_message)
        activity_log = [f"Identified objective: {intent}"]
        if ro_id:
            activity_log.append(f"Found repair order context: {ro_id}")

        if intent == "violations_query":
            violations = self.sla_agent.get_sla_violations()
            activity_log.append(f"Retrieved {len(violations)} SLA violations")
            return {
                "intent": intent,
                "activity_log": activity_log,
                "text": self._format_table(violations.head(10)),
                "data": {"violations": violations},
            }

        if intent == "dashboard_query":
            kpis = self.data_agent.repository.get_kpis()
            activity_log.append("Loaded dashboard KPI snapshot")
            return {
                "intent": intent,
                "activity_log": activity_log,
                "text": "Today's SLA compliance snapshot loaded from DuckDB.",
                "data": {"kpis": kpis},
            }

        if intent == "impact_ranking":
            top = self.sla_agent.get_highest_impact_violations(10)
            activity_log.append("Ranked highest customer-impact violations")
            return {
                "intent": intent,
                "activity_log": activity_log,
                "text": self._format_table(top[["ro_id", "violation_type", "customer_impact", "customer_impact_score", "root_cause"]]),
                "data": {"violations": top},
            }

        if intent == "advisor_ranking":
            advisors = self.data_agent.repository.get_advisor_performance()
            activity_log.append("Aggregated advisor SLA performance")
            return {
                "intent": intent,
                "activity_log": activity_log,
                "text": self._format_table(advisors),
                "data": {"advisors": advisors},
            }

        if intent == "recall_query" and ro_id:
            recalls = self.context_agent.get_recall_context(ro_id)
            activity_log.append("Retrieved recall context")
            return {
                "intent": intent,
                "activity_log": activity_log,
                "text": str(recalls),
                "data": {"recalls": recalls},
            }

        if intent in {"investigation", "general_question", "mitigation"} and ro_id:
            investigation = self.investigation_agent.investigate(ro_id)
            if "error" in investigation:
                return {"intent": intent, "activity_log": activity_log, "text": investigation["error"], "data": {}}
            activity_log.extend(
                [
                    f"Retrieved {len(investigation['events'])} service events",
                    f"Checked {len(self.sla_agent.check_sla(ro_id))} SLA rules",
                    f"Found {len(investigation['violations'])} violations",
                    "Analyzed root cause",
                    "Calculated customer impact",
                    "Retrieved NHTSA context",
                    "Retrieved weather context",
                ]
            )
            if intent == "mitigation":
                plan = self.mitigation_agent.generate_plan(ro_id)
                if not plan:
                    return {"intent": intent, "activity_log": activity_log, "text": "No active mitigation plan is needed.", "data": {}}
                activity_log.append("Generated mitigation plan")
                activity_log.append("Waiting for approval")
                return {
                    "intent": intent,
                    "activity_log": activity_log,
                    "text": "\n".join(f"{index + 1}. {action}" for index, action in enumerate(plan.actions)),
                    "data": {"plan": plan, "investigation": investigation},
                }

            summary = self._compose_investigation_summary(user_message, ro_id, investigation)
            return {
                "intent": intent,
                "activity_log": activity_log,
                "text": summary,
                "data": {"investigation": investigation},
            }

        return {
            "intent": intent,
            "activity_log": activity_log,
            "text": "Unsupported request. Try asking about violations, a specific RO, advisor breaches, recalls, or mitigation.",
            "data": {},
        }

    @staticmethod
    def _format_table(frame) -> str:
        if frame.empty:
            return "No matching records found."
        return frame.to_string(index=False)

    def _compose_investigation_summary(self, user_message: str, ro_id: str, investigation: dict[str, Any]) -> str:
        root_cause = investigation["root_cause"]
        violations = investigation["violations"]
        ro = investigation["repair_order"]
        deterministic_summary = (
            f"{ro_id} for {ro['customer_name']} on {ro['make']} {ro['model']} has {len(violations)} active or historical SLA findings. "
            f"Primary root cause is {root_cause.primary_root_cause}. "
            f"Top contributing delay accounts for {root_cause.contribution_pct:.0f}% of the total observed overrun."
        )
        llm_response = self.llm_client.chat(
            system_prompt=(
                "You are assisting with an automotive SLA demo. Summarize evidence-based findings only. "
                "Do not invent facts. Keep answers short and operational."
            ),
            user_prompt=(
                f"User question: {user_message}\n"
                f"Repair order: {ro.to_dict() if hasattr(ro, 'to_dict') else ro}\n"
                f"Violations: {violations[['violation_type','status','severity','root_cause','difference_minutes']].to_dict(orient='records')}\n"
                f"Root cause evidence: {root_cause.evidence}"
            ),
        )
        if llm_response.ok:
            return f"{deterministic_summary}\n\nLLM explanation:\n{llm_response.content}"
        return f"{deterministic_summary}\n\n{llm_response.content}"

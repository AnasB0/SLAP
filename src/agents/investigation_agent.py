from __future__ import annotations

from pathlib import Path
from typing import Any

from src.agents.context_agent import ContextAgent
from src.agents.data_agent import DataAgent
from src.agents.root_cause_agent import RootCauseAgent
from src.agents.sla_agent import SLAAgent
from src.database.connection import DEFAULT_DB_PATH


class InvestigationAgent:
    objective = "Explain why an SLA violation occurred using evidence from service events and contextual data."

    def __init__(self, db_path: str | Path = DEFAULT_DB_PATH) -> None:
        self.data_agent = DataAgent(db_path)
        self.sla_agent = SLAAgent(db_path)
        self.root_cause_agent = RootCauseAgent(db_path)
        self.context_agent = ContextAgent(db_path)

    def investigate(self, ro_id: str) -> dict[str, Any]:
        ro = self.data_agent.get_repair_order(ro_id)
        if not ro:
            return {"error": f"Repair order {ro_id} was not found."}
        events = self.data_agent.get_service_events(ro_id)
        violations = self.sla_agent.get_sla_violations(ro_id)
        root_cause = self.root_cause_agent.analyze(ro_id)
        recalls = self.context_agent.get_recall_context(ro_id)
        weather = self.context_agent.get_weather_context()
        return {
            "repair_order": ro,
            "events": events,
            "violations": violations,
            "root_cause": root_cause,
            "recalls": recalls,
            "weather": weather,
        }

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from src.agents.data_agent import DataAgent
from src.agents.investigation_agent import InvestigationAgent
from src.agents.sla_agent import SLAAgent
from src.database.connection import DEFAULT_DB_PATH
from src.database.repository import WarehouseRepository


@dataclass(slots=True)
class MitigationPlan:
    ro_id: str
    violation_id: str
    primary_action: str
    actions: list[str]
    reason: str
    customer_message: str
    waiting_for_approval: bool


class MitigationAgent:
    objective = "Generate and execute controlled corrective actions after explicit user approval."

    ACTION_MAP = {
        "PARTS_UNAVAILABLE": ["ESCALATE_PARTS", "ESCALATE_TO_ADVISOR", "NOTIFY_CUSTOMER", "UPDATE_CUSTOMER_PROMISE"],
        "TECHNICIAN_UNAVAILABLE": ["REASSIGN_TECHNICIAN", "PRIORITIZE_REPAIR", "ESCALATE_TO_ADVISOR", "NOTIFY_CUSTOMER"],
        "QC_BACKLOG": ["START_PRIORITY_QC", "ESCALATE_TO_ADVISOR", "NOTIFY_CUSTOMER"],
        "ADVISOR_DELAY": ["ESCALATE_TO_ADVISOR", "NOTIFY_CUSTOMER", "UPDATE_CUSTOMER_PROMISE"],
        "REPAIR_COMPLEXITY": ["PRIORITIZE_REPAIR", "ESCALATE_TO_ADVISOR", "NOTIFY_CUSTOMER", "UPDATE_CUSTOMER_PROMISE"],
        "INSPECTION_DELAY": ["ESCALATE_TO_ADVISOR", "PRIORITIZE_REPAIR", "NOTIFY_CUSTOMER"],
        "CUSTOMER_DELAY": ["NOTIFY_CUSTOMER", "UPDATE_CUSTOMER_PROMISE"],
        "UNKNOWN": ["ESCALATE_TO_ADVISOR", "NOTIFY_CUSTOMER"],
    }

    def __init__(self, db_path: str | Path = DEFAULT_DB_PATH) -> None:
        self.repository = WarehouseRepository(db_path)
        self.data_agent = DataAgent(db_path)
        self.sla_agent = SLAAgent(db_path)
        self.investigation_agent = InvestigationAgent(db_path)

    def generate_plan(self, ro_id: str) -> MitigationPlan | None:
        investigation = self.investigation_agent.investigate(ro_id)
        if "error" in investigation:
            return None
        primary_violation = self.repository.get_primary_violation_for_ro(ro_id)
        if not primary_violation:
            return None
        root_cause = str(primary_violation["root_cause"])
        actions = self.ACTION_MAP.get(root_cause, self.ACTION_MAP["UNKNOWN"])
        reason = (
            f"{primary_violation['violation_type']} is {primary_violation['status']} with {primary_violation['difference_minutes']:.0f} minutes above threshold. "
            f"Primary root cause is {root_cause}."
        )
        customer_message = (
            "Your vehicle repair is taking longer than expected. "
            f"We have started corrective actions related to {root_cause.replace('_', ' ').lower()} and will provide an updated completion time shortly."
        )
        return MitigationPlan(
            ro_id=ro_id,
            violation_id=str(primary_violation["violation_id"]),
            primary_action=actions[0],
            actions=actions,
            reason=reason,
            customer_message=customer_message,
            waiting_for_approval=True,
        )

    def execute_mitigation(self, ro_id: str, actions: list[str], executed_by: str = "UI_USER") -> dict[str, Any]:
        primary_violation = self.repository.get_primary_violation_for_ro(ro_id)
        if not primary_violation:
            return {"ok": False, "message": f"No violation found for {ro_id}."}
        idempotency_key = f"{ro_id}:{primary_violation['violation_id']}:{'-'.join(actions)}"
        combined_action = "COMBINATION" if len(actions) > 1 else actions[0]
        mitigation = self.repository.insert_mitigation(
            ro_id=ro_id,
            violation_id=str(primary_violation["violation_id"]),
            action=combined_action,
            reason=f"Mitigation executed for root cause {primary_violation['root_cause']}",
            executed_by=executed_by,
            customer_notification="NOTIFY_CUSTOMER" in actions,
            idempotency_key=idempotency_key,
        )
        customer_notification = None
        if "NOTIFY_CUSTOMER" in actions:
            ro = self.repository.get_repair_order(ro_id)
            customer_notification = self.repository.insert_notification(
                ro_id=ro_id,
                customer_id=int(ro["customer_id"]),
                message=(
                    "Your vehicle repair is taking longer than expected due to operational delays. "
                    "We have escalated the work and will provide an updated completion time."
                ),
            )
        ro = self.repository.get_repair_order(ro_id)
        promised = ro["promised_ready_at"]
        new_promise = promised + timedelta(minutes=45) if "UPDATE_CUSTOMER_PROMISE" in actions else None
        if new_promise is not None:
            self.repository.execute("UPDATE fact_repair_order SET promised_ready_at = ? WHERE ro_id = ?", [new_promise, ro_id])
        self.sla_agent.refresh_states()
        self.repository.execute(
            "UPDATE fact_sla_violation SET status = 'MITIGATED' WHERE ro_id = ? AND status IN ('AT_RISK', 'VIOLATED')",
            [ro_id],
        )
        self.repository.add_service_event(
            ro_id=ro_id,
            event_type="MITIGATION_EXECUTED",
            event_timestamp=datetime.now(UTC),
            actor_type="SYSTEM",
            actor_id="0",
            notes=", ".join(actions),
        )
        return {
            "ok": True,
            "message": f"Mitigation executed for {ro_id}.",
            "mitigation": mitigation,
            "notification": customer_notification,
        }

from __future__ import annotations

from pathlib import Path

from scripts.seed_data import seed_database
from src.agents.mitigation_agent import MitigationAgent
from src.database.repository import WarehouseRepository


def test_mitigation_changes_state_and_logs(tmp_path: Path) -> None:
    db_path = tmp_path / "mitigation.duckdb"
    seed_database(db_path)
    agent = MitigationAgent(db_path)
    repo = WarehouseRepository(db_path)

    plan = agent.generate_plan("RO-1002")
    assert plan is not None

    result = agent.execute_mitigation("RO-1002", plan.actions, executed_by="pytest")
    assert result["ok"] is True

    violations = repo.get_sla_violations("RO-1002")
    assert not violations.empty
    assert set(violations["status"].unique()) == {"MITIGATED"}

    history = repo.get_mitigation_history()
    assert not history[history["ro_id"] == "RO-1002"].empty

    notifications = repo.get_notifications("RO-1002")
    assert not notifications.empty

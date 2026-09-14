from __future__ import annotations

from pathlib import Path

from src.analysis.root_cause import RootCauseResult, analyze_root_cause
from src.database.connection import DEFAULT_DB_PATH
from src.database.repository import WarehouseRepository


class RootCauseAgent:
    objective = "Identify the most likely operational bottleneck."

    def __init__(self, db_path: str | Path = DEFAULT_DB_PATH) -> None:
        self.repository = WarehouseRepository(db_path)

    def analyze(self, ro_id: str) -> RootCauseResult:
        events = self.repository.get_service_events(ro_id)
        parts = self.repository.get_part_requests(ro_id)
        return analyze_root_cause(events, parts)

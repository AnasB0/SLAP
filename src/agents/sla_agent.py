from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd

from src.database.connection import DEFAULT_DB_PATH
from src.database.repository import WarehouseRepository
from src.sla.sla_engine import SLAEngine


class SLAAgent:
    objective = "Determine SLA state using deterministic business rules."

    def __init__(self, db_path: str | Path = DEFAULT_DB_PATH) -> None:
        self.engine = SLAEngine(db_path)
        self.repository = WarehouseRepository(db_path)

    def check_sla(self, ro_id: str) -> list[dict[str, Any]]:
        return self.engine.evaluate_ro(ro_id)

    def get_sla_violations(self, ro_id: str | None = None) -> pd.DataFrame:
        return self.repository.get_sla_violations(ro_id)

    def get_highest_impact_violations(self, limit: int = 10) -> pd.DataFrame:
        return self.engine.get_top_violations(limit)

    def refresh_states(self) -> None:
        self.engine.refresh_sla_states()

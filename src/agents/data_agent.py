from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd

from src.database.connection import DEFAULT_DB_PATH
from src.database.repository import WarehouseRepository


class DataAgent:
    objective = "Retrieve reliable operational data from DuckDB."

    def __init__(self, db_path: str | Path = DEFAULT_DB_PATH) -> None:
        self.repository = WarehouseRepository(db_path)

    def get_repair_order(self, ro_id: str) -> dict[str, Any] | None:
        return self.repository.get_repair_order(ro_id)

    def get_repair_orders(self) -> pd.DataFrame:
        return self.repository.get_repair_orders()

    def get_service_events(self, ro_id: str) -> pd.DataFrame:
        return self.repository.get_service_events(ro_id)

    def get_customer(self, customer_id: int) -> dict[str, Any] | None:
        return self.repository.get_customer(customer_id)

    def get_vehicle(self, vehicle_id: int) -> dict[str, Any] | None:
        return self.repository.get_vehicle(vehicle_id)

    def get_advisor(self, advisor_id: int) -> dict[str, Any] | None:
        return self.repository.get_advisor(advisor_id)

    def get_technician(self, technician_id: int) -> dict[str, Any] | None:
        return self.repository.get_technician(technician_id)

    def query_warehouse(self, sql: str) -> pd.DataFrame:
        return self.repository.query_warehouse(sql)

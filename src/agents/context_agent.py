from __future__ import annotations

from pathlib import Path
from typing import Any

from src.database.connection import DEFAULT_DB_PATH
from src.database.repository import WarehouseRepository
from src.external.nhtsa import get_nhtsa_recalls
from src.external.weather import get_weather


class ContextAgent:
    objective = "Retrieve relevant external recall and weather information."

    def __init__(self, db_path: str | Path = DEFAULT_DB_PATH) -> None:
        self.repository = WarehouseRepository(db_path)

    def get_recall_context(self, ro_id: str) -> dict[str, Any]:
        ro = self.repository.get_repair_order(ro_id)
        if not ro:
            return {"api_available": False, "message": "Invalid repair order.", "results": []}
        return get_nhtsa_recalls(ro["make"], ro["model"], int(ro["model_year"]))

    def get_weather_context(self) -> dict[str, Any]:
        return get_weather()

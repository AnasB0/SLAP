from __future__ import annotations

from pathlib import Path

from scripts.seed_data import seed_database
from src.database.repository import WarehouseRepository
from src.analysis.root_cause import analyze_root_cause


def _root_cause_for(db_path: Path, ro_id: str) -> str:
    repo = WarehouseRepository(db_path)
    result = analyze_root_cause(repo.get_service_events(ro_id), repo.get_part_requests(ro_id))
    return result.primary_root_cause


def test_parts_delay_detected(tmp_path: Path) -> None:
    db_path = tmp_path / "parts_root.duckdb"
    seed_database(db_path)
    assert _root_cause_for(db_path, "RO-1002") == "PARTS_UNAVAILABLE"


def test_technician_delay_detected(tmp_path: Path) -> None:
    db_path = tmp_path / "tech_root.duckdb"
    seed_database(db_path)
    assert _root_cause_for(db_path, "RO-1010") == "TECHNICIAN_UNAVAILABLE"


def test_qc_delay_detected(tmp_path: Path) -> None:
    db_path = tmp_path / "qc_root.duckdb"
    seed_database(db_path)
    assert _root_cause_for(db_path, "RO-1020") == "QC_BACKLOG"

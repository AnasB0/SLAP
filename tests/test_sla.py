from __future__ import annotations

from pathlib import Path

from scripts.seed_data import seed_database
from src.sla.sla_engine import SLAEngine


def _find_status(results: list[dict], policy_id: str) -> str:
    for item in results:
        if item["policy_id"] == policy_id:
            return item["status"]
    raise AssertionError(f"Policy {policy_id} not found")


def test_on_track_sla_exists(tmp_path: Path) -> None:
    db_path = tmp_path / "sla_on_track.duckdb"
    seed_database(db_path)
    engine = SLAEngine(db_path)
    results = engine.evaluate_ro("RO-1001")
    assert _find_status(results, "parts_wait") == "ON_TRACK"


def test_at_risk_sla_exists(tmp_path: Path) -> None:
    db_path = tmp_path / "sla_at_risk.duckdb"
    seed_database(db_path)
    engine = SLAEngine(db_path)
    results = engine.evaluate_ro("RO-1040")
    assert _find_status(results, "parts_wait") == "AT_RISK"


def test_violated_sla_exists(tmp_path: Path) -> None:
    db_path = tmp_path / "sla_violated.duckdb"
    seed_database(db_path)
    engine = SLAEngine(db_path)
    results = engine.evaluate_ro("RO-1002")
    assert _find_status(results, "parts_wait") == "VIOLATED"

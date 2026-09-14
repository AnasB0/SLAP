from __future__ import annotations

from pathlib import Path

import duckdb

from scripts.seed_data import seed_database
from src.database.bootstrap import initialize_schema
from src.database.repository import WarehouseRepository


def test_database_initializes_and_tables_exist(tmp_path: Path) -> None:
    db_path = tmp_path / "test.duckdb"
    initialize_schema(db_path)
    conn = duckdb.connect(str(db_path))
    try:
        tables = {
            row[0]
            for row in conn.execute(
                "SELECT table_name FROM information_schema.tables WHERE table_schema = 'main'"
            ).fetchall()
        }
    finally:
        conn.close()
    assert "fact_repair_order" in tables
    assert "fact_service_event" in tables
    assert "fact_sla_violation" in tables


def test_seed_data_exists(tmp_path: Path) -> None:
    db_path = tmp_path / "seeded.duckdb"
    seed_database(db_path)
    repo = WarehouseRepository(db_path)
    assert repo.table_count("dim_customer") >= 100
    assert repo.table_count("dim_vehicle") >= 100
    assert repo.table_count("fact_repair_order") >= 50
    assert repo.table_count("fact_service_event") >= 500

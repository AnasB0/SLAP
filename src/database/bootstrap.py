from __future__ import annotations

from pathlib import Path

from src.database.connection import DEFAULT_DB_PATH, get_connection


def initialize_schema(db_path: str | Path = DEFAULT_DB_PATH) -> None:
    schema_path = Path("sql/schema.sql")
    schema_sql = schema_path.read_text(encoding="utf-8")
    conn = get_connection(db_path)
    try:
        conn.execute(schema_sql)
    finally:
        conn.close()


def is_seeded(db_path: str | Path = DEFAULT_DB_PATH) -> bool:
    conn = get_connection(db_path)
    try:
        conn.execute("SELECT COUNT(*) FROM information_schema.tables WHERE table_name = 'fact_repair_order'")
        exists = conn.fetchone()[0] == 1
        if not exists:
            return False
        conn.execute("SELECT COUNT(*) FROM fact_repair_order")
        return conn.fetchone()[0] > 0
    finally:
        conn.close()


def ensure_database(db_path: str | Path = DEFAULT_DB_PATH) -> None:
    from scripts.seed_data import seed_database

    initialize_schema(db_path)
    if not is_seeded(db_path):
        seed_database(db_path)

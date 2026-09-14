from __future__ import annotations

from pathlib import Path

import duckdb


DEFAULT_DB_PATH = Path("data/automotive_sla.duckdb")


def get_connection(db_path: str | Path = DEFAULT_DB_PATH) -> duckdb.DuckDBPyConnection:
    path = Path(db_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    return duckdb.connect(str(path))
